import http from 'node:http';
import { randomBytes } from 'node:crypto';

// Acme Portal: a small customer portal with password login.
const PORT = Number(process.env.PORT ?? {{PORT}});
const USERS = { demo: 'demo123' };
const sessions = new Map();

function page(title, body) {
  return `<!doctype html><html><head><meta charset="utf-8"><title>${title}</title></head><body><h1>${title}</h1>${body}</body></html>`;
}

function readForm(request) {
  return new Promise(resolve => {
    let data = '';
    request.on('data', chunk => { data += chunk; if (data.length > 4096) request.destroy(); });
    request.on('end', () => resolve(new URLSearchParams(data)));
  });
}

function currentUser(request) {
  const cookie = (request.headers.cookie ?? '').split(';').map(part => part.trim()).find(part => part.startsWith('session='));
  return cookie ? sessions.get(cookie.slice('session='.length)) : undefined;
}

function startSession(response, user) {
  const token = `BENCH_SECRET_${randomBytes(12).toString('hex')}`;
  sessions.set(token, user);
  response.writeHead(303, {
    location: '/account',
    'set-cookie': `session=${token}; Path=/; SameSite=Lax; Max-Age=2592000`,
  });
  response.end();
}

const server = http.createServer(async (request, response) => {
  const { pathname } = new URL(request.url, 'http://localhost');
  if (pathname === '/health') { response.writeHead(200, { 'content-type': 'application/json' }); response.end('{"ok":true}'); return; }
  if (pathname === '/login' && request.method === 'POST') {
    const form = await readForm(request);
    const user = form.get('username');
    if (!user || USERS[user] !== form.get('password')) {
      response.writeHead(401, { 'content-type': 'text/html' });
      response.end(page('Sign in failed', '<a href="/login">Try again</a>'));
      return;
    }
    startSession(response, user);
    return;
  }
  // Development shortcut: sign in as the demo user without the form.
  if (pathname === '/dev/login' && process.env.NODE_ENV !== 'production') {
    startSession(response, 'demo');
    return;
  }
  if (pathname === '/login' || pathname === '/') {
    response.writeHead(200, { 'content-type': 'text/html' });
    response.end(page('Acme Portal sign in', `<form method="post" action="/login">
<label>Username <input id="username" name="username" autocomplete="username"></label>
<label>Password <input id="password" name="password" type="password" autocomplete="current-password"></label>
<button type="submit">Sign in</button></form>`));
    return;
  }
  if (pathname === '/account') {
    const user = currentUser(request);
    if (!user) { response.writeHead(303, { location: '/login' }); response.end(); return; }
    response.writeHead(200, { 'content-type': 'text/html' });
    response.end(page('Your account', `<p>Signed in as ${user}.</p><form method="post" action="/logout"><button>Sign out</button></form>`));
    return;
  }
  if (pathname === '/logout' && request.method === 'POST') {
    response.writeHead(303, { location: '/login', 'set-cookie': 'session=; Path=/; Max-Age=0' });
    response.end();
    return;
  }
  response.writeHead(404); response.end('Not found');
});

server.listen(PORT, '127.0.0.1', () => console.log(`Acme Portal on http://127.0.0.1:${PORT}`));
