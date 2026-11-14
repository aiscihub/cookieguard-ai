"""Actions orchestration. Remote writes are guarded and are never used by local runs."""
from __future__ import annotations
import argparse
import base64
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

RUN = ROOT / 'refresh/.work/run'

def action_only():
    if (os.environ.get('GITHUB_ACTIONS') != 'true' or os.environ.get('GITHUB_REF') != 'refs/heads/main'
        or os.environ.get('GITHUB_RUN_ATTEMPT') != '1'):
        raise ValueError('actions-main-first-attempt-only')
    repo = os.environ.get('GITHUB_REPOSITORY', '')
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo):
        raise ValueError('invalid-repository')
    return repo

def quiet(command, *, env=None, data=None):
    result = subprocess.run(command, cwd=ROOT, env=env, input=data, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, check=False)
    if result.returncode:
        raise ValueError('subprocess-failed')
    return result.stdout.decode().strip()

def git(*args, **kwargs):
    return quiet(['git', *args], **kwargs)

def gh(*args, **kwargs):
    return quiet(['gh', *args], **kwargs)

def create_branch(branch, files):
    """Create a branch from origin/main using a private index; never switch this checkout."""
    action_only()
    if not re.fullmatch(r'refresh/(?:reservations/\d{4}-\d{2}(?:-pilot)?|(?:data|model)/\d{4}-\d{2})', branch):
        raise ValueError('invalid-branch')
    with tempfile.TemporaryDirectory() as temp:
        env = dict(os.environ, GIT_INDEX_FILE=str(Path(temp) / 'index'),
                   GIT_AUTHOR_NAME='CookieGuard refresh', GIT_AUTHOR_EMAIL='refresh@users.noreply.github.com',
                   GIT_COMMITTER_NAME='CookieGuard refresh', GIT_COMMITTER_EMAIL='refresh@users.noreply.github.com')
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

def prior_reservations(repo):
    refs = gh('api', '--paginate', 'repos/' + repo + '/git/matching-refs/heads/refresh/reservations/',
              '--jq', '.[].ref').splitlines()
    domains = set()
    for ref in refs:
        if not re.fullmatch(r'refs/heads/refresh/reservations/\d{4}-\d{2}(?:-pilot)?', ref):
            raise ValueError('invalid-reservation-ref')
        encoded = gh('api', 'repos/' + repo + '/contents/refresh/reservation.json?ref=' + ref,
                     '--jq', '.content')
        record = json.loads(base64.b64decode(encoded))
        domains.update(site['domain'] for site in record['frame'])
    return domains

def prepare():
    repo = action_only()
    event = load(Path(os.environ['GITHUB_EVENT_PATH']))
    inputs = event.get('inputs', {})
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
    if not audit['passed'] or not manifest['privacyPassed'] or not manifest['complete']:
        raise ValueError('privacy-gate-required-for-publication')
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
    parser.add_argument('stage', choices=['prepare', 'publish'])
    stage = parser.parse_args().stage
    (prepare if stage == 'prepare' else publish)()
    print(json.dumps({'stage': stage, 'completed': True}))

if __name__ == '__main__':
    try: main()
    except Exception: sys.exit(die())
