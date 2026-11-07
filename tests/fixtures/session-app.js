import http from 'node:http';
import { randomBytes } from 'node:crypto';

// A loopback login app whose session handling can be made insecure one property
// at a time. Session ids carry a sentinel prefix so tests can prove that no
// value reaches a report.
export const SID_PREFIX = 'SENTINEL_SID_';
export const STORAGE_TOKEN = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJTRU5USU5FTF9KV1QifQ.U0VOVElORUxfU0lHTkFUVVJFX1ZBTFVF';

export function createSessionApp({ rotate = true, revoke = true, storageToken = false } = {}) {
  const sessions = new Map();
  const issue = (response, user) => {
    const sid = SID_PREFIX + randomBytes(12).toString('hex');
    sessions.set(sid, { user });
    response.setHeader('set-cookie', `sid=${sid}; Path=/; HttpOnly; Secure; SameSite=Lax`);
    return sid;
  };
  const sidOf = request => /(?:^|;\s*)sid=([^;]+)/.exec(request.headers.cookie ?? '')?.[1] ?? null;
  const page = (response, status, body) => {
    response.writeHead(status, { 'content-type': 'text/html; charset=utf-8', 'cache-control': 'no-store' });
    response.end(`<!doctype html><html><body>${body}</body></html>`);
  };
  return http.createServer((request, response) => {
    const { pathname } = new URL(request.url, 'http://127.0.0.1');
    const sid = sidOf(request);
    const session = sid ? sessions.get(sid) : undefined;
    if (request.method === 'GET' && pathname === '/login') {
      // An anonymous session exists before login, as in many frameworks.
      if (!session) issue(response, null);
      return page(response, 200, '<form method="post" action="/login"><input id="username" name="username">'
        + '<input id="password" name="password" type="password"><button type="submit">Sign in</button></form>');
    }
    if (request.method === 'POST' && pathname === '/login') {
      let body = '';
      request.on('data', chunk => { body += chunk; });
      request.on('end', () => {
        const form = new URLSearchParams(body);
        if (form.get('username') !== 'alice' || form.get('password') !== 'pw') return page(response, 401, 'Sign in failed');
        if (rotate || !session) {
          if (sid) sessions.delete(sid);
          issue(response, 'alice');
        } else session.user = 'alice'; // Vulnerable: the pre-login id becomes authenticated.
        response.writeHead(303, { location: '/account' });
        response.end();
      });
      return;
    }
    if (request.method === 'GET' && pathname === '/account') {
      if (!session?.user) { response.writeHead(303, { location: '/login' }); response.end(); return; }
      const script = storageToken ? `<script>localStorage.setItem('access_token', '${STORAGE_TOKEN}')</script>` : '';
      return page(response, 200, `<h1>Account</h1>${script}<form method="post" action="/logout"><button id="logout">Sign out</button></form>`);
    }
    if (request.method === 'POST' && pathname === '/logout') {
      if (revoke && sid) sessions.delete(sid); // Without this, the old id stays valid.
      response.writeHead(303, { location: '/login', 'set-cookie': 'sid=; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=0' });
      response.end();
      return;
    }
    response.writeHead(404);
    response.end();
  });
}
