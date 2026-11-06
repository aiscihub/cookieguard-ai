"""Local staging copy of the Acme Portal login, used by the browser agent."""

import os
import secrets
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

PORT = int(os.environ.get('PORT', '{{PORT}}'))
USERS = {'demo': 'demo123'}
SESSIONS: dict[str, str] = {}

LOGIN = b'''<!doctype html><title>Acme sign in</title><h1>Acme sign in</h1>
<form method="post" action="/login">
<label>Username <input id="username" name="username"></label>
<label>Password <input id="password" name="password" type="password"></label>
<button type="submit">Sign in</button></form>'''


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _user(self):
        cookie = SimpleCookie(self.headers.get('Cookie', ''))
        return SESSIONS.get(cookie['sid'].value) if 'sid' in cookie else None

    def do_GET(self):
        if self.path in ('/', '/login'):
            self._send(200, LOGIN)
        elif self.path == '/dashboard':
            user = self._user()
            if user:
                self._send(200, f'<!doctype html><title>Dashboard</title><h1>Welcome, {user}</h1><p>Login succeeded</p>'.encode())
            else:
                self._send(303, headers={'Location': '/login'})
        else:
            self._send(404, b'Not found')

    def do_POST(self):
        if self.path != '/login':
            return self._send(404, b'Not found')
        length = min(int(self.headers.get('Content-Length', 0)), 4096)
        form = parse_qs(self.rfile.read(length).decode())
        user, password = form.get('username', [''])[0], form.get('password', [''])[0]
        if USERS.get(user) != password:
            return self._send(401, LOGIN)
        token = f'BENCH_SECRET_{secrets.token_hex(12)}'
        SESSIONS[token] = user
        self._send(303, headers={'Location': '/dashboard', 'Set-Cookie': f'sid={token}; Path=/; SameSite=Lax'})

    def _send(self, status, body=b'', headers=None):
        self.send_response(status)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)


if __name__ == '__main__':
    print(f'Acme staging app on http://127.0.0.1:{PORT}')
    ThreadingHTTPServer(('127.0.0.1', PORT), Handler).serve_forever()
