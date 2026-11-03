"""Public CookieGuard audit for a Browser Use BrowserSession."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable, Mapping
from typing import Any

from ._collector import CdpEvidenceCollector
from ._engine import LocalEngine
from ._errors import CookieGuardError
from ._origins import validate_origins
from ._result import AuditResult, guard_values

_logger = logging.getLogger('cookieguard_browser_use')
_SEVERITIES = ('info', 'low', 'medium', 'high', 'critical')
DEFAULT_ACTION_NAME = 'cookieguard_audit'
ACTION_DESCRIPTION = (
	'Check authentication-cookie security for the authorized test application with CookieGuard. '
	'Read-only: returns sanitized cookie metadata findings, never cookie values. Use after logging in. '
	'This is a provisional check; the final pass/fail result is enforced outside the agent.'
)


async def _sanitized(awaitable, code: str):
	"""Await, re-raising only fixed-message errors. No exception text or context escapes."""
	error: CookieGuardError | None = None
	try:
		return await awaitable
	except CookieGuardError as caught:
		error = CookieGuardError(caught.code)
	except asyncio.CancelledError:
		raise
	except Exception:
		error = CookieGuardError(code)
	raise error


def _names(values: Iterable[str] | None) -> list[str]:
	if values is None:
		return []
	if isinstance(values, str):
		raise CookieGuardError('CONFIG')
	names = list(values)
	if len(names) > 100 or any(not isinstance(name, str) or not name for name in names):
		raise CookieGuardError('CONFIG')
	return names


class CookieGuardAudit:
	"""Audit authentication cookies created during a Browser Use workflow.

	Collection starts with :meth:`start` and ends with :meth:`finish`, both called
	by developer code. The final status is decided by the CookieGuard core engine,
	never by the agent. One instance audits one workflow; create a new instance for
	another workflow or session.
	"""

	def __init__(
		self,
		*,
		allowed_origins: Iterable[str],
		auth_cookies: Iterable[str] | None = None,
		fail_on: str = 'high',
		allowed_same_site: Iterable[str] = ('lax', 'strict'),
		require_explicit_same_site: bool = False,
		require_host_only: bool = False,
		max_lifetime_days: float = 30,
		auth_evidence: Iterable[Mapping[str, str]] | None = None,
		capture_headers: bool = True,
		require_header_evidence: bool | None = None,
		allow_nonlocal_origins: bool = False,
		timeout_seconds: float = 600,
		node_path: str | None = None,
	) -> None:
		if isinstance(allowed_origins, str):
			raise CookieGuardError('CONFIG')
		self.origins = validate_origins(list(allowed_origins), allow_nonlocal_origins)
		if fail_on not in _SEVERITIES or isinstance(allowed_same_site, str):
			raise CookieGuardError('CONFIG')
		for flag in (require_explicit_same_site, require_host_only, capture_headers):
			if not isinstance(flag, bool):
				raise CookieGuardError('CONFIG')
		if require_header_evidence is None:
			require_header_evidence = capture_headers
		if not isinstance(require_header_evidence, bool) or (require_header_evidence and not capture_headers):
			raise CookieGuardError('CONFIG')
		if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)) or not 0.1 <= timeout_seconds <= 600:
			raise CookieGuardError('CONFIG')
		if isinstance(max_lifetime_days, bool) or not isinstance(max_lifetime_days, (int, float)):
			raise CookieGuardError('CONFIG')
		evidence = []
		for entry in auth_evidence or ():
			if not isinstance(entry, Mapping):
				raise CookieGuardError('CONFIG')
			evidence.append(dict(entry))
		# Semantic validation (names, SameSite values, limits, evidence) is done by
		# the CookieGuard core when the audit starts; unknown keys are rejected.
		self.policy: dict[str, Any] = {
			'authCookies': _names(auth_cookies), 'failOn': fail_on, 'allowedSameSite': list(allowed_same_site),
			'requireExplicitSameSite': require_explicit_same_site, 'requireHostOnly': require_host_only,
			'maxLifetimeDays': max_lifetime_days, 'authEvidence': evidence,
		}
		self.capture_headers = capture_headers
		self.require_header_evidence = require_header_evidence
		self._timeout_ms = int(timeout_seconds * 1000)
		self._node_path = node_path
		self._state = 'new'
		self._session: Any = None
		self._engine: LocalEngine | None = None
		self._collector: CdpEvidenceCollector | None = None
		self._lock = asyncio.Lock()
		self._agent_checks = 0

	@property
	def state(self) -> str:
		"""``new``, ``running``, ``finished``, or ``closed``."""
		return self._state

	def browser_allowed_domains(self) -> list[str]:
		"""Patterns for ``BrowserProfile(allowed_domains=...)`` that keep the agent on audited hosts.

		Browser Use matches scheme and host; it does not distinguish ports.
		"""
		result: list[str] = []
		for origin in self.origins:
			scheme, rest = origin.split('://', 1)
			host = rest.rsplit(':', 1)[0] if not rest.startswith('[') else rest.split(']', 1)[0] + ']'
			pattern = f'{scheme}://{host}'
			if pattern not in result:
				result.append(pattern)
		return result

	# ----- Browser Use tool ------------------------------------------------

	def register_tools(self, tools: Any, *, action_name: str = DEFAULT_ACTION_NAME) -> None:
		"""Register a read-only ``cookieguard_audit`` action on a Browser Use ``Tools`` instance."""
		from browser_use import ActionResult
		from pydantic import BaseModel, ConfigDict, Field

		if not isinstance(action_name, str) or not action_name.isidentifier():
			raise CookieGuardError('CONFIG')
		audit = self

		class CookieGuardAuditParams(BaseModel):
			# Same shape as Browser Use's NoParamsAction; any note is ignored.
			model_config = ConfigDict(extra='ignore')
			note: str | None = Field(None, description='Optional; ignored by CookieGuard')

		# Deliberately unannotated: Browser Use type-checks injected parameters
		# against real classes, and this module uses postponed annotations.
		async def action(params, browser_session):
			text = await audit._agent_check(browser_session)
			return ActionResult(extracted_content=text, long_term_memory=text.split('\n', 1)[0])

		action.__name__ = action_name
		action.__qualname__ = action_name
		tools.registry.action(ACTION_DESCRIPTION, param_model=CookieGuardAuditParams)(action)

	async def _agent_check(self, browser_session: Any) -> str:
		# Agent-visible path: fixed text only, never exceptions or values.
		if self._state != 'running':
			return 'CookieGuard audit is not active. The developer must start it before the agent runs.'
		if browser_session is not self._session:
			return 'CookieGuard is attached to a different browser session; no audit was performed.'
		self._agent_checks += 1
		try:
			result = await self.check()
		except CookieGuardError as error:
			return f'CookieGuard provisional check could not complete ({error.code}). The final audit is unaffected.'
		except Exception:
			return 'CookieGuard provisional check could not complete. The final audit is unaffected.'
		return result.agent_summary()

	# ----- lifecycle -------------------------------------------------------

	async def start(self, browser_session: Any) -> None:
		"""Begin passive evidence collection on a started BrowserSession. Call before login."""
		await _sanitized(self._start(browser_session), 'SESSION')

	async def _start(self, browser_session: Any) -> None:
		async with self._lock:
			if self._state != 'new':
				raise CookieGuardError('STATE')
			profile = getattr(browser_session, 'browser_profile', None)
			if profile is None or getattr(profile, 'keep_alive', None) is not True:
				raise CookieGuardError('KEEP_ALIVE')
			try:
				root = browser_session.cdp_client
			except Exception:
				root = None
			if root is None or not getattr(root, 'url', None):
				raise CookieGuardError('SESSION')
			engine = LocalEngine(self._node_path)
			collector = CdpEvidenceCollector(self.origins, engine, capture_headers=self.capture_headers)
			error: CookieGuardError | None = None
			try:
				await engine.start({'origins': list(self.origins), 'policy': self.policy, 'timeoutMs': self._timeout_ms,
					'requireHeaderEvidence': self.require_header_evidence})
			except CookieGuardError as caught:
				error = CookieGuardError(caught.code)
			except Exception:
				error = CookieGuardError('ENGINE')
			if error is None:
				try:
					await collector.start(root)
				except Exception:
					error = CookieGuardError('SESSION')
			if error is not None:
				await collector.stop()
				await engine.close()
				self._state = 'closed'
				raise error
			self._session, self._engine, self._collector = browser_session, engine, collector
			self._state = 'running'

	async def check(self) -> AuditResult:
		"""Provisional, store-only evaluation while collection continues. Never satisfies policy."""
		return await _sanitized(self._check(), 'COLLECT')

	async def _check(self) -> AuditResult:
		async with self._lock:
			if self._state != 'running' or not self._collector or not self._engine:
				raise CookieGuardError('STATE')
			cookies, values = await self._collector.store_cookies()
			reply = await self._engine.snapshot(cookies)
			del cookies
			result = AuditResult.from_engine(reply, provisional=True,
				collection={**self._collector.stats(), 'evidence': 'browser-store-only'})
			return guard_values(result, values)

	async def finish(self, *, baseline: Mapping[str, Any] | None = None) -> AuditResult:
		"""Stop collection and return the final CookieGuard result. Enforce it with ``assert_policy()``."""
		return await _sanitized(self._finish(baseline), 'COLLECT')

	async def _finish(self, baseline: Mapping[str, Any] | None) -> AuditResult:
		async with self._lock:
			if self._state != 'running' or not self._collector or not self._engine:
				raise CookieGuardError('STATE')
			self._state = 'finished'
			collector, engine = self._collector, self._engine
			try:
				healthy = await collector.healthy()
				collector.settle()
				cookies, values = await collector.store_cookies() if healthy else (None, [])
				reasons = set(collector.reasons)
				if not healthy:
					reasons.add('observer-disconnected')
				if cookies is None:
					reasons.add('cookie-store-unavailable')
				stats = collector.stats()
				await collector.stop()
				if reasons:
					await engine.mark_incomplete()
				reply = await engine.finish(cookies, None if baseline is None else dict(baseline))
				del cookies
				missing = reply.get('headerEvidenceMissing') or []
				if missing:
					reasons.add('auth-cookie-declaration-not-observed')
				result = AuditResult.from_engine(reply, provisional=False, collection={
					**stats, 'evidence': 'server-declarations-and-browser-store' if self.capture_headers else 'browser-store-only',
					'requireHeaderEvidence': self.require_header_evidence, 'incompleteReasons': sorted(reasons),
					'agentChecks': self._agent_checks})
				return guard_values(result, values)
			finally:
				await self._release()

	async def close(self) -> None:
		"""Stop collection without a result. Safe to call repeatedly."""
		async with self._lock:
			await self._release()
			if self._state != 'finished':
				self._state = 'closed'

	async def _release(self) -> None:
		collector, engine = self._collector, self._engine
		self._collector = self._engine = None
		self._session = None
		if collector is not None:
			await collector.stop()
		if engine is not None:
			await engine.close()

	async def __aenter__(self) -> CookieGuardAudit:
		return self

	async def __aexit__(self, *exc_info: object) -> None:
		await self.close()
