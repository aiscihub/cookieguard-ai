"""Default-on, best-effort invocation counts with explicit opt-outs and no audit inputs."""

from __future__ import annotations

import http.client
import json
import math
import os
import queue
import re
import ssl
import threading
import time
import uuid

from . import _usage_config

_HOSTS = {'us': 'us.i.posthog.com', 'eu': 'eu.i.posthog.com'}
_TOKEN = re.compile(r'phc_[A-Za-z0-9_-]{20,200}', re.ASCII)
_TIMEOUT = 0.5
_QUEUE_LIMIT = 16
_reporter: _Reporter | None = None
_reporter_lock = threading.Lock()


def _configuration(enabled: bool | None) -> tuple[str, str] | None:
	metrics_env = os.environ.get('COOKIEGUARD_USAGE_METRICS')
	if metrics_env == '0' or os.environ.get('DO_NOT_TRACK') == '1':
		return None
	# Missing configuration uses the package default. Unrecognized explicit values
	# retain their conservative behavior unless the caller explicitly enables usage.
	if enabled is False or (enabled is not True and metrics_env not in (None, '1')):
		return None
	token = os.environ.get('COOKIEGUARD_POSTHOG_PROJECT_TOKEN', _usage_config.PROJECT_TOKEN)
	region = os.environ.get('COOKIEGUARD_POSTHOG_REGION', _usage_config.REGION)
	if not isinstance(token, str) or not _TOKEN.fullmatch(token) or region not in _HOSTS:
		return None
	return token, _HOSTS[region]


def _send(host: str, body: bytes) -> None:
	# http.client neither follows redirects nor reads proxy/cookie configuration.
	# Build the verified context directly: create_default_context honors
	# SSLKEYLOGFILE and would write TLS secrets to a caller-selected local file.
	context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
	context.load_default_certs()
	context.set_alpn_protocols(['http/1.1'])
	connection = http.client.HTTPSConnection(host, timeout=_TIMEOUT, context=context)
	try:
		connection.request('POST', '/i/v0/e/', body=body, headers={'Content-Type': 'application/json'})
		connection.getresponse()
	finally:
		connection.close()


class _Reporter:
	def __init__(self) -> None:
		self.queue: queue.Queue[tuple[str, bytes]] = queue.Queue(maxsize=_QUEUE_LIMIT)
		self.worker = threading.Thread(target=self._run, name='cookieguard-usage', daemon=True)
		self.worker.start()

	def _run(self) -> None:
		while True:
			host, body = self.queue.get()
			try:
				_send(host, body)
			except Exception:
				pass
			finally:
				self.queue.task_done()

	def flush(self, timeout: float) -> bool:
		deadline = time.monotonic() + timeout
		with self.queue.all_tasks_done:
			while self.queue.unfinished_tasks:
				remaining = deadline - time.monotonic()
				if remaining <= 0:
					return False
				self.queue.all_tasks_done.wait(remaining)
		return True


def report_invocation(enabled: bool | None) -> None:
	"""Queue one allowlisted event; never raise or inspect the audit/session."""
	global _reporter
	try:
		configuration = _configuration(enabled)
		if configuration is None:
			return
		from . import __version__

		token, host = configuration
		body = json.dumps({
			'api_key': token,
			'event': 'cookieguard_invoked',
			'distinct_id': str(uuid.uuid4()),
			'properties': {
				'$process_person_profile': False,
				'$geoip_disable': True,
				'$ip': '0.0.0.0',
				'schema_version': 1,
				'package': 'cookieguard',
				'package_version': __version__,
				'integration': 'browser-use',
			},
		}, separators=(',', ':'), allow_nan=False).encode('utf-8')
		with _reporter_lock:
			if _reporter is None:
				_reporter = _Reporter()
			_reporter.queue.put_nowait((host, body))
	except Exception:
		pass


def flush_usage_metrics(timeout_seconds: float = _TIMEOUT) -> bool:
	"""Wait at most one second for queued usage events; return whether they drained.

	This optional helper never enables reporting or retries delivery. A drained
	queue does not guarantee delivery; network failures silently discard events.
	"""
	try:
		if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)) or not math.isfinite(timeout_seconds):
			return False
		reporter = _reporter
		return reporter is None or reporter.flush(max(0.0, min(timeout_seconds, 1.0)))
	except Exception:
		return False
