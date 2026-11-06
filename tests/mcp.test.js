import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { mkdtemp, writeFile, rm } from 'node:fs/promises';
import { join, resolve } from 'node:path';
import { tmpdir } from 'node:os';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { Client, InMemoryTransport } from '@modelcontextprotocol/client';
import { StdioClientTransport } from '@modelcontextprotocol/client/stdio';
import { createCookieGuardServer } from '@aiscihub/cookieguard-mcp';
import { readConfig } from '../packages/mcp/src/config.js';
import { createDemoServer, DEMO_VALUE } from '../examples/demo/server.js';

const exec = promisify(execFile);
export const TOOL_NAMES = ['cookieguard_audit', 'cookieguard_capabilities', 'cookieguard_explain', 'cookieguard_policy', 'cookieguard_scan'];
const bin = resolve('packages/mcp/bin/cookieguard-mcp.js');
let demo, hostile, target, hostileTarget, temp, requests = 0, sawSlow;
before(async () => {
  temp = await mkdtemp(join(tmpdir(), 'cookieguard-mcp-test-'));
  demo = createDemoServer();
  hostile = createServer((req, res) => {
    requests++;
    assert.equal(req.headers.cookie, undefined);
    assert.equal(req.headers.authorization, undefined);
    if (req.url === '/slow') { sawSlow?.(); return; }
    if (req.url === '/redirect') { res.writeHead(302, { location: `${target}/secure` }); res.end(); return; }
    if (req.url === '/many') {
      res.writeHead(200, { 'set-cookie': Array.from({ length: 60 }, (_, i) => `session_id=${DEMO_VALUE}; Path=/item${i}; SameSite=Lax`) });
    } else {
      res.writeHead(200, { 'set-cookie': [
        `session_id=${DEMO_VALUE}; Path=/${DEMO_VALUE}; SameSite=Lax`,
        `session_${DEMO_VALUE}=ignored; Path=/; Domain=${DEMO_VALUE}.invalid; SameSite=Lax`,
      ] });
    }
    res.end(DEMO_VALUE);
  });
  for (const server of [demo, hostile]) await new Promise((done, reject) => server.once('error', reject).listen(0, '127.0.0.1', done));
  target = `http://127.0.0.1:${demo.address().port}`;
  hostileTarget = `http://127.0.0.1:${hostile.address().port}`;
});
after(async () => {
  for (const server of [demo, hostile]) {
    server?.closeAllConnections();
    if (server?.listening) await new Promise(done => server.close(done));
  }
  if (temp) await rm(temp, { recursive: true, force: true });
});

function clean(value) {
  assert.equal(JSON.stringify(value).includes(DEMO_VALUE), false, 'Private canary reached MCP output');
}

async function connect(t, options = {}) {
  const config = { allowedOrigins: [target], policy: { authCookies: ['session_id'] }, timeoutMs: 500, ...options.config };
  const path = join(temp, `config-${Math.random()}.json`);
  await writeFile(path, JSON.stringify(config));
  const transport = new StdioClientTransport({ command: process.execPath, args: [bin, '--config', path], stderr: 'pipe' });
  let stderr = '';
  transport.stderr.on('data', data => { stderr += data; });
  const client = new Client({ name: 'cookieguard-test', version: '1.0.0' }, {
    versionNegotiation: { mode: options.mode ?? 'legacy' },
  });
  t.after(async () => { await client.close(); clean(stderr); assert.equal(stderr, ''); });
  await client.connect(transport);
  const { tools } = await client.listTools();
  assert.deepEqual(tools.map(tool => tool.name).sort(), TOOL_NAMES);
  return { client, path, tools, scan: async args => {
    const result = await client.callTool({ name: 'cookieguard_scan', arguments: typeof args === 'string' ? { url: args } : args });
    clean(result);
    if (result.structuredContent) assert.deepEqual(JSON.parse(result.content[0].text), result.structuredContent);
    return result;
  } };
}

for (const mode of ['legacy', { pin: '2026-07-28' }]) {
  test(`stdio discovery, schema, and pass/fail/incomplete (${JSON.stringify(mode)})`, async t => {
    const { client, scan, tools } = await connect(t, { mode });
    const scanTool = tools.find(tool => tool.name === 'cookieguard_scan');
    assert.equal(scanTool.inputSchema.additionalProperties, false);
    assert.deepEqual(scanTool.inputSchema.required, ['url']);
    assert.ok(scanTool.outputSchema);
    assert.equal(scanTool.annotations.readOnlyHint, false);
    const policy = await client.callTool({ name: 'cookieguard_policy', arguments: {} });
    assert.deepEqual(policy.structuredContent.allowedOrigins, [target]);
    assert.deepEqual(policy.structuredContent.policy.authCookies, ['session_id']);
    assert.equal(policy.structuredContent.evidenceDir, null);
    for (const [path, status, code] of [['secure', 'passed', 0], ['missing-httponly', 'failed', 1], ['preference', 'incomplete', 2], ['login', 'incomplete', 2]]) {
      const response = await scan(`${target}/${path}`);
      assert.equal(response.isError, false);
      assert.equal(response.structuredContent.status, status);
      assert.equal(response.structuredContent.exitCode, code);
      if (code === 1) assert.ok(response.structuredContent.findings.some(f => f.ruleId === 'CG001' && f.cookieName === 'session_id'));
    }
  });
}

