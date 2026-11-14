import json
import contextlib
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import ROOT, normalize_name, sha, structural, write_json, load
from evaluate import paired, summary
from gate import assess
from lookup import Lookup, build_lookup
from privacy_audit import check_file
from train import training_files
from ci import action_only, protected_auto_merge
import merge

class PipelineTests(unittest.TestCase):
    def test_merge_rejects_tampering_then_accepts_complete_receipts(self):
        with tempfile.TemporaryDirectory(prefix='merge-test-', dir=ROOT / 'refresh/.work') as directory:
            run = Path(directory)
            site = {'siteId': 'fixture', 'rank': 1, 'domain': 'fixture.example', 'shard': 1}
            frame = {'month': '2026-01', 'shards': 1, 'sites': 1, 'frame': [site], 'dryRun': True,
                     'trancoListId': 'FIXTURE', 'trancoSha256': '0' * 64}
            write_json(run / 'frame.json', frame)
            (run / 'exclusions.txt').write_text('previous.example\n')
            (run / 'state.txt').write_text('previous.example\n')
            shard = run / 'shards/shard-1'
            shard.mkdir(parents=True)
            (shard / 'cookies.jsonl').touch()
            write_json(shard / 'attempts.json', [{**site, 'status': 'no-supported-cmp', 'visited': True, 'robotsStatus': 'allowed', 'cmp': 'none'}])
            receipt = {'frameSha256': sha(run / 'frame.json'), 'shard': 1, 'of': 1, 'month': '2026-01',
                       'privacy': {'passed': True}, 'attempted': 1, 'visitedSites': 1, 'rows': 0,
                       'engineSha256': sha(ROOT / 'packages/core/vendor/engine.cjs'),
                       'featureNames': load(ROOT / 'refresh/reference/feature_names.json')['featureNames'],
                       'rowsSha256': sha(shard / 'cookies.jsonl'), 'attemptsSha256': '0' * 64}
            args = ['merge.py', '--run', str(run), '--releases', str(run / 'releases'), '--state', str(run / 'state.txt')]
            write_json(shard / 'receipt.json', receipt)
            with patch.object(sys, 'argv', args), self.assertRaises(ValueError):
                merge.main()
            self.assertFalse((run / 'releases').exists())
            receipt['attemptsSha256'] = sha(shard / 'attempts.json')
            write_json(shard / 'receipt.json', receipt)
            with patch.object(sys, 'argv', args), contextlib.redirect_stdout(io.StringIO()):
                merge.main()
            self.assertTrue(load(run / 'releases/2026-01/manifest.json')['privacyPassed'])
            self.assertEqual(set((run / 'state.txt').read_text().splitlines()), {'fixture.example', 'previous.example'})

    def test_remote_writes_refused_locally_and_on_retries(self):
        for env in [{}, {'GITHUB_ACTIONS': 'true', 'GITHUB_REF': 'refs/heads/main', 'GITHUB_RUN_ATTEMPT': '2'}]:
            with patch.dict('os.environ', env, clear=True):
                with self.assertRaises(ValueError): action_only()

    def test_auto_merge_requires_all_four_strict_app_bound_checks(self):
        checks = [{'context': 'Linux / Node 24 / Chromium / packaged consumers', 'integration_id': 15368}]
        checks += [{'context': 'Linux / Python ' + v + ' / Browser Use / Chromium', 'integration_id': 15368}
                   for v in ['3.11', '3.12', '3.13']]
        settings = json.dumps({'allow_auto_merge': True, 'allow_squash_merge': True})
        def rules(items):
            return json.dumps([{'type': 'required_status_checks', 'parameters': {
                'strict_required_status_checks_policy': True, 'required_status_checks': items}}])
        with patch('ci.gh', side_effect=[settings, rules(checks)]):
            self.assertTrue(protected_auto_merge('fixture/repo'))
        with patch('ci.gh', side_effect=[settings, rules(checks[:-1])]):
            self.assertFalse(protected_auto_merge('fixture/repo'))

    def test_paired_bootstrap_same_sites_and_missing_classes(self):
        y = np.array([0, 1] * 20)
        sites = np.repeat(np.arange(20), 2)
        result = paired(y, y, y, sites, 42)
        for m in result['metrics'].values():
            self.assertEqual((m['estimate'], m['lower'], m['upper']), (0, 0, 0))
        empty = summary(np.array([], dtype=int), [], [], 42)
        self.assertIsNone(empty['metrics']['balancedAccuracy']['estimate'])
        single = summary(np.array([0, 0]), [0, 0], ['a', 'b'], 42)
        self.assertIsNone(single['metrics']['balancedAccuracy']['lower'])

    def test_lookup_majority_ties_exact_and_pinned_prefix(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'ocd.csv'
            path.write_text('Cookie / Data Key name,Category,Wildcard match\nprefix_,marketing,1\nambiguous,marketing,0\nambiguous,functional,0\n')
            data = build_lookup([{'name': 'cookie_1', 'label': 0}, {'name': 'cookie_2', 'label': 1},
                                 {'name': 'exact', 'label': 1}, {'name': 'exact', 'label': 0}], path)
            match = Lookup(data)
            self.assertEqual(match.match('cookie_1')[1]['label'], 0)
            self.assertIsNone(match.match('cookie_3'))
            self.assertIsNone(match.match('exact'))
            self.assertIsNone(match.match('ambiguous'))
            self.assertEqual(match.match('prefix_new')[1]['label'], 1)

    def test_training_excludes_current_future_and_dry_months(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for month in ['2026-08', '2026-09', '2026-10', '2026-11', '2026-12']:
                dest = root / month
                dest.mkdir()
                (dest / 'cookies.jsonl').touch()
                (dest / 'manifest.json').write_text(json.dumps({'dryRun': month == '2026-09', 'privacyPassed': month != '2026-08'}))
            selected = training_files('2026-11', root / 'pool.gz', root)
            self.assertEqual([p.parent.name for p in selected[2:]], ['2026-10'])

    def test_missing_or_negative_regression_bounds_block_promotion(self):
        pair = {'metrics': {'balancedAccuracy': {'lower': None}}}
        evaluation = {'candidateMinus': {name: {'natural': pair, 'unseenNames': pair}
                                        for name in ['production-rules', 'production-v1']}}
        gates = assess({'privacyPassed': True, 'structuralPassed': True, 'complete': True,
                        'usableSites': 0, 'attempted': 100}, evaluation,
                       {'passed': True, 'rows': 1000, 'maxAbsoluteDifference': 1e-7}, {'passed': True})
        self.assertFalse(gates['No regression']['passed'])
        self.assertFalse(gates['Unseen names']['passed'])
        self.assertFalse(gates['Health']['passed'])
        self.assertTrue(gates['Privacy']['passed'])

    def test_output_scanner_rejects_nested_contents_and_credentials(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'sample.json'
            path.write_text(json.dumps({'nested': {'value': 'fixture'}}))
            self.assertFalse(check_file(path))
            path.write_text(json.dumps({'name': 'phc_' + 'q' * 30}))
            self.assertFalse(check_file(path))
            path.write_text(json.dumps({'valueLength': 3, 'valueCharacterSet': 'digits'}))
            self.assertTrue(check_file(path))
        self.assertEqual(normalize_name('a12345_99'), '#_0')

if __name__ == '__main__': unittest.main()
