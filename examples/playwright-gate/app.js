// A minimal app with a real form login, a session, and logout, for the gate example.
// FLAW=httponly drops HttpOnly from the session cookie; FLAW=logout keeps the server
// session alive after logout. The demo password is for this local fixture only.
import http from 'node:http';
import { randomBytes } from 'node:crypto';

const USER = { name: 'demo', password: 'demo-password' };
const flaw = process.env.FLAW ?? '';
const sessions = new Map();

const sidOf = req => (req.headers.cookie ?? '').split(';').map(s => s.trim()).find(s => s.startsWith('sid='))?.slice(4);
const html = (res, status, body) => { res.writeHead(status, { 'content-type': 'text/html; charset=utf-8' }); res.end(`<!doctype html><title>Gate example</title>${body}`); };
const redirect = (res, location, cookie) => { res.writeHead(303, { location, ...(cookie ? { 'set-cookie': cookie } : {}) }); res.end(); };
const body = req => new Promise(resolve => { let data = ''; req.on('data', c => { data += c; }); req.on('end', () => resolve(new URLSearchParams(data))); });

http.createServer(async (req, res) => {
  const { pathname } = new URL(req.url, 'http://localhost');
  const user = sessions.get(sidOf(req));
  if (req.method === 'GET' && pathname === '/login') {
    return html(res, 200, `<form method="post" action="/login"><label>Username <input name="username"></label>
<label>Password <input name="password" type="password"></label><button>Sign in</button></form>`);
  }
  if (req.method === 'POST' && pathname === '/login') {
    const form = await body(req);
    if (form.get('username') !== USER.name || form.get('password') !== USER.password) return html(res, 401, '<p role="alert">Wrong username or password.</p>');
    const sid = randomBytes(24).toString('hex');
    sessions.set(sid, USER.name);
    return redirect(res, '/account', `sid=${sid}; Path=/; Secure;${flaw === 'httponly' ? '' : ' HttpOnly;'} SameSite=Lax; Max-Age=3600`);
  }
  if (req.method === 'GET' && pathname === '/account') {
    if (!user) return redirect(res, '/login');
    return html(res, 200, `<h1>Signed in as ${user}</h1><form method="post" action="/logout"><button>Sign out</button></form>`);
  }
  // The protected URL the session probe replays the session against: 401 unless signed in.
  if (req.method === 'GET' && pathname === '/api/me') {
    res.writeHead(user ? 200 : 401, { 'content-type': 'application/json' });
    return res.end(JSON.stringify(user ? { user } : { error: 'not signed in' }));
  }
  if (req.method === 'POST' && pathname === '/logout') {
    if (flaw !== 'logout') sessions.delete(sidOf(req));
    return redirect(res, '/login', 'sid=; Path=/; Secure; HttpOnly; SameSite=Lax; Max-Age=0');
  }
  res.writeHead(404); res.end();
}).listen(Number(process.env.PORT ?? 3100), '127.0.0.1');
