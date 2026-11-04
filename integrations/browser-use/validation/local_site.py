"""Loopback fixtures for measuring cookie policy, never real credentials or accounts."""

from __future__ import annotations

import secrets
import threading
from dataclasses import dataclass
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


@dataclass(frozen=True)
class Case:
	name: str
	attributes: str | None
	expected_status: str
	expected_rules: tuple[str, ...] = ()
	preference: bool = False


# Ground truth is specified independently of CookieGuard's output. All runs use
# fail_on='medium', explicit SameSite, and a maximum lifetime of 30 days.
CASES = (
	Case('secure_lax', 'Secure; HttpOnly; SameSite=Lax', 'PASS'),
	Case('secure_strict', 'Secure; HttpOnly; SameSite=Strict', 'PASS'),
	Case('preference_control', 'Secure; HttpOnly; SameSite=Lax', 'PASS', preference=True),
	Case('missing_httponly', 'Secure; SameSite=Lax', 'FAIL', ('CG001',)),
	Case('missing_secure', 'HttpOnly; SameSite=Lax', 'FAIL', ('CG002',)),
	Case('missing_both', 'SameSite=Lax', 'FAIL', ('CG001', 'CG002')),
	Case('samesite_none', 'Secure; HttpOnly; SameSite=None', 'FAIL', ('CG003',)),
	Case('samesite_omitted', 'Secure; HttpOnly', 'FAIL', ('CG003',)),
	Case('long_lifetime', 'Secure; HttpOnly; SameSite=Lax; Max-Age=2678400', 'FAIL', ('CG005',)),
	Case('missing_session', None, 'INCOMPLETE'),
)
TOKEN_PREFIX = 'CG_VALIDATION_CANARY_'


class LocalSite:
	"""A button issues a synthetic session; /account verifies it on the server."""

	def __init__(self, case: Case):
		self.case = case
		self.token = TOKEN_PREFIX + secrets.token_hex(16)
		self.account_visits = 0
		site = self

		class Handler(BaseHTTPRequestHandler):
			def log_message(self, *_args):
				pass

			def respond(self, status: int, body: str = '', headers: tuple[tuple[str, str], ...] = ()):
				data = body.encode()
				self.send_response(status)
				self.send_header('Content-Type', 'text/html; charset=utf-8')
				self.send_header('Content-Length', str(len(data)))
				self.send_header('Cache-Control', 'no-store')
				for name, value in headers:
					self.send_header(name, value)
				self.end_headers()
				self.wfile.write(data)

			def do_GET(self):  # noqa: N802
				if self.path == '/login':
					self.respond(
						200,
						'<!doctype html><title>Synthetic login</title><h1>Synthetic login</h1>'
						'<form method="post" action="/login"><button id="login">Create test session</button></form>',
					)
				elif self.path == '/account':
					cookie = SimpleCookie(self.headers.get('Cookie', ''))
					entry = cookie.get('session_id')
					if entry and secrets.compare_digest(entry.value, site.token):
						site.account_visits += 1
						self.respond(200, '<!doctype html><title>Login succeeded</title><h1>Login succeeded</h1>')
					else:
						self.respond(401, '<!doctype html><title>No session issued</title><h1>No session issued</h1>')
				else:
					self.respond(404)

			def do_POST(self):  # noqa: N802
				if self.path != '/login':
					self.respond(404)
					return
				headers = [('Location', '/account')]
				if site.case.attributes is not None:
					headers.append(('Set-Cookie', f'session_id={site.token}; Path=/; {site.case.attributes}'))
				if site.case.preference:
					# A non-authentication cookie may intentionally be script-readable.
					headers.append(('Set-Cookie', 'theme=light; Path=/; SameSite=Lax'))
				self.respond(303, headers=tuple(headers))

		self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
		self.server.daemon_threads = True
		self.thread = threading.Thread(target=self.server.serve_forever, kwargs={'poll_interval': 0.05}, daemon=True)

	@property
	def origin(self) -> str:
		return f'http://127.0.0.1:{self.server.server_port}'

	def __enter__(self):
		self.thread.start()
		return self

	def __exit__(self, *_args):
		self.server.shutdown()
		self.server.server_close()
		self.thread.join(timeout=2)
