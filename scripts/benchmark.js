import { performance } from 'node:perf_hooks';
import assert from 'node:assert/strict';
import { mkdir, writeFile } from 'node:fs/promises';
import { normalizeCookie, parseSetCookie, evaluateCookiePolicy, formatJson, formatText, exitCode } from '@aiscihub/cookieguard-core';
import { scanUrl } from 'cookieguard-ci';
import { createDemoServer, DEMO_VALUE } from '../examples/demo/server.js';

const SENTINEL = 'BENCHMARK_SENTINEL_NOT_A_REAL_SESSION_13ac98';
const now = 1800000000000;
const origin = 'https://fixture.example.test';
const raw = attributes => parseSetCookie(`session_id=${SENTINEL}; Path=/; ${attributes}`, origin, { now });
// Independently specified ground truth, not predictions from a training set.
const cases = [
  { case: 'A-secure', observations: [raw('Secure; HttpOnly; SameSite=Strict')], policy: { authCookies: ['session_id'] }, expected: 0 },
  { case: 'B-missing-httponly', observations: [raw('Secure; SameSite=Lax')], policy: { authCookies: ['session_id'] }, expected: 1 },
  { case: 'C-missing-secure', observations: [raw('HttpOnly; SameSite=Lax')], policy: { authCookies: ['session_id'] }, expected: 1 },
  { case: 'D-preference', observations: [normalizeCookie({ name: 'theme', value: 'dark', secure: false, httpOnly: false })], policy: {}, expected: 0 },
  { case: 'E-unconfirmed', observations: [normalizeCookie({ name: 'auth_hint', value: SENTINEL, secure: false, httpOnly: false })], policy: {}, expected: 0 },
  { case: 'F-store-only', observations: [normalizeCookie({ name: 'session_id', value: SENTINEL, secure: true, httpOnly: true, sameSite: 'Lax' }, { source: 'browser', origin })], policy: { authCookies: ['session_id'], requireExplicitSameSite: true }, expected: 0 },
];
const reports = cases.map(item => {
  const report = evaluateCookiePolicy(item.observations, item.policy);
  assert.equal(exitCode(report), item.expected, item.case);
  assert.equal(formatJson(report), formatJson(evaluateCookiePolicy([...item.observations].reverse(), item.policy)), 'unstable output');
  for (const text of [formatJson(report), formatText(report)]) assert.equal(text.includes(SENTINEL), false, 'sentinel leakage');
  return { case: item.case, expectedExitCode: item.expected, observedExitCode: exitCode(report),
    confirmedViolations: report.summary.confirmedViolations, reviewItems: report.summary.reviewItems,
    confirmedAuth: report.summary.confirmedAuth, candidateAuth: report.summary.candidateAuth,
    unknownDeclaration: report.cookies.some(entry => entry.observation.sameSite.declared === 'unknown') };
});
const server = createDemoServer();
await new Promise((resolve, reject) => server.once('error', reject).listen(0, '127.0.0.1', resolve));
const samples = [];
try {
  for (let i = 0; i < 20; i++) {
    const start = performance.now();
    const collection = await scanUrl(`http://127.0.0.1:${server.address().port}/${i % 2 ? 'missing-httponly' : 'secure'}`);
    const report = evaluateCookiePolicy(collection.observations, { authCookies: ['session_id'] }, collection);
    samples.push(performance.now() - start);
    assert.equal(exitCode(report), i % 2);
    assert.equal(formatJson(report).includes(DEMO_VALUE), false, 'sentinel leakage');
  }
} finally { await new Promise(resolve => server.close(resolve)); }
samples.sort((a, b) => a - b);
const result = { suite: 'controlled-local-fixtures', realWorldValidation: false,
  node: process.version, platform: process.platform, architecture: process.arch,
  cases: reports, caseExpectationsMet: reports.length, confirmedFlagViolations: reports.reduce((n, r) => n + r.confirmedViolations, 0),
  nonAuthConfirmedFalsePositives: reports.find(r => r.case === 'D-preference').confirmedViolations,
  stableOutputs: true, sentinelLeaks: 0, httpScans: samples.length,
  runtimeMs: { min: samples[0], median: samples[Math.floor(samples.length / 2)], p95: samples[Math.ceil(samples.length * 0.95) - 1], max: samples.at(-1) },
  timingScope: 'In-process HTTP scan plus policy evaluation; excludes Node startup, browser startup, and login.' };
await mkdir('artifacts', { recursive: true });
await writeFile('artifacts/benchmark.json', JSON.stringify(result, null, 2) + '\n', { mode: 0o600 });
process.stdout.write(JSON.stringify(result, null, 2) + '\n');
