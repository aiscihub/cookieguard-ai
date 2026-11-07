import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, readFile, readdir, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { AUTH_COOKIES, CONDITIONS, PROMPT, matrix, readApp, redact } from '../benchmarks/auth-testing/bench.mjs';
import { differential, scoreTranscript, summarize, toolInWorkspace, wilson } from '../benchmarks/auth-testing/score.mjs';
import { APP_FILES, FLAWED, VERSIONS, versionFiles } from '../benchmarks/auth-testing/variants.mjs';

const LEAK = /cookie[\s_-]?guard|aiscihub/i;
const FIXTURE = 'benchmarks/auth-testing/fixture';

test('the prompt, the app, and every app version never name the tool under test', async () => {
  assert.doesNotMatch(PROMPT, LEAK);
  assert.doesNotMatch(PROMPT, /secur|cookie|httponly|redirect/i, 'the prompt asks for tests, not a security review');
  for (const entry of await readdir(FIXTURE, { recursive: true, withFileTypes: true })) {
    if (!entry.isFile()) continue;
    const path = join(entry.parentPath, entry.name);
    assert.doesNotMatch(path, LEAK);
    assert.doesNotMatch(await readFile(path, 'utf8'), LEAK, path);
  }
  const pristine = await readApp(FIXTURE);
  for (const version of Object.keys(VERSIONS)) {
    for (const content of Object.values(versionFiles(pristine, version))) assert.doesNotMatch(content, LEAK, version);
  }
  assert.deepEqual(Object.keys(CONDITIONS), ['A', 'B']);
  assert.equal(CONDITIONS.A.tool, false);
});

test('each flawed version applies its edits exactly once and differs from the fixed app only in app files', async () => {
  const pristine = await readApp(FIXTURE);
  assert.ok(APP_FILES.every(file => typeof pristine[file] === 'string'));
  assert.deepEqual(versionFiles(pristine, 'fixed'), pristine);
  assert.deepEqual(FLAWED, ['no-httponly', 'js-token', 'open-redirect']);
  for (const version of FLAWED) {
    const files = versionFiles(pristine, version);
    const changed = APP_FILES.filter(file => files[file] !== pristine[file]);
    assert.ok(changed.length >= 1, version);
    assert.ok(changed.every(file => VERSIONS[version].edits.some(edit => edit.file === file)), version);
  }
  assert.throws(() => versionFiles({ ...pristine, 'app.js': '' }, 'no-httponly'), /matched 0 times/);
  // Every version has both credential cookies, so tests about either can pass on the fixed app.
  for (const version of Object.keys(VERSIONS)) {
    const files = versionFiles(pristine, version);
    for (const name of AUTH_COOKIES) assert.match(files['app.js'] + files['public/app.js'], new RegExp(name), `${version} ${name}`);
  }
});

test('a flaw counts as caught only when the suite fails on it and passes every fixed run', () => {
  const runs = (codes) => ['fixed', ...FLAWED, 'fixed'].map((version, index) => ({ version, exitCode: codes[index] }));
  const strong = differential(runs([0, 1, 1, 1, 0]), 'js-token');
  assert.deepEqual(strong, { passesFixed: true, flaky: false, caught: { 'no-httponly': true, 'js-token': true, 'open-redirect': true }, caughtSeen: true, caughtCount: 3 });
  const broken = differential(runs([1, 1, 1, 1, 1]), 'no-httponly');
  assert.equal(broken.passesFixed, false);
  assert.equal(broken.caughtCount, 0, 'a suite that fails on the fixed app catches nothing');
  const flaky = differential(runs([0, 1, 0, 0, 1]), 'no-httponly');
  assert.equal(flaky.flaky, true);
  assert.equal(flaky.caughtSeen, false);
  const hung = differential(runs([0, null, 0, 0, 0]), 'no-httponly');
  assert.equal(hung.caughtSeen, false, 'a timeout is not a reported failure');
  assert.equal(differential(runs([0, 0, 0, 0, 0]), 'fixed').caughtSeen, null);
});

const use = (id, name, input) => ({ type: 'assistant', message: { content: [{ type: 'tool_use', id, name, input }] } });
const result = (id, content) => ({ type: 'user', message: { content: [{ type: 'tool_result', tool_use_id: id, content }] } });
const SESSION = 'sess_' + '0123456789abcdef'.repeat(2);
const MADE_UP = 'sess_' + 'fedcba9876543210'.repeat(2);

