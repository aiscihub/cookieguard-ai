import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, readFile, rm, writeFile, stat } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { execFile } from 'node:child_process';
import { createServer } from 'node:http';
import { createDemoServer, DEMO_VALUE } from '../examples/demo/server.js';
import { runCli, scanUrl, validateTarget } from 'cookieguard-ci';

let server, target, temp;
before(async () => {
  server = createDemoServer();
  await new Promise((resolve, reject) => server.once('error', reject).listen(0, '127.0.0.1', resolve));
  target = `http://127.0.0.1:${server.address().port}`;
  temp = await mkdtemp(join(tmpdir(), 'cookieguard-test-'));
});
after(async () => { if (server?.listening) await new Promise(resolve => server.close(resolve)); if (temp) await rm(temp, { recursive: true, force: true }); });

async function run(args) {
  let out = '', err = '';
  const code = await runCli(args, { stdout: { write: s => { out += s; } }, stderr: { write: s => { err += s; } } });
  assert.equal((out + err).includes(DEMO_VALUE), false, 'Sensitive sentinel was emitted');
  return { code, out, err };
}

test('CLI end-to-end pass/fail, JSON/text, output permissions, and review', async () => {
  assert.equal((await run(['scan', `${target}/secure`, '--auth-cookie', 'session_id'])).code, 0);
  for (const path of ['missing-httponly', 'missing-secure']) {
    const file = join(temp, `${path}.json`);
    const result = await run(['scan', `${target}/${path}`, '--auth-cookie', 'session_id', '--format', 'json', '--output', file]);
    assert.equal(result.code, 1);
    assert.equal(JSON.parse(result.out).status, 'failed');
    assert.equal(await readFile(file, 'utf8'), result.out);
    assert.equal((await stat(file)).mode & 0o777, 0o600);
  }
  assert.equal((await run(['scan', `${target}/preference`])).code, 0);
  const review = await run(['scan', `${target}/unknown`]);
  assert.equal(review.code, 0); assert.match(review.out, /REVIEW/);
  assert.equal((await run(['scan', `${target}/login`, '--auth-cookie', 'session_id'])).code, 2);
});
test('executable honors documented exit statuses', async () => {
  for (const [path, expected] of [['secure', 0], ['missing-httponly', 1], ['absent', 2]]) {
    const result = await new Promise(resolve => execFile(process.execPath, ['packages/cli/bin/cookieguard-ci.js', 'scan', `${target}/${path}`, '--auth-cookie', 'session_id'], (error, stdout, stderr) => resolve({ code: error?.code ?? 0, output: stdout + stderr })));
    assert.equal(result.code, expected); assert.equal(result.output.includes(DEMO_VALUE), false);
  }
});
test('nonlocal, credential, query, private, and unsupported URLs are rejected without output leakage', async () => {
  for (const url of ['https://example.com/', 'http://169.254.169.254/', 'file:///etc/passwd', `http://user:${DEMO_VALUE}@localhost/`, `http://localhost/?token=${DEMO_VALUE}`, 'http://localhost.evil.invalid/']) {
    assert.equal((await run(['scan', url])).code, 2);
  }
  assert.throws(() => validateTarget('http://example.com', ['https://example.com']));
  assert.equal(validateTarget('https://example.com', ['https://example.com']).origin, 'https://example.com');
  assert.equal((await run(['scan', 'http://10.0.0.1/', '--allow-origin', 'http://10.0.0.1'])).code, 2);
});
test('redirects stay on the initial origin and stop after a bounded count', async () => {
  assert.equal((await run(['scan', `${target}/redirect`, '--auth-cookie', 'session_id'])).code, 0);
  for (const path of ['outside', 'loop']) assert.equal((await run(['scan', `${target}/${path}`])).code, 2);
});
test('HTTP errors, no headers, timeouts, and bad options cannot report success', async () => {
  const slow = createServer(() => {});
  await new Promise((resolve, reject) => slow.once('error', reject).listen(0, '127.0.0.1', resolve));
  try {
    await assert.rejects(scanUrl(`http://127.0.0.1:${slow.address().port}`, { timeoutMs: 100 }), /could not complete/);
  } finally { slow.closeAllConnections(); await new Promise(resolve => slow.close(resolve)); }
  assert.equal((await run(['scan', `${target}/missing`, '--auth-cookie', 'session_id'])).code, 2);
  assert.equal((await run(['scan', `${target}/secure`, '--fail-on', DEMO_VALUE])).code, 2);
  assert.equal((await run([`--${DEMO_VALUE}`])).code, 2);
  assert.equal((await run(['--help'])).code, 0);
  assert.equal((await run(['--version'])).out, '0.1.0\n');
});
test('fixture parse errors and nested legacy data are never reflected', async () => {
  const file = join(temp, 'input.json');
  await writeFile(file, `{"broken": "${DEMO_VALUE}`);
  assert.equal((await run(['scan', '--input', file])).code, 2);
  await writeFile(file, JSON.stringify({ cookies: [{ cookie: { name: 'session_id', value: DEMO_VALUE, secure: false, httpOnly: false } }], context: { token: DEMO_VALUE } }));
  const result = await run(['scan', '--input', file, '--auth-cookie', 'session_id', '--format', 'json']);
  assert.equal(result.code, 1); assert.equal(JSON.parse(result.out).mode, 'fixture');
  await writeFile(file, 'x'.repeat(1024 * 1024 + 1));
  assert.equal((await run(['scan', '--input', file])).code, 2);
});
