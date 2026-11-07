import { test } from 'node:test';
import assert from 'node:assert/strict';
import { EventEmitter } from 'node:events';
import { mkdtemp, readFile, readdir, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { cookieGuardFixtures, checkId, startCookieAudit } from '@aiscihub/cookieguard-playwright';
import { exitCode } from '@aiscihub/cookieguard-core';
import { runCli } from 'cookieguard-ci';

const TOKEN = 'SENTINEL_GATE_VALUE_NEVER_SERIALIZE_7c41e2';
class Context extends EventEmitter {
  constructor(cookies = []) { super(); this.store = cookies; }
  async cookies() { return this.store; }
}
const origin = 'https://app.test';
const response = (header, url = `${origin}/login`) => ({ url: () => url, headersArray: async () => [].concat(header).map(value => ({ name: 'Set-Cookie', value })) });
const storeCookie = (overrides = {}) => ({ name: 'sid', value: TOKEN, domain: 'app.test', path: '/', secure: true, httpOnly: true, sameSite: 'Lax', expires: -1, ...overrides });

async function runFixture(dir, options, body, title = 'Sign in and out') {
  const { cookieGuard } = cookieGuardFixtures({ origins: [origin], evidenceDir: dir, ...options });
  const context = new Context();
  let error = null;
  try { await cookieGuard({ context }, async check => body(context, check), { title }); } catch (e) { error = e; }
  return { error, files: await readdir(dir).catch(() => []) };
}

async function gate(args) {
  let out = '', err = '';
  const code = await runCli(['gate', ...args], { stdout: { write: s => { out += s; } }, stderr: { write: s => { err += s; } } });
  return { code, out, err };
}

test('the fixture writes value-free evidence and fails the test with only blocking findings', async () => {
  const dir = await mkdtemp(join(tmpdir(), 'cg-gate-'));
  try {
    const { error, files } = await runFixture(dir, { policy: { authCookies: ['sid'] } }, async context => {
      context.store = [storeCookie({ httpOnly: false })];
      context.emit('response', response([`sid=${TOKEN}; Path=/; Secure; SameSite=Lax`, `csrf=${TOKEN}; Path=/; Secure; SameSite=Strict`]));
    });
    assert.deepEqual(files, ['sign-in-and-out.json']);
    assert.equal(error.name, 'CookiePolicyError');
    assert.equal(error.exitCode, 1);
    assert.match(error.message, /CookieGuard FAIL for "sign-in-and-out"/);
    assert.match(error.message, /HIGH CG001 "sid": Missing HttpOnly/);
    assert.doesNotMatch(error.message, /"csrf"/, 'review items are counted, not listed');
    assert.match(error.message, /review items? not shown/);
    const evidence = await readFile(join(dir, files[0]), 'utf8');
    assert.equal(evidence.includes(TOKEN), false);
    assert.equal(error.message.includes(TOKEN), false);
    assert.equal(JSON.parse(evidence).status, 'failed');
  } finally { await rm(dir, { recursive: true, force: true }); }
});

test('the fixture passes a secure login and reports a test that never logged in as INCOMPLETE', async () => {
  const dir = await mkdtemp(join(tmpdir(), 'cg-gate-'));
  try {
    const pass = await runFixture(dir, { policy: { authCookies: ['sid'] } }, async context => {
      context.store = [storeCookie()];
      context.emit('response', response(`sid=${TOKEN}; Path=/; Secure; HttpOnly; SameSite=Lax`));
    }, 'secure');
    assert.equal(pass.error, null);
    const none = await runFixture(dir, { policy: { authCookies: ['sid'] } }, async () => {}, 'no login');
    assert.equal(none.error.exitCode, 2);
    assert.match(none.error.message, /CookieGuard INCOMPLETE/);
    assert.match(none.error.message, /expected-auth-cookie-not-observed/);
    const relaxed = await runFixture(dir, { policy: { authCookies: ['sid'] }, enforce: false }, async () => {}, 'not enforced');
    assert.equal(relaxed.error, null, 'enforce: false leaves the verdict to the gate');
    assert.deepEqual((await readdir(dir)).sort(), ['no-login.json', 'not-enforced.json', 'secure.json']);
  } finally { await rm(dir, { recursive: true, force: true }); }
});

test('a configured cookie set by page script and gone before evaluation is still judged', async () => {
  const context = new Context([storeCookie({ name: 'api_token', httpOnly: false })]);
  const audit = startCookieAudit(context, { origins: [origin], policy: { authCookies: ['api_token'] } });
  context.emit('response', response('theme=light; Path=/; SameSite=Lax', `${origin}/api/notes`));
  await new Promise(resolve => setTimeout(resolve, 10));
  context.store = []; // logout cleared it
  const report = await audit.evaluate();
  assert.deepEqual(report.issues, []);
  assert.ok(report.findings.some(f => f.ruleId === 'CG001' && f.cookie.name === 'api_token' && f.status === 'confirmed'));
  assert.equal(JSON.stringify(report).includes(TOKEN), false);
});

test('Set-Cookie lines without a cookie name are skipped without losing the rest of the evidence', async () => {
  const context = new Context([storeCookie(), storeCookie({ name: '', value: `sid_backup${TOKEN}` })]);
  const audit = startCookieAudit(context, { origins: [origin], policy: { authCookies: ['sid'] } });
  context.emit('response', response([`=${TOKEN}; Secure`, `sid_backup${TOKEN}`, `sid=${TOKEN}; Path=/; Secure; HttpOnly; SameSite=Lax`]));
  const report = await audit.evaluate();
  assert.equal(exitCode(report), 0);
  assert.equal(JSON.stringify(report).includes(TOKEN), false);
});

test('the gate requires fresh evidence and decides with its own policy', async () => {
  const dir = await mkdtemp(join(tmpdir(), 'cg-gate-'));
  try {
    process.env.COOKIEGUARD_RUN_ID = 'run-1';
    // The workspace test was weakened: it no longer names sid as an authentication cookie.
    const weakened = await runFixture(dir, { policy: {} }, async context => {
      context.store = [storeCookie({ httpOnly: false })];
      context.emit('response', response(`sid=${TOKEN}; Path=/; Secure; SameSite=Lax`));
    }, 'weakened');
    assert.equal(weakened.error, null);
    const failed = await gate(['--evidence', dir, '--require', 'weakened', '--auth-cookie', 'sid', '--run-id', 'run-1']);
    assert.equal(failed.code, 1);
    assert.match(failed.out, /\[FAIL\] weakened/);
    assert.match(failed.out, /CG001 — "sid": Missing HttpOnly/);
    const missing = await gate(['--evidence', dir, '--require', 'Sign in and out', '--auth-cookie', 'sid']);
    assert.equal(missing.code, 2);
    assert.match(missing.out, /evidence-missing — no evidence file/);
    const stale = await gate(['--evidence', dir, '--require', 'weakened', '--auth-cookie', 'sid', '--run-id', 'run-2']);
    assert.equal(stale.code, 2);
    assert.match(stale.out, /evidence-stale/);
    const session = await gate(['--evidence', dir, '--require', 'weakened', '--auth-cookie', 'sid', '--require-logout', '--json']);
    const json = JSON.parse(session.out);
    assert.equal(json.status, 'failed', 'a confirmed violation is FAIL even when other evidence is missing');
    assert.deepEqual(json.checks[0].issues, ['session-check-not-run']);
    await writeFile(join(dir, 'forged.json'), JSON.stringify({ schemaVersion: 1, integration: 'cookieguard-playwright-check', check: 'other', report: {} }));
    assert.match((await gate(['--evidence', dir, '--require', 'forged', '--auth-cookie', 'sid'])).out, /evidence-invalid/);
    for (const result of [failed, missing, stale, session]) assert.equal(result.out.includes(TOKEN), false);
  } finally { delete process.env.COOKIEGUARD_RUN_ID; await rm(dir, { recursive: true, force: true }); }
});

test('gate arguments are validated', async () => {
  assert.equal((await gate(['--evidence', '.'])).code, 2);
  assert.equal((await gate(['--evidence', '.', '--require', 'x'])).code, 2, 'an authentication cookie name is required');
  assert.equal((await gate(['--evidence', '.', '--require', 'x', '--auth-cookie', 'sid', '--run-id', 'bad id'])).code, 2);
  assert.equal(await runCli(['scan', 'http://127.0.0.1:1/', '--require', 'x'], { stdout: { write: () => {} }, stderr: { write: () => {} } }), 2);
  assert.equal(checkId('Sign in & out!'), 'sign-in-out');
});
