import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, mkdir, writeFile, rm, symlink, readFile } from 'node:fs/promises';
import { join, resolve } from 'node:path';
import { tmpdir } from 'node:os';
import { Client } from '@modelcontextprotocol/client';
import { StdioClientTransport } from '@modelcontextprotocol/client/stdio';
import { runCli } from 'cookieguard-ci';
import { EXPLAIN_IDS } from '@aiscihub/cookieguard-core';
import { createDemoServer, DEMO_VALUE } from '../examples/demo/server.js';
import { mcpAuditResultSchema, mcpCapabilitiesSchema, mcpExplainResultSchema } from '../packages/mcp/src/schemas.js';

const bin = resolve('packages/mcp/bin/cookieguard-mcp.js');
const quiet = { stdout: { write() {} }, stderr: { write() {} } };
let demo, other, target, otherTarget, temp, evidenceDir;
before(async () => {
  temp = await mkdtemp(join(tmpdir(), 'cookieguard-mcp-tools-'));
  evidenceDir = join(temp, 'evidence');
  await mkdir(evidenceDir);
  demo = createDemoServer();
  other = createDemoServer();
  for (const server of [demo, other]) await new Promise((done, reject) => server.once('error', reject).listen(0, '127.0.0.1', done));
  target = `http://127.0.0.1:${demo.address().port}`;
  otherTarget = `http://127.0.0.1:${other.address().port}`;
  // The developer's own runs write sanitized reports into the evidence directory.
  for (const [name, path] of [['secure', 'secure'], ['insecure', 'missing-httponly'], ['no-session', 'preference']]) {
    await runCli(['scan', `${target}/${path}`, '--auth-cookie', 'session_id', '--json', '--output', join(evidenceDir, `${name}.json`)], quiet);
  }
  await runCli(['scan', `${otherTarget}/secure`, '--auth-cookie', 'session_id', '--json', '--output', join(evidenceDir, 'other-origin.json')], quiet);
});
after(async () => {
  for (const server of [demo, other]) {
    server?.closeAllConnections();
    if (server?.listening) await new Promise(done => server.close(done));
  }
  if (temp) await rm(temp, { recursive: true, force: true });
});

function clean(value) {
  assert.equal(JSON.stringify(value).includes(DEMO_VALUE), false, 'Private canary reached MCP output');
}

async function connect(t, config) {
  const path = join(temp, `config-${Math.random()}.json`);
  await writeFile(path, JSON.stringify({ allowedOrigins: [target], policy: { authCookies: ['session_id'] }, timeoutMs: 1000, ...config }));
  const transport = new StdioClientTransport({ command: process.execPath, args: [bin, '--config', path], stderr: 'pipe' });
  let stderr = '';
  transport.stderr.on('data', data => { stderr += data; });
  const client = new Client({ name: 'cookieguard-tools-test', version: '1.0.0' }, { versionNegotiation: { mode: { pin: '2026-07-28' } } });
  t.after(async () => { await client.close(); clean(stderr); assert.equal(stderr, ''); });
  await client.connect(transport);
  const call = async (name, args = {}) => {
    const response = await client.callTool({ name, arguments: args });
    clean(response);
    if (response.structuredContent) assert.deepEqual(JSON.parse(response.content[0].text), response.structuredContent);
    return response;
  };
  return { client, call };
}

test('an MCP client can discover capabilities, audit a URL, and explain a finding', async t => {
  const { client, call } = await connect(t);
  const { tools } = await client.listTools();
  const audit = tools.find(tool => tool.name === 'cookieguard_audit');
  assert.equal(audit.inputSchema.additionalProperties, false);
  assert.deepEqual(audit.inputSchema.required ?? [], []);
  assert.equal(tools.find(tool => tool.name === 'cookieguard_capabilities').annotations.readOnlyHint, true);

  const capabilities = mcpCapabilitiesSchema.parse((await call('cookieguard_capabilities')).structuredContent);
  assert.deepEqual(capabilities.configuration.allowedOrigins, [target]);
  assert.equal(capabilities.configuration.evidenceFiles, false);
  assert.ok(capabilities.checks.some(check => check.ruleId === 'CG001' && check.severity === 'high'));
  assert.ok(capabilities.integrations.some(i => i.package === 'cookieguard-browser-use'));

  for (const [path, status, code] of [['secure', 'passed', 0], ['missing-httponly', 'failed', 1], ['preference', 'incomplete', 2]]) {
    const response = await call('cookieguard_audit', { url: `${target}/${path}` });
    assert.equal(response.isError, false);
    const result = mcpAuditResultSchema.parse(response.structuredContent);
    assert.equal(result.status, status);
    assert.equal(result.exitCode, code);
    assert.deepEqual(result.provenance, { source: 'http-scan', producer: 'cookieguard-http-scan', observedByServer: true });
    if (code === 1) {
      const finding = result.findings.find(f => f.ruleId === 'CG001');
      assert.deepEqual([finding.status, finding.cookieName, finding.evidenceSource, finding.identityBasis],
        ['confirmed', 'session_id', 'header', 'developer-name']);
      const explained = mcpExplainResultSchema.parse((await call('cookieguard_explain', { id: finding.ruleId })).structuredContent);
      assert.equal(explained.explanation.title, 'Missing HttpOnly');
      assert.match(explained.explanation.fix, /HttpOnly/);
    }
    if (code === 2) {
      const reason = (await call('cookieguard_explain', { id: result.issues[0] })).structuredContent.explanation;
      assert.equal(reason.kind, 'issue');
    }
  }
  // The legacy scan tool now carries the same provenance and evidence fields.
  const legacy = mcpAuditResultSchema.parse((await call('cookieguard_scan', { url: `${target}/missing-httponly` })).structuredContent);
  assert.equal(legacy.findings.find(f => f.ruleId === 'CG001').evidenceSource, 'header');
});

