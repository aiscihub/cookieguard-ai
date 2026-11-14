import base64
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ci
from common import load, write_json
from health import attempt_metrics, assess_health, health_report

def manifest(visited=50, usable=2, unavailable=10):
    return {'attempted': 100, 'visitedSites': visited, 'usableSites': usable,
            'robotsUnavailableSites': unavailable, 'unreachableOrTlsSites': 0,
            'cmpFamilyCounts': {'cookiebot': 2, 'onetrust': 3, 'none': 95},
            'robotsStatusCounts': {'allowed': 50, 'disallowed': 40, 'server-error': 10}}

class FixTests(unittest.TestCase):
    def test_health_uses_visited_sites_and_both_rules_are_required(self):
        result = assess_health(manifest())
        self.assertTrue(result['passed'])
        self.assertEqual(result['usableSiteYield'], .04)  # 2/50, not 2/100.
        self.assertEqual(result['robotsUnavailableRate'], .10)
        self.assertTrue(assess_health(manifest(unavailable=20))['passed'])
        self.assertFalse(assess_health(manifest(unavailable=21))['passed'])
        self.assertFalse(assess_health(manifest(usable=1))['passed'])
        self.assertFalse(assess_health(manifest(visited=0, usable=0))['passed'])
        self.assertFalse(assess_health(manifest(visited=101))['passed'])
        self.assertFalse(assess_health(manifest(usable=51))['passed'])
        self.assertFalse(assess_health({'attempted': 100, 'usableSites': 2})['passed'])

    def test_robots_failure_union_counts_each_site_once_and_tracks_cmp_family(self):
        observations = [
            {'status': 'robots-unavailable', 'robotsStatus': 'server-error', 'visited': False, 'cmp': 'none'},
            {'status': 'robots-unavailable', 'robotsStatus': 'network-error', 'visited': False, 'cmp': 'none'},
            {'status': 'robots-unavailable', 'robotsStatus': 'redirect-limit', 'visited': False, 'cmp': 'none'},
            {'status': 'declaration-failed', 'robotsStatus': 'allowed', 'visited': True, 'cmp': 'cookiebot'},
            {'status': 'usable', 'robotsStatus': 'absent-4xx', 'visited': True, 'cmp': 'onetrust'},
        ]
        result = attempt_metrics(observations)
        self.assertEqual(result['visitedSites'], 2)
        self.assertEqual(result['robotsUnavailableSites'], 3)
        self.assertEqual(result['cmpFamilyCounts'], {'cookiebot': 1, 'onetrust': 1, 'none': 3})
        with self.assertRaises(ValueError): attempt_metrics([{'status': 'usable'}])
        with self.assertRaises(ValueError): attempt_metrics([dict(observations[-1], visited=False)])

    def test_report_includes_both_denominators_cmp_counts_and_comparability_notice(self):
        report = '\n'.join(health_report(manifest()))
        self.assertIn('| Usable / visited | 2 / 50 | 4.00%', report)
        self.assertIn('| Robots response/protocol failures / attempted | 10 / 100 | 10.00%', report)
        self.assertIn('| Cookiebot | 2 |', report)
        self.assertIn('| OneTrust | 3 |', report)
        self.assertIn('| None | 95 |', report)
        self.assertIn('| Unreachable + TLS / attempted | 0 / 100 | 0.00% | Report only; no gate |', report)
        self.assertIn('| unreachable | 0 |', report)
        self.assertIn('| tls-error | 0 |', report)
        self.assertIn('not directly comparable', report)
        self.assertIn('CookieGuardResearch/1.0', report)
        self.assertIn('datacenter addresses', report)

    def test_pilot_and_real_reservation_names_are_accepted_and_domains_union(self):
        real = ci.reservation_branch('2026-11', False)
        pilot = ci.reservation_branch('2026-11', True)
        self.assertEqual(real, 'refresh/reservations/2026-11')
        self.assertEqual(pilot, 'refresh/reservations/2026-11-pilot')
        with patch('ci.action_only'), patch('ci.git', return_value='a' * 40) as git:
            ci.create_branch(real, ['refresh/reservation.json'])
            ci.create_branch(pilot, ['refresh/reservation.json'])
            with self.assertRaises(ValueError): ci.create_branch('refresh/data/2026-11-pilot', [])
            pushes = [call.args for call in git.call_args_list if 'push' in call.args]
            self.assertEqual(len(pushes), 2)
            self.assertTrue(pushes[-1][-1].endswith(pilot))
        refs = '\n'.join(['refs/heads/' + real, 'refs/heads/' + pilot])
        payload = lambda domain: base64.b64encode(json.dumps({'frame': [{'domain': domain}]}).encode()).decode()
        with patch('ci.gh', side_effect=[refs, payload('real.example'), payload('pilot.example')]):
            self.assertEqual(ci.prior_reservations('fixture/repo'), {'real.example', 'pilot.example'})
        with patch('ci.gh', return_value='refs/heads/refresh/reservations/2026-11-pilot-again'):
            with self.assertRaises(ValueError): ci.prior_reservations('fixture/repo')

    def test_real_prepare_excludes_pilot_domains_before_frame_selection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); run = root / 'refresh/.work/run'
            (root / 'refresh/state').mkdir(parents=True)
            (root / 'refresh/state/crawled_domains.txt').write_text('historical.example\n')
            write_json(root / 'data/releases/index.json', {'releases': []})
            event = root / 'event.json'
            write_json(event, {'inputs': {'sites': '100', 'shards': '2', 'dry_run': 'false'}})
            output = root / 'outputs.txt'
            commands = []
            def quiet(command):
                commands.append(command)
                if command[0] == 'node':
                    state = Path(command[command.index('--state') + 1])
                    self.assertEqual(set(state.read_text().splitlines()), {'historical.example', 'pilot.example'})
                    write_json(run / 'frame.json', {'frame': []})
                return ''
            with patch('ci.ROOT', root), patch('ci.RUN', run), patch('ci.action_only', return_value='fixture/repo'), \
                 patch('ci.prior_reservations', return_value={'pilot.example'}), patch('ci.quiet', side_effect=quiet), \
                 patch('ci.create_branch') as branch, patch('ci.git', return_value='a' * 40), patch('ci.datetime') as clock, \
                 patch.dict(os.environ, {'GITHUB_EVENT_PATH': str(event), 'GITHUB_EVENT_NAME': 'workflow_dispatch', 'GITHUB_OUTPUT': str(output)}):
                clock.now.return_value.strftime.return_value = '2026-11'
                ci.prepare()
            branch.assert_called_once_with('refresh/reservations/2026-11', ['refresh/reservation.json'])
            self.assertNotIn('--dry-run', commands[-1])

    def test_dataset_publication_matrix_health_and_first_run_with_only_mocked_remote_calls(self):
        for healthy in [False, True]:
            for first in [False, True]:
                with self.subTest(healthy=healthy, first=first), tempfile.TemporaryDirectory() as directory:
                    root = Path(directory); run = root / 'refresh/.work/run'; month = '2026-11'
                    write_json(run / 'frame.json', {'month': month, 'dryRun': False})
                    write_json(run / 'workflow.json', {'dryRun': False, 'firstRealRun': first, 'sourceCommit': 'a' * 40})
                    write_json(run / 'privacy-audit.json', {'passed': True, 'files': []})
                    gate = {'gates': {'Health': {'passed': healthy}}, 'eligibleForModelPR': False, 'allGatesPassed': False}
                    write_json(run / 'gate.json', gate)
                    write_json(root / 'data/releases' / month / 'manifest.json', {'dryRun': False, 'privacyPassed': True, 'complete': True})
                    (run / 'REPORT.md').write_text('In-memory policy fixture.\n')
                    def gh(*args):
                        return 'https://github.com/fixture/repo/pull/1' if args[:2] == ('pr', 'create') else ''
                    with patch('ci.ROOT', root), patch('ci.RUN', run), patch('ci.action_only', return_value='fixture/repo'), \
                         patch('ci.git', return_value='a' * 40), patch('ci.create_branch', return_value='b' * 40), \
                         patch('ci.gh', side_effect=gh) as remote, patch('ci.protected_auto_merge', return_value=True) as protection:
                        ci.publish()
                    commands = [call.args for call in remote.call_args_list]
                    create = next(args for args in commands if args[:2] == ('pr', 'create'))
                    self.assertEqual('--label' in create, healthy)
                    self.assertEqual('--draft' in create, first)
                    self.assertEqual(any(args[:2] == ('label', 'create') for args in commands), healthy)
                    self.assertEqual(any(args[:2] == ('pr', 'merge') for args in commands), healthy and not first)
                    self.assertEqual(protection.called, healthy and not first)
                    if not healthy:
                        self.assertTrue((run / 'data-pr.md').read_text().startswith('Health gate failed: a person must review this release.'))
                    self.assertEqual(load(run / 'publication.json')['pullRequests'][0]['autoMergeRequested'], healthy and not first)

