// Reference suite (harness validation only): functional checks that catch no seeded flaw.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createApp, DEMO_USER } from '../app.js';

async function start(t) {
  const server = createApp().listen(0, '127.0.0.1');
  t.after(() => server.close());
  await new Promise(resolve => server.once('listening', resolve));
  return `http://127.0.0.1:${server.address().port}`;
}

async function signIn(base, password) {
  const form = await fetch(`${base}/login`);
  const cookie = form.headers.getSetCookie().map(line => line.split(';')[0]).join('; ');
  const csrf = /name="csrf" value="([^"]+)"/.exec(await form.text())[1];
  return fetch(`${base}/login`, {
    method: 'POST', redirect: 'manual',
    headers: { cookie, 'content-type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({ csrf, username: DEMO_USER.username, password }),
  });
}

test('valid credentials sign in', async t => {
  const response = await signIn(await start(t), DEMO_USER.password);
  assert.equal(response.status, 303);
  assert.equal(response.headers.get('location'), '/notes');
  assert.ok(response.headers.getSetCookie().some(line => line.startsWith('sid=')));
});

test('a wrong password is rejected', async t => {
  const response = await signIn(await start(t), 'wrong');
  assert.equal(response.status, 401);
});

test('notes need a session', async t => {
  const response = await fetch(`${await start(t)}/notes`, { redirect: 'manual' });
  assert.equal(response.status, 303);
});
