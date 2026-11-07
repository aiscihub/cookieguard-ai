import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { createDemoServer, DEMO_VALUE } from '../examples/demo/server.js';
import { runCli, capabilities } from 'cookieguard-ci';
import { explain, readEvidence, isEvidenceReport, EXPLAIN_IDS, RULES } from '@aiscihub/cookieguard-core';
import { capabilitiesSchema, reportSchema, explanationSchema, cliErrorSchema } from '../packages/mcp/src/schemas.js';

const exec = promisify(execFile);
let server, target, temp;
before(async () => {
  server = createDemoServer();
  await new Promise((done, reject) => server.once('error', reject).listen(0, '127.0.0.1', done));
  target = `http://127.0.0.1:${server.address().port}`;
  temp = await mkdtemp(join(tmpdir(), 'cookieguard-capabilities-'));
});
after(async () => {
  server?.closeAllConnections();
  if (server?.listening) await new Promise(done => server.close(done));
  if (temp) await rm(temp, { recursive: true, force: true });
});

async function run(args) {
  let out = '', err = '';
  const code = await runCli(args, { stdout: { write: s => { out += s; } }, stderr: { write: s => { err += s; } } });
  assert.equal((out + err).includes(DEMO_VALUE), false, 'Sensitive sentinel was emitted');
  return { code, out, err };
}

test('capability document is schema-valid, stable, and identical to the published copies', async () => {
  const document = capabilities();
  capabilitiesSchema.parse(document);
  const { code, out } = await run(['capabilities', '--json']);
  assert.equal(code, 0);
  assert.deepEqual(JSON.parse(out), document);
  for (const path of ['cookieguard.capabilities.json', 'skills/cookieguard-browser-auth-security/references/capabilities.json']) {
    assert.equal(await readFile(path, 'utf8'), out, `${path} is stale; run npm run build:schemas`);
  }
  await exec(process.execPath, ['scripts/build-schemas.js', '--check']);
  // Every rule the engine can emit is described, with its real severity.
  assert.deepEqual(document.checks.map(c => [c.ruleId, c.severity]), Object.entries(RULES).map(([id, r]) => [id, r.severity]));
  assert.deepEqual(document.results.statuses.map(s => [s.label, s.exitCode]), [['PASS', 0], ['FAIL', 1], ['INCOMPLETE', 2]]);
  // Published-package instructions must point at versions that exist.
  for (const integration of document.integrations.filter(i => i.registry)) {
    assert.match(integration.version, /^\d+\.\d+\.\d+$/);
  }
  // Operations that exist only on main stay "unreleased" until their packages are
  // published; scripts/release-gate.js refuses a release while any remain.
  assert.deepEqual(document.operations.filter(o => o.availability !== 'released').map(o => [o.id, o.availability]),
    [['check-session-lifecycle', 'unreleased'], ['check-web-storage', 'unreleased'], ['enforce-login-checks', 'unreleased']]);
});

test('every explainable identifier has a schema-valid explanation; unknown identifiers are not reflected', async () => {
  for (const id of EXPLAIN_IDS) {
    const entry = explanationSchema.parse(explain(id));
    assert.equal(entry.id, id);
    const { code, out } = await run(['explain', id, '--json']);
    assert.equal(code, 0);
    assert.deepEqual(JSON.parse(out), entry);
  }
  assert.equal(explain(DEMO_VALUE), null);
  assert.equal(explain('__proto__'), null);
  assert.match((await run(['explain', 'CG001'])).out, /Confirmed when:/);
  const unknown = await run(['explain', DEMO_VALUE, '--json']);
  assert.equal(unknown.code, 2);
  assert.equal(cliErrorSchema.parse(JSON.parse(unknown.out)).error.code, 'CONFIG');
});

