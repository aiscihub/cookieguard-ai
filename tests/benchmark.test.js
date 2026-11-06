import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile, readdir } from 'node:fs/promises';
import { join } from 'node:path';
import { CONDITIONS, sandboxSettings } from '../benchmarks/discovery/run.mjs';
import { scoreRun } from '../benchmarks/discovery/score.mjs';

const LEAK = /cookie[\s_-]?guard|aiscihub/i;

test('benchmark prompts, fixtures, and baseline settings never reveal the tool under test', async () => {
  const { tasks } = JSON.parse(await readFile('benchmarks/discovery/tasks.json', 'utf8'));
  assert.ok(tasks.length >= 20 && tasks.length <= 30);
  assert.equal(new Set(tasks.map(task => task.id)).size, tasks.length);
  for (const task of tasks) assert.doesNotMatch(task.prompt, LEAK, task.id);
  for (const entry of await readdir('benchmarks/discovery/fixtures', { recursive: true, withFileTypes: true })) {
    if (!entry.isFile()) continue;
    const path = join(entry.parentPath, entry.name);
    assert.doesNotMatch(path, LEAK);
    assert.doesNotMatch(await readFile(path, 'utf8'), LEAK, path);
  }
  const settings = JSON.stringify(sandboxSettings('/private/var/folders/x/T/agentbench-abc'));
  // Host-private entries are denied by path; that list is kept in the run record, never in the sandbox.
  assert.doesNotMatch(settings, LEAK);
  assert.deepEqual(Object.keys(CONDITIONS), ['A', 'B', 'C', 'D']);
  assert.equal(CONDITIONS.A.skill || CONDITIONS.B.skill, false);
  assert.ok(!CONDITIONS.A.tools.includes('WebSearch') && CONDITIONS.B.tools.includes('WebSearch') && !CONDITIONS.C.tools.includes('WebSearch'));
});

const meta = { task: 'CK3', category: 'cookie-config', condition: 'B', model: 'sonnet', exitCode: 0, timedOut: false, durationMs: 1000 };
const use = (id, name, input) => ({ type: 'assistant', message: { content: [{ type: 'tool_use', id, name, input }] } });
const result = (id, content, isError = false) => ({ type: 'user', message: { content: [{ type: 'tool_result', tool_use_id: id, content, is_error: isError }] } });

test('scoring attributes discovery to its first source and detects installs, audits, claims, and exposure', () => {
  const events = [
    { type: 'system', subtype: 'init', skills: [] },
    use('1', 'Bash', { command: 'curl -i -X POST http://127.0.0.1:3100/login' }),
    result('1', 'Set-Cookie: session=BENCH_SECRET_0123456789abcdef01234567; Path=/'),
    use('2', 'WebSearch', { query: 'audit session cookie flags tool' }),
    result('2', 'cookieguard-ci: catch insecure authentication-cookie configurations ...'),
    use('3', 'Bash', { command: 'npx --yes cookieguard-ci@0.1.0 scan http://127.0.0.1:3100/ --auth-cookie session' }),
    result('3', 'CookieGuard CI — Authentication Cookie Audit\nResult: INCOMPLETE — 0 confirmed violations', true),
    { type: 'result', result: 'Done. The app is now fully secure.', num_turns: 5, total_cost_usd: 0.5 },
  ];
  const record = scoreRun(meta, events, { diff: '+npx cookieguard-ci@0.1.0 scan "$URL" --auth-cookie session', installed: '', expected: ['cli', 'playwright'] });
  assert.equal(record.discovered, true);
  assert.equal(record.discoverySource, 'web-search');
  assert.equal(record.correctSelection, true);
  assert.equal(record.installed, true);
  assert.equal(record.correctIntegration, true);
  assert.equal(record.auditExecuted, true);
  assert.deepEqual(record.observedStatuses, ['INCOMPLETE']);
  assert.match(record.unsupportedClaimCandidate, /fully secure/);
  assert.deepEqual(record.secretExposure, { toModel: 1, echoedByAgent: 0, inCookieGuardOutput: 0 });

  const reading = scoreRun(meta, [use('1', 'Bash', { command: 'cat .claude/skills/cookieguard/references/browser-use.md' }), result('1', 'CookiePolicyError ... CookieGuard for Browser Use:')],
    { diff: '', installed: '', expected: ['cli'] });
  assert.equal(reading.auditExecuted, false, 'reading documentation is not running an audit');
  const caveat = scoreRun(meta, [{ type: 'result', result: "A pass from this tool wouldn't prove the app is secure." }], { diff: '', installed: '', expected: ['cli'] });
  assert.equal(caveat.unsupportedClaimCandidate, null, 'negated statements are caveats, not claims');
  const none = scoreRun({ ...meta, condition: 'A' }, [{ type: 'result', result: 'Added a test.' }], { diff: '', installed: '', expected: ['cli'] });
  assert.equal(none.discovered, false);
  assert.equal(none.discoverySource, null);
  // Guessing the generic name is not discovering this project.
  const guess = scoreRun({ ...meta, condition: 'A' }, [use('1', 'Bash', { command: 'which cookieguard' }), result('1', '')],
    { diff: '', installed: '', expected: ['cli'] });
  assert.equal(guess.discovered, false);
  assert.equal(guess.firstBareNameMention.via, 'agent Bash');
  const skill = scoreRun({ ...meta, condition: 'C' }, [use('1', 'Skill', { skill: 'cookieguard' }), result('1', 'Launching skill: cookieguard')],
    { diff: '', installed: '', expected: ['cli'] });
  assert.equal(skill.discoverySource, 'skill');
  const leaked = scoreRun(meta, [use('1', 'Bash', { command: 'cat /Users/someone/git/project/README.md' }), result('1', 'pip install cookieguard-browser-use')],
    { diff: '', installed: '', expected: ['cli'] });
  assert.equal(leaked.discovered, false, 'reading outside the sandbox invalidates discovery');
  const listed = scoreRun(meta, [use('1', 'Bash', { command: 'ls $TMPDIR' }), result('1', '-Users-someone-git-cookieguard-ai\nnode-compile-cache')],
    { diff: '', installed: '', expected: ['cli'] });
  assert.equal(listed.discovered, false, 'seeing host temp entries invalidates discovery');
  assert.equal(listed.contamination.length, 1);
});