test('transcript scoring counts real credentials shown to the model, tool use, and cost', () => {
  const events = [
    use('1', 'Write', { file_path: 'test/fake.test.js', content: `const fake = '${MADE_UP}';` }),
    result('1', `File written. Echo: ${MADE_UP}`),
    use('2', 'Bash', { command: 'curl -i -X POST http://127.0.0.1:3000/login' }),
    result('2', `HTTP/1.1 303 See Other\nSet-Cookie: sid=${SESSION}; Path=/; HttpOnly`),
    use('3', 'Bash', { command: `curl -b sid=${SESSION} http://127.0.0.1:3000/api/notes` }),
    result('3', '{"notes":[]}'),
    use('4', 'Skill', { skill: 'cookieguard-browser-auth-security' }),
    use('5', 'mcp__cookieguard__cookieguard_audit', { url: 'http://127.0.0.1:3000/login' }),
    result('5', '{"status":"incomplete"}'),
    { type: 'result', subtype: 'success', is_error: false, result: 'Added tests. Login handling is secure. The sid cookie lacks HttpOnly.', num_turns: 9, total_cost_usd: 0.42, duration_ms: 60000, usage: { input_tokens: 10, output_tokens: 20 } },
  ];
  const scored = scoreTranscript(events);
  assert.equal(scored.credentialsShownToModel, 1, 'the made-up value the agent wrote itself does not count');
  assert.equal(scored.credentialsEchoedByAgent, 1);
  assert.equal(scored.mcpCalls, 1);
  assert.equal(scored.skillLoaded, true);
  assert.equal(scored.completed, true);
  assert.equal(scored.costUsd, 0.42);
  assert.equal(scored.heuristic.unsupportedClaim, 'Login handling is secure.');
  assert.deepEqual(scored.heuristic.mentions, { 'no-httponly': true, 'js-token': false, 'open-redirect': false });
  assert.match(scored.toolNameSeen.where, /Skill/);
  const caveat = scoreTranscript([{ type: 'result', subtype: 'success', result: 'Passing tests do not prove the session is secure.' }]);
  assert.equal(caveat.heuristic.unsupportedClaim, null);
  assert.equal(scoreTranscript([use('1', 'Bash', { command: 'npm test' }), result('1', 'ok')]).toolNameSeen, null);
});

test('workspace detection requires an enforced check, not a mention', () => {
  assert.deepEqual(toolInWorkspace('+// TODO: try cookieguard'), { mentioned: true, playwright: false, cli: false });
  const imported = "+import { startCookieAudit, assertCookiePolicy } from '@aiscihub/cookieguard-playwright';\n";
  assert.equal(toolInWorkspace(imported).playwright, false, 'an import alone enforces nothing');
  const wired = `${imported}+const audit = startCookieAudit(context, { policy });\n+assertCookiePolicy(await audit.evaluate());`;
  assert.equal(toolInWorkspace(wired).playwright, true);
});

test('summaries keep denominators and confidence intervals per condition', () => {
  const record = (id, condition, version, caught, exposed) => ({ id, condition, version,
    differential: differential(['fixed', ...FLAWED, 'fixed'].map(entry => ({ version: entry, exitCode: entry === version && caught ? 1 : 0 })), version),
    transcript: { completed: true, credentialsShownToModel: exposed, mcpCalls: 0, skillLoaded: false, costUsd: 1, durationMs: 60000 },
    workspace: { appModified: [], tool: { mentioned: false, playwright: false, cli: false } } });
  const summary = summarize([record('a1', 'A', 'no-httponly', false, 1), record('b1', 'B', 'no-httponly', true, 0), record('b2', 'B', 'fixed', false, 0)]);
  assert.deepEqual(summary.conditions.A.caughtSeenFlaw['no-httponly'], { hits: 0, n: 1, ci95: wilson(0, 1) });
  assert.equal(summary.conditions.B.caughtSeenFlaw['no-httponly'].hits, 1);
  assert.equal(summary.conditions.B.caughtSeenFlaw['js-token'].n, 0);
  assert.equal(summary.conditions.A.credentialExposureRuns.hits, 1);
  assert.deepEqual(wilson(5, 10), [0.237, 0.763]);
});

test('the run matrix interleaves conditions and rejects unknown entries', () => {
  const { include } = matrix({ versions: Object.keys(VERSIONS), conditions: ['A', 'B'], repeats: 2 });
  assert.equal(include.length, 16);
  assert.deepEqual(include.slice(0, 2).map(job => job.id), ['fixed-A-1', 'fixed-B-1']);
  assert.throws(() => matrix({ versions: ['nope'], conditions: ['A'], repeats: 1 }));
});

test('redaction removes harness credentials from a run directory', async () => {
  const run = await mkdtemp(join(tmpdir(), 'bench-redact-'));
  try {
    const key = 'sk-ant-api03-' + 'x'.repeat(40);
    await writeFile(join(run, 'transcript.jsonl'), `{"text":"env shows ANTHROPIC_API_KEY=${key}"}\n`);
    await writeFile(join(run, 'meta.json'), '{}');
    await redact(run);
    assert.doesNotMatch(await readFile(join(run, 'transcript.jsonl'), 'utf8'), /sk-ant-/);
    assert.equal(JSON.parse(await readFile(join(run, 'meta.json'), 'utf8')).filesRedacted, 1);
  } finally {
    await rm(run, { recursive: true, force: true });
  }
});
