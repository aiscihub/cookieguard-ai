import { test, before, after, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { EventEmitter } from 'node:events';
import { createServer } from 'node:http';
import { execFile } from 'node:child_process';
import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { promisify } from 'node:util';
import { Client, InMemoryTransport } from '@modelcontextprotocol/client';
import { messages, workers, transport, acknowledgeMessages, restoreWorker } from './fixtures/usage-worker.mjs';
import cliManifest from '../packages/cli/package.json' with { type: 'json' };
import playwrightManifest from '../packages/playwright/package.json' with { type: 'json' };
import mcpManifest from '../packages/mcp/package.json' with { type: 'json' };

// Imports occur after the fake Worker is installed. These tests cannot contact PostHog.
const { runCli, scanUrl } = await import('cookieguard-ci');
const { startCookieAudit, auditPage, cookieGuardFixtures } = await import('@aiscihub/cookieguard-playwright');
const { createCookieGuardServer } = await import('@aiscihub/cookieguard-mcp');
const { evaluateCookiePolicy, formatJson, assertCookiePolicy } = await import('@aiscihub/cookieguard-core');
const { flushUsage } = await import('@aiscihub/cookieguard-core/usage');
const exec = promisify(execFile);
const CANARY = 'PRIVATE_AUDIT_INPUT_CANARY';
const ENV_KEYS = ['COOKIEGUARD_USAGE_METRICS', 'COOKIEGUARD_POSTHOG_PROJECT_TOKEN', 'COOKIEGUARD_POSTHOG_REGION', 'DO_NOT_TRACK'];
const enabledEnv = { COOKIEGUARD_USAGE_METRICS: '1', COOKIEGUARD_POSTHOG_PROJECT_TOKEN: 'phc_synthetic_adapter_test', COOKIEGUARD_POSTHOG_REGION: 'us' };
let temp, fixture, server, target, slowArrived, slowResponse;

class Context extends EventEmitter {
  async cookies() {
    return [{ name: CANARY, value: `${CANARY}_VALUE`, domain: 'app.test', path: `/${CANARY}`, secure: true, httpOnly: true, sameSite: 'Lax', expires: -1 }];
  }
}

function configure(t, values = enabledEnv) {
  const saved = Object.fromEntries(ENV_KEYS.map(key => [key, process.env[key]]));
  for (const key of ENV_KEYS) delete process.env[key];
  Object.assign(process.env, values);
  t.after(() => {
    for (const key of ENV_KEYS) {
      if (saved[key] === undefined) delete process.env[key];
      else process.env[key] = saved[key];
    }
  });
}

async function cli(args) {
  let stdout = '', stderr = '';
  const code = await runCli(args, { stdout: { write: text => { stdout += text; } }, stderr: { write: text => { stderr += text; } } });
  return { code, stdout, stderr };
}

function eventsSince(start) {
  return messages.slice(start).map(({ message }) => JSON.parse(message.body));
}

function assertEvents(start, manifest, integration, count) {
  const events = eventsSince(start);
  assert.equal(events.length, count);
  for (const event of events) {
    assert.deepEqual(Object.keys(event).sort(), ['api_key', 'distinct_id', 'event', 'properties']);
    assert.equal(event.event, 'cookieguard_invoked');
    assert.deepEqual(event.properties, { $process_person_profile: false, $geoip_disable: true, $ip: '0.0.0.0',
      schema_version: 1, package: manifest.name, package_version: manifest.version, integration });
    assert.equal(JSON.stringify(event).includes(CANARY), false);
  }
}

async function connect(t, options = {}) {
  const mcp = createCookieGuardServer({ allowedOrigins: [target], policy: { authCookies: [CANARY] }, evidenceDir: temp, ...options });
  const client = new Client({ name: 'usage-test', version: '1.0.0' });
  const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();
  t.after(async () => { await client.close(); await mcp.close(); });
  await mcp.connect(serverTransport);
  await client.connect(clientTransport);
  return (name, args = {}) => client.callTool({ name, arguments: args });
}

before(async () => {
  temp = await mkdtemp(join(tmpdir(), 'cookieguard-usage-adapters-'));
  fixture = join(temp, `${CANARY}.json`);
  await writeFile(fixture, JSON.stringify([{ name: CANARY, value: `${CANARY}_VALUE`, secure: true, httpOnly: true, sameSite: 'Lax' }]));
  server = createServer((request, response) => {
    if (request.url === '/slow') { slowResponse = response; slowArrived?.(); return; }
    response.writeHead(200, { 'set-cookie': `${CANARY}=${CANARY}_VALUE; Path=/; Secure; HttpOnly; SameSite=Lax` });
    response.end();
  });
  await new Promise((done, reject) => server.once('error', reject).listen(0, '127.0.0.1', done));
  target = `http://127.0.0.1:${server.address().port}`;
});

afterEach(async () => { acknowledgeMessages(); await flushUsage(); transport.mode = 'success'; });
after(async () => {
  restoreWorker();
  server?.closeAllConnections();
  if (server?.listening) await new Promise(done => server.close(done));
  if (temp) await rm(temp, { recursive: true, force: true });
});

test('disabled adapters and direct scanner/core calls create no usage worker', async t => {
  configure(t, { COOKIEGUARD_POSTHOG_PROJECT_TOKEN: enabledEnv.COOKIEGUARD_POSTHOG_PROJECT_TOKEN, COOKIEGUARD_USAGE_METRICS: '0' });
  assert.equal(workers.length, 0);
  await cli(['scan', '--input', fixture]);
  await startCookieAudit(new Context(), { origins: ['https://app.test'] }).evaluate();
  const call = await connect(t);
  await call('cookieguard_audit', { url: target });
  assert.equal(workers.length, 0);
  delete process.env.COOKIEGUARD_USAGE_METRICS;
  const collected = await scanUrl(target);
  const report = evaluateCookiePolicy(collected.observations, {}, collected);
  formatJson(report); assertCookiePolicy(report);
  assert.equal(workers.length, 0);
});

test('CLI, Playwright, and MCP report accepted audits by default without an enable flag', async t => {
  configure(t, {}); // Exercise the bundled project configuration with the fake Worker.
  let start = messages.length;
  const collector = startCookieAudit(new Context(), { origins: ['https://app.test'], usageMetrics: null });
  const call = await connect(t);
  await cli(['--help']);
  await call('cookieguard_capabilities');
  assert.equal(messages.length, start, 'Construction and static commands must not report');
  assert.equal((await cli(['scan', '--input', fixture, '--auth-cookie', CANARY, '--json'])).code, 0);
  assertEvents(start, cliManifest, 'cli', 1);
  start = messages.length;
  await collector.evaluate();
  assertEvents(start, playwrightManifest, 'playwright', 1);
  start = messages.length;
  await call('cookieguard_audit', { url: target });
  assertEvents(start, mcpManifest, 'mcp', 1);
});

test('CLI counts accepted URL and input scans once and ignores static/invalid commands', async t => {
  configure(t);
  const start = messages.length;
  for (const args of [['--help'], ['--version'], ['capabilities', '--json'], ['explain', 'CG001'],
    ['scan'], ['scan', target, '--timeout-ms', '0'], ['scan', 'https://not-authorized.invalid'],
    ['scan', '--input', fixture, '--allow-origin', target]]) await cli(args);
  assert.equal(messages.length, start);
  assert.equal((await cli(['scan', `${target}/${CANARY}`, '--auth-cookie', CANARY, '--json'])).code, 0);
  assert.equal((await cli(['scan', '--input', fixture, '--auth-cookie', CANARY, '--json'])).code, 0);
  assertEvents(start, cliManifest, 'cli', 2);
});

test('CLI counts one admitted gate, preserves missing-evidence failure, and ignores invalid gates', async t => {
  configure(t);
  const start = messages.length;
  for (const args of [
    ['gate'],
    ['gate', '--evidence', temp, '--require', CANARY],
    ['gate', '--evidence', temp, '--require', CANARY, '--auth-cookie', CANARY, '--run-id', 'invalid id'],
    ['gate', '--evidence', temp, '--require', CANARY, '--auth-cookie', CANARY, '--timeout-ms', '100'],
  ]) assert.equal((await cli(args)).code, 2);
  assert.equal(messages.length, start);
  const result = await cli(['gate', '--evidence', temp, '--require', CANARY, '--require', 'another test', '--auth-cookie', CANARY, '--json']);
  assert.equal(result.code, 2);
  assert.equal(JSON.parse(result.stdout).status, 'incomplete');
  assertEvents(start, cliManifest, 'cli', 1);
});

test('CLI returns its normal result within a bounded delivery wait', async t => {
  configure(t);
  transport.mode = 'stall';
  const started = Date.now();
  assert.equal((await cli(['scan', '--input', fixture, '--auth-cookie', CANARY, '--json'])).code, 0);
  assert.ok(Date.now() - started < 1500, 'Pending reporting exceeded the bounded CLI flush budget');
});

test('Playwright counts first collection once across concurrent calls and auditPage delegation', async t => {
  configure(t);
  const start = messages.length;
  const options = { origins: ['https://app.test'], usageMetrics: true };
  const collector = startCookieAudit(new Context(), options);
  assert.equal(messages.length, start);
  options.usageMetrics = false; // The trusted reporting choice is captured at construction.
  await Promise.all([collector.collect(), collector.collect(), collector.evaluate(), collector.evaluate()]);
  collector.dispose();
  assertEvents(start, playwrightManifest, 'playwright', 1);
  await auditPage({ url: () => `https://app.test/${CANARY}`, context: () => new Context() });
  assertEvents(start, playwrightManifest, 'playwright', 2);
});

test('Playwright gate fixture reports once and forwards the trusted opt-out', async t => {
  configure(t);
  const start = messages.length;
  for (const usageMetrics of [true, false]) {
    const { cookieGuard } = cookieGuardFixtures({ origins: ['https://app.test'], evidenceDir: temp, enforce: false, usageMetrics });
    await cookieGuard({ context: new Context() }, async check => {
      await Promise.all([check.evaluate(), check.evaluate()]);
    }, { title: CANARY });
  }
  assertEvents(start, playwrightManifest, 'playwright', 1);
});

test('Playwright trusted usage settings respect all opt-outs and reject invalid values', async t => {
  configure(t);
  const start = messages.length;
  await startCookieAudit(new Context(), { origins: ['https://app.test'], usageMetrics: false }).evaluate();
  process.env.COOKIEGUARD_USAGE_METRICS = '0';
  await startCookieAudit(new Context(), { origins: ['https://app.test'], usageMetrics: true }).evaluate();
  process.env.COOKIEGUARD_USAGE_METRICS = '1'; process.env.DO_NOT_TRACK = '1';
  await startCookieAudit(new Context(), { origins: ['https://app.test'], usageMetrics: true }).evaluate();
  assert.equal(messages.length, start);
  for (const value of ['true', 1, {}]) assert.throws(() => startCookieAudit(new Context(), { origins: ['https://app.test'], usageMetrics: value }), { code: 'CONFIG' });
  delete process.env.DO_NOT_TRACK;
  await startCookieAudit(new Context(), { origins: ['https://app.test'], usageMetrics: null }).evaluate();
  assertEvents(start, playwrightManifest, 'playwright', 1);
  delete process.env.COOKIEGUARD_USAGE_METRICS;
  await startCookieAudit(new Context(), { origins: ['https://app.test'], usageMetrics: true }).evaluate();
  assertEvents(start, playwrightManifest, 'playwright', 2);
});

test('MCP counts admitted audits and aliases once; discovery and BUSY rejection do not count', async t => {
  configure(t);
  const start = messages.length;
  const call = await connect(t);
  for (const name of ['cookieguard_capabilities', 'cookieguard_policy']) await call(name);
  await call('cookieguard_explain', { id: 'CG001' });
  await call('cookieguard_audit', {});
  await call('cookieguard_audit', { url: target, evidenceFile: 'report.json' });
  await call('cookieguard_audit', { url: target, usageMetrics: true });
  assert.equal(messages.length, start);
  transport.mode = 'stall';
  const arrived = new Promise(done => { slowArrived = done; });
  const slow = call('cookieguard_audit', { url: `${target}/slow` });
  await arrived;
  assert.equal((await call('cookieguard_scan', { url: target })).structuredContent.error.code, 'BUSY');
  assertEvents(start, mcpManifest, 'mcp', 1);
  slowResponse.writeHead(200); slowResponse.end();
  await slow;
  // Delivery is still pending, but the next audit must be admitted immediately.
  assert.equal((await call('cookieguard_scan', { url: target })).structuredContent.status, 'passed');
  const report = evaluateCookiePolicy([], {}, { mode: 'fixture', complete: true });
  await writeFile(join(temp, 'evidence.json'), formatJson(report));
  await call('cookieguard_audit', { evidenceFile: 'evidence.json' });
  assertEvents(start, mcpManifest, 'mcp', 3);
});

test('MCP trusted reporting configuration is validated and cannot override opt-outs', async t => {
  configure(t);
  const start = messages.length;
  const call = await connect(t, { usageMetrics: false });
  await call('cookieguard_audit', { url: target });
  assert.equal(messages.length, start);
  for (const value of ['true', 1, {}]) assert.throws(() => createCookieGuardServer({ allowedOrigins: [target], usageMetrics: value }), { code: 'CONFIG' });
  process.env.DO_NOT_TRACK = '1';
  const disabled = await connect(t, { usageMetrics: true });
  await disabled('cookieguard_audit', { url: target });
  assert.equal(messages.length, start);
  delete process.env.DO_NOT_TRACK;
  delete process.env.COOKIEGUARD_USAGE_METRICS;
  const enabled = await connect(t, { usageMetrics: true });
  await enabled('cookieguard_audit', { url: target });
  assertEvents(start, mcpManifest, 'mcp', 1);
});

test('delivery errors do not alter CLI, Playwright, or MCP audit results', async t => {
  configure(t);
  const expected = await cli(['scan', '--input', fixture, '--auth-cookie', CANARY, '--json']);
  const expectedBrowser = await startCookieAudit(new Context(), { origins: ['https://app.test'] }).evaluate();
  const call = await connect(t);
  const expectedMcp = await call('cookieguard_audit', { url: target });
  transport.mode = 'throw';
  assert.deepEqual(await cli(['scan', '--input', fixture, '--auth-cookie', CANARY, '--json']), expected);
  assert.deepEqual(await startCookieAudit(new Context(), { origins: ['https://app.test'] }).evaluate(), expectedBrowser);
  assert.deepEqual(await call('cookieguard_audit', { url: target }), expectedMcp);
});

test('GitHub Action emits only its own event and preserves results when delivery fails', async t => {
  configure(t);
  for (const [mode, enabled, fail, expectedCount] of [['default', undefined, false, 1], ['disabled', '0', false, 0], ['enabled', '1', false, 1], ['failure', undefined, true, 1]]) {
    const output = join(temp, `${mode}-output`), summary = join(temp, `${mode}-summary`), captured = join(temp, `${mode}-events`);
    await writeFile(captured, '');
    const env = { ...process.env, ...enabledEnv, RUNNER_TEMP: temp, GITHUB_OUTPUT: output, GITHUB_STEP_SUMMARY: summary,
      CG_TARGET: `${target}/${CANARY}`, CG_AUTH_COOKIES: CANARY, CG_TEST_USAGE_CAPTURE: captured, CG_TEST_USAGE_FAILURE: fail ? '1' : '0' };
    if (enabled === undefined) delete env.COOKIEGUARD_USAGE_METRICS;
    else env.COOKIEGUARD_USAGE_METRICS = enabled;
    const result = await exec(process.execPath, ['--import', resolve('tests/fixtures/usage-worker.mjs'), 'action/run.js'], { env, timeout: 5000 });
    assert.equal(result.stderr, '');
    assert.match(await readFile(output, 'utf8'), /exit-code=0\n/);
    const events = (await readFile(captured, 'utf8')).trim().split('\n').filter(Boolean).map(line => JSON.parse(line));
    assert.equal(events.length, expectedCount);
    for (const event of events) {
      assert.equal(event.properties.package, cliManifest.name);
      assert.equal(event.properties.package_version, cliManifest.version);
      assert.equal(event.properties.integration, 'github-action');
      assert.equal(JSON.stringify(event).includes(CANARY), false);
    }
  }
});
