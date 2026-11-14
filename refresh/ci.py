"""Actions orchestration. Remote writes are guarded and are never used by local runs."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from common import ROOT, die, load, month_seed, sha, write_json
from health import assess_coverage, included_privacy_passed
from resume import build_plan, prefixes, stage_plan, source_paths, run_id, plan_report

RUN = ROOT / 'refresh/.work/run'
SOURCE = ROOT / 'refresh/.work/source'

def action_only():
    if (os.environ.get('GITHUB_ACTIONS') != 'true' or os.environ.get('GITHUB_REF') != 'refs/heads/main'
        or os.environ.get('GITHUB_RUN_ATTEMPT') != '1'):
        raise ValueError('actions-main-first-attempt-only')
    repo = os.environ.get('GITHUB_REPOSITORY', '')
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo):
        raise ValueError('invalid-repository')
    return repo

def quiet(command, *, env=None, data=None, raw=False):
    result = subprocess.run(command, cwd=ROOT, env=env, input=data, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, check=False)
    if result.returncode:
        raise ValueError('subprocess-failed')
    return result.stdout if raw else result.stdout.decode().strip()

def git(*args, **kwargs):
    return quiet(['git', *args], **kwargs)

def gh(*args, **kwargs):
    return quiet(['gh', *args], **kwargs)

def create_branch(branch, files):
    """Create a branch from origin/main using a private index; never switch this checkout."""
    action_only()
    if not re.fullmatch(r'refresh/(?:reservations/\d{4}-\d{2}(?:-pilot)?|(?:data|model)/\d{4}-\d{2}|resumes/[1-9]\d{0,19})', branch):
        raise ValueError('invalid-branch')
    with tempfile.TemporaryDirectory() as temp:
        # GitHub's official Actions bot; the numeric ID avoids attributing automation to another user.
        env = dict(os.environ, GIT_INDEX_FILE=str(Path(temp) / 'index'),
                   GIT_AUTHOR_NAME='github-actions[bot]', GIT_AUTHOR_EMAIL='41898282+github-actions[bot]@users.noreply.github.com',
                   GIT_COMMITTER_NAME='github-actions[bot]', GIT_COMMITTER_EMAIL='41898282+github-actions[bot]@users.noreply.github.com')
        base = git('rev-parse', 'origin/main')
        git('read-tree', base, env=env)
        git('add', '--', *files, env=env)
        tree = git('write-tree', env=env)
        commit = git('commit-tree', tree, '-p', base, env=env, data=('Monthly refresh: ' + branch + '\n').encode())
        # GH_TOKEN is supplied by Actions only. Never embed it in arguments or remote URLs.
        # Empty expected ref forbids overwriting any existing branch, including reruns.
        git('-c', 'credential.helper=', '-c', 'credential.helper=!gh auth git-credential',
            'push', '--force-with-lease=refs/heads/' + branch + ':', 'origin',
            commit + ':refs/heads/' + branch, env=env)
        return commit

def protected_auto_merge(repo):
    settings = json.loads(gh('api', 'repos/' + repo))
    rules = json.loads(gh('api', 'repos/' + repo + '/rules/branches/main?per_page=100'))
    required = ['Linux / Node 24 / Chromium / packaged consumers'] + [
        'Linux / Python ' + version + ' / Browser Use / Chromium' for version in ['3.11', '3.12', '3.13']]
    protected = any(rule.get('type') == 'required_status_checks' and
                    rule['parameters'].get('strict_required_status_checks_policy') is True and
                    all(any(check.get('context') == name and check.get('integration_id') == 15368
                            for check in rule['parameters'].get('required_status_checks', [])) for name in required)
                    for rule in rules)
    return settings.get('allow_auto_merge') and settings.get('allow_squash_merge') and protected

def reservation_branch(month, dry_run):
    month_seed(month)
    return 'refresh/reservations/' + month + ('-pilot' if dry_run else '')

def reservation_bytes(repo, ref):
    # A 10,000-site frame can exceed the Contents API's inline base64 size limit.
    # Raw media preserves the bytes (including newlines) for the exact comparison.
    return gh('api', 'repos/' + repo + '/contents/refresh/reservation.json?ref=' + ref,
              '--header', 'Accept: application/vnd.github.raw+json', raw=True)

def prior_reservations(repo):
    refs = gh('api', '--paginate', 'repos/' + repo + '/git/matching-refs/heads/refresh/reservations/',
              '--jq', '.[].ref').splitlines()
    domains = set()
    for ref in refs:
        if not re.fullmatch(r'refs/heads/refresh/reservations/\d{4}-\d{2}(?:-pilot)?', ref):
            raise ValueError('invalid-reservation-ref')
        record = json.loads(reservation_bytes(repo, ref))
        domains.update(site['domain'] for site in record['frame'])
    return domains

def prepare():
    repo = action_only()
    event = load(Path(os.environ['GITHUB_EVENT_PATH']))
    inputs = event.get('inputs', {})
    if inputs.get('resume_run') or inputs.get('evaluate_run'):
        raise ValueError('resume-cannot-prepare-new-frame')
    scheduled = os.environ['GITHUB_EVENT_NAME'] == 'schedule'
    sites, shards = int(inputs.get('sites', 10000)), int(inputs.get('shards', 16))
    dry = False if scheduled else str(inputs.get('dry_run', 'true')).lower() == 'true'
    if not 1 <= shards <= 16 or not shards <= sites <= 10000:
        raise ValueError('invalid-size')
    month = datetime.now(timezone.utc).strftime('%Y-%m')
    month_seed(month)
    # Check the owner's explicit asset approval before ranking downloads or site visits.
    quiet([sys.executable, 'refresh/fetch_training.py'])
    RUN.mkdir(parents=True, exist_ok=True)
    domains = set((ROOT / 'refresh/state/crawled_domains.txt').read_text().splitlines())
    domains.update(prior_reservations(repo))
    history = RUN / 'history-exclusions.txt'
    history.write_text('\n'.join(sorted(domains)) + '\n')
    command = ['node', 'refresh/frame.mjs', '--month', month, '--sites', str(sites), '--shards', str(shards),
               '--state', str(history), '--out', str(RUN)]
    if dry:
        command.append('--dry-run')
    quiet(command)
    # Reserve the whole frame before any browser visit. Failed/cancelled runs also count.
    # Separate pilot and real reservations; both join every subsequent exclusion set.
    branch = reservation_branch(month, dry)
    shutil.copyfile(RUN / 'frame.json', ROOT / 'refresh/reservation.json')
    create_branch(branch, ['refresh/reservation.json'])
    first = not any(e.get('kind') == 'monthly' and not e.get('dryRun')
                    for e in load(ROOT / 'data/releases/index.json')['releases'])
    write_json(RUN / 'workflow.json', {'month': month, 'dryRun': dry, 'firstRealRun': first,
                                     'reservationBranch': branch,
                                     'sourceCommit': git('rev-parse', 'HEAD')})
    with open(os.environ['GITHUB_OUTPUT'], 'a') as output:
        output.write('month=' + month + '\ndry_run=' + str(dry).lower() + '\nmatrix=' +
                     json.dumps({'shard': list(range(1, shards + 1))}) + '\nshards=' + str(shards) + '\n')

def resume(visited_prefix=None):
    """Verify a saved frame and stage a single resume; only later shard jobs may visit sites."""
    repo = action_only()
    inputs = load(Path(os.environ['GITHUB_EVENT_PATH'])).get('inputs', {})
    if inputs.get('evaluate_run'):
        raise ValueError('incompatible-recovery-inputs')
    source = run_id(inputs.get('resume_run'))
    overrides = prefixes(' '.join([inputs.get('visited_prefix', ''), *(visited_prefix or [])]))
    branch = 'refresh/resumes/' + source
    refs = gh('api', 'repos/' + repo + '/git/matching-refs/heads/' + branch, '--jq', '.[].ref').splitlines()
    if 'refs/heads/' + branch in refs:
        raise ValueError('source-run-already-resumed')
    frame_dir, _ = source_paths(SOURCE)
    frame, workflow = load(frame_dir / 'frame.json'), load(frame_dir / 'workflow.json')
    month = frame['month']
    reservation = reservation_branch(month, False)
    if (frame.get('dryRun') is not False or (frame_dir / 'frame.json').read_bytes() != reservation_bytes(repo, reservation) or
        workflow.get('month') != month or workflow.get('dryRun') is not False or
        workflow.get('reservationBranch') != reservation or type(workflow.get('firstRealRun')) is not bool or
        not re.fullmatch(r'[0-9a-f]{40}', workflow.get('sourceCommit', ''))):
        raise ValueError('resume-reservation-mismatch')
    plan, payloads = build_plan(SOURCE, source, overrides)
    stage_plan(SOURCE, RUN, plan, payloads)
    current = git('rev-parse', 'HEAD')
    record = {'schemaVersion': 1, 'sourceRun': source, 'month': month, 'frameSha256': plan['frameSha256'],
              'reservationBranch': reservation, 'sourceCommit': workflow['sourceCommit'], 'resumeCommit': current,
              'planSha256': sha(RUN / 'resume-plan.json'), 'visitedPrefixOverrides': plan['visitedPrefixOverrides']}
    write_json(ROOT / 'refresh/resume.json', record)
    # Empty expected ref is the atomic guard, including two resumes racing the read above.
    create_branch(branch, ['refresh/resume.json'])
    first = workflow['firstRealRun'] or not any(e.get('kind') == 'monthly' and not e.get('dryRun')
                                               for e in load(ROOT / 'data/releases/index.json')['releases'])
    write_json(RUN / 'resume.json', record)
    write_json(RUN / 'workflow.json', {**workflow, 'firstRealRun': first, 'sourceCommit': current, 'resumeRun': source})
    (RUN / 'RESUME_PLAN.md').write_text(plan_report(plan))
    pending = [s['shard'] for s in plan['shards'] if s['remaining']]
    with open(os.environ['GITHUB_OUTPUT'], 'a') as output:
        output.write('month=' + month + '\ndry_run=false\nshards=' + str(frame['shards']) +
                     '\nmatrix=' + json.dumps({'shard': pending}) + '\nhas_work=' + str(bool(pending)).lower() + '\n')


def recover():
    """Stage saved artifacts for evaluation; never reserve a frame or launch a crawler."""
    repo = action_only()
    inputs = load(Path(os.environ['GITHUB_EVENT_PATH'])).get('inputs', {})
    if inputs.get('resume_run') or inputs.get('visited_prefix'):
        raise ValueError('incompatible-recovery-inputs')
    source = run_id(inputs.get('evaluate_run'))
    frame_dir, shards_dir = source_paths(SOURCE)
    frame, workflow = load(frame_dir / 'frame.json'), load(frame_dir / 'workflow.json')
    month = frame['month']
    reservation = reservation_branch(month, False)
    remote = json.loads(gh('api', 'repos/' + repo + '/actions/runs/' + source))
    if (remote.get('status') != 'completed' or remote.get('head_branch') != 'main' or
        remote.get('path') != '.github/workflows/monthly-refresh.yml' or
        remote.get('head_sha') != workflow.get('sourceCommit') or
        not re.fullmatch(r'[0-9a-f]{40}', workflow.get('sourceCommit', '')) or
        frame.get('dryRun') is not False or workflow.get('dryRun') is not False or
        workflow.get('month') != month or type(workflow.get('firstRealRun')) is not bool or
        workflow.get('reservationBranch') != reservation or
        (frame_dir / 'frame.json').read_bytes() != reservation_bytes(repo, reservation)):
        raise ValueError('evaluation-source-mismatch')
    if RUN.exists():
        raise ValueError('evaluation-output-already-exists')
    RUN.mkdir(parents=True)
    for name in ('frame.json', 'workflow.json', 'exclusions.txt', 'history-exclusions.txt', 'ranking.csv',
                 'resume.json', 'resume-plan.json', 'RESUME_PLAN.md'):
        if (frame_dir / name).exists():
            shutil.copyfile(frame_dir / name, RUN / name)
    # A resumed run carries completed shards in its frame artifact and emits only
    # newly completed shards separately. Select whole directories, never mix files.
    for shard in range(1, frame['shards'] + 1):
        name = 'shard-' + str(shard)
        folder = shards_dir / name
        if not folder.exists():
            folder = frame_dir / 'shards' / name
        if folder.exists():
            shutil.copytree(folder, RUN / 'shards' / name)
        inherited = frame_dir / 'resume-inputs' / name
        if inherited.exists():
            shutil.copytree(inherited, RUN / 'resume-inputs' / name)
    # Merge and the full privacy audit still validate every included receipt,
    # digest and kept-prefix proof before any deliverable is uploaded or published.
    current = git('rev-parse', 'HEAD')
    first = workflow['firstRealRun'] or not any(e.get('kind') == 'monthly' and not e.get('dryRun')
                                               for e in load(ROOT / 'data/releases/index.json')['releases'])
    write_json(RUN / 'recovery.json', {'schemaVersion': 1, 'sourceRun': source,
               'sourceCommit': workflow['sourceCommit'], 'evaluationCommit': current,
               'frameSha256': sha(RUN / 'frame.json'), 'mode': 'evaluation-only'})
    write_json(RUN / 'workflow.json', {**workflow, 'firstRealRun': first,
                                     'sourceCommit': current, 'evaluateRun': source})
    with open(os.environ['GITHUB_OUTPUT'], 'a') as output:
        output.write('month=' + month + '\ndry_run=false\n')
    with open(os.environ['GITHUB_ENV'], 'a') as output:
        output.write('REFRESH_MONTH=' + month + '\n')


def dataset_policy(gate, first):
    healthy = gate.get('gates', {}).get('Health', {}).get('passed') is True
    return {'label': healthy, 'auto': healthy and not first}

def pr_body(kind, first, gate, report):
    warning = ('Health gate failed: a person must review this release.\n\n'
               if kind == 'data' and not dataset_policy(gate, first)['label'] else '')
    description = ('Timestamped cookie dataset; every exported row passed the privacy checks.\n\n' if kind == 'data' else
                   'Optional lookup and model artifacts for human review. Every fixed gate passed; package defaults are unchanged.\n\n')
    checkpoint = 'Checkpoint 2: this first-run PR is a draft. Owner review is required before either PR can merge.\n\n' if first else ''
    return warning + description + checkpoint + report

def publish():
    repo = action_only()
    frame, workflow, audit, gate = [load(RUN / name) for name in
                                   ['frame.json', 'workflow.json', 'privacy-audit.json', 'gate.json']]
    month = frame['month']
    month_seed(month)
    release = ROOT / 'data/releases' / month
    manifest = load(release / 'manifest.json')
    if frame['dryRun'] or workflow['dryRun'] or manifest['dryRun']:
        raise ValueError('dry-run-cannot-publish')
    if (not audit['passed'] or not manifest['privacyPassed'] or not manifest['structuralPassed'] or
        not included_privacy_passed(manifest)):
        raise ValueError('privacy-gate-required-for-publication')
    if not assess_coverage(manifest)['passed']:
        raise ValueError('too-many-excluded-sites')
    if workflow['sourceCommit'] != git('rev-parse', 'HEAD'):
        raise ValueError('source-changed')
    # Verify every audited output again immediately before any push or PR.
    for record in audit['files']:
        if sha(ROOT / record['path']) != record['sha256']:
            raise ValueError('output-changed-after-audit')
    first = workflow['firstRealRun']
    plans = [('data', ['data/releases/' + month, 'data/releases/index.json', 'refresh/state/crawled_domains.txt'])]
    if gate['eligibleForModelPR'] and gate['allGatesPassed']:
        model_dest = ROOT / 'models/releases' / month
        shutil.copytree(RUN / 'candidate', model_dest)
        plans.append(('model', ['models/releases/' + month]))
    receipts = []
    for kind, files in plans:
        branch = 'refresh/' + kind + '/' + month
        head = create_branch(branch, files)
        body = RUN / (kind + '-pr.md')
        body.write_text(pr_body(kind, first, gate, (RUN / 'REPORT.md').read_text()))
        command = ['pr', 'create', '--repo', repo, '--base', 'main', '--head', branch,
                   '--title', 'Monthly ' + kind + ' refresh: ' + month, '--body-file', str(body)]
        if first:
            command.append('--draft')
        if kind == 'data' and dataset_policy(gate, first)['label']:
            # Idempotently ensure the requested label exists; no model PR gets this label.
            gh('label', 'create', 'auto-merge', '--repo', repo, '--color', '0e8a16', '--force')
            command.extend(['--label', 'auto-merge'])
        url = gh(*command)
        # GITHUB_TOKEN-created PRs do not trigger pull_request CI. Explicit dispatch does.
        gh('workflow', 'run', 'cookieguard-ci.yml', '--repo', repo, '--ref', branch)
        auto = kind == 'data' and dataset_policy(gate, first)['auto'] and protected_auto_merge(repo)
        if auto:
            gh('pr', 'merge', url, '--auto', '--squash', '--match-head-commit', head, '--repo', repo)
        receipts.append({'kind': kind, 'url': url, 'draft': first, 'autoMergeRequested': bool(auto)})
    write_json(RUN / 'publication.json', {'pullRequests': receipts, 'humanModelApprovalRequired': True})

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=['prepare', 'resume', 'recover', 'publish'])
    parser.add_argument('--visited-prefix', action='append', default=[])
    args = parser.parse_args()
    stage = args.stage
    if stage == 'resume':
        resume(args.visited_prefix)
    else:
        {'prepare': prepare, 'recover': recover, 'publish': publish}[stage]()
    print(json.dumps({'stage': stage, 'completed': True}))

if __name__ == '__main__':
    try: main()
    except Exception: sys.exit(die())
