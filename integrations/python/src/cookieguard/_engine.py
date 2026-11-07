"""Local bridge to the CookieGuard Node.js engine.

Evidence travels only over the child's stdin pipe. The child gets a minimal
environment, read-only file access to its own directory through Node's
permission model, and no inherited NODE_OPTIONS. Its stderr is discarded and
never surfaced, because it is the one channel this adapter cannot sanitize.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Any

from ._errors import CookieGuardError, engine_error

MIN_NODE_MAJOR = 24
PROTOCOL = 1
_ENGINE_DIR = Path(__file__).resolve().parent / '_node'
_REPLY_LIMIT = 16 * 1024 * 1024
_verified_dirs: set[Path] = set()


def engine_dir() -> Path:
	return _ENGINE_DIR


def verify_engine_files(directory: Path | None = None) -> dict[str, Any]:
	"""Check that the vendored engine matches its manifest. Raises CookieGuardError('ENGINE')."""
	directory = (directory or _ENGINE_DIR).resolve()
	failed = False
	manifest: dict[str, Any] = {}
	try:
		manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
		expected = dict(manifest['bridge'])
		for package in manifest['packages']:
			expected.update(package['files'])
		if directory not in _verified_dirs:
			for relative, digest in expected.items():
				path = (directory / relative).resolve()
				if directory not in path.parents or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
					failed = True
					break
	except Exception:
		failed = True
	if failed:
		raise CookieGuardError('ENGINE')
	_verified_dirs.add(directory)
	return {package['name']: package['version'] for package in manifest['packages']}


def resolve_node(node_path: str | None = None) -> str:
	candidate = node_path or os.environ.get('COOKIEGUARD_NODE') or shutil.which('node')
	if not candidate or not Path(candidate).is_file() or not os.access(candidate, os.X_OK):
		raise CookieGuardError('ENGINE')
	return str(Path(candidate).resolve())


def node_command(node: str, directory: Path, script: str = 'bridge.mjs') -> list[str]:
	"""Node with read-only access to the engine directory; no writes, child processes, workers, or addons.

	Node 25+ also denies network access under --permission; Node 24 does not.
	"""
	return [node, '--permission', f'--allow-fs-read={directory}', '--max-old-space-size=256',
		'--disallow-code-generation-from-strings', str(directory / script)]


def child_env() -> dict[str, str]:
	env = {'PATH': os.environ.get('PATH', os.defpath), 'NODE_NO_WARNINGS': '1', 'NODE_DISABLE_COLORS': '1',
		'ORT_DISABLE_TELEMETRY': '1'}
	if sys.platform == 'win32':
		for key in ('SYSTEMROOT', 'WINDIR'):
			if key in os.environ:
				env[key] = os.environ[key]
	return env


async def node_major(node: str) -> int:
	failed = False
	major = 0
	try:
		process = await asyncio.create_subprocess_exec(node, '--version', stdin=asyncio.subprocess.DEVNULL,
			stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL, env=child_env())
		stdout, _ = await asyncio.wait_for(process.communicate(), 10)
		match = re.fullmatch(r'v(\d+)\.\d+\.\d+\s*', stdout.decode('ascii', 'replace'))
		major = int(match.group(1)) if match else 0
	except Exception:
		failed = True
	if failed or major == 0:
		raise CookieGuardError('ENGINE')
	return major


class LocalEngine:
	"""One Node child per audit. Not shared between audits, sessions, or threads."""

	def __init__(self, node_path: str | None = None) -> None:
		self._node_path = node_path
		self._process: asyncio.subprocess.Process | None = None
		self._reader: asyncio.Task | None = None
		self._stderr: asyncio.Task | None = None
		self._waiters: dict[object, asyncio.Future] = {}
		self._write_lock = asyncio.Lock()
		self._next_id = 0
		self._dead = False
		self.versions: dict[str, str] = {}

	@property
	def alive(self) -> bool:
		return self._process is not None and not self._dead and self._process.returncode is None

	async def start(self, config: dict[str, Any]) -> None:
		self.versions = verify_engine_files()
		node = resolve_node(self._node_path)
		if await node_major(node) < MIN_NODE_MAJOR:
			raise CookieGuardError('ENGINE')
		failed = False
		try:
			self._process = await asyncio.create_subprocess_exec(
				*node_command(node, _ENGINE_DIR),
				stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
				env=child_env(), cwd=str(_ENGINE_DIR), limit=_REPLY_LIMIT)
		except Exception:
			failed = True
		if failed:
			raise CookieGuardError('ENGINE')
		self._reader = asyncio.create_task(self._read_replies())
		self._stderr = asyncio.create_task(self._discard_stderr())
		await self._request('ready', {'type': 'start', **config}, timeout=20)

	async def _discard_stderr(self) -> None:
		assert self._process and self._process.stderr
		try:
			while await self._process.stderr.read(65536):
				pass
		except Exception:
			pass

	async def _read_replies(self) -> None:
		assert self._process and self._process.stdout
		try:
			while True:
				line = await self._process.stdout.readline()
				if not line:
					break
				reply = json.loads(line)
				if not isinstance(reply, dict):
					break
				if reply.get('type') == 'error' and reply.get('fatal'):
					self._fail_all(engine_error(reply.get('code')))
					break
				key = 'ready' if reply.get('type') == 'ready' else reply.get('id')
				waiter = self._waiters.pop(key, None)
				if waiter and not waiter.done():
					waiter.set_result(reply)
		except Exception:
			pass
		self._fail_all(CookieGuardError('ENGINE'))

	def _fail_all(self, error: CookieGuardError) -> None:
		self._dead = True
		for waiter in self._waiters.values():
			if not waiter.done():
				waiter.set_exception(CookieGuardError(error.code))
		self._waiters.clear()

	async def _write(self, message: dict[str, Any]) -> None:
		if not self.alive or not self._process or not self._process.stdin:
			raise CookieGuardError('ENGINE')
		failed = False
		data = (json.dumps({'protocol': PROTOCOL, **message}, separators=(',', ':'), allow_nan=False) + '\n').encode()
		async with self._write_lock:
			try:
				self._process.stdin.write(data)
				await asyncio.wait_for(self._process.stdin.drain(), 10)
			except Exception:
				failed = True
		del data
		if failed:
			self._dead = True
			raise CookieGuardError('ENGINE')

	async def _request(self, key: object, message: dict[str, Any], timeout: float) -> dict[str, Any]:
		waiter = asyncio.get_running_loop().create_future()
		self._waiters[key] = waiter
		try:
			await self._write(message)
		except CookieGuardError:
			self._waiters.pop(key, None)
			waiter.cancel()
			raise
		failed: CookieGuardError | None = None
		reply: dict[str, Any] = {}
		try:
			reply = await asyncio.wait_for(waiter, timeout)
		except CookieGuardError as error:
			failed = CookieGuardError(error.code)
		except Exception:
			failed = CookieGuardError('ENGINE')
		finally:
			self._waiters.pop(key, None)
		if failed:
			raise failed
		if reply.get('type') == 'error':
			raise engine_error(reply.get('code'))
		return reply

	async def response(self, url: str, set_cookie: list[str], from_service_worker: bool) -> None:
		await self._write({'type': 'response', 'url': url, 'setCookie': set_cookie, 'fromServiceWorker': from_service_worker})

	async def mark_incomplete(self) -> None:
		await self._write({'type': 'close'})

	async def snapshot(self, cookies: list[dict[str, Any]] | None) -> dict[str, Any]:
		self._next_id += 1
		return await self._request(self._next_id, {'type': 'snapshot', 'id': self._next_id, 'cookies': cookies}, timeout=30)

	async def finish(self, cookies: list[dict[str, Any]] | None, baseline: dict[str, Any] | None = None, *,
			session: dict[str, Any] | None = None, storage: list[dict[str, Any]] | None = None) -> dict[str, Any]:
		self._next_id += 1
		message: dict[str, Any] = {'type': 'finish', 'id': self._next_id, 'cookies': cookies}
		if baseline is not None:
			message['baseline'] = baseline
		if session is not None:
			message['session'] = session  # Value-free timeline; the core summarizes it.
		if storage is not None:
			message['storage'] = storage  # Classified by the core, then dropped.
		return await self._request(self._next_id, message, timeout=30)

	async def close(self) -> None:
		process, self._process = self._process, None
		self._dead = True
		self._fail_all(CookieGuardError('STATE'))
		if process is None:
			return
		try:
			if process.stdin and not process.stdin.is_closing():
				process.stdin.close()
			await asyncio.wait_for(process.wait(), 5)
		except Exception:
			pass
		if process.returncode is None:
			try:
				process.kill()
				await asyncio.wait_for(process.wait(), 5)
			except Exception:
				pass
		for task in (self._reader, self._stderr):
			if task and not task.done():
				task.cancel()
				try:
					await task
				except BaseException:
					pass
		self._reader = self._stderr = None
