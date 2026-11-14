"""Plan a resume from immutable artifacts. This module never makes network requests."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
from common import ROOT, die, load, month_seed, sha, structural, validate_row, write_json
from health import attempt_metrics

RULE = 'Resume crawls only remainingSiteIds; recorded and visitedNotRecorded sites are never revisited.'
PASSED = {'passed': True, 'structuralPassed': True, 'crossScanPassed': True}

def digest(data):
    return hashlib.sha256(data).hexdigest()

def run_id(value):
    if not isinstance(value, str) or not re.fullmatch(r'[1-9]\d{0,19}', value):
        raise ValueError('invalid-source-run')
    return value

def prefixes(text):
    result = {}
    for item in text.split():
        if not re.fullmatch(r'[1-9]\d*=\d+', item):
            raise ValueError('invalid-visited-prefix')
        shard, count = map(int, item.split('='))
        if shard in result:
            raise ValueError('duplicate-visited-prefix')
        result[shard] = count
    return result

def source_paths(source):
    source = Path(source)
    frame = source / 'frame' if (source / 'frame/frame.json').exists() else source
    shards = source / 'shards' if (source / 'shards').exists() else source
    return frame, shards

def privacy_passed(receipt):
    return all(receipt.get('privacy', {}).get(key) is True for key in PASSED)

def validate_prefix(frame, shard, attempts, records):
    expected = [s for s in frame['frame'] if s['shard'] == shard]
    if len(attempts) > len(expected) or not structural(attempts):
        raise ValueError('invalid-recorded-prefix')
    for site, attempt in zip(expected, attempts):
        if any(site[key] != attempt.get(key) for key in ('siteId', 'domain', 'rank', 'shard')):
            raise ValueError('recorded-attempts-not-frame-prefix')
    attempt_metrics(attempts)
    usable = {a['rank'] for a in attempts if a['status'] == 'usable'}
    identities = set()
    for row in records:
        validate_row(row)
        identity = (row['rank'], row['name'], row['domain'], row['path'])
        if row['rank'] not in usable or row['trancoListId'] != frame['trancoListId'] or identity in identities:
            raise ValueError('recorded-row-provenance')
        identities.add(identity)
    if {r['rank'] for r in records} != usable:
        raise ValueError('recorded-usable-count')

def skipped_attempt(site):
    # The request may have reached the site, but no document/robots outcome survived.
    return {**site, 'status': 'visited-not-recorded', 'visited': False, 'robotsStatus': 'not-checked',
            'cmp': 'none', 'counts': {'observedCookies': 0, 'unmatchedDeclarations': 0, 'duplicateObservations': 0}}

def build_plan(source, source_run, overrides=None):
    source_run = run_id(source_run)
    overrides = overrides or {}
    frame_dir, shards_dir = source_paths(source)
    frame, workflow = load(frame_dir / 'frame.json'), load(frame_dir / 'workflow.json')
    month_seed(frame['month'])
    if (frame['dryRun'] is not False or len(frame['frame']) != frame['sites'] or
        len({s['siteId'] for s in frame['frame']}) != frame['sites'] or
        any(s['shard'] not in range(1, frame['shards'] + 1) for s in frame['frame']) or
        any(s not in range(1, frame['shards'] + 1) for s in overrides)):
        raise ValueError('invalid-resume-frame')
    frame_hash = sha(frame_dir / 'frame.json')
    # scripts/build.js copies these exact tracked bytes to the vendor engine.
    # Planning runs before npm installation on a fresh Actions checkout.
    engine_hash = sha(ROOT / 'extension-standalone/engine.js')
    features = load(ROOT / 'refresh/reference/feature_names.json')['featureNames']
    plan = {'schemaVersion': 1, 'sourceRun': source_run, 'month': frame['month'], 'frameSha256': frame_hash,
            'rule': RULE, 'visitedPrefixOverrides': {str(k): v for k, v in sorted(overrides.items())}, 'shards': []}
    payloads = {}
    for shard in range(1, frame['shards'] + 1):
        name = 'shard-' + str(shard)
        folder = shards_dir / name
        # A source run may itself be a resume: completed shards travel in its frame artifact.
        if not folder.exists() and (frame_dir / 'shards' / name).exists():
            folder = frame_dir / 'shards' / name
        inherited_dir = frame_dir / 'resume-inputs' / name
        inherited = not folder.exists() and inherited_dir.exists()
        sites = [s for s in frame['frame'] if s['shard'] == shard]
        ids = [s['siteId'] for s in sites]
        receipt = load(folder / 'receipt.json') if (folder / 'receipt.json').exists() else None
        ledger = load(folder / 'visited.json') if (folder / 'visited.json').exists() else None
        checkpoint = (load(folder / 'checkpoint.json') if (folder / 'checkpoint.json').exists() and
                      not (receipt and receipt.get('status') == 'failed-closed') else None)
        started = (folder / 'started.json').exists()
        if inherited:
            prior = load(inherited_dir / 'plan.json')
            a_bytes = (inherited_dir / 'kept-attempts.json').read_bytes()
            r_bytes = (inherited_dir / 'kept-cookies.jsonl').read_bytes()
            if (prior['frameSha256'] != frame_hash or prior['shard'] != shard or
                digest(a_bytes) != prior['keptAttemptsSha256'] or digest(r_bytes) != prior['keptRowsSha256'] or
                not 0 <= prior['recorded'] <= prior['visitedPrefix'] <= len(sites) or
                not all(prior['keptPrivacy'].get(k) is True for k in PASSED)):
                raise ValueError('invalid-inherited-resume-prefix')
            kept = json.loads(a_bytes)
            if len(kept) != prior['recorded']:
                raise ValueError('invalid-inherited-recorded-count')
            checkpoint = {'shard': shard, 'frameSha256': frame_hash, 'engineSha256': engine_hash, 'featureNames': features,
                          'attempts': kept + [skipped_attempt(site) for site in sites[prior['recorded']:prior['visitedPrefix']]],
                          'rows': [json.loads(line) for line in r_bytes.splitlines() if line.strip()], 'privacy': prior['keptPrivacy']}
            ledger = {'schemaVersion': 1, 'shard': shard, 'frameSha256': frame_hash, 'siteIds': ids[:prior['visitedPrefix']]}
        state = ('failed-closed' if receipt and receipt.get('status') == 'failed-closed' else
                 'complete' if receipt else 'interrupted' if started or ledger or checkpoint or
                 (folder / 'attempts.json').exists() or (folder / 'cookies.jsonl').exists() else 'never-started')
        attempts, records = [], []
        attempts_bytes, rows_bytes = b'[]\n', b''
        kept_privacy = {**PASSED, 'evidence': 'empty-prefix'}
        if receipt:
            if (not structural(receipt) or receipt.get('shard') != shard or receipt.get('frameSha256') != frame_hash or
                receipt.get('of') != frame['shards'] or receipt.get('month') != frame['month']):
                raise ValueError('source-receipt-provenance')
            if state == 'failed-closed' and receipt.get('privacy', {}).get('passed') is not False:
                raise ValueError('invalid-failed-receipt')
        if state in ('complete', 'interrupted'):
            if checkpoint and state == 'interrupted':
                if (not structural(checkpoint) or not privacy_passed(checkpoint) or checkpoint.get('shard') != shard or
                    checkpoint.get('frameSha256') != frame_hash or checkpoint.get('engineSha256') != engine_hash or
                    checkpoint.get('featureNames') != features):
                    raise ValueError('invalid-batch-checkpoint')
                attempts, records = checkpoint['attempts'], checkpoint['rows']
                attempts_bytes = (json.dumps(attempts, separators=(',', ':'), ensure_ascii=False) + '\n').encode()
                rows_bytes = ''.join(json.dumps(r, separators=(',', ':'), ensure_ascii=False) + '\n' for r in records).encode()
                kept_privacy = {**checkpoint['privacy'], 'evidence': 'inherited-resume-prefix' if inherited else 'atomic-batch-checkpoint'}
            elif (folder / 'attempts.json').exists() or (folder / 'cookies.jsonl').exists():
                attempts_bytes = (folder / 'attempts.json').read_bytes()
                rows_bytes = (folder / 'cookies.jsonl').read_bytes()
                attempts = json.loads(attempts_bytes)
                records = [json.loads(line) for line in rows_bytes.splitlines() if line.strip()]
                kept_privacy = {**PASSED, 'evidence': 'legacy-incremental-batch-check', 'sourceCommit': workflow['sourceCommit']}
            validate_prefix(frame, shard, attempts, records)
            if state == 'complete':
                if (not privacy_passed(receipt) or receipt.get('attempted') != len(sites) or len(attempts) != len(sites) or
                    receipt.get('rows') != len(records) or receipt.get('rowsSha256') != digest(rows_bytes) or
                    receipt.get('attemptsSha256') != digest(attempts_bytes) or receipt.get('engineSha256') != engine_hash or
                    receipt.get('featureNames') != features):
                    raise ValueError('incomplete-or-changed-source-shard')
                kept_privacy = {**receipt['privacy'], 'evidence': 'completed-shard-receipt'}
            elif not checkpoint and len(attempts) != len(sites) and len(attempts) % 4:
                raise ValueError('partial-legacy-batch')
        recorded = len(attempts)
        if ledger:
            if (set(ledger) != {'schemaVersion', 'frameSha256', 'shard', 'siteIds'} or ledger['schemaVersion'] != 1 or
                ledger['frameSha256'] != frame_hash or ledger['shard'] != shard or
                ledger['siteIds'] != ids[:len(ledger['siteIds'])] or len(ledger['siteIds']) < recorded):
                raise ValueError('invalid-visited-ledger')
            visited = len(ledger['siteIds'])
            basis = 'visited-ledger'
        elif state == 'complete':
            visited, basis = len(sites), 'completed-receipt'
        elif state == 'failed-closed':
            if shard not in overrides:
                raise ValueError('failed-shard-needs-visited-prefix')
            visited, basis = overrides[shard], 'explicit-visited-prefix'
        elif state == 'interrupted':
            visited, basis = min(len(sites), recorded + 4), 'legacy-next-batch'
        else:
            visited, basis = 0, 'never-started'
        if shard in overrides:
            if type(overrides[shard]) is not int or overrides[shard] < visited or overrides[shard] > len(sites):
                raise ValueError('unsafe-visited-prefix')
            visited, basis = overrides[shard], 'explicit-visited-prefix'
        if not recorded <= visited <= len(sites):
            raise ValueError('invalid-visited-count')
        info = {'shard': shard, 'state': state, 'planned': len(sites), 'recorded': recorded,
                'visitedNotRecorded': visited - recorded, 'remaining': len(sites) - visited,
                'usableSites': sum(a['status'] == 'usable' for a in attempts), 'rows': len(records),
                'keepRows': bool(recorded), 'remainingSiteIds': ids[visited:], 'visitedPrefix': visited,
                'visitedBasis': basis, 'keptAttemptsSha256': digest(attempts_bytes), 'keptRowsSha256': digest(rows_bytes),
                'keptPrivacy': kept_privacy,
                'sourceReceiptSha256': sha(folder / 'receipt.json') if receipt else None,
                'sourceCheckpointSha256': sha(folder / 'checkpoint.json') if checkpoint and not inherited and state != 'failed-closed' else None,
                'sourceResumePlanSha256': sha(inherited_dir / 'plan.json') if inherited else None}
        plan['shards'].append(info)
        payloads[shard] = (attempts_bytes, rows_bytes)
    plan['totals'] = {key: sum(s[field] for s in plan['shards']) for key, field in
                      [('planned', 'planned'), ('recorded', 'recorded'), ('inFlight', 'visitedNotRecorded'),
                       ('remaining', 'remaining'), ('usableSites', 'usableSites'), ('rows', 'rows')]}
    return plan, payloads

def provenance(plan, item):
    return {'sourceRun': plan['sourceRun'], 'sourceState': item['state'], 'keptPrefix': item['recorded'],
            'visitedPrefix': item['visitedPrefix'], 'visitedNotRecorded': item['visitedNotRecorded'],
            'visitedBasis': item['visitedBasis'], 'keptAttemptsSha256': item['keptAttemptsSha256'],
            'keptRowsSha256': item['keptRowsSha256'], 'keptPrivacy': item['keptPrivacy'],
            'sourceReceiptSha256': item['sourceReceiptSha256'], 'sourceCheckpointSha256': item['sourceCheckpointSha256'],
            'sourceResumePlanSha256': item['sourceResumePlanSha256']}

def stage_plan(source, dest, plan, payloads):
    """Copy only verified source data into a fresh run; never mutate downloaded artifacts."""
    frame_dir, _ = source_paths(source)
    if dest.exists():
        raise ValueError('resume-output-already-exists')
    dest.mkdir(parents=True)
    for name in ('frame.json', 'workflow.json', 'exclusions.txt', 'history-exclusions.txt', 'ranking.csv'):
        if (frame_dir / name).exists():
            shutil.copyfile(frame_dir / name, dest / name)
    frame = load(dest / 'frame.json')
    for item in plan['shards']:
        folder = dest / 'resume-inputs' / ('shard-' + str(item['shard']))
        folder.mkdir(parents=True)
        (folder / 'kept-attempts.json').write_bytes(payloads[item['shard']][0])
        (folder / 'kept-cookies.jsonl').write_bytes(payloads[item['shard']][1])
        proof = provenance(plan, item)
        write_json(folder / 'plan.json', {**item, 'sourceRun': plan['sourceRun'], 'frameSha256': plan['frameSha256'], 'resume': proof})
        if not item['remaining']:
            output = dest / 'shards' / folder.name
            sites = [s for s in frame['frame'] if s['shard'] == item['shard']]
            attempts = json.loads(payloads[item['shard']][0]) + [skipped_attempt(s) for s in sites[item['recorded']:item['visitedPrefix']]]
            write_json(output / 'attempts.json', attempts)
            (output / 'cookies.jsonl').write_bytes(payloads[item['shard']][1])
            write_json(output / 'visited.json', {'schemaVersion': 1, 'shard': item['shard'], 'frameSha256': plan['frameSha256'],
                                                'siteIds': [s['siteId'] for s in sites]})
            write_json(output / 'receipt.json', {'schemaVersion': 1, 'shard': item['shard'], 'of': frame['shards'],
                'month': frame['month'], 'dryRun': False, 'frameSha256': plan['frameSha256'], 'attempted': len(attempts),
                'rows': item['rows'], 'visitedSites': sum(a['visited'] for a in attempts),
                'rowsSha256': sha(output / 'cookies.jsonl'), 'attemptsSha256': sha(output / 'attempts.json'),
                'engineSha256': sha(ROOT / 'extension-standalone/engine.js'),
                'featureNames': load(ROOT / 'refresh/reference/feature_names.json')['featureNames'],
                'privacy': PASSED, 'resume': proof, 'newPart': {'attempted': 0, 'rows': 0, 'privacy': PASSED}})
    write_json(dest / 'resume-plan.json', plan)

def verify_resumed_shard(run, frame, receipt, attempts, records):
    plan_path = run / 'resume-plan.json'
    if not plan_path.exists():
        if 'resume' in receipt:
            raise ValueError('resume-plan-required')
        return
    plan = load(plan_path)
    item = next(s for s in plan['shards'] if s['shard'] == receipt['shard'])
    if plan['frameSha256'] != sha(run / 'frame.json') or receipt.get('resume') != provenance(plan, item):
        raise ValueError('resume-receipt-provenance')
    folder = run / 'resume-inputs' / ('shard-' + str(item['shard']))
    if (sha(folder / 'kept-attempts.json') != item['keptAttemptsSha256'] or
        sha(folder / 'kept-cookies.jsonl') != item['keptRowsSha256']):
        raise ValueError('changed-kept-prefix')
    kept_attempts = load(folder / 'kept-attempts.json')
    kept_rows = [json.loads(line) for line in (folder / 'kept-cookies.jsonl').read_text().splitlines() if line.strip()]
    sites = [s for s in frame['frame'] if s['shard'] == item['shard']]
    skipped = [skipped_attempt(s) for s in sites[item['recorded']:item['visitedPrefix']]]
    new = receipt.get('newPart', {})
    if (attempts[:item['recorded']] != kept_attempts or records[:item['rows']] != kept_rows or
        attempts[item['recorded']:item['visitedPrefix']] != skipped or len(attempts) != len(sites) or
        new.get('attempted') != item['remaining'] or new.get('rows') != len(records) - item['rows'] or not privacy_passed(new)):
        raise ValueError('invalid-resumed-output')
    ledger = load(run / 'shards' / folder.name / 'visited.json')
    if ledger != {'schemaVersion': 1, 'shard': item['shard'], 'frameSha256': plan['frameSha256'],
                  'siteIds': [s['siteId'] for s in sites]}:
        raise ValueError('incomplete-resumed-ledger')


def plan_report(plan):
    t = plan['totals']
    lines = ['# Resume plan: ' + plan['sourceRun'], '', RULE, '',
             'Recorded: ' + str(t['recorded']) + '; visited but not recorded: ' + str(t['inFlight']) +
             '; never visited: ' + str(t['remaining']) + '. Kept usable sites: ' + str(t['usableSites']) +
             '; kept cookie rows: ' + str(t['rows']) + '.', '',
             'Explicit visited-prefix inputs: ' + (', '.join(k + '=' + str(v) for k, v in plan['visitedPrefixOverrides'].items()) or 'none') + '.', '',
             '| Shard | State | Recorded | Visited, not recorded | Remaining | Kept rows |', '|---|---|---:|---:|---:|---:|']
    for s in plan['shards']:
        lines.append('| ' + ' | '.join(str(s[k]) for k in ('shard', 'state', 'recorded', 'visitedNotRecorded', 'remaining', 'rows')) + ' |')
    lines += ['', 'Recorded prefixes are preserved by digest. Their original batch scans are source evidence; old cookie contents are unavailable for a new scan. '
              'New visits retain a separate privacy receipt. Visited-not-recorded attempts have unknown document/robots outcomes and no cookie rows.', '']
    return '\n'.join(lines)

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--source-run', required=True)
    p.add_argument('--visited-prefix', action='append', default=[])
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--expect', type=Path)
    a = p.parse_args()
    plan, _ = build_plan(a.source, a.source_run, prefixes(' '.join(a.visited_prefix)))
    if a.expect:
        expected = load(a.expect)
        if (any(plan[k] != expected[k] for k in ('sourceRun', 'month', 'frameSha256', 'totals')) or
            len(plan['shards']) != len(expected['shards']) or
            any(any(actual.get(k) != v for k, v in wanted.items()) for actual, wanted in zip(plan['shards'], expected['shards']))):
            raise ValueError('saved-resume-state-mismatch')
    a.out.mkdir(parents=True, exist_ok=False)
    write_json(a.out / 'resume-plan.json', plan)
    (a.out / 'RESUME_PLAN.md').write_text(plan_report(plan))
    print(json.dumps({'totals': plan['totals'], 'matchesSavedState': True if a.expect else None}))

if __name__ == '__main__':
    try: main()
    except Exception: sys.exit(die())
