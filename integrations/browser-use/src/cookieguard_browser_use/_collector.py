"""Passive CDP evidence collection on a dedicated observer connection.

cdp-use keeps one handler per CDP event per client, so registering on Browser
Use's own client would replace (or be replaced by) its watchdog handlers.
Like Browser Use's own toolset integrations, CookieGuard opens a second CDP
client to the same browser and attaches its own sessions to page targets.

Server declarations come from ``Network.responseReceivedExtraInfo`` raw
headers, which carry no URL. Each one is attributed to its redirect hop by
order and verified by status code; unattributable headers are discarded and
never forwarded. Browser state comes from ``Storage.getCookies``.

Raw cookie values exist only transiently in this process: Set-Cookie lines
for authorized origins are forwarded to the local engine immediately, other
origins' lines are dropped, and store values are sent once and released.
"""

from __future__ import annotations

import asyncio
import logging
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any

from ._engine import LocalEngine
from ._origins import cookie_matches_origins, origin_of

_logger = logging.getLogger('cookieguard_browser_use')

MAX_TRACKED_REQUESTS = 4096
MAX_FORWARDED_RESPONSES = 1000
MAX_LINES_PER_RESPONSE = 200
MAX_HEADER_LENGTH = 16384
MAX_STORE_COOKIES = 1000
OBSERVED_TARGET_TYPES = ('page', 'iframe')
CDP_TIMEOUT = 8.0


@dataclass
class _Hop:
	url: str
	status: int | None = None
	cached: bool = False
	extra_status: int | None = None  # Status of the ExtraInfo attributed to this hop.


@dataclass
class _Request:
	hops: list[_Hop] = field(default_factory=list)
	attributed: int = 0
	pending: list[tuple[int | None, list[str]]] = field(default_factory=list)
	had_lines: bool = False
	mismatch: bool = False


def _from_cache(response: dict[str, Any]) -> bool:
	return bool(response.get('fromDiskCache') or response.get('fromPrefetchCache') or response.get('fromServiceWorker')
		or response.get('fromEarlyHints'))


def _set_cookie_lines(headers: Any) -> list[str]:
	lines: list[str] = []
	if isinstance(headers, dict):
		for name, value in headers.items():
			if isinstance(name, str) and name.lower() == 'set-cookie' and isinstance(value, str):
				lines.extend(line for line in value.split('\n') if line.strip())
	return lines


