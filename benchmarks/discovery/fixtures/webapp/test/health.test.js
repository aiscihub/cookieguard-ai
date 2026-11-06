import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';

test('health endpoint responds', async () => {
  const port = {{TEST_PORT}};
  const child = spawn(process.execPath, ['server.js'], { env: { ...process.env, PORT: String(port) }, stdio: 'ignore' });
  try {
    let response;
    for (let attempt = 0; attempt < 50 && !response; attempt++) {
      response = await fetch(`http://127.0.0.1:${port}/health`).catch(() => undefined);
      if (!response) await new Promise(done => setTimeout(done, 100));
    }
    assert.equal(response?.status, 200);
  } finally { child.kill(); }
});
