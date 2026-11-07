// Reference suite (harness validation only): catches every seeded flaw.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createApp, DEMO_USER } from '../app.js';

async function start(t) {
  const server = createApp().listen(0, '127.0.0.1');
  t.after(() => server.close());
  await new Promise(resolve => server.once('listening', resolve));
  return `http://127.0.0.1:${server.address().port}`;
}

async function signIn(base, next) {
  const form = await fetch(`${base}/login`);
  const cookie = form.headers.getSetCookie().map(line => line.split(';')[0]).join('; ');
  const csrf = /name="csrf" value="([^"]+)"/.exec(await form.text())[1];
  return fetch(`${base}/login`, {
    method: 'POST', redirect: 'manual',
    headers: { cookie, 'content-type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({ csrf, username: DEMO_USER.username, password: DEMO_USER.password, next }),
  });
}

test('sign-in never redirects to another origin', async t => {
  const base = await start(t);
  for (const next of ['https://evil.example/', '//evil.example/', '/\\evil.example/']) {
    const response = await signIn(base, next);
    assert.equal(response.status, 303);
    assert.equal(new URL(response.headers.get('location'), base).origin, base, `next=${next}`);
  }
});
