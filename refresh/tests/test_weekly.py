"""Weekly migration: pure date, fixture and mocked remote-call checks; no website visits."""
import contextlib
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import ROOT, historical_releases, load, month_seed, period_start, prior_period, weekly_period, write_json
from ci import create_branch, prior_reservations, reservation_branch
from train import training_files
from test_shard_recovery import make_run
import merge

class WeeklyTests(unittest.TestCase):
    def test_utc_monday_periods_and_year_boundary(self):
        for value, expected in [('2026-11-18T01:00:00+00:00','2026-11-16'),
            ('2026-11-22T23:59:59+00:00','2026-11-16'),('2026-11-23T00:00:00+00:00','2026-11-23'),
            ('2027-01-01T02:00:00+00:00','2026-12-28'),('2027-01-04T00:00:00+00:00','2027-01-04'),
            ('2026-11-22T18:30:00-08:00','2026-11-23')]:
            with self.subTest(value=value):self.assertEqual(weekly_period(datetime.fromisoformat(value)),expected)
        with self.assertRaises(ValueError):weekly_period(datetime(2026,11,18))

    def test_seed_compatibility_and_invalid_dates(self):
        for value, expected in [('2026-11',202611),('2026-11-16',20261116),('2026-11-23',20261123)]:
            self.assertEqual(month_seed(value),expected)
        for value in ['2026-13','2026-11-18','2026-02-30','2026-11-31','2026-11-16/other','2026-11-pilot','0000-01',None]:
            with self.subTest(value=value),self.assertRaises(ValueError):month_seed(value)

    def test_distinct_reservations_and_pilot_names_for_two_weeks(self):
        a=reservation_branch('2026-11-16',False);b=reservation_branch('2026-11-23',False)
        self.assertNotEqual(a,b)
        self.assertEqual(reservation_branch('2026-11-23',True),'refresh/reservations/2026-11-23-pilot')
        with patch('ci.action_only'),patch('ci.git',return_value='a'*40) as git:
            for branch in [a,b,b+'-pilot','refresh/data/2026-11-23','refresh/model/2026-11-23','refresh/data/2026-11']:
                create_branch(branch,[])
            self.assertEqual(sum('push' in c.args for c in git.call_args_list),6)
            for bad in ['refresh/data/2026-11-18','refresh/data/2026-11-23-pilot','refresh/reservations/2026-13','refresh/data/2026-11-23/extra']:
                with self.subTest(bad=bad),self.assertRaises(ValueError):create_branch(bad,[])

    def test_reservation_union_retains_monthly_and_weekly_failed_frames(self):
        names=['2026-11','2026-11-pilot','2026-11-16','2026-11-16-pilot','2026-11-23']
        refs='\n'.join('refs/heads/refresh/reservations/'+n for n in names)
        responses=[refs]+[json.dumps({'frame':[{'domain':str(i)+'.example'}]}).encode() for i in range(len(names))]
        with patch('ci.gh',side_effect=responses):self.assertEqual(prior_reservations('fixture/repo'),{str(i)+'.example' for i in range(5)})
        with patch('ci.gh',return_value='refs/heads/refresh/reservations/2026-11-18'):
            with self.assertRaises(ValueError):prior_reservations('fixture/repo')

    def test_overlapping_monthly_release_never_enters_same_month_weekly_training(self):
        self.assertFalse(prior_period('2026-11','2026-11-16'))
        self.assertFalse(prior_period('2026-11','2026-11-30'))
        self.assertTrue(prior_period('2026-11','2026-12-07'))
        self.assertTrue(prior_period('2026-10','2026-11-16'))
        self.assertTrue(prior_period('2026-11-09','2026-11-16'))
        self.assertFalse(prior_period('2026-11-16','2026-11-16'))
        self.assertFalse(prior_period('2026-11-23','2026-11-16'))

    def test_training_and_model_history_select_past_periods_only(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for name in ['2026-10','2026-11','2026-11-02','2026-11-09','2026-11-16','2026-11-23','notes']:
                p=root/name;p.mkdir();(p/'cookies.jsonl').touch()
                write_json(p/'manifest.json',{'dryRun':name=='2026-11-02','privacyPassed':True})
            selected=training_files('2026-11-16',root/'pool.gz',root)
            self.assertEqual([p.parent.name for p in selected[2:]],['2026-10','2026-11-09'])
            # The evaluator uses this same helper for earlier candidate directories.
            self.assertEqual([p.name for p in historical_releases(root,'2026-11-16')],['2026-10','2026-11-02','2026-11-09'])

    def test_weekly_merge_keeps_prior_monthly_and_weekly_releases(self):
        with tempfile.TemporaryDirectory(prefix='weekly-merge-',dir=ROOT/'refresh/.work') as temp:
            root=Path(temp)
            run=make_run(root,missing=(),failed=())
            from common import sha
            frame=load(run/'frame.json');frame['month']='2026-11-16';write_json(run/'frame.json',frame)
            workflow=load(run/'workflow.json');workflow['month']=frame['month'];write_json(run/'workflow.json',workflow)
            for receipt in (run/'shards').glob('shard-*/receipt.json'):
                r=load(receipt);r.update(month=frame['month'],frameSha256=sha(run/'frame.json'));write_json(receipt,r)
            # Keep an already published historical entry as an immutable positive control.
            release_root=root/'data/releases';old=release_root/'2026-10';old.mkdir(parents=True)
            (old/'sentinel').write_text('retained monthly bytes')
            write_json(release_root/'index.json',{'releases':[{'id':'2026-10','kind':'monthly','dryRun':False}]})
            argv=['merge.py','--run',str(run),'--releases',str(release_root),'--state',str(root/'refresh/state/crawled_domains.txt')]
            with patch.object(sys,'argv',argv),contextlib.redirect_stdout(io.StringIO()):merge.main()
            actual=load(release_root/'2026-11-16/manifest.json')
            self.assertEqual(actual['month'],'2026-11-16')
            entries=load(release_root/'index.json')['releases']
            self.assertEqual({r['kind'] for r in entries},{'monthly','weekly'})
            self.assertEqual((old/'sentinel').read_text(),'retained monthly bytes')

    def test_workflow_is_weekly_with_manual_and_recovery_paths_preserved(self):
        import yaml
        text=(ROOT/'.github/workflows/monthly-refresh.yml').read_text()
        workflow=yaml.load(text,Loader=yaml.BaseLoader)
        self.assertEqual(workflow['on']['schedule'],[{'cron':'17 2 * * 1'}])
        self.assertIn('workflow_dispatch',workflow['on'])
        self.assertEqual(workflow['concurrency']['cancel-in-progress'],'false')
        self.assertIn('resume',workflow['jobs']);self.assertIn('evaluate',workflow['jobs'])
        self.assertIn('refresh/tests/periods.test.mjs',text)
