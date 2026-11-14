"""Synthetic observations and in-memory GitHub/browser responses only; no public visits."""
import contextlib
import io
import json
import os
import re
import subprocess
import yaml
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ci
import merge
from common import ROOT, load, normalize_name, sha, write_json
from health import assess_coverage, assess_health, exclusion_report, included_privacy_passed
from privacy_audit import check_file, receipt_audit

PRIVACY = {'passed': True, 'structuralPassed': True, 'crossScanPassed': True}

def make_run(root, missing=(14,), failed=(2,), reason='privacy-rejected'):
    run = root / 'refresh/.work/run'
    sites = [{'siteId': 'site-' + str(i), 'rank': i, 'domain': 'site' + str(i) + '.example',
              'shard': (i - 1) // 10 + 1} for i in range(1, 161)]
    frame = {'month': '2026-11', 'shards': 16, 'sites': 160, 'frame': sites, 'dryRun': False,
             'trancoListId': 'FIXTURE', 'trancoSha256': '0' * 64}
    write_json(run / 'frame.json', frame)
    (run / 'exclusions.txt').write_text('historical.example\n')
    state = root / 'refresh/state/crawled_domains.txt'
    state.parent.mkdir(parents=True)
    state.write_text('historical.example\n')
    for shard in range(1, 17):
        if shard in missing:
            continue
        folder = run / 'shards' / ('shard-' + str(shard))
        folder.mkdir(parents=True)
        selected = [site for site in sites if site['shard'] == shard]
        row = {'crawl': 'monthly', 'rank': selected[0]['rank'], 'cmp': 'cookiebot',
               'declaredCategory': 'statistics', 'declaredGroup': 'statistics', 'name': 'metrics_id',
               'normalizedName': normalize_name('metrics_id'), 'domain': selected[0]['domain'],
               'path': '/', 'label': 'tracker', 'secure': True, 'httpOnly': False, 'sameSite': 'Lax',
               'hostOnly': True, 'session': True, 'lifetimeSeconds': None, 'valueLength': 10,
               'valueCharacterSet': 'letters', 'declarationMatch': 'exact', 'features': [0] * 38,
               'crawlDate': '2026-11-14T00:00:00Z', 'trancoListId': 'FIXTURE'}
        if shard in failed:
            row['path'] = '/failed-shard-payload-sentinel'
        (folder / 'cookies.jsonl').write_text(json.dumps(row) + '\n')
        observations = [{**site, 'status': 'usable' if i == 0 else 'no-supported-cmp', 'visited': True,
                         'robotsStatus': 'allowed', 'cmp': 'cookiebot' if i == 0 else 'none'}
                        for i, site in enumerate(selected)]
        write_json(folder / 'attempts.json', observations)
        receipt = {'frameSha256': sha(run / 'frame.json'), 'shard': shard, 'of': 16, 'month': frame['month'],
                   'privacy': PRIVACY, 'attempted': 10, 'visitedSites': 10, 'rows': 1,
                   'engineSha256': sha(ROOT / 'packages/core/vendor/engine.cjs'),
                   'featureNames': load(ROOT / 'refresh/reference/feature_names.json')['featureNames'],
                   'rowsSha256': sha(folder / 'cookies.jsonl'), 'attemptsSha256': sha(folder / 'attempts.json')}
        if shard in failed:
            receipt = {k: receipt[k] for k in ['frameSha256', 'shard', 'of', 'month']}
            receipt.update(status='failed-closed', privacy={'passed': False})
            if reason is not None:
                receipt['reasonCode'] = reason
        write_json(folder / 'receipt.json', receipt)
    write_json(run / 'workflow.json', {'month': frame['month'], 'dryRun': False, 'firstRealRun': True,
                                     'reservationBranch': 'refresh/reservations/2026-11', 'sourceCommit': 'a' * 40})
    write_json(root / 'data/releases/index.json', {'releases': []})
    return run

def do_merge(root, run):
    argv = ['merge.py', '--run', str(run), '--releases', str(root / 'data/releases'),
            '--state', str(root / 'refresh/state/crawled_domains.txt')]
    with patch.object(sys, 'argv', argv), contextlib.redirect_stdout(io.StringIO()):
        merge.main()
    return load(root / 'data/releases/2026-11/manifest.json')

def fake_publish(root, run, manifest):
    write_json(run / 'privacy-audit.json', {'passed': True, 'files': []})
    write_json(run / 'gate.json', {'gates': {'Health': assess_health(manifest)},
                                 'eligibleForModelPR': False, 'allGatesPassed': False})
    (run / 'REPORT.md').write_text('\n'.join(exclusion_report(manifest)))
    with patch('ci.ROOT', root), patch('ci.RUN', run), patch('ci.action_only', return_value='fixture/repo'), \
         patch('ci.git', return_value='a' * 40), patch('ci.create_branch', return_value='b' * 40) as branch, \
         patch('ci.gh', return_value='https://github.com/fixture/repo/pull/1') as remote:
        if assess_coverage(manifest)['passed']:
            ci.publish()
            branch.assert_called_once()
            create = next(call.args for call in remote.call_args_list if call.args[:2] == ('pr', 'create'))
            assert '--draft' in create
        else:
            with unittest.TestCase().assertRaisesRegex(ValueError, 'too-many-excluded-sites'):
                ci.publish()
            branch.assert_not_called()
            remote.assert_not_called()

class ShardTests(unittest.TestCase):
    def temp_root(self):
        temp = tempfile.TemporaryDirectory(prefix='shard-test-', dir=ROOT / 'refresh/.work')
        self.addCleanup(temp.cleanup)
        return Path(temp.name)

    def test_missing_and_failed_shards_are_excluded_and_rest_publish(self):
        root = self.temp_root(); run = make_run(root)
        manifest = do_merge(root, run)
        self.assertEqual(manifest['excludedShards'], [
            {'shard': 2, 'sites': 10, 'reasonCode': 'privacy-rejected'},
            {'shard': 14, 'sites': 10, 'reasonCode': 'missing-shard'}])
        self.assertEqual((manifest['attempted'], manifest['excludedSites'], manifest['rows']), (140, 20, 14))
        self.assertFalse(manifest['complete'])
        self.assertTrue(manifest['privacyPassed'])
        self.assertTrue(included_privacy_passed(manifest))
        self.assertTrue(assess_coverage(manifest)['passed'])
        self.assertEqual(assess_health(manifest)['attemptedSites'], 140)
        self.assertEqual(assess_health(manifest)['visitedSites'], 140)
        self.assertTrue(receipt_audit(run, manifest))
        fake_publish(root, run, manifest)
        report = (run / 'REPORT.md').read_text()
        self.assertIn('| 2 | 10 | privacy-rejected |', report)
        self.assertIn('| 14 | 10 | missing-shard |', report)
        self.assertEqual(len((root / 'refresh/state/crawled_domains.txt').read_text().splitlines()), 161)

    def test_failed_rows_never_enter_any_retained_artifact(self):
        root = self.temp_root(); run = make_run(root)
        manifest = do_merge(root, run)
        self.assertFalse((run / 'shards/shard-2').exists())
        for path in root.rglob('*'):
            if path.is_file():
                self.assertNotIn(b'failed-shard-payload-sentinel', path.read_bytes())
                self.assertTrue(check_file(path))
        self.assertTrue(receipt_audit(run, manifest))

    def test_four_of_sixteen_allowed_but_five_fail_even_when_health_passes(self):
        for count in (4, 5):
            with self.subTest(excluded=count):
                root = self.temp_root(); run = make_run(root, missing=tuple(range(1, count + 1)), failed=())
                manifest = do_merge(root, run)
                self.assertTrue(assess_health(manifest)['passed'])
                self.assertEqual(assess_coverage(manifest)['passed'], count == 4)
                self.assertEqual(manifest['coveragePassed'], count == 4)
                fake_publish(root, run, manifest)

    def test_coverage_counts_sites_not_shards_and_no_included_shards_fails(self):
        manifest = {'planned': 100, 'attempted': 74, 'excludedSites': 26, 'plannedShards': 4,
                    'includedShards': [1, 2, 3], 'excludedShards': [{'shard': 4, 'sites': 26, 'reasonCode': 'missing-shard'}]}
        self.assertFalse(assess_coverage(manifest)['passed'])
        root = self.temp_root(); run = make_run(root, missing=tuple(range(1, 17)), failed=())
        empty = do_merge(root, run)
        self.assertEqual(empty['rows'], 0)
        self.assertFalse(empty['privacyPassed'])
        self.assertFalse(assess_coverage(empty)['passed'])

    def test_audit_rejects_changed_included_payload_or_reintroduced_excluded_folder(self):
        root = self.temp_root(); run = make_run(root)
        manifest = do_merge(root, run)
        path = run / 'shards/shard-1/cookies.jsonl'
        original = path.read_text()
        path.write_text(original + '\n')
        self.assertFalse(receipt_audit(run, manifest))
        path.write_text(original)
        (run / 'shards/shard-2').mkdir()
        self.assertFalse(receipt_audit(run, manifest))

    def test_legacy_failure_is_reported_without_guessing_cause(self):
        root = self.temp_root(); run = make_run(root, reason=None)
        manifest = do_merge(root, run)
        self.assertEqual(manifest['excludedShards'][0]['reasonCode'], 'failed-closed')
        self.assertIn('no cause is inferred', '\n'.join(exclusion_report(manifest)))

    def test_included_receipt_requires_cross_scan_and_structural_evidence(self):
        for field in ['crossScanPassed', 'structuralPassed']:
            root = self.temp_root(); run = make_run(root)
            path = run / 'shards/shard-1/receipt.json'; receipt = load(path)
            del receipt['privacy'][field]
            write_json(path, receipt)
            with self.assertRaisesRegex(ValueError, 'missing-shard-privacy-evidence'):
                do_merge(root, run)
            self.assertFalse((root / 'data/releases/2026-11').exists())

class RecoveryTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name); self.run = make_run(self.root, missing=tuple(range(1, 17)), failed=())
        self.event = self.root / 'event.json'
        write_json(self.event, {'inputs': {'from_run': '43627693953', 'dry_run': 'true'}})
        self.remote_frame = (self.run / 'frame.json').read_bytes()
        self.refs, self.git_calls, self.gh_calls = set(), [], []
        self.stack = contextlib.ExitStack(); self.addCleanup(self.stack.close)
        for target, value in [('ci.ROOT', self.root), ('ci.RUN', self.run)]:
            self.stack.enter_context(patch(target, value))
        self.stack.enter_context(patch('ci.action_only', return_value='fixture/repo'))
        self.stack.enter_context(patch('ci.git', side_effect=self.git))
        self.stack.enter_context(patch('ci.gh', side_effect=self.gh))
        self.quiet = self.stack.enter_context(patch('ci.quiet', side_effect=AssertionError('unexpected-subprocess')))
        self.stack.enter_context(patch.dict(os.environ, {'GITHUB_EVENT_PATH': str(self.event),
            'GITHUB_OUTPUT': str(self.root / 'output.txt')}))

    def gh(self, *args, **kwargs):
        self.gh_calls.append(args)
        if 'matching-refs' in args[1]:
            return '\n'.join(sorted(self.refs))
        self.assertTrue(kwargs.get('raw'))
        self.assertIn('Accept: application/vnd.github.raw+json', args)
        return self.remote_frame

    def git(self, *args, **kwargs):
        self.git_calls.append(args)
        if 'push' in args:
            ref = args[-1].split(':', 1)[1]
            self.assertIn('--force-with-lease=' + ref + ':', args)
            if ref in self.refs:
                raise ValueError('subprocess-failed')
            self.refs.add(ref)
        return 'b' * 40

    def test_recovery_uses_exact_real_reservation_without_crawl_and_preserves_first_draft(self):
        ci.recover()
        self.assertEqual(self.refs, {'refs/heads/refresh/recoveries/43627693953'})
        self.assertEqual((self.run / 'frame.json').read_bytes(), self.remote_frame)
        self.assertTrue(load(self.run / 'workflow.json')['firstRealRun'])
        self.assertEqual(load(self.run / 'workflow.json')['sourceCommit'], 'b' * 40)
        self.assertEqual(load(self.run / 'recovery.json')['sourceCommit'], 'a' * 40)
        self.assertIn('ref=refresh/reservations/2026-11', self.gh_calls[1][1])
        self.assertEqual((self.root / 'output.txt').read_text(), 'month=2026-11\ndry_run=false\n')
        self.quiet.assert_not_called()
        self.assertIn('first-run PR is a draft', ci.pr_body('data', True, {'gates': {'Health': {'passed': True}}}, ''))

    def test_raw_reservation_supports_a_frame_over_one_megabyte(self):
        frame = load(self.run / 'frame.json')
        frame['sampling'] = 'synthetic-metadata ' * 70000
        write_json(self.run / 'frame.json', frame)
        self.remote_frame = (self.run / 'frame.json').read_bytes()
        self.assertGreater(len(self.remote_frame), 1024 * 1024)
        ci.recover()
        self.assertEqual((self.run / 'frame.json').read_bytes(), self.remote_frame)

    def test_recovery_refuses_mismatched_frame_before_reserving(self):
        changed = load(self.run / 'frame.json'); changed['frame'][0]['domain'] = 'different.example'
        write_json(self.run / 'frame.json', changed)
        with self.assertRaisesRegex(ValueError, 'recovery-reservation-mismatch'):
            ci.recover()
        self.assertFalse(self.refs)
        self.assertFalse(self.git_calls)

    def test_recovery_refuses_pilot_even_if_bytes_match(self):
        frame = load(self.run / 'frame.json'); frame['dryRun'] = True
        write_json(self.run / 'frame.json', frame)
        self.remote_frame = (self.run / 'frame.json').read_bytes()
        with self.assertRaisesRegex(ValueError, 'recovery-reservation-mismatch'):
            ci.recover()
        self.assertFalse(self.refs)

    def test_second_recovery_refused_and_no_overwrite_guard_also_stops_race(self):
        ci.recover()
        with self.assertRaisesRegex(ValueError, 'source-run-already-recovered'):
            ci.recover()
        with patch('ci.gh', side_effect=['', self.remote_frame]):
            with self.assertRaisesRegex(ValueError, 'subprocess-failed'):
                ci.recover()
        self.assertEqual(len(self.refs), 1)

    def test_prepare_rejects_recovery_and_invalid_source_ids_never_call_remote(self):
        with self.assertRaisesRegex(ValueError, 'recovery-cannot-prepare-or-crawl'):
            ci.prepare()
        for value in ['', '0', '-1', '123/456', '1; command', 123]:
            write_json(self.event, {'inputs': {'from_run': value}})
            with self.assertRaisesRegex(ValueError, 'invalid-source-run'):
                ci.recover()
        self.assertFalse(self.git_calls)
        self.assertFalse(self.gh_calls)
        self.quiet.assert_not_called()

class WorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = yaml.load((ROOT / '.github/workflows/monthly-refresh.yml').read_text(), Loader=yaml.BaseLoader)

    def job_runs(self, name, context, statuses):
        job = self.workflow['jobs'][name]
        needs = job.get('needs', [])
        if isinstance(needs, str):
            needs = [needs]
        expression = job.get('if', 'true')
        # GitHub applies implicit success() to jobs unless a status function is present.
        if 'always()' not in expression and any(statuses.get(n) != 'success' for n in needs):
            return False
        values = dict(context)
        values.update({'needs.' + n + '.result': status for n, status in statuses.items()})
        expression = re.sub(r'(?:github|inputs|needs)\.[A-Za-z0-9_.]+', lambda m: repr(values.get(m[0], '')), expression)
        expression = expression.replace('always()', 'True').replace('&&', ' and ').replace('||', ' or ')
        return bool(eval(expression, {'__builtins__': {}}, {'true': True, 'false': False}))

    def test_recovery_skips_frame_and_crawl_but_runs_evaluate_and_publish(self):
        context = {'github.ref': 'refs/heads/main', 'github.run_attempt': 1, 'inputs.from_run': '43627693953',
                   'needs.recover.outputs.dry_run': 'false'}
        statuses = {'frame': 'skipped', 'crawl': 'skipped', 'recover': 'success', 'evaluate': 'success'}
        self.assertFalse(self.job_runs('frame', context, statuses))
        self.assertFalse(self.job_runs('crawl', context, statuses))
        for job in ['recover', 'evaluate', 'publish']:
            self.assertTrue(self.job_runs(job, context, statuses))
        for failed in ['failure', 'cancelled']:
            statuses['recover'] = failed
            self.assertFalse(self.job_runs('evaluate', context, statuses))
        statuses['evaluate'] = 'failure'
        self.assertFalse(self.job_runs('publish', context, statuses))

    def test_scheduled_run_evaluates_after_failed_shard_and_still_publishes(self):
        context = {'github.ref': 'refs/heads/main', 'github.run_attempt': 1, 'inputs.from_run': '',
                   'needs.frame.outputs.dry_run': 'false'}
        statuses = {'frame': 'success', 'crawl': 'failure', 'recover': 'skipped', 'evaluate': 'success'}
        for job in ['frame', 'crawl', 'evaluate', 'publish']:
            self.assertTrue(self.job_runs(job, context, statuses))
        self.assertFalse(self.job_runs('recover', context, statuses))
        self.assertEqual(self.workflow['on']['schedule'][0]['cron'], '0 2 1 * *')

    def test_cross_run_downloads_are_authenticated_and_only_verified_frame_goes_downstream(self):
        for job, artifact in [('recover', 'name'), ('evaluate', 'pattern')]:
            config = self.workflow['jobs'][job]
            self.assertEqual(config['permissions']['actions'], 'read')
            downloads = [step['with'] for step in config['steps'] if step.get('uses', '').startswith('actions/download-artifact@')]
            source = next(step for step in downloads if artifact in step)
            self.assertIn('inputs.from_run', source['run-id'])
            self.assertEqual(source['github-token'], '${{ github.token }}')
        frame = next(step['with'] for step in self.workflow['jobs']['evaluate']['steps']
                     if step.get('with', {}).get('name') == 'frame')
        self.assertNotIn('run-id', frame)  # Current run's verified/rebound workflow metadata.

    def test_actual_npm_retry_scripts_stop_on_success_and_after_three_failures(self):
        scripts = [step['run'] for job in ['crawl', 'evaluate'] for step in self.workflow['jobs'][job]['steps']
                   if 'npm ci ' in step.get('run', '')]
        self.assertEqual(len(scripts), 4)
        for script in scripts:
            for succeed_on in (1, 3, 4):
                # Shell functions are the only npm/sleep implementations; nothing installs or connects.
                fake = ('calls=0\nnpm() { calls=$((calls + 1)); test "$calls" -ge ' + str(succeed_on) + '; }\n'
                        'sleep() { :; }\ntrap \'echo "$calls"\' EXIT\n')
                result = subprocess.run(['bash'], input=fake + script, text=True, capture_output=True)
                self.assertEqual(result.returncode, 0 if succeed_on <= 3 else 1)
                self.assertEqual(result.stdout.strip(), str(min(succeed_on, 3)))

if __name__ == '__main__':
    unittest.main()
