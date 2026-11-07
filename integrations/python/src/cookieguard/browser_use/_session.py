"""Opt-in session probe for Browser Use audits.

Mirrors the Playwright adapter's probe. It keeps the values of the configured
authentication cookies in this process only, sends them only to the configured
probe URL on an allowed origin, and produces a value-free timeline in which each
value is an opaque id. The CookieGuard core decides rotation (CG010) and logout
revocation (CG011) from that timeline alone.
"""

from __future__ import annotations

import asyncio
import email.utils
import http.client
import ssl
import time
from typing import Any
from urllib.parse import urljoin, urlsplit

from .._errors import CookieGuardError
from .._origins import origin_of

SAFE_TIMEOUT = 5.0
MAX_PROBES_LIMIT = 200


def probe_url(url: str, origins: tuple[str, ...]) -> str:
	"""An absolute http(s) URL on an allowed origin, without credentials, query, or fragment."""
	try:
		parts = urlsplit(url)
		if parts.scheme not in ('http', 'https') or parts.username or parts.password or parts.query or parts.fragment \
			or origin_of(url) not in origins:
			raise ValueError
	except Exception:
		raise CookieGuardError('CONFIG') from None
	return url if parts.path else url + '/'


def _default_path(path: str) -> str:
	end = path.rfind('/')
	return '/' if end <= 0 else path[:end]


def parse_line(url: str, line: str, now: float | None = None) -> dict[str, Any] | None:
	"""Name, value, scope, and deletion of one Set-Cookie line, as the core parser scopes it."""
	pair, _, rest = line.partition(';')
	if '=' not in pair:
		return None
	name, _, value = pair.partition('=')
	name, value = name.strip(), value.strip()
	if not name:
		return None
	attrs: dict[str, str | None] = {}
	for part in rest.split(';'):
		if part.strip():
			key, sep, val = part.partition('=')
			attrs[key.strip().lower()] = val.strip() if sep else None
	parts = urlsplit(url)
	host = (parts.hostname or '').lower()
	domain = (attrs.get('domain') or '').lstrip('.').lower() if 'domain' in attrs else host
	declared = attrs.get('path')
	path = declared if declared and declared.startswith('/') else _default_path(parts.path or '/')
	now = time.time() if now is None else now
	deleted = False
	max_age = attrs.get('max-age')
	if max_age is not None and max_age.lstrip('-').isdigit():
		deleted = int(max_age) <= 0
	elif attrs.get('expires'):
		try:
			deleted = email.utils.parsedate_to_datetime(attrs['expires']).timestamp() <= now
		except Exception:
			deleted = False
	return {'cookie': {'name': name, 'domain': domain, 'path': path, 'origin': origin_of(url)}, 'value': value, 'deleted': deleted}


def _key(cookie: dict[str, str]) -> tuple[str, str, str, str]:
	return (cookie['origin'], cookie['name'], cookie['domain'], cookie['path'])


def _applies(cookie: dict[str, str], url: str) -> bool:
	parts = urlsplit(url)
	host = (parts.hostname or '').lower()
	path = parts.path or '/'
	prefix = cookie['path'] if cookie['path'].endswith('/') else cookie['path'] + '/'
	return (cookie['origin'] == origin_of(url) and (host == cookie['domain'] or host.endswith('.' + cookie['domain']))
		and (path == cookie['path'] or path.startswith(prefix)))


def _request(url: str, cookie_header: str | None, timeout: float) -> dict[str, Any]:
	"""One GET without following redirects. Only the status and the redirect path are kept."""
	parts = urlsplit(url)
	connection: http.client.HTTPConnection
	try:
		if parts.scheme == 'https':
			connection = http.client.HTTPSConnection(parts.hostname, parts.port, timeout=timeout, context=ssl.create_default_context())
		else:
			connection = http.client.HTTPConnection(parts.hostname, parts.port, timeout=timeout)
		try:
			headers = {'User-Agent': 'CookieGuard-session-probe'}
			if cookie_header:
				headers['Cookie'] = cookie_header
			connection.request('GET', parts.path or '/', headers=headers)
			response = connection.getresponse()
			location = response.getheader('Location')
			status = response.status
		finally:
			connection.close()
	except Exception:
		return {'error': True}
	path = urlsplit(urljoin(url, location)).path if location else None
	return {'status': status, 'location': path or None}


