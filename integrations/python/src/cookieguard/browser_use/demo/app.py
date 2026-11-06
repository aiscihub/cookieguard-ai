"""Loopback-only demo application with a real login form.

``insecure`` mode deliberately omits HttpOnly on the session cookie; ``secure``
mode sets it. Everything else, including the login flow, is identical.
Credentials are disposable demo values. The server never logs requests,
headers, credentials, or cookie values.
"""

from __future__ import annotations

import argparse
import html
import secrets
import threading
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

# Distinctive values: Browser Use masks every occurrence of a sensitive_data value.
DEMO_USERNAME = 'cg-demo-user'
DEMO_PASSWORD = 'cg-disposable-password-41f7'
SESSION_COOKIE = 'session_id'
MODES = ('insecure', 'secure')
_LOOPBACK = ('127.0.0.1', 'localhost', '::1')

_STYLE = ('body{font-family:system-ui,sans-serif;max-width:32rem;margin:4rem auto;padding:0 1rem;color:#1d2433}'
	'label{display:block;margin:.75rem 0 .25rem}input{width:100%;padding:.5rem;font-size:1rem;box-sizing:border-box}'
	'button{margin-top:1rem;padding:.6rem 1.2rem;font-size:1rem}.note{color:#5b6475;font-size:.9rem}')


def _page(title: str, body: str) -> bytes:
	return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{html.escape(title)}</title>'
		f'<style>{_STYLE}</style></head><body>{body}</body></html>').encode()


def set_cookie_header(mode: str, token: str) -> str:
	# The only difference between the scenarios is HttpOnly.
	# Secure is accepted by Chromium on loopback HTTP; production needs HTTPS.
	flags = 'Path=/; Secure; SameSite=Lax' if mode == 'insecure' else 'Path=/; Secure; HttpOnly; SameSite=Lax'
	return f'{SESSION_COOKIE}={token}; {flags}'


class DemoApp:
	"""A tiny login app bound to a loopback address. Use as a context manager."""

	def __init__(self, mode: str = 'insecure', *, host: str = '127.0.0.1', port: int = 0,
		token_factory: Callable[[], str] | None = None) -> None:
		if mode not in MODES:
			raise ValueError('mode must be "insecure" or "secure"')
		if host not in _LOOPBACK:
			raise ValueError('The demo app only binds to loopback addresses.')
		self.mode = mode
		self._sessions: set[str] = set()
		self._lock = threading.Lock()
		self._token_factory = token_factory or (lambda: secrets.token_urlsafe(24))
		self.logins = 0
		self._server = ThreadingHTTPServer((host, port), self._handler())
		self._server.daemon_threads = True
		self._thread: threading.Thread | None = None

	@property
	def origin(self) -> str:
		host, port = self._server.server_address[:2]
		host = f'[{host}]' if ':' in host else host
		return f'http://{host}:{port}'

	def start(self) -> DemoApp:
		self._thread = threading.Thread(target=self._server.serve_forever, name='cookieguard-demo-app', daemon=True)
		self._thread.start()
		return self

	def stop(self) -> None:
		self._server.shutdown()
		self._server.server_close()
		with self._lock:
			self._sessions.clear()

	def __enter__(self) -> DemoApp:
		return self.start()

	def __exit__(self, *exc_info: object) -> None:
		self.stop()

	def _handler(self):
		app = self

		class Handler(BaseHTTPRequestHandler):
			server_version = 'CookieGuardDemo'
			sys_version = ''

			def log_message(self, format, *args):  # noqa: A002 - never log requests or headers.
				return

			def _send(self, status: int, body: bytes = b'', headers: dict[str, str] | None = None) -> None:
				self.send_response(status)
				self.send_header('Cache-Control', 'no-store')
				self.send_header('Content-Type', 'text/html; charset=utf-8')
				for name, value in (headers or {}).items():
					self.send_header(name, value)
				self.send_header('Content-Length', str(len(body)))
				self.end_headers()
				self.wfile.write(body)

			def _authenticated(self) -> bool:
				for part in self.headers.get('Cookie', '').split(';'):
					name, _, value = part.strip().partition('=')
					if name == SESSION_COOKIE:
						with app._lock:
							if value in app._sessions:
								return True
				return False

			def do_GET(self):  # noqa: N802
				path = urlsplit(self.path).path
				if path in ('/', ''):
					self._send(303, headers={'Location': '/login'})
				elif path == '/login':
					self._send(200, _page('Sign in — CookieGuard demo', (
						'<h1>Sign in</h1><p class="note">Local CookieGuard demo. Disposable test account only.</p>'
						'<form method="post" action="/login">'
						'<label for="username">Username</label><input id="username" name="username" autocomplete="username">'
						'<label for="password">Password</label>'
						'<input id="password" name="password" type="password" autocomplete="current-password">'
						'<button type="submit">Sign in</button></form>')))
				elif path == '/account':
					if not self._authenticated():
						self._send(303, headers={'Location': '/login'})
					else:
						self._send(200, _page('Account — CookieGuard demo',
							'<h1>Login succeeded</h1><p>The server accepted the session cookie.</p>'))
				else:
					self._send(404, _page('Not found', '<h1>Not found</h1>'))

			def do_POST(self):  # noqa: N802
				if urlsplit(self.path).path != '/login':
					self._send(404, _page('Not found', '<h1>Not found</h1>'))
					return
				try:
					length = int(self.headers.get('Content-Length', '0'))
				except ValueError:
					length = -1
				if not 0 <= length <= 4096:
					self._send(413, _page('Rejected', '<h1>Request rejected</h1>'))
					return
				form = parse_qs(self.rfile.read(length).decode('utf-8', 'replace'))
				username = form.get('username', [''])[0]
				password = form.get('password', [''])[0]
				if not (secrets.compare_digest(username, DEMO_USERNAME) and secrets.compare_digest(password, DEMO_PASSWORD)):
					self._send(401, _page('Sign in failed', '<h1>Sign in failed</h1><p><a href="/login">Try again</a></p>'))
					return
				token = app._token_factory()
				with app._lock:
					app._sessions.add(token)
					app.logins += 1
				self._send(303, headers={'Location': '/account', 'Set-Cookie': set_cookie_header(app.mode, token)})

		return Handler


def main(argv: list[str] | None = None) -> None:
	parser = argparse.ArgumentParser(description='Run the loopback-only CookieGuard demo login app.')
	parser.add_argument('--mode', choices=MODES, default='insecure')
	parser.add_argument('--port', type=int, default=8765)
	args = parser.parse_args(argv)
	app = DemoApp(args.mode, port=args.port).start()
	print(f'CookieGuard demo ({args.mode}) at {app.origin}/login — user {DEMO_USERNAME!r}. Ctrl+C to stop.')
	try:
		threading.Event().wait()
	except KeyboardInterrupt:
		pass
	finally:
		app.stop()


if __name__ == '__main__':
	main()
