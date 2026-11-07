"""A loopback login app whose session handling can be made insecure one property at a time.

Session ids and the stored token are synthetic canaries, so tests can prove that
no value reaches a result.
"""

from __future__ import annotations

import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

from conftest import CANARY_PREFIX

# A JWT-shaped token: header {"alg":"HS256","typ":"JWT"}, payload and signature are synthetic.
STORAGE_TOKEN = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJDR0JVX0NBTkFSWSJ9.Q0dCVV9DQU5BUllfU0lHTkFUVVJF'


class SessionApp:
	def __init__(self, *, rotate: bool = True, revoke: bool = True, storage_token: bool = False) -> None:
		self.rotate, self.revoke, self.storage_token = rotate, revoke, storage_token
		self.sessions: dict[str, dict] = {}
		self.lock = threading.Lock()
		app = self

		class Handler(BaseHTTPRequestHandler):
			def log_message(self, *args) -> None:
				pass

			def _sid(self) -> str | None:
				for part in (self.headers.get('Cookie') or '').split(';'):
					name, _, value = part.strip().partition('=')
					if name == 'sid':
						return value
				return None

			def _send(self, status: int, body: str = '', headers: dict[str, str] | None = None) -> None:
				data = f'<!doctype html><html><body>{body}</body></html>'.encode()
				self.send_response(status)
				for key, value in (headers or {}).items():
					self.send_header(key, value)
				self.send_header('Content-Type', 'text/html; charset=utf-8')
				self.send_header('Cache-Control', 'no-store')
				self.send_header('Content-Length', str(len(data)))
				self.end_headers()
				self.wfile.write(data)

			def _issue(self, user: str | None) -> str:
				sid = CANARY_PREFIX + secrets.token_hex(12)
				with app.lock:
					app.sessions[sid] = {'user': user}
				return f'sid={sid}; Path=/; HttpOnly; Secure; SameSite=Lax'

			def do_GET(self) -> None:  # noqa: N802
				sid = self._sid()
				with app.lock:
					session = app.sessions.get(sid) if sid else None
				if self.path == '/login':
					headers = {} if session else {'Set-Cookie': self._issue(None)}
					return self._send(200, '<form method="post" action="/login"><input id="username" name="username">'
						'<input id="password" name="password" type="password"><button type="submit">Sign in</button></form>', headers)
				if self.path == '/account':
					if not session or not session.get('user'):
						return self._send(303, '', {'Location': '/login'})
					script = f"<script>localStorage.setItem('access_token', '{STORAGE_TOKEN}')</script>" if app.storage_token else ''
					return self._send(200, f'<h1>Account</h1>{script}<form method="post" action="/logout">'
						'<button id="logout" type="submit">Sign out</button></form>')
				self._send(404, 'Not found')

			def do_POST(self) -> None:  # noqa: N802
				length = int(self.headers.get('Content-Length') or 0)
				form = parse_qs(self.rfile.read(length).decode())
				sid = self._sid()
				with app.lock:
					session = app.sessions.get(sid) if sid else None
				if self.path == '/login':
					if form.get('username') != ['alice'] or form.get('password') != ['pw']:
						return self._send(401, 'Sign in failed')
					headers = {'Location': '/account'}
					if app.rotate or not session:
						with app.lock:
							app.sessions.pop(sid or '', None)
						headers['Set-Cookie'] = self._issue('alice')
					else:
						session['user'] = 'alice'  # Vulnerable: the pre-login id becomes authenticated.
					return self._send(303, '', headers)
				if self.path == '/logout':
					if app.revoke and sid:
						with app.lock:
							app.sessions.pop(sid, None)
					return self._send(303, '', {'Location': '/login', 'Set-Cookie': 'sid=; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=0'})
				self._send(404, 'Not found')

		self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
		self.origin = f'http://127.0.0.1:{self.server.server_address[1]}'
		self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

	def __enter__(self) -> SessionApp:
		self.thread.start()
		return self

	def __exit__(self, *exc_info: object) -> None:
		self.server.shutdown()
		self.server.server_close()
