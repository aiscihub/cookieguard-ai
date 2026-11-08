# Automatic PR merging

A maintainer can opt a ready PR into automatic squash merging by adding the
`auto-merge` label. The PR must target `main`. GitHub waits for the required CI
checks and branch rules before merging. No AI model, Anthropic service, external
API key, or automated review approval is involved.

## Use it

1. Open a PR and finish any review you want before opting in.
2. Add `auto-merge` using an account with write, maintain, or admin access.
3. Check the **Merge labeled PRs after CI** workflow. Its job summary reports
   whether auto-merge was requested or why the PR is ineligible.
4. GitHub squash-merges when the required checks pass and the branch is current.

The label remains an opt-in for subsequent commits on that PR. New commits must
pass CI again. If `main` advances, update the PR branch and let CI rerun. The bot
does not update branches or resolve conflicts for you. If GitHub disables
auto-merge after a contributor without write access pushes, the next PR event
can restore it while a valid maintainer label remains.

To cancel, remove `auto-merge` and wait for the label workflow to report
`disabled`. Label events are asynchronous: for immediate cancellation, use
**Disable auto-merge** on the PR, then remove the label. Converting to draft or
changing the target away from `main` also makes the PR ineligible. Cancellation
cannot undo a merge that has already completed.

## Required CI

The active `main_protection` ruleset requires these checks from the GitHub
Actions app, with **Require branches to be up to date before merging** enabled:

| Required check | Coverage |
| --- | --- |
| `Linux / Node 24 / Chromium / packaged consumers` | JavaScript, Playwright, packages, release checks |
| `Linux / Python 3.11 / Browser Use / Chromium` | Python 3.11 integration and browser checks |
| `Linux / Python 3.12 / Browser Use / Chromium` | Python 3.12 integration and browser checks |
| `Linux / Python 3.13 / Browser Use / Chromium` | Python 3.13 integration and browser checks |

Failed, cancelled, or unfinished required checks block merging. GitHub also
accepts `skipped` and `neutral` check conclusions under its
[native status-check rules](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks);
the current four CI jobs run unconditionally. A maintainer should review
changes to CI definitions before applying the label. Keep required check names
in the ruleset and `scripts/pr-auto-merge.mjs` aligned if CI jobs are renamed.

The bot verifies the active required-check rules before requesting auto-merge.
It does not bypass additional branch requirements, approve reviews, publish
packages, or use an administrator override. The label is the maintainer's merge
authorization; this workflow does not assess code quality beyond CI.

## Diagnose a waiting PR

- **No label or draft:** finish the PR and add `auto-merge` when it is ready.
- **Failed or pending CI:** inspect the required check; fix the failure or wait
  for completion. A cancelled check needs another run.
- **Branch behind or conflicts:** update the branch and resolve conflicts.
- **`blocked` job summary:** check label-author permissions, repository
  auto-merge/squash settings, and required-check rules.
- **No workflow run after a bot added the label:** `GITHUB_TOKEN`-generated label
  events do not trigger another workflow. Apply the label as a maintainer or
  use the manual dispatch below.

For a read-only eligibility check, open **Actions → Merge labeled PRs after CI
→ Run workflow**, select `main`, enter the PR number, and leave **dry_run**
enabled. Disable **dry_run** to reconcile the current label with auto-merge.
Manual runs still enforce the same label, permission, and branch requirements.

## Implementation and permissions

The workflow checks out only the trusted default branch, with credential
persistence disabled. It runs no PR code or dependency installation. The
built-in `GITHUB_TOKEN` has only `contents: write` and `pull-requests: write`;
the repository's default token remains read-only. GitHub Actions review
approvals remain disabled.

The script checks the latest label event and the label author's current write
permission, then rechecks the PR head and label before requesting auto-merge
with `--match-head-commit`. GitHub enforces required checks on the current PR.
Removing a label and disabling native auto-merge are separate operations, so
use the native disable control when cancellation timing matters.

A merge performed with `GITHUB_TOKEN` may not trigger later `push` or
`pull_request: closed` workflows. This does not skip the required PR checks.
Do not rely on this bot to start a release or deployment; those need their own
explicit trigger. See GitHub's [workflow trigger rules](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow).

To disable this automation, disable **Merge labeled PRs after CI** and cancel
any already-pending native auto-merge requests. Disabling the workflow alone
does not cancel GitHub's existing requests. Keep the required CI branch rules.