test('audit and explain reject ambiguous, disabled, unknown, and injected arguments without reflecting them', async t => {
  const { call } = await connect(t);
  for (const args of [{}, { url: `${target}/secure`, evidenceFile: 'secure.json' }]) {
    const response = await call('cookieguard_audit', args);
    assert.equal(response.isError, true);
    assert.equal(response.structuredContent.error.code, 'CONFIG');
    assert.equal(response.structuredContent.exitCode, 2);
  }
  const disabled = await call('cookieguard_audit', { evidenceFile: 'secure.json' });
  assert.equal(disabled.structuredContent.error.code, 'EVIDENCE');
  for (const args of [{ url: `${target}/secure`, policy: { failOn: 'critical' } }, { evidenceDir: '/' }, { url: { [DEMO_VALUE]: 1 } }]) {
    assert.equal((await call('cookieguard_audit', args)).isError, true);
  }
  const unknown = await call('cookieguard_explain', { id: DEMO_VALUE });
  assert.equal(unknown.isError, true);
  assert.equal(unknown.structuredContent.error.code, 'UNKNOWN_ID');
  assert.deepEqual(unknown.structuredContent.knownIds, [...EXPLAIN_IDS]);
  for (const id of ['../CG001', 'CG001; rm', '', 'x'.repeat(65)]) assert.equal((await call('cookieguard_explain', { id })).isError, true);
  assert.equal((await call('cookieguard_capabilities', { verbose: true })).isError, true);
});

test('evidence files written by developer runs are audited under the server policy, inside the evidence directory only', async t => {
  await writeFile(join(evidenceDir, 'malformed.json'), '{not json');
  await writeFile(join(evidenceDir, 'forged.json'), JSON.stringify({ schemaVersion: 1, mode: 'http', target, issues: [],
    cookies: [{ observation: { schemaVersion: 1, name: 'session_id', value: DEMO_VALUE, domain: '127.0.0.1', path: '/', secure: true, httpOnly: false,
      hostOnly: true, sameSite: { declared: 'lax', effective: null }, expiresAt: null, lifetimeSeconds: null, deleted: false, source: 'header',
      origin: target, confidence: 'observed', header: { prefixValid: null, scheme: 'http', warnings: [], raw: DEMO_VALUE }, storeStatus: 'unverified',
      triage: { mode: 'rule', label: 'authentication', score: 0.9, origin: 'extension-rule-heuristic' }, note: DEMO_VALUE } }] }));
  await writeFile(join(evidenceDir, 'huge.json'), ' '.repeat(1024 * 1024 + 1));
  await writeFile(join(temp, 'outside.json'), await readFile(join(evidenceDir, 'insecure.json')));
  await symlink(join(temp, 'outside.json'), join(evidenceDir, 'link.json'));
  const browserUse = JSON.parse(await readFile(join(evidenceDir, 'secure.json'), 'utf8'));
  await writeFile(join(evidenceDir, 'provisional.json'), JSON.stringify({ schemaVersion: 1, integration: 'cookieguard-browser-use',
    provisional: true, report: browserUse }));

  const { call } = await connect(t, { evidenceDir });
  const audit = async evidenceFile => (await call('cookieguard_audit', { evidenceFile })).structuredContent;
  for (const [file, status, code] of [['secure.json', 'passed', 0], ['insecure.json', 'failed', 1], ['no-session.json', 'incomplete', 2],
    ['forged.json', 'failed', 1], ['provisional.json', 'incomplete', 2]]) {
    const result = mcpAuditResultSchema.parse(await audit(file));
    assert.equal(result.status, status, file);
    assert.equal(result.exitCode, code, file);
    assert.equal(result.provenance.source, 'evidence-file');
    assert.equal(result.provenance.observedByServer, false);
    assert.ok(result.limitations[0].startsWith('Supplied evidence'));
  }
  assert.equal((await audit('provisional.json')).provenance.producer, 'cookieguard-browser-use');
  for (const [file, code] of [['malformed.json', 'INPUT'], ['huge.json', 'INPUT'], ['other-origin.json', 'TARGET'],
    ['link.json', 'EVIDENCE'], ['missing.json', 'EVIDENCE'], ['../outside.json', 'EVIDENCE'], ['evidence/secure.json', 'EVIDENCE'],
    ['.hidden.json', 'EVIDENCE'], ['secure.txt', 'EVIDENCE'], [`${DEMO_VALUE}.json`, 'EVIDENCE']]) {
    const result = await audit(file);
    assert.equal(result.status, 'incomplete', file);
    assert.equal(result.error.code, code, file);
  }
});

test('evidenceDir must be an existing absolute directory at startup', async () => {
  const { createCookieGuardServer } = await import('@aiscihub/cookieguard-mcp');
  for (const directory of ['relative', join(temp, 'missing'), join(evidenceDir, 'secure.json'), 7]) {
    assert.throws(() => createCookieGuardServer({ allowedOrigins: [target], evidenceDir: directory }), { code: 'CONFIG' });
  }
  assert.ok(createCookieGuardServer({ allowedOrigins: [target], evidenceDir }));
});