class SessionProbe:
	def __init__(self, url: str, names: list[str], *, require_logout: bool, max_probes: int = 50, timeout: float = SAFE_TIMEOUT) -> None:
		if not names or isinstance(max_probes, bool) or not isinstance(max_probes, int) or not 2 <= max_probes <= MAX_PROBES_LIMIT:
			raise CookieGuardError('CONFIG')
		self.url = url
		self._names = set(names)
		self._require_logout = require_logout
		self._max_probes = max_probes
		self._timeout = timeout
		self._jar: dict[tuple[str, str, str, str], dict[str, Any]] = {}
		self._events: list[dict[str, Any]] = []
		self._tasks: set[asyncio.Task] = set()
		self._replays: list[list[dict[str, Any]]] = []
		self._values: list[str] = []
		self._anonymous: asyncio.Task | None = None
		self._next = 0
		self._sent = 0
		self._truncated = False

	def values(self) -> list[str]:
		"""Every value this probe saw, for the output guard."""
		return list(self._values)

	async def _call(self, entries: list[dict[str, Any]]) -> dict[str, Any]:
		header = '; '.join(f"{entry['cookie']['name']}={entry['value']}" for entry in entries) or None
		return await asyncio.to_thread(_request, self.url, header, self._timeout)

	def _probe(self, phase: str, entries: list[dict[str, Any]] | None = None) -> None:
		entries = [entry for entry in self._jar.values() if _applies(entry['cookie'], self.url)] if entries is None else entries
		if not entries:
			return
		if self._sent >= self._max_probes:
			self._truncated = True
			return
		self._sent += 1
		event: dict[str, Any] = {'type': 'probe', 'phase': phase,
			'values': [{'cookie': entry['cookie'], 'valueId': entry['id']} for entry in entries], 'result': None}
		self._events.append(event)  # Its place in the timeline is when the request starts.
		if self._anonymous is None:
			self._anonymous = asyncio.ensure_future(self._call([]))

		async def run() -> None:
			event['result'] = await self._call(entries)
		task = asyncio.ensure_future(run())
		self._tasks.add(task)
		task.add_done_callback(self._tasks.discard)

	def set_cookie(self, url: str, line: str, method: str | None) -> None:
		parsed = parse_line(url, line)
		if not parsed or parsed['cookie']['name'] not in self._names:
			return
		cookie, value = parsed['cookie'], parsed['value']
		key = _key(cookie)
		current = self._jar.get(key)
		if parsed['deleted']:
			if current is None:
				return
			snapshot = [entry for entry in self._jar.values() if _applies(entry['cookie'], self.url)]
			self._events.append({'type': 'deleted', 'cookie': cookie, 'valueId': current['id']})
			del self._jar[key]
			self._replays.append(snapshot)
			return
		if current is not None and current['value'] == value:
			return
		self._next += 1
		entry = {'cookie': cookie, 'value': value, 'id': f'v{self._next}'}
		self._jar[key] = entry
		self._values.append(value)
		self._events.append({'type': 'issued', 'cookie': cookie, 'valueId': entry['id'],
			'method': method.upper() if isinstance(method, str) else None})
		self._probe('issued')

	def navigation(self) -> None:
		self._probe('navigation')

	async def finish(self) -> dict[str, Any]:
		"""The value-free timeline for the core. Values are dropped afterwards."""
		try:
			if self._tasks:
				await asyncio.gather(*list(self._tasks), return_exceptions=True)
			self._probe('final')
			for snapshot in self._replays:
				self._probe('replay', snapshot)
			if self._tasks:
				await asyncio.gather(*list(self._tasks), return_exceptions=True)
			if self._anonymous is None:
				self._anonymous = asyncio.ensure_future(self._call([]))
			anonymous = await self._anonymous
			events = [{**event, 'result': event['result'] or {'error': True}} if event['type'] == 'probe' else event
				for event in self._events]
			return {'url': self.url, 'anonymous': anonymous, 'truncated': self._truncated,
				'requireLogout': self._require_logout, 'events': events}
		finally:
			self.clear()

	def clear(self) -> None:
		self._jar.clear()
		self._replays.clear()
		for task in list(self._tasks):
			task.cancel()
