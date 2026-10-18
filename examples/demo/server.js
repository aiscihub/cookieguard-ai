import http from 'node:http';
import { pathToFileURL } from 'node:url';

// Deliberately artificial tokens. Never use real credentials in this fixture.
export const DEMO_VALUE = 'COOKIEGUARD_DEMO_SENTINEL_4e29bc7f';
export function createDemoServer() {
  return http.createServer((request, response) => {
    const path = new URL(request.url, 'http://127.0.0.1').pathname;
    const configs = {
      '/secure': `session_id=${DEMO_VALUE}; Path=/; Secure; HttpOnly; SameSite=Lax`,
      '/missing-httponly': `session_id=${DEMO_VALUE}; Path=/; Secure; SameSite=Lax`,
      '/missing-secure': `session_id=${DEMO_VALUE}; Path=/; HttpOnly; SameSite=Lax`,
      '/preference': 'theme=light; Path=/; SameSite=Lax',
      '/unknown': `auth_hint=${DEMO_VALUE}; Path=/; SameSite=Lax`,
      '/rejected-prefix': `__Host-session_id=${DEMO_VALUE}; Path=/sub; Secure; HttpOnly; SameSite=Lax`,
      '/rejected-none': `session_id=${DEMO_VALUE}; Path=/; SameSite=None`,
      '/default-samesite': `session_id=${DEMO_VALUE}; Path=/; Secure; HttpOnly`,
      '/delete': 'session_id=deleted; Path=/; Max-Age=0',
    };
    if (path === '/redirect') { response.writeHead(302, { location: '/secure' }); response.end(); return; }
    if (path === '/outside') { response.writeHead(302, { location: 'http://127.0.0.1:1/private' }); response.end(); return; }
    if (path === '/loop') { response.writeHead(302, { location: '/loop' }); response.end(); return; }
    if (path === '/login' || path === '/') {
      response.writeHead(200, { 'content-type': 'text/html; charset=utf-8' });
      response.end('<!doctype html><title>CookieGuard local demo</title><h1>CookieGuard local demo</h1><p>No passwords or external resources.</p><a href="/secure">Create secure demo session</a>'); return;
    }
    if (configs[path]) {
      response.writeHead(200, { 'set-cookie': configs[path], 'content-type': 'text/html; charset=utf-8' });
      response.end('<!doctype html><title>Demo session</title><p>Local cookie fixture loaded.</p>'); return;
    }
    response.writeHead(404); response.end('Not found');
  });
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const server = createDemoServer();
  const port = Number(process.env.PORT ?? 3000);
  server.listen(port, '127.0.0.1', () => process.stdout.write(`CookieGuard demo listening on http://127.0.0.1:${server.address().port}\n`));
  for (const signal of ['SIGINT', 'SIGTERM']) process.on(signal, () => server.close());
}
