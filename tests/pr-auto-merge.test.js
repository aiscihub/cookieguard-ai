import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { ACTIONS_APP_ID, LABEL, REQUIRED_CHECKS, reconcile, requestFromEvent, requiredChecksProtected, latestOptIn } from '../scripts/pr-auto-merge.mjs';

const repository = 'owner/repo';
const head = 'a'.repeat(40);
const protections = () => [{ type: 'required_status_checks', parameters: {
  strict_required_status_checks_policy: true,
  required_status_checks: REQUIRED_CHECKS.map(context => ({ context, integration_id: ACTIONS_APP_ID })),
} }];
const pull = () => ({ number: 7, state: 'open', merged: false, draft: false,
  base: { ref: 'main', repo: { full_name: repository } }, head: { sha: head }, labels: [{ name: LABEL }], auto_merge: null });
const label = () => ({ id: 10, event: 'labeled', label: { name: LABEL }, actor: { login: 'maintainer' } });

function harness(options = {}) {
  const state = { pr: pull(), rules: protections(), repo: { default_branch: 'main', allow_auto_merge: true, allow_squash_merge: true },
    permission: 'write', events: [label()], merges: [], reads: 0, eventReads: 0, ...options };
  return { state, run: (extra = {}) => reconcile({ repository, number: 7, dryRun: false,
    merge: async args => { state.merges.push(args); },
    api: async route => {
      if (route === `repos/${repository}`) return structuredClone(state.repo);
      if (route.endsWith('/pulls/7')) {
        state.reads++;
        return structuredClone(state.reads > 1 && state.nextPr ? state.nextPr : state.pr);
      }
      if (route.includes('/rules/branches/')) return structuredClone(state.rules);
      if (route.includes('/events?')) {
        state.eventReads++;
        return structuredClone(state.eventReads > 1 && state.nextEvents ? state.nextEvents : state.events);
      }
      if (route.endsWith('/permission')) return { permission: state.permission };
      throw new Error('Unexpected API route');
    }, ...extra }) };
}

test('only explicit authorized opt-in requests native, SHA-matched squash auto-merge', async () => {
  const h = harness();
  assert.equal((await h.run()).action, 'requested');
  assert.deepEqual(h.state.merges, [['pr', 'merge', '7', '--repo', repository, '--auto', '--squash', '--match-head-commit', head]]);
  assert.ok(!h.state.merges.flat().includes('--admin'));
});

for (const [name, change] of [
  ['unlabeled', { labels: [] }], ['draft', { draft: true }], ['closed', { state: 'closed' }],
  ['merged', { merged: true }], ['another base branch', { base: { ref: 'release', repo: { full_name: repository } } }],
  ['another repository', { base: { ref: 'main', repo: { full_name: 'someone/else' } } }],
]) test(`${name} PR does not request a merge`, async () => {
  const h = harness({ pr: { ...pull(), ...change } });
  assert.equal((await h.run()).action, 'skip');
  assert.deepEqual(h.state.merges, []);
});

for (const permission of ['read', 'triage', 'none']) test(`${permission} cannot opt a PR into automatic merging`, async () => {
  const h = harness({ permission });
  assert.equal((await h.run()).action, 'blocked');
  assert.deepEqual(h.state.merges, []);
});

test('missing authorization, disabled auto-merge, or missing CI protections block', async () => {
  for (const options of [{ events: [] }, { rules: [] }, { repo: { default_branch: 'main', allow_auto_merge: false } }]) {
    const h = harness(options);
    assert.equal((await h.run()).action, 'blocked');
    assert.deepEqual(h.state.merges, []);
  }
});

test('all four required checks must be from GitHub Actions and require a current base', () => {
  assert.equal(requiredChecksProtected(protections()), true);
  for (const alter of [p => p.required_status_checks.pop(), p => { p.strict_required_status_checks_policy = false; },
    p => { p.required_status_checks[0].integration_id = null; }]) {
    const rules = protections(); alter(rules[0].parameters);
    assert.equal(requiredChecksProtected(rules), false);
  }
});

for (const [name, nextPr] of [
  ['new head', { ...pull(), head: { sha: 'b'.repeat(40) } }],
  ['removed label', { ...pull(), labels: [] }], ['new draft', { ...pull(), draft: true }],
]) test(`${name} during reconciliation prevents a stale merge request`, async () => {
  const h = harness({ nextPr });
  assert.equal((await h.run()).action, 'skip');
  assert.deepEqual(h.state.merges, []);
});

test('reapplied label needs a new authorization check', async () => {
  const h = harness({ nextEvents: [{ ...label(), id: 20, actor: { login: 'someone-else' } }] });
  assert.equal((await h.run()).action, 'skip');
  assert.deepEqual(h.state.merges, []);
});

test('label removal cancels an existing native queue', async () => {
  const h = harness({ pr: { ...pull(), labels: [], auto_merge: { enabled_by: { login: 'maintainer' } } } });
  assert.equal((await h.run({ cancelRequested: true })).action, 'disabled');
  assert.deepEqual(h.state.merges, [['pr', 'merge', '7', '--repo', repository, '--disable-auto']]);
});