test('exact-origin boundary rejects unconfigured loopback, network targets, credentials, queries, and fragments', async t => {
  const { scan } = await connect(t);
  const previous = requests;
  for (const url of [hostileTarget, 'https://example.com', 'http://169.254.169.254/', 'file:///etc/passwd',
    `http://user:${DEMO_VALUE}@127.0.0.1/`, `${target}/?token=${DEMO_VALUE}`, `${target}/#${DEMO_VALUE}`]) {
    const result = await scan(url);
    assert.equal(result.isError, true);
    assert.equal(result.structuredContent.error.code, 'TARGET');
    assert.equal(result.structuredContent.exitCode, 2);
  }
  assert.equal(requests, previous);
});

test('tool arguments cannot alter policy, allowlist, timeout, or inject reflected validation keys', async t => {
  const { scan, path } = await connect(t);
  for (const extra of [{ policy: { failOn: 'critical' } }, { allowedOrigins: [hostileTarget] }, { timeoutMs: 10000 }, { [DEMO_VALUE]: DEMO_VALUE }]) {
    assert.equal((await scan({ url: `${target}/secure`, ...extra })).isError, true);
  }
  for (const args of [{}, { url: { [DEMO_VALUE]: DEMO_VALUE } }, { url: DEMO_VALUE.repeat(100) }]) {
    assert.equal((await scan(args)).isError, true);
  }
  // Changes to the on-disk configuration require a server restart.
  await writeFile(path, JSON.stringify({ allowedOrigins: [hostileTarget], policy: { failOn: 'critical' } }));
  assert.equal((await scan(`${target}/missing-httponly`)).structuredContent.status, 'failed');
  assert.equal((await scan(hostileTarget)).isError, true);
});

test('remote metadata and bodies stay out of both result representations; output truncation is explicit', async t => {
  const { scan } = await connect(t, { config: { allowedOrigins: [hostileTarget] } });
  const output = (await scan(`${hostileTarget}/${DEMO_VALUE}`)).structuredContent;
  assert.equal(output.target, hostileTarget);
  assert.equal(output.status, 'failed');
  assert.ok(output.findings.some(f => f.cookieName === 'session_id'));
  assert.ok(output.findings.some(f => f.cookieName === null));
  const many = (await scan(`${hostileTarget}/many`)).structuredContent;
  assert.equal(many.findings.length, 100);
  assert.equal(many.omittedFindings, 20);
  assert.equal(many.summary.failures, 120);
});

test('same-origin redirects succeed; cross-origin and looping redirects and HTTP errors stay incomplete', async t => {
  const { scan } = await connect(t, { config: { allowedOrigins: [target, hostileTarget] } });
  assert.equal((await scan(`${target}/redirect`)).structuredContent.status, 'passed');
  for (const url of [`${target}/outside`, `${target}/loop`, `${hostileTarget}/redirect`]) {
    assert.equal((await scan(url)).structuredContent.error.code, 'REDIRECT');
  }
  const result = await scan(`${target}/missing`);
  assert.equal(result.isError, true);
  assert.equal(result.structuredContent.error.code, 'NETWORK');
});

test('timeout and overlapping requests are bounded, and later scans recover', async t => {
  const { scan } = await connect(t, { config: { allowedOrigins: [hostileTarget] } });
  const arrived = new Promise(done => { sawSlow = done; });
  const slow = scan(`${hostileTarget}/slow`);
  await arrived;
  assert.equal((await scan(hostileTarget)).structuredContent.error.code, 'BUSY');
  assert.equal((await slow).structuredContent.error.code, 'NETWORK');
  assert.equal((await scan(hostileTarget)).structuredContent.status, 'failed');
});

test('factory snapshots caller configuration and leaves unknown identity in review', async t => {
  const options = { allowedOrigins: [target], policy: { authCookies: [] } };
  const server = createCookieGuardServer(options);
  options.allowedOrigins[0] = hostileTarget;
  options.policy.authCookies.push('session_id');
  const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();
  const client = new Client({ name: 'snapshot-test', version: '1.0.0' });
  t.after(async () => { await client.close(); await server.close(); });
  await server.connect(serverTransport);
  await client.connect(clientTransport);
  const response = await client.callTool({ name: 'cookieguard_scan', arguments: { url: `${target}/missing-httponly` } });
  clean(response);
  assert.equal(response.structuredContent.status, 'passed');
  assert.equal(response.structuredContent.summary.confirmedAuth, 0);
  assert.ok(response.structuredContent.summary.reviewItems > 0);
});

test('bad startup configuration exits 2 without reflecting paths or input; help and version work', async () => {
  const path = join(temp, `${DEMO_VALUE}.json`);
  for (const contents of ['{broken', JSON.stringify({ allowedOrigins: [] }), JSON.stringify({ allowedOrigins: [target], policy: { failOn: DEMO_VALUE } }), 'x'.repeat(65537)]) {
    await writeFile(path, contents);
    await assert.rejects(exec(process.execPath, [bin, '--config', path]), error => {
      clean(error.stdout + error.stderr);
      assert.equal(error.stdout, ''); assert.equal(error.code, 2); return true;
    });
  }
  for (const options of [null, {}, { allowedOrigins: [target], unknown: true }, { allowedOrigins: [`${target}/path`] }, { allowedOrigins: [target], timeoutMs: 10001 }]) {
    assert.throws(() => createCookieGuardServer(options), { code: 'CONFIG' });
  }
  await assert.rejects(readConfig('relative.json'), { code: 'CONFIG' });
  assert.match((await exec(process.execPath, [bin, '--help'])).stdout, /--config/);
  assert.equal((await exec(process.execPath, [bin, '--version'])).stdout.trim(), '0.1.0');
  await assert.rejects(exec(process.execPath, [bin, `--${DEMO_VALUE}`]), error => { clean(error.stdout + error.stderr); return error.code === 2; });
});