class ReachabilityHealthTests(unittest.TestCase):
    @staticmethod
    def scenario(unreachable=0, tls=0, server=0, usable=3):
        observations = []
        for code, count in [('unreachable', unreachable), ('tls-error', tls), ('server-error', server)]:
            observations.extend({'status': 'robots-unavailable', 'robotsStatus': code, 'visited': False, 'cmp': 'none'}
                                for _ in range(count))
        for i in range(100 - len(observations)):
            observations.append({'status': 'usable' if i < usable else 'no-supported-cmp', 'robotsStatus': 'allowed',
                                 'visited': True, 'cmp': 'cookiebot' if i < usable else 'none'})
        return {'attempted': 100, 'usableSites': usable, **attempt_metrics(observations)}

    def test_25_unreachable_and_5_server_errors_in_100_pass_but_21_server_errors_fail(self):
        result = assess_health(self.scenario(unreachable=25, server=5))
        self.assertTrue(result['passed'])
        self.assertEqual(result['visitedSites'], 70)
        self.assertEqual(result['robotsUnavailableSites'], 5)
        self.assertEqual(result['robotsUnavailableRate'], .05)
        self.assertEqual(result['unreachableOrTlsSites'], 25)
        self.assertEqual(result['unreachableOrTlsRate'], .25)
        result = assess_health(self.scenario(server=21))
        self.assertTrue(result['yieldPassed'])
        self.assertFalse(result['robotsAvailabilityPassed'])
        self.assertFalse(result['passed'])
        self.assertEqual(result['robotsUnavailableRate'], .21)

    def test_unreachable_and_tls_share_is_ungated_and_reported_separately(self):
        data = self.scenario(unreachable=80, tls=5, server=5, usable=1)
        result = assess_health(data)
        self.assertTrue(result['passed'])
        self.assertEqual(result['unreachableOrTlsRate'], .85)
        report = '\n'.join(health_report(data))
        self.assertIn('| Unreachable + TLS / attempted | 85 / 100 | 85.00% | Report only; no gate |', report)
        self.assertIn('| unreachable | 80 |', report)
        self.assertIn('| tls-error | 5 |', report)
        self.assertIn('study navigation-failed equivalent', report)

    def test_only_the_four_response_protocol_statuses_count_against_cap(self):
        codes = ['unreachable', 'tls-error', 'server-error', 'redirect-limit', 'too-large', 'network-error', 'disallowed']
        observations = [{'status': 'robots-unavailable', 'robotsStatus': code, 'visited': False, 'cmp': 'none'} for code in codes]
        counts = attempt_metrics(observations)
        self.assertEqual(counts['robotsUnavailableSites'], 4)
        self.assertEqual(counts['unreachableOrTlsSites'], 2)

if __name__ == '__main__': unittest.main()