test('bot queue is canceled on conversion to draft; unrelated manual queues are untouched', async () => {
  const h = harness({ pr: { ...pull(), draft: true, auto_merge: { enabled_by: { login: 'github-actions[bot]' } } } });
  assert.equal((await h.run()).action, 'disabled');
  const manual = harness({ pr: { ...pull(), labels: [], auto_merge: { enabled_by: { login: 'maintainer' } } } });
  assert.equal((await manual.run()).action, 'skip');
  assert.deepEqual(manual.state.merges, []);
});

test('a stale removal event cannot cancel a newly opted-in PR', async () => {
  const h = harness({ pr: { ...pull(), labels: [], auto_merge: {} }, nextPr: { ...pull(), auto_merge: {} } });
  assert.equal((await h.run({ cancelRequested: true })).action, 'skip');
  assert.deepEqual(h.state.merges, []);
});

test('existing queue is idempotent and dry-run performs no writes', async () => {
  const queued = harness({ pr: { ...pull(), auto_merge: {} } });
  assert.equal((await queued.run()).action, 'queued');
  assert.deepEqual(queued.state.merges, []);
  const h = harness();
  assert.equal((await h.run({ dryRun: true })).action, 'would-enable');
  assert.deepEqual(h.state.merges, []);
  const cancel = harness({ pr: { ...pull(), labels: [], auto_merge: {} } });
  assert.equal((await cancel.run({ dryRun: true, cancelRequested: true })).action, 'would-disable');
  assert.deepEqual(cancel.state.merges, []);
});

test('GitHub read failures never fall through to a merge', async () => {
  for (const failAt of [1, 2, 3, 4, 5, 6, 7]) {
    const h = harness();
    let reads = 0;
    const responses = [pull(), h.state.repo, [label()], { permission: 'write' }, protections(), pull(), [label()]];
    await assert.rejects(h.run({ api: async () => {
      if (++reads === failAt) throw new Error('GitHub unavailable');
      return structuredClone(responses[reads - 1]);
    } }), /GitHub unavailable/);
    assert.deepEqual(h.state.merges, []);
  }
});

test('revoked authorization or CI protection cancels a pending bot request', async () => {
  for (const options of [{ permission: 'triage' }, { events: [] }, { rules: [] }]) {
    const h = harness({ ...options, pr: { ...pull(), auto_merge: { enabled_by: { login: 'github-actions[bot]' } } } });
    assert.equal((await h.run()).action, 'blocked');
    assert.deepEqual(h.state.merges, [['pr', 'merge', '7', '--repo', repository, '--disable-auto']]);
  }
});

test('revocation dry run and obsolete label events never cancel a current request', async () => {
  const options = { permission: 'triage', pr: { ...pull(), auto_merge: { enabled_by: { login: 'github-actions[bot]' } } } };
  const dry = harness(options);
  assert.equal((await dry.run({ dryRun: true })).action, 'blocked');
  assert.deepEqual(dry.state.merges, []);
  const newer = harness({ ...options, nextEvents: [{ ...label(), id: 20 }] });
  assert.equal((await newer.run()).action, 'skip');
  assert.deepEqual(newer.state.merges, []);
});

test('label history is paginated, and its latest removal wins', async () => {
  let page = 0;
  const api = async () => ++page === 1 ? Array.from({ length: 100 }, (_, id) => ({ ...label(), id }))
    : [{ ...label(), event: 'unlabeled', id: 200 }];
  assert.equal(await latestOptIn(api, repository, 7), null);
  assert.equal(page, 2);
});

test('event inputs fail closed and manual dispatch defaults to read-only', () => {
  assert.deepEqual(requestFromEvent('workflow_dispatch', { inputs: { pull_number: '7' } }), { number: 7, dryRun: true });
  assert.equal(requestFromEvent('workflow_dispatch', { inputs: { pull_number: '7', dry_run: 'false' } }).dryRun, false);
  assert.equal(requestFromEvent('pull_request_target', { action: 'unlabeled', label: { name: LABEL }, pull_request: { number: 7 } }).cancelRequested, true);
  assert.throws(() => requestFromEvent('workflow_dispatch', { inputs: { pull_number: '7; command' } }));
  assert.throws(() => requestFromEvent('pull_request', {}));
});

test('privileged workflow uses trusted main code and no dependency install or AI secret', async () => {
  const workflow = await readFile(new URL('../.github/workflows/pr-auto-merge.yml', import.meta.url), 'utf8');
  assert.match(workflow, /ref: \$\{\{ github\.event\.repository\.default_branch \}\}/);
  assert.match(workflow, /persist-credentials: false/);
  assert.match(workflow, /cancel-in-progress: false/);
  assert.match(workflow, /inputs\.dry_run && github\.run_id \|\| 'write'/);
  assert.match(workflow, /GH_TOKEN: \$\{\{ github\.token \}\}/);
  assert.doesNotMatch(workflow, /secrets\.|ANTHROPIC|npm (?:ci|install)|pull_request\.head/);
  assert.equal(REQUIRED_CHECKS.length, 4);
});
