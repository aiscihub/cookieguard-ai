/** Label opt-in for GitHub's native auto-merge, protected by required checks.
 * Runs only trusted default-branch code. PR code is never checked out or run.
 * No model, API key, review approval, or administrator bypass is used.
 */
import { execFile } from 'node:child_process';
import { readFile, appendFile } from 'node:fs/promises';
import { pathToFileURL } from 'node:url';
import { promisify } from 'node:util';

export const LABEL = 'auto-merge';
export const ACTIONS_APP_ID = 15368;
export const REQUIRED_CHECKS = Object.freeze([
  'Linux / Node 24 / Chromium / packaged consumers',
  ...['3.11', '3.12', '3.13'].map(version => `Linux / Python ${version} / Browser Use / Chromium`),
]);

const hasLabel = pr => pr.labels?.some(label => label.name === LABEL) === true;
const isBotQueue = pr => pr.auto_merge?.enabled_by?.login === 'github-actions[bot]';
const validNumber = number => Number.isSafeInteger(number) && number > 0;
const exec = promisify(execFile);

export function requiredChecksProtected(rules) {
  // Requiring these checks on GitHub prevents a queued merge from running
  // early, on an older commit, or after the base branch moves forward.
  return rules.some(rule => rule.type === 'required_status_checks'
    && rule.parameters?.strict_required_status_checks_policy === true
    && REQUIRED_CHECKS.every(name => rule.parameters.required_status_checks?.some(check =>
      check.context === name && check.integration_id === ACTIONS_APP_ID)));
}

export async function latestOptIn(api, repository, number) {
  let latest = null;
  for (let page = 1; page <= 20; page++) {
    const events = await api(`repos/${repository}/issues/${number}/events?per_page=100&page=${page}`);
    if (!Array.isArray(events)) throw new Error('Unexpected label-event response.');
    for (const event of events) {
      if (['labeled', 'unlabeled'].includes(event.event) && event.label?.name === LABEL
        && (!latest || event.id > latest.id)) latest = event;
    }
    if (events.length < 100) return latest?.event === 'labeled' ? latest : null;
  }
  throw new Error('Label history exceeds the review limit; no merge was requested.');
}

export async function reconcile({ api, merge, repository, number, cancelRequested = false, dryRun = true }) {
  if (!/^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(repository) || !validNumber(number)) {
    throw new Error('A repository and positive pull-request number are required.');
  }
  const route = `repos/${repository}`;
  let pr = await api(`${route}/pulls/${number}`);
  const result = (action, reason) => ({ number, action, reason });
  if (pr.state !== 'open' || pr.merged) return result('skip', 'Pull request is not open.');
  const repo = await api(route);
  const eligible = candidate => candidate.state === 'open' && !candidate.merged && !candidate.draft
    && candidate.base?.ref === repo.default_branch && candidate.base?.repo?.full_name === repository
    && hasLabel(candidate);

  async function disable(reason) {
    // Re-read to avoid acting on an old unlabeled/draft event after a new opt-in.
    const current = await api(`${route}/pulls/${number}`);
    if (current.state !== 'open' || !current.auto_merge || eligible(current)) return result('skip', 'No cancellation needed.');
    if (dryRun) return result('would-disable', reason);
    await merge(['pr', 'merge', String(number), '--repo', repository, '--disable-auto']);
    return result('disabled', reason);
  }

  if (!eligible(pr)) {
    if (pr.auto_merge && (cancelRequested || isBotQueue(pr))) {
      return disable('Opt-in removed, PR converted to draft, or target branch changed.');
    }
    return result('skip', 'Requires the auto-merge label, a ready PR, and the default target branch.');
  }
  if (!repo.allow_auto_merge || !repo.allow_squash_merge) {
    return result('blocked', 'Enable repository auto-merge and squash merging first.');
  }
  const rules = await api(`${route}/rules/branches/${encodeURIComponent(repo.default_branch)}?per_page=100`);
  if (!Array.isArray(rules) || !requiredChecksProtected(rules)) {
    return result('blocked', 'All four CI checks must be required from GitHub Actions, with an up-to-date branch.');
  }
  const optIn = await latestOptIn(api, repository, number);
  if (!optIn?.actor?.login) return result('blocked', 'No current label authorization found.');
  const permission = await api(`${route}/collaborators/${encodeURIComponent(optIn.actor.login)}/permission`);
  if (!['write', 'maintain', 'admin'].includes(permission.permission)) {
    return result('blocked', 'The auto-merge label must be applied by a maintainer with write access.');
  }
  const head = pr.head?.sha;
  if (!/^[a-f0-9]{40}$/.test(head || '')) throw new Error('Unexpected pull-request head.');
  pr = await api(`${route}/pulls/${number}`);
  const currentOptIn = await latestOptIn(api, repository, number);
  if (!eligible(pr) || pr.head?.sha !== head || currentOptIn?.id !== optIn.id) {
    return result('skip', 'The PR or its label changed during the check; retry on the next event.');
  }
  if (pr.auto_merge) return result('queued', 'GitHub is already waiting for the required checks and branch rules.');
  if (dryRun) return result('would-enable', 'Authorized label and required CI protections verified.');
  await merge(['pr', 'merge', String(number), '--repo', repository, '--auto', '--squash', '--match-head-commit', head]);
  return result('requested', 'GitHub will squash-merge only when the required checks and branch rules are satisfied.');
}

export function requestFromEvent(name, event) {
  if (name === 'pull_request_target') return {
    number: event.pull_request?.number,
    cancelRequested: (event.action === 'unlabeled' && event.label?.name === LABEL)
      || event.action === 'converted_to_draft' || event.action === 'edited',
    dryRun: false,
  };
  if (name === 'workflow_dispatch') {
    const raw = event.inputs?.pull_number;
    if (!/^[1-9][0-9]*$/.test(String(raw || ''))) throw new Error('Enter one positive pull-request number.');
    return { number: Number(raw), dryRun: event.inputs?.dry_run !== 'false' && event.inputs?.dry_run !== false };
  }
  throw new Error('Unsupported event; no merge was requested.');
}

async function gh(args) {
  try {
    return (await exec('gh', args, { timeout: 60000, maxBuffer: 8 * 1024 * 1024,
      env: { ...process.env, GH_PROMPT_DISABLED: '1' } })).stdout;
  } catch {
    // Do not expose credentials or untrusted CLI output in logs.
    throw new Error('GitHub operation failed. Inspect the PR checks, rules, and workflow permissions.');
  }
}

async function main() {
  const event = JSON.parse(await readFile(process.env.GITHUB_EVENT_PATH, 'utf8'));
  const request = requestFromEvent(process.env.GITHUB_EVENT_NAME, event);
  const outcome = await reconcile({ ...request, repository: process.env.GITHUB_REPOSITORY,
    api: async route => JSON.parse(await gh(['api', route, '--method', 'GET'])), merge: gh });
  const summary = `PR #${outcome.number}: **${outcome.action}**. ${outcome.reason}\n`;
  process.stdout.write(summary);
  if (process.env.GITHUB_STEP_SUMMARY) await appendFile(process.env.GITHUB_STEP_SUMMARY, summary);
  if (outcome.action === 'blocked') process.exitCode = 1;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main().catch(() => {
    process.stderr.write('Auto-merge did not complete. Check label authorization, required CI protection, and GitHub permissions.\n');
    process.exitCode = 1;
  });
}
