import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, writeFile, rm } from 'node:fs/promises';
import { join, resolve } from 'node:path';
import { tmpdir } from 'node:os';
import { chromium } from 'playwright-core';
import { Client } from '@modelcontextprotocol/client';
import { StdioClientTransport } from '@modelcontextprotocol/client/stdio';
import { startCookieAudit } from '@aiscihub/cookieguard-playwright';
import { evaluateCookiePolicy, formatJson, exitCode, readEvidence, summarizeSession, classifyStorageEntry,
  storageObservation, safeStorageKey } from '@aiscihub/cookieguard-core';
import { reportSchema, mcpAuditResultSchema } from '../packages/mcp/src/schemas.js';
import { createSessionApp, SID_PREFIX, STORAGE_TOKEN } from './fixtures/session-app.js';

let browser;
before(async () => { browser = await chromium.launch(); });
after(async () => { await browser?.close(); });

async function runLogin(appOptions, auditOptions = {}, { logout = true } = {}) {
  const server = createSessionApp(appOptions);
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const origin = `http://127.0.0.1:${server.address().port}`;
  const context = await browser.newContext();
  try {
    const audit = startCookieAudit(context, { origins: [origin],
      policy: { authCookies: ['sid'], authStorageKeys: ['access_token'], ...auditOptions.policy },
      sessionProbe: { url: `${origin}/account`, requireLogout: logout, ...auditOptions.sessionProbe },
      ...(auditOptions.storage === undefined ? {} : { storage: auditOptions.storage }) });
    const page = await context.newPage();
    await page.goto(`${origin}/login`);
    await page.fill('#username', 'alice');
    await page.fill('#password', 'pw');
    await Promise.all([page.waitForURL('**/account'), page.click('button[type=submit]')]);
    if (logout) await Promise.all([page.waitForURL('**/login'), page.click('#logout')]);
    const report = await audit.evaluate();
    return { report, origin, json: formatJson(report) };
  } finally {
    await context.close();
    server.close();
  }
}

// The new rules, plus any confirmed finding. CG009 review items about repeated
// Set-Cookie instructions are expected here and never fail a run.
const ruleIds = report => report.findings.filter(f => ['CG010', 'CG011', 'CG012'].includes(f.ruleId) || f.status === 'confirmed')
  .map(f => `${f.ruleId}:${f.status}`).sort();

test('a correct login rotates the session, logout revokes it, and the audit passes', async () => {
  const { report, json } = await runLogin({});
  reportSchema.parse(JSON.parse(json));
  assert.equal(report.status, 'passed', JSON.stringify(report.issues));
  assert.deepEqual(report.session.cookies.map(c => [c.name, c.rotation, c.logout]), [['sid', 'rotated', 'revoked']]);
  assert.equal(report.session.probe.status, 'ok');
  assert.deepEqual(ruleIds(report), []);
  assert.equal(json.includes(SID_PREFIX), false);
});

test('a session id that survives login is CG010 and fails the run', async () => {
  const { report, json } = await runLogin({ rotate: false });
  assert.equal(exitCode(report), 1);
  assert.deepEqual(ruleIds(report), ['CG010:confirmed']);
  const finding = report.findings[0];
  assert.equal(finding.evidence.source, 'probe');
  assert.deepEqual(finding.evidence.changes, ['unauthenticated-before-login', 'authenticated-after-login']);
  assert.equal(json.includes(SID_PREFIX), false);
});

test('a session that stays valid after logout is CG011', async () => {
  const { report, json } = await runLogin({ revoke: false });
  assert.equal(exitCode(report), 1);
  assert.deepEqual(ruleIds(report), ['CG011:confirmed']);
  assert.equal(report.session.cookies[0].logout, 'still-valid');
  assert.equal(json.includes(SID_PREFIX), false);
});

test('a token in localStorage is CG012: confirmed for a configured key, review otherwise; the value never appears', async () => {
  const configured = await runLogin({ storageToken: true });
  assert.deepEqual(ruleIds(configured.report), ['CG012:confirmed']);
  assert.deepEqual(configured.report.storage.map(s => [s.area, s.key, s.token, s.configured]), [['local', 'access_token', 'jwt', true]]);
  const unconfigured = await runLogin({ storageToken: true }, { policy: { authStorageKeys: [] } });
  assert.deepEqual(ruleIds(unconfigured.report), ['CG012:review']);
  assert.equal(unconfigured.report.status, 'passed');
  for (const { json } of [configured, unconfigured]) {
    assert.equal(json.includes(STORAGE_TOKEN), false);
    assert.equal(json.includes('SENTINEL_JWT'), false);
  }
  const off = await runLogin({ storageToken: true }, { storage: false });
  assert.deepEqual(off.report.storage, []);
});

test('requireLogout makes a workflow without logout incomplete; without it, logout is not-observed', async () => {
  const required = await runLogin({}, { sessionProbe: { requireLogout: true } }, { logout: false });
  assert.equal(required.report.status, 'incomplete');
  assert.ok(required.report.issues.includes('logout-not-observed'));
  const optional = await runLogin({}, { sessionProbe: { requireLogout: false } }, { logout: false });
  assert.equal(optional.report.status, 'passed', JSON.stringify(optional.report.issues));
  assert.equal(optional.report.session.cookies[0].logout, 'not-observed');
});

