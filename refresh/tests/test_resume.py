"""Resume plans and full merge tests use synthetic files and in-memory site responses."""
import json
from pathlib import Path
import subprocess
import sys
import shutil
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import ROOT, load, sha, write_json
from resume import build_plan, stage_plan, prefixes, plan_report
from privacy_audit import receipt_audit
from test_shard_recovery import make_run, do_merge, PRIVACY, fake_publish

class ResumeTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='resume-test-', dir=ROOT / 'refresh/.work')
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.source = make_run(self.root)
        self.dest = self.root / 'resumed'
        interrupted = self.source / 'shards/shard-3'
        (interrupted / 'receipt.json').unlink()
        write_json(interrupted / 'started.json', {'shard': 3, 'month': '2026-11'})
        write_json(interrupted / 'attempts.json', load(interrupted / 'attempts.json')[:4])

    def plan(self):
        return build_plan(self.source, '123', {2: 4})

    def ledger(self, shard, count):
        frame = load(self.source / 'frame.json')
        write_json(self.source / 'shards' / ('shard-' + str(shard)) / 'visited.json', {
            'schemaVersion': 1, 'shard': shard, 'frameSha256': sha(self.source / 'frame.json'),
            'siteIds': [s['siteId'] for s in frame['frame'] if s['shard'] == shard][:count]})

    def test_four_states_and_conservative_legacy_in_flight_batch(self):
        plan, _ = self.plan()
        by = {s['shard']: s for s in plan['shards']}
        self.assertEqual([by[n]['state'] for n in (1, 2, 3, 14)], ['complete', 'failed-closed', 'interrupted', 'never-started'])
        self.assertEqual((by[3]['recorded'], by[3]['visitedPrefix'], by[3]['remaining']), (4, 8, 2))
        self.assertEqual((by[2]['recorded'], by[2]['visitedPrefix'], by[2]['rows']), (0, 4, 0))
        self.assertEqual(plan['totals'], {'planned': 160, 'recorded': 134, 'inFlight': 8, 'remaining': 18, 'usableSites': 14, 'rows': 14})
        self.assertIn('2=4', plan_report(plan))
        (self.source / 'shards/shard-2/checkpoint.json').write_text('discarded-private-fixture')
        self.assertEqual(self.plan()[0]['totals'], plan['totals'])

    def test_planning_uses_tracked_engine_without_a_generated_vendor_directory(self):
        checkout = self.root / 'fresh-checkout'
        for name in ['extension-standalone/engine.js', 'refresh/reference/feature_names.json']:
            dest = checkout / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, dest)
        with patch('resume.ROOT', checkout):
            plan, _ = self.plan()
        self.assertEqual(plan['totals']['remaining'], 18)
        self.assertFalse((checkout / 'packages/core/vendor').exists())

    def test_new_ledgers_eliminate_log_overrides_and_never_repeat_in_flight_ids(self):
        self.ledger(2, 4); self.ledger(3, 8)
        plan, _ = build_plan(self.source, '123')
        for shard in (2, 3):
            item = plan['shards'][shard - 1]
            self.assertEqual(item['visitedBasis'], 'visited-ledger')
            visited = load(self.source / 'shards' / ('shard-' + str(shard)) / 'visited.json')['siteIds']
            self.assertFalse(set(visited) & set(item['remainingSiteIds']))
        with self.assertRaisesRegex(ValueError, 'unsafe-visited-prefix'):
            build_plan(self.source, '123', {2: 0})

    def test_atomic_checkpoint_survives_a_torn_attempts_export(self):
        self.ledger(2, 4); self.ledger(3, 8)
        folder = self.source / 'shards/shard-3'
        checkpoint = {'schemaVersion': 1, 'shard': 3, 'frameSha256': sha(self.source / 'frame.json'),
            'engineSha256': sha(ROOT / 'packages/core/vendor/engine.cjs'),
            'featureNames': load(ROOT / 'refresh/reference/feature_names.json')['featureNames'], 'privacy': PRIVACY,
            'attempts': load(folder / 'attempts.json'), 'rows': [json.loads(line) for line in (folder / 'cookies.jsonl').read_text().splitlines()]}
        write_json(folder / 'checkpoint.json', checkpoint)
        (folder / 'attempts.json').write_text('interrupted-export')
        plan, payloads = build_plan(self.source, '123')
        self.assertEqual(plan['shards'][2]['recorded'], 4)
        self.assertEqual(plan['shards'][2]['keptPrivacy']['evidence'], 'atomic-batch-checkpoint')
        stage_plan(self.source, self.dest, plan, payloads)
        self.assertEqual(len(load(self.dest / 'resume-inputs/shard-3/kept-attempts.json')), 4)

    def test_bad_prefix_unknown_visit_count_and_changed_receipt_are_refused(self):
        with self.assertRaisesRegex(ValueError, 'failed-shard-needs-visited-prefix'):
            build_plan(self.source, '123')
        self.ledger(2, 4)
        path = self.source / 'shards/shard-3/attempts.json'
        attempts = load(path); attempts[0], attempts[1] = attempts[1], attempts[0]
        write_json(path, attempts)
        with self.assertRaisesRegex(ValueError, 'recorded-attempts-not-frame-prefix'):
            build_plan(self.source, '123')
        attempts[0], attempts[1] = attempts[1], attempts[0]; write_json(path, attempts)
        receipt = self.source / 'shards/shard-1/receipt.json'; data = load(receipt)
        data['attemptsSha256'] = '0' * 64; write_json(receipt, data)
        with self.assertRaisesRegex(ValueError, 'incomplete-or-changed-source-shard'):
            build_plan(self.source, '123')

    def test_kept_and_resumed_rows_merge_and_each_part_has_provenance(self):
        plan, payloads = self.plan()
        source_hashes = {str(p.relative_to(self.source)): sha(p) for p in self.source.rglob('*') if p.is_file()}
        stage_plan(self.source, self.dest, plan, payloads)
        self.assertEqual(len(list((self.dest / 'shards').iterdir())), 13)  # Complete shards need no new crawl job.
        result = subprocess.run(['node', 'refresh/tests/resume_fixture.mjs', str(self.dest)], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {'fakeVisits': 18, 'publicVisits': 0})
        manifest = do_merge(self.root, self.dest)
        self.assertEqual((manifest['attempted'], manifest['rows'], manifest['visitedNotRecordedSites']), (160, 32, 8))
        self.assertTrue(manifest['coveragePassed']); self.assertTrue(receipt_audit(self.dest, manifest))
        fake_publish(self.root, self.dest, manifest)
        for item, receipt in zip(plan['shards'], manifest['shardReceipts']):
            self.assertEqual(receipt['resume']['sourceRun'], '123')
            self.assertEqual(receipt['resume']['keptPrefix'], item['recorded'])
            self.assertEqual(receipt['newPart']['attempted'], item['remaining'])
            self.assertTrue(receipt['newPart']['privacy']['crossScanPassed'])
        self.assertEqual(source_hashes, {str(p.relative_to(self.source)): sha(p) for p in self.source.rglob('*') if p.is_file()})
        (self.dest / 'resume-inputs/shard-3/kept-cookies.jsonl').write_text('')
        self.assertFalse(receipt_audit(self.dest, manifest))

    def test_resume_of_a_resume_keeps_carried_shards_and_never_repeats_inherited_visits(self):
        plan, payloads = self.plan()
        stage_plan(self.source, self.dest, plan, payloads)
        # A downloaded frame artifact contains completed shards and inputs for pending jobs.
        download = self.root / 'downloaded-again'
        shutil.copytree(self.dest, download / 'frame')
        next_plan, _ = build_plan(download, '124')
        self.assertEqual(next_plan['shards'][0]['state'], 'complete')
        self.assertEqual(next_plan['shards'][1]['visitedPrefix'], 4)
        self.assertEqual(next_plan['shards'][2]['visitedPrefix'], 8)
        self.assertEqual(next_plan['totals']['remaining'], plan['totals']['remaining'])
        self.assertEqual([s['remainingSiteIds'] for s in next_plan['shards']], [s['remainingSiteIds'] for s in plan['shards']])

    def test_failed_resumed_shard_excludes_its_kept_rows_and_input_payload(self):
        plan, payloads = self.plan()
        stage_plan(self.source, self.dest, plan, payloads)
        subprocess.run(['node', 'refresh/tests/resume_fixture.mjs', str(self.dest)], cwd=ROOT, check=True, capture_output=True)
        folder = self.dest / 'shards/shard-3'
        receipt = load(folder / 'receipt.json')
        receipt.update(status='failed-closed', reasonCode='privacy-rejected', privacy={'passed': False})
        write_json(folder / 'receipt.json', receipt)
        manifest = do_merge(self.root, self.dest)
        self.assertEqual(manifest['excludedSites'], 10)
        self.assertEqual(manifest['rows'], 29)
        self.assertFalse(folder.exists())
        self.assertFalse((self.dest / 'resume-inputs/shard-3').exists())
        self.assertTrue(receipt_audit(self.dest, manifest))

    def test_invalid_override_syntax_and_duplicate_entries_are_refused(self):
        self.assertEqual(prefixes('2=36 10=424'), {2: 36, 10: 424})
        for text in ('2=-1', '2=4 2=8', '../2=4', '2=4;command'):
            with self.assertRaises(ValueError): prefixes(text)

if __name__ == '__main__':
    unittest.main()
