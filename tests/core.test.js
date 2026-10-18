import { test } from 'node:test';
import assert from 'node:assert/strict';
import { normalizeCookie, normalizeCookies, normalizeLegacyResults, parseSetCookie,
  evaluateCookiePolicy, exitCode, formatJson, formatText, formatMarkdown, assertCookiePolicy } from '@aiscihub/cookieguard-core';

const TOKEN = 'SENTINEL_SESSION_NEVER_SERIALIZE_84af20';
const now = 1800000000000;
const url = 'https://app.example.test/login';
const policy = { authCookies: ['session_id'] };
const header = (attributes, name = 'session_id') => parseSetCookie(`${name}=${TOKEN}; Path=/; ${attributes}`, url, { now });
const audit = (observations, rules = policy, options = {}) => evaluateCookiePolicy(observations, rules, { target: url, ...options });

test('A: secure authentication cookie passes', () => {
  const result = audit([header('Secure; HttpOnly; SameSite=Lax')]);
  assert.equal(exitCode(result), 0); assert.equal(result.findings.length, 0);
});
test('B/C: missing HttpOnly and Secure are confirmed configuration failures', () => {
  for (const [attributes, rule] of [['Secure; SameSite=Lax', 'CG001'], ['HttpOnly; SameSite=Lax', 'CG002']]) {
    const result = audit([header(attributes)]);
    assert.equal(exitCode(result), 1);
    assert.ok(result.findings.some(f => f.ruleId === rule && f.status === 'confirmed'));
    assert.throws(() => assertCookiePolicy(result), { name: 'CookiePolicyError', exitCode: 1 });
  }
});
test('D: preference/tracking triage does not confirm insecure authentication', () => {
  const cookies = normalizeCookies([{ name: 'theme', value: 'light', secure: false, httpOnly: false }, { name: '_ga', value: '123', secure: false, httpOnly: false }]);
  const result = audit(cookies, {});
  assert.equal(exitCode(result), 0); assert.equal(result.summary.confirmedViolations, 0);
  assert.equal(result.findings.length, 0);
});
test('E: candidate and unknown identity are review only', () => {
  const cookies = [header('SameSite=Lax', 'auth_hint'), normalizeCookie({ name: 'opaque', value: TOKEN })];
  const result = audit(cookies, {});
  assert.equal(exitCode(result), 0);
  assert.ok(result.findings.some(f => f.ruleId === 'CG008'));
  assert.ok(result.findings.every(f => f.status === 'review'));
});
test('F: browser defaults never establish an explicit SameSite declaration', () => {
  const cookie = normalizeCookie({ name: 'session_id', value: TOKEN, domain: 'app.example.test', path: '/', secure: true, httpOnly: true, sameSite: 'Lax', expires: -1 }, { source: 'browser', origin: url });
  const result = audit([cookie], { ...policy, requireExplicitSameSite: true });
  assert.equal(cookie.sameSite.declared, 'unknown'); assert.equal(cookie.sameSite.effective, 'lax');
  assert.equal(exitCode(result), 0); assert.ok(result.findings.some(f => f.ruleId === 'CG009'));
});
test('SameSite None is policy-dependent; absence is distinct from unknown', () => {
  const none = header('Secure; HttpOnly; SameSite=None');
  assert.equal(exitCode(audit([none], { ...policy, failOn: 'medium' })), 1);
  assert.equal(exitCode(audit([none], { ...policy, allowedSameSite: ['none'] })), 0);
  const absent = header('Secure; HttpOnly');
  assert.equal(absent.sameSite.declared, 'absent');
  assert.equal(exitCode(audit([absent], { ...policy, requireExplicitSameSite: true, failOn: 'medium' })), 1);
  assert.equal(header('Secure; HttpOnly; SameSite=no_restriction').sameSite.declared, 'invalid');
});
test('domain scope review is confirmed only by explicit host-only policy', () => {
  const cookie = header('Secure; HttpOnly; SameSite=Lax; Domain=example.test');
  assert.equal(cookie.hostOnly, false);
  assert.equal(exitCode(audit([cookie], { ...policy, failOn: 'medium' })), 0);
  assert.equal(exitCode(audit([cookie], { ...policy, failOn: 'medium', requireHostOnly: true })), 1);
});
test('expiry precedence, deletion, malformed/combined/duplicate attributes', () => {
  const long = header('Secure; HttpOnly; SameSite=Lax; Max-Age=2678400; Expires=Wed, 01 Jan 2030 00:00:00 GMT');
  assert.equal(long.lifetimeSeconds, 31 * 86400);
  assert.equal(exitCode(audit([long], { ...policy, failOn: 'medium' })), 1);
  assert.equal(exitCode(audit([header('Max-Age=0')])), 2);
  const duplicate = header('Secure; Secure=false; HttpOnly; SameSite=Lax');
  assert.equal(duplicate.confidence, 'uncertain');
  assert.ok(audit([duplicate]).findings.every(f => f.status === 'review'));
  assert.throws(() => parseSetCookie(`a=${TOKEN}, b=${TOKEN}`, url), /withheld/);
  assert.throws(() => parseSetCookie(`a=${TOKEN}\r\nX-Test: yes`, url), /withheld/);
});
test('prefix findings require observed headers and describe possible rejection', () => {
  const cookie = header('Secure; HttpOnly; SameSite=Lax; Domain=app.example.test', '__Host-session');
  const result = audit([cookie], { authCookies: ['__Host-session'] });
  assert.equal(exitCode(result), 1);
  assert.ok(result.findings.some(f => f.ruleId === 'CG006' && /reject/.test(f.why)));
  const store = normalizeCookie({ name: '__Host-session', secure: false }, { source: 'browser' });
  assert.ok(audit([store], {}).findings.every(f => f.ruleId !== 'CG006'));
  assert.equal(parseSetCookie('__Secure-session=synthetic; Secure', 'http://127.0.0.1').header.prefixValid, true);
  assert.equal(parseSetCookie('__Secure-session=synthetic; Secure', 'http://127.attacker.test').header.prefixValid, false);
});
test('validated flow evidence must match the full scope and origin', () => {
  const cookie = header('SameSite=Lax');
  const evidence = { name: cookie.name, domain: cookie.domain, path: cookie.path, origin: cookie.origin, validation: 'server-session-validated' };
  assert.equal(exitCode(audit([cookie], { authEvidence: [evidence] })), 1);
  assert.equal(exitCode(audit([cookie], { authEvidence: [{ ...evidence, path: '/different' }] })), 2);
  assert.throws(() => audit([cookie], { authEvidence: [{ ...evidence, validation: 'appeared-during-login' }] }));
});
test('empty scans and missing expected cookies are incomplete; bad config is rejected', () => {
  assert.equal(exitCode(audit([])), 2);
  assert.equal(exitCode(audit([header('SameSite=Lax', 'different')])), 2);
  assert.throws(() => audit([], { failOn: 'hgh' }));
  assert.throws(() => audit([], { authCookie: 'typo' }));
  assert.throws(() => audit([], { maxLifetimeDays: -1 }));
});
test('baseline compares only compatible, unambiguous observations', () => {
  const baseline = JSON.parse(formatJson(audit([header('Secure; HttpOnly; SameSite=Lax')])));
  const current = audit([header('SameSite=Lax')], policy, { baseline });
  assert.equal(current.comparison.comparedCookies, 1);
  assert.deepEqual(current.findings.find(f => f.ruleId === 'CG007').evidence.changes, ['secure', 'httpOnly']);
  const incompatible = audit([header('SameSite=Lax')], policy, { baseline: { ...baseline, target: 'https://different.test' } });
  assert.equal(incompatible.comparison.status, 'not-comparable');
  assert.ok(incompatible.findings.every(f => f.ruleId !== 'CG007'));
});
test('allowlisted nested data and fixed report rendering never leak sentinel tokens', () => {
  const legacy = { cookies: [{ cookie: { name: 'session_id', value: TOKEN, secure: false, httpOnly: false,
    nested: { raw: TOKEN } }, error: TOKEN, explanations: { secret: TOKEN } }], context: { token: TOKEN } };
  const cookies = normalizeLegacyResults(legacy);
  cookies[0].context = { value: TOKEN };
  const result = audit(cookies);
  result.extra = TOKEN; result.findings[0].why = TOKEN;
  for (const output of [JSON.stringify(cookies[0].triage), formatJson(result), formatText(result), formatMarkdown(result)]) {
    assert.equal(output.includes(TOKEN), false, 'Sensitive sentinel was emitted');
  }
  assert.equal(JSON.stringify(normalizeCookie({ name: TOKEN, value: TOKEN })).includes(TOKEN), false);
  assert.throws(() => formatJson({ value: TOKEN }));
});
test('output order is deterministic and Markdown metadata is escaped', () => {
  const a = header('Secure; HttpOnly; SameSite=Lax');
  const b = header('SameSite=None', 'auth_hint');
  assert.equal(formatJson(audit([a, b])), formatJson(audit([b, a])));
  const hostile = normalizeCookie({ name: '</pre><script>alert(1)</script>', secure: false });
  assert.ok(!formatMarkdown(audit([hostile], {})).includes('<script>'));
});