test('session summaries: unprotected URLs, probe errors, POST-issued races, and replay outcomes', () => {
  const cookie = { name: 'sid', domain: '127.0.0.1', path: '/', origin: 'http://127.0.0.1:3000' };
  const anon = { status: 303, location: '/login' }, auth = { status: 200, location: null };
  const at = (events, anonymous = anon) => summarizeSession({ url: 'http://127.0.0.1:3000/account', anonymous, events });
  const issued = (id, method) => ({ type: 'issued', cookie, valueId: id, method });
  const probe = (id, result, phase = 'navigation') => ({ type: 'probe', phase, values: [{ cookie, valueId: id }], result });
  assert.equal(at([issued('v1', 'GET'), probe('v1', auth)], auth).probe.reason, 'unprotected-url');
  assert.equal(at([issued('v1', 'GET'), probe('v1', { error: true })]).probe.reason, 'probe-error');
  // A value issued by the login POST is never treated as fixation, even if first seen unauthenticated.
  assert.equal(at([issued('v1', 'POST'), probe('v1', anon), probe('v1', auth)]).cookies[0].rotation, 'inconclusive');
  assert.equal(at([issued('v1', 'GET'), probe('v1', anon), probe('v1', auth)]).cookies[0].rotation, 'not-rotated');
  const logout = result => at([issued('v1', 'POST'), probe('v1', auth), { type: 'deleted', cookie, valueId: 'v1' }, probe('v1', result, 'replay')]).cookies[0].logout;
  assert.equal(logout(auth), 'still-valid');
  assert.equal(logout(anon), 'revoked');
  assert.equal(logout({ status: 500, location: null }), 'inconclusive');
  // An inconclusive summary is INCOMPLETE for a configured cookie.
  const summary = at([issued('v1', 'GET'), probe('v1', anon)]);
  const report = evaluateCookiePolicy([], { authCookies: ['sid'] }, { mode: 'browser', session: summary });
  assert.equal(report.status, 'incomplete');
  assert.ok(report.issues.includes('session-check-inconclusive'));
});

test('storage classification finds tokens, ignores ordinary values, and redacts identifiers in keys', () => {
  assert.equal(classifyStorageEntry('anything', STORAGE_TOKEN), 'jwt');
  assert.equal(classifyStorageEntry('auth', JSON.stringify({ user: { accessToken: 'a1b2c3d4e5f6g7h8i9j0' } })), 'token-in-json');
  assert.equal(classifyStorageEntry('accessToken', 'a1b2c3d4e5f6g7h8i9j0k1'), 'token-key');
  for (const [key, value] of [['theme', 'dark'], ['lastVisited', '2026-11-07'], ['session_count', '3'], ['tokenSeen', 'true'],
    ['csrf', JSON.stringify({ csrf: 'abc' })], ['cart', '[1,2,3]']]) assert.equal(classifyStorageEntry(key, value), null, key);
  assert.equal(safeStorageKey('CognitoIdentityServiceProvider.4abcdefghij1234567890klm.alice.idToken'),
    'CognitoIdentityServiceProvider.[redacted].alice.idToken');
  const observation = storageObservation({ origin: 'http://127.0.0.1:3000', area: 'session', key: `token-${STORAGE_TOKEN}`, value: STORAGE_TOKEN });
  assert.equal(JSON.stringify(observation).includes(STORAGE_TOKEN), false);
});

test('evidence files carry session and storage results and re-evaluate under a new policy', async () => {
  const { report, json } = await runLogin({ revoke: false, storageToken: true });
  assert.deepEqual(ruleIds(report), ['CG011:confirmed', 'CG012:confirmed']);
  const evidence = readEvidence(JSON.parse(json));
  assert.equal(evidence.session.cookies[0].logout, 'still-valid');
  assert.equal(evidence.storage.length, 1);
  // Without configured names the same evidence becomes review items and cannot fail.
  const again = evaluateCookiePolicy(evidence.observations, {}, evidence);
  assert.deepEqual(ruleIds(again), ['CG011:review', 'CG012:review']);
  assert.equal(exitCode(again), 0);
});

test('the MCP server re-evaluates session and storage evidence and names a storage key only when configured', async t => {
  const { report, origin, json } = await runLogin({ revoke: false, storageToken: true });
  assert.deepEqual(ruleIds(report), ['CG011:confirmed', 'CG012:confirmed']);
  const temp = await mkdtemp(join(tmpdir(), 'cookieguard-session-mcp-'));
  t.after(() => rm(temp, { recursive: true, force: true }));
  await writeFile(join(temp, 'login.json'), json);
  for (const [authStorageKeys, expectedName, status] of [[['access_token'], 'access_token', 'failed'], [[], null, 'failed']]) {
    const config = join(temp, `config-${authStorageKeys.length}.json`);
    await writeFile(config, JSON.stringify({ allowedOrigins: [origin], policy: { authCookies: ['sid'], authStorageKeys }, evidenceDir: temp }));
    const client = new Client({ name: 'cookieguard-session-test', version: '1.0.0' }, { versionNegotiation: { mode: { pin: '2026-07-28' } } });
    await client.connect(new StdioClientTransport({ command: process.execPath, args: [resolve('packages/mcp/bin/cookieguard-mcp.js'), '--config', config] }));
    try {
      const response = await client.callTool({ name: 'cookieguard_audit', arguments: { evidenceFile: 'login.json' } });
      const result = mcpAuditResultSchema.parse(response.structuredContent);
      assert.equal(result.status, status);
      const storageFinding = result.findings.find(f => f.ruleId === 'CG012');
      assert.equal(storageFinding.cookieName, expectedName);
      assert.equal(storageFinding.evidenceSource, 'storage');
      assert.equal(storageFinding.status, authStorageKeys.length ? 'confirmed' : 'review');
      assert.equal(result.findings.find(f => f.ruleId === 'CG011').status, 'confirmed');
      const text = JSON.stringify(response);
      assert.equal(text.includes(SID_PREFIX) || text.includes(STORAGE_TOKEN), false);
    } finally { await client.close(); }
  }
});