class CdpEvidenceCollector:
	def __init__(self, origins: tuple[str, ...], engine: LocalEngine, *, capture_headers: bool) -> None:
		self._origins = origins
		self._engine = engine
		self._capture_headers = capture_headers
		self._client: Any = None
		self._targets: dict[str, str] = {}
		self._attach_tasks: dict[str, asyncio.Task] = {}
		self._sessions: set[str] = set()
		self._contexts: set[str] = set()
		self._requests: OrderedDict[tuple[str | None, str], _Request] = OrderedDict()
		self._tasks: set[asyncio.Task] = set()
		self._reasons: set[str] = set()
		self._header_names: set[str] = set()
		self._forwarded = 0
		self._unattributed = 0
		self._attach_failures = 0
		self._attached_total = 0
		self._stopping = False

	# ----- lifecycle -------------------------------------------------------

	async def start(self, root_client: Any) -> None:
		from cdp_use import CDPClient

		self._client = CDPClient(root_client.url, additional_headers=getattr(root_client, 'additional_headers', None))
		await asyncio.wait_for(self._client.start(), CDP_TIMEOUT)
		register = self._client.register
		register.Target.targetCreated(self._guard(self._on_target_created))
		register.Target.detachedFromTarget(self._guard(self._on_detached))
		if self._capture_headers:
			register.Network.requestWillBeSent(self._guard(self._on_request))
			register.Network.requestServedFromCache(self._guard(self._on_served_from_cache))
			register.Network.responseReceived(self._guard(self._on_response))
			register.Network.responseReceivedExtraInfo(self._guard(self._on_extra_info))
			register.Network.loadingFinished(self._guard(self._on_loading_done))
			register.Network.loadingFailed(self._guard(self._on_loading_done))
		await asyncio.wait_for(self._client.send.Target.setDiscoverTargets(params={'discover': True}), CDP_TIMEOUT)
		targets = await asyncio.wait_for(self._client.send.Target.getTargets(), CDP_TIMEOUT)
		pending = [self._ensure_attached(info) for info in targets.get('targetInfos', [])
			if info.get('type') in OBSERVED_TARGET_TYPES]
		# targetCreated may already have started some of these attaches; await all.
		await asyncio.gather(*(task for task in pending if task is not None), return_exceptions=True)
		if not self._contexts:
			raise RuntimeError('no page target')

	async def stop(self) -> None:
		self._stopping = True
		for task in list(self._tasks):
			task.cancel()
		for task in list(self._tasks):
			try:
				await task
			except BaseException:
				pass
		self._tasks.clear()
		client, self._client = self._client, None
		if client is not None:
			try:
				await asyncio.wait_for(client.stop(), CDP_TIMEOUT)
			except BaseException:
				pass
		self._discard_buffers()

	def _discard_buffers(self) -> None:
		for request in self._requests.values():
			request.pending.clear()
		self._requests.clear()

	def _incomplete(self, reason: str) -> None:
		self._reasons.add(reason)

	@property
	def reasons(self) -> tuple[str, ...]:
		return tuple(sorted(self._reasons))

	@property
	def header_cookie_names(self) -> frozenset[str]:
		return frozenset(self._header_names)

	def stats(self) -> dict[str, Any]:
		return {'headerCapture': 'enabled' if self._capture_headers else 'disabled',
			'targetsObserved': self._attached_total, 'setCookieResponsesForwarded': self._forwarded,
			'unattributedSetCookieResponses': self._unattributed, 'attachFailures': self._attach_failures}

	def _guard(self, handler):
		# cdp-use logs handler exceptions with their text. Never let one escape.
		def wrapped(event, session_id=None):
			try:
				result = handler(event, session_id)
				if asyncio.iscoroutine(result):
					return self._swallow(result)
			except Exception:
				self._incomplete('collector-error')
			return None
		return wrapped

	async def _swallow(self, coroutine) -> None:
		try:
			await coroutine
		except Exception:
			self._incomplete('collector-error')

	# ----- targets ---------------------------------------------------------

	def _on_target_created(self, event, session_id=None) -> None:
		info = event.get('targetInfo', {})
		if info.get('type') in OBSERVED_TARGET_TYPES:
			self._ensure_attached(info)

	def _ensure_attached(self, info: dict[str, Any]) -> asyncio.Task | None:
		"""One attach task per target, shared by discovery events and the initial scan."""
		target_id = info.get('targetId')
		if not isinstance(target_id, str) or self._stopping or self._client is None:
			return None
		task = self._attach_tasks.get(target_id)
		if task is None:
			task = asyncio.create_task(self._swallow(self._attach(target_id, info)))
			self._attach_tasks[target_id] = task
			self._tasks.add(task)
			task.add_done_callback(self._tasks.discard)
		return task

	async def _attach(self, target_id: str, info: dict[str, Any]) -> None:
		try:
			result = await asyncio.wait_for(
				self._client.send.Target.attachToTarget(params={'targetId': target_id, 'flatten': True}), CDP_TIMEOUT)
			session_id = result['sessionId']
			if self._capture_headers:
				await asyncio.wait_for(self._client.send.Network.enable(session_id=session_id), CDP_TIMEOUT)
		except Exception:
			# Usually a target that closed before attachment. Missed headers can
			# only remove declaration evidence; store evidence is read at finish.
			self._attach_failures += 1
			return
		self._targets[target_id] = session_id
		self._sessions.add(session_id)
		self._attached_total += 1
		if info.get('type') == 'page' and isinstance(info.get('browserContextId'), str):
			self._contexts.add(info['browserContextId'])

	def _on_detached(self, event, session_id=None) -> None:
		self._sessions.discard(event.get('sessionId'))

	# ----- network: Set-Cookie attribution ---------------------------------

	def _request_for(self, key, create: bool) -> _Request | None:
		request = self._requests.get(key)
		if request is None and create:
			request = _Request()
			self._requests[key] = request
			while len(self._requests) > MAX_TRACKED_REQUESTS:
				_, evicted = self._requests.popitem(last=False)
				if evicted.pending:
					self._drop_unattributed(evicted)
		return request

	def _authorized(self, url: str) -> bool:
		return origin_of(url) in self._origins

	async def _on_request(self, event, session_id=None) -> None:
		key = (session_id, event.get('requestId'))
		url = event.get('request', {}).get('url', '')
		redirect = event.get('redirectResponse')
		request = self._request_for(key, create=True)
		if isinstance(redirect, dict):
			if not request.hops:
				# Attached mid-flight: the redirect response names the earlier hop.
				request.hops.append(_Hop(url=redirect.get('url', '') if isinstance(redirect.get('url'), str) else ''))
			previous = request.hops[-1]
			previous.cached = previous.cached or _from_cache(redirect)
			self._set_status(request, previous, redirect.get('status'))
			if redirect.get('fromServiceWorker') and self._authorized(previous.url):
				self._incomplete('service-worker-response')
		elif request.hops:
			self._drop_unattributed(request)
			request.hops.clear()
			request.attributed = 0
		request.hops.append(_Hop(url=url if isinstance(url, str) else ''))
		await self._resolve(request)

	def _on_served_from_cache(self, event, session_id=None) -> None:
		request = self._request_for((session_id, event.get('requestId')), create=False)
		if request and request.hops:
			request.hops[-1].cached = True

	async def _on_response(self, event, session_id=None) -> None:
		request = self._request_for((session_id, event.get('requestId')), create=False)
		response = event.get('response', {})
		url = response.get('url', '') if isinstance(response.get('url'), str) else ''
		if response.get('fromServiceWorker') and self._authorized(url):
			self._incomplete('service-worker-response')
		if request is None:
			return
		if not request.hops:
			if len(request.pending) > 1:
				# Missed earlier hops cannot be ordered safely.
				self._drop_unattributed(request)
				return
			request.hops.append(_Hop(url=url))
		hop = request.hops[-1]
		hop.cached = hop.cached or _from_cache(response)
		self._set_status(request, hop, response.get('status'))
		await self._resolve(request)

	async def _on_extra_info(self, event, session_id=None) -> None:
		request = self._request_for((session_id, event.get('requestId')), create=True)
		status = event.get('statusCode')
		lines = _set_cookie_lines(event.get('headers'))
		request.had_lines = request.had_lines or bool(lines)
		# Every ExtraInfo is queued, with or without Set-Cookie, to keep hop order.
		request.pending.append((status if isinstance(status, int) else None, lines))
		if len(request.pending) > MAX_LINES_PER_RESPONSE:
			self._drop_unattributed(request)
		await self._resolve(request)

	def _on_loading_done(self, event, session_id=None) -> None:
		key = (session_id, event.get('requestId'))
		if key in self._requests:
			self._requests.move_to_end(key)

	def _set_status(self, request: _Request, hop: _Hop, status: Any) -> None:
		if isinstance(status, int):
			hop.status = status
			if hop.extra_status is not None and hop.extra_status != status:
				request.mismatch = True
				self._check_mismatch(request)

	def _check_mismatch(self, request: _Request) -> None:
		# Order-based attribution is wrong for this request. That only matters if
		# it carried Set-Cookie and touched an authorized origin.
		if request.mismatch and request.had_lines and any(self._authorized(hop.url) for hop in request.hops):
			self._incomplete('header-attribution-mismatch')

	async def _resolve(self, request: _Request) -> None:
		network_hops = [hop for hop in request.hops if not hop.cached]
		while request.pending and request.attributed < len(network_hops):
			hop = network_hops[request.attributed]
			status, lines = request.pending.pop(0)
			request.attributed += 1
			hop.extra_status = status
			if hop.status is not None and status is not None and hop.status != status:
				request.mismatch = True
			self._check_mismatch(request)
			if request.mismatch:
				continue
			if lines and self._authorized(hop.url):
				await self._forward(hop.url, lines)

	def _drop_unattributed(self, request: _Request) -> None:
		if any(lines for _, lines in request.pending):
			self._unattributed += 1
			if any(self._authorized(hop.url) for hop in request.hops):
				self._incomplete('unattributed-set-cookie')
		request.pending.clear()

	async def _forward(self, url: str, lines: list[str]) -> None:
		if self._stopping:
			return
		if self._forwarded >= MAX_FORWARDED_RESPONSES:
			self._incomplete('response-limit')
			return
		if len(lines) > MAX_LINES_PER_RESPONSE or any(len(line) > MAX_HEADER_LENGTH for line in lines):
			self._incomplete('oversized-set-cookie')
			return
		self._forwarded += 1
		for line in lines:
			name = line.split('=', 1)[0].strip() if '=' in line else ''
			if name:
				self._header_names.add(name[:256])
		await self._engine.response(url, lines, False)

	# ----- finish ----------------------------------------------------------

	async def healthy(self) -> bool:
		"""A CDP round trip also guarantees that events sent before it were delivered."""
		if self._client is None:
			return False
		try:
			await asyncio.wait_for(self._client.send.Browser.getVersion(), CDP_TIMEOUT)
			return True
		except Exception:
			return False

	def settle(self) -> None:
		for request in self._requests.values():
			self._drop_unattributed(request)

	async def store_cookies(self) -> tuple[list[dict[str, Any]] | None, list[str]]:
		"""Return engine-ready store cookies for authorized hosts, plus their values for output guarding."""
		if self._client is None:
			return None, []
		cookies: list[dict[str, Any]] = []
		failed = False
		try:
			raw: list[dict[str, Any]] = []
			for context in sorted(self._contexts):
				result = await asyncio.wait_for(
					self._client.send.Storage.getCookies(params={'browserContextId': context}), CDP_TIMEOUT)
				raw.extend(result.get('cookies', []))
				if len(raw) > MAX_STORE_COOKIES * 4:
					raise ValueError
			for cookie in raw:
				if not cookie_matches_origins(cookie.get('domain'), self._origins):
					continue
				same_site = cookie.get('sameSite')
				cookies.append({'name': cookie.get('name'), 'value': cookie.get('value', ''), 'domain': cookie.get('domain'),
					'path': cookie.get('path'), 'expires': cookie.get('expires', -1), 'httpOnly': cookie.get('httpOnly'),
					'secure': cookie.get('secure'), **({'sameSite': same_site} if isinstance(same_site, str) else {}),
					'partitioned': 'partitionKey' in cookie})
			del raw
			if len(cookies) > MAX_STORE_COOKIES:
				raise ValueError
		except Exception:
			failed = True
		if failed:
			return None, []
		return cookies, [c['value'] for c in cookies if isinstance(c.get('value'), str)]