test('scan --json emits schema-valid reports for pass, fail, and incomplete, and JSON errors without reflection', async () => {
  for (const [path, status, code] of [['secure', 'passed', 0], ['missing-httponly', 'failed', 1], ['preference', 'incomplete', 2]]) {
    const result = await run(['scan', `${target}/${path}`, '--auth-cookie', 'session_id', '--json']);
    assert.equal(result.code, code);
    const report = reportSchema.parse(JSON.parse(result.out));
    assert.equal(report.status, status);
    if (code === 1) assert.ok(report.findings.some(f => f.ruleId === 'CG001' && f.status === 'confirmed' && f.evidence.source === 'header'));
  }
  for (const args of [['scan', `${target}/?token=${DEMO_VALUE}`, '--json'], ['scan', target, `--${DEMO_VALUE}`, '--json'],
    ['scan', target, '--fail-on', DEMO_VALUE, '--format=json'], ['scan', 'http://127.0.0.1:1/', '--format', 'json', '--timeout-ms', '200']]) {
    const result = await run(args);
    assert.equal(result.code, 2);
    const error = cliErrorSchema.parse(JSON.parse(result.out));
    assert.ok(['TARGET', 'CONFIG', 'NETWORK'].includes(error.error.code));
  }
  // Text mode keeps stdout empty on errors, as in 0.1.0.
  assert.equal((await run(['scan', `${target}/?q=1`])).out, '');
  assert.equal((await run(['capabilities', '--format', 'text'])).code, 2);
  assert.equal((await run(['capabilities', '--auth-cookie', 'session_id'])).code, 2);
});

test('a written report is reusable evidence: re-evaluated under the current policy, values dropped, provisional stays incomplete', async () => {
  const insecure = join(temp, 'insecure.json');
  await run(['scan', `${target}/missing-httponly`, '--auth-cookie', 'session_id', '--json', '--output', insecure]);
  const original = JSON.parse(await readFile(insecure, 'utf8'));
  assert.ok(isEvidenceReport(original));
  const again = await run(['scan', '--input', insecure, '--auth-cookie', 'session_id', '--json']);
  assert.equal(again.code, 1);
  const report = reportSchema.parse(JSON.parse(again.out));
  assert.equal(report.mode, 'http');
  assert.ok(report.limitations.some(l => l.startsWith('Evaluated from a supplied evidence file')));
  // A different policy changes the decision; the evidence does not carry the old verdict.
  assert.equal((await run(['scan', '--input', insecure, '--auth-cookie', 'session_id', '--fail-on', 'critical'])).code, 0);
  assert.equal((await run(['scan', '--input', insecure, '--auth-cookie', 'other_cookie'])).code, 2);

  // Forged fields, including cookie values, never survive reconstruction.
  const forged = structuredClone(original);
  forged.cookies[0].observation.value = DEMO_VALUE;
  forged.cookies[0].observation.header.raw = `session_id=${DEMO_VALUE}`;
  forged.cookies[0].identity.note = DEMO_VALUE;
  const forgedPath = join(temp, 'forged.json');
  await writeFile(forgedPath, JSON.stringify(forged));
  assert.equal((await run(['scan', '--input', forgedPath, '--auth-cookie', 'session_id', '--json'])).code, 1);
  assert.equal(JSON.stringify(readEvidence(forged)).includes(DEMO_VALUE), false);

  // A Browser Use result wraps the same report; provisional evidence never passes.
  const secureReport = JSON.parse((await run(['scan', `${target}/secure`, '--auth-cookie', 'session_id', '--json'])).out);
  for (const [provisional, code] of [[false, 0], [true, 2]]) {
    const path = join(temp, `browser-use-${provisional}.json`);
    await writeFile(path, JSON.stringify({ schemaVersion: 1, integration: 'cookieguard-browser-use', status: 'PASS', exitCode: 0,
      provisional, collection: {}, findings: [], report: secureReport }));
    const result = await run(['scan', '--input', path, '--auth-cookie', 'session_id', '--json']);
    assert.equal(result.code, code);
    if (provisional) assert.ok(JSON.parse(result.out).issues.includes('collection-incomplete'));
  }
  for (const bad of [{ schemaVersion: 1, mode: 'http', cookies: [{ observation: { name: 'x' } }], issues: [] },
    { schemaVersion: 1, integration: 'cookieguard-browser-use', report: null }]) {
    await writeFile(join(temp, 'bad.json'), JSON.stringify(bad));
    const result = await run(['scan', '--input', join(temp, 'bad.json'), '--json']);
    assert.equal(result.code, 2);
    assert.equal(JSON.parse(result.out).error.code, 'INPUT');
  }
});
