import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createApp } from '../app.js';

test('health check responds', async t => {
  const server = createApp().listen(0, '127.0.0.1');
  t.after(() => server.close());
  await new Promise(resolve => server.once('listening', resolve));
  const response = await fetch(`http://127.0.0.1:${server.address().port}/health`);
  assert.equal(response.status, 200);
  assert.equal(await response.text(), 'ok');
});
