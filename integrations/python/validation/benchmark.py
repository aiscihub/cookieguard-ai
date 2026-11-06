"""Paired real-browser comparison using the installed wheels; no model or API key.

The Browser Use Actor drives identical synthetic login actions in both arms.
Baseline has no audit and makes no cookie-security decision. Imports are outside
the timer. Each trial owns a fresh browser, profile, and local site.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import os
import platform
import statistics
import subprocess
import time
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

# Set before importing Browser Use. No .env file or real profile is loaded.
os.environ['ANONYMIZED_TELEMETRY'] = 'false'
os.environ['BROWSER_USE_CLOUD_SYNC'] = 'false'
os.environ['BROWSER_USE_DISABLE_EXTENSIONS'] = '1'

import browser_use
import cookieguard_browser_use
from browser_use import BrowserProfile, BrowserSession
from cookieguard_browser_use import CookieGuardAudit, CookiePolicyError
from local_site import CASES, TOKEN_PREFIX, Case, LocalSite


async def workflow(session: BrowserSession, site: LocalSite) -> None:
	page = await session.get_current_page()
	if page is None:
		raise RuntimeError('Browser Use did not create a page')
	await page.goto(site.origin + '/login')
	async with asyncio.timeout(15):
		# The Actor API returns immediately; polling is bounded by the timeout.
		while not (buttons := await page.get_elements_by_css_selector('#login')):  # noqa: ASYNC110
			await asyncio.sleep(0.02)
		await buttons[0].click()
		expected = 'No session issued' if site.case.attributes is None else 'Login succeeded'
		while await page.get_title() != expected:  # noqa: ASYNC110
			await asyncio.sleep(0.02)


async def run_trial(case: Case, guarded: bool) -> dict:
	with LocalSite(case) as site:
		start = time.perf_counter()
		session = BrowserSession(
			browser_profile=BrowserProfile(
				headless=True,
				keep_alive=True,
				enable_default_extensions=False,
				user_data_dir=None,
				allowed_domains=['http://127.0.0.1'],
			)
		)
		audit = (
			CookieGuardAudit(
				allowed_origins=[site.origin],
				auth_cookies=['session_id'],
				fail_on='medium',
				require_explicit_same_site=True,
				max_lifetime_days=30,
			)
			if guarded
			else None
		)
		result = None
		error = None
		browser_version = {}
		timing = dict.fromkeys(('browser_start_ms', 'audit_start_ms', 'workflow_ms', 'audit_finish_ms', 'cleanup_ms'), 0.0)
		phase = 'browser_start'
		try:
			t = time.perf_counter()
			await session.start()
			timing['browser_start_ms'] = (time.perf_counter() - t) * 1000
			if audit:
				phase = 'audit_start'
				t = time.perf_counter()
				await audit.start(session)
				timing['audit_start_ms'] = (time.perf_counter() - t) * 1000
			phase = 'workflow'
			t = time.perf_counter()
			await workflow(session, site)
			timing['workflow_ms'] = (time.perf_counter() - t) * 1000
			if audit:
				phase = 'audit_finish'
				t = time.perf_counter()
				result = await audit.finish()
				timing['audit_finish_ms'] = (time.perf_counter() - t) * 1000
			phase = 'version_probe'
			browser_version = await session.cdp_client.send.Browser.getVersion()
		except Exception as caught:
			# Preserve the failure in the data; never record arbitrary exception text
			# which could contain evidence. The process log remains available locally.
			error = {'phase': phase, 'type': type(caught).__name__}
		finally:
			t = time.perf_counter()
			try:
				try:
					if audit:
						await audit.close()
				finally:
					await session.kill()
			except Exception as caught:
				error = error or {'phase': 'cleanup', 'type': type(caught).__name__}
			timing['cleanup_ms'] = (time.perf_counter() - t) * 1000
		# Server setup/shutdown is outside timing, browser setup/kill is inside.
		timing['total_ms'] = (time.perf_counter() - start) * 1000
		timing['audited_workflow_ms'] = sum(timing[k] for k in ('audit_start_ms', 'workflow_ms', 'audit_finish_ms'))
		blocked = False
		if result:
			try:
				result.assert_policy()
			except CookiePolicyError:
				blocked = True
		row = {
			'case': case.name,
			'arm': 'cookieguard' if guarded else 'baseline',
			'expected_status': case.expected_status,
			'expected_rules': list(case.expected_rules),
			'login_succeeded': site.account_visits > 0,
			'status': 'ERROR' if error else result.status if result else 'NOT_AUDITED',
			'error': error,
			'policy_blocked': blocked,
			'confirmed_rules': sorted({f.rule_id for f in result.confirmed_findings}) if result else [],
			'confirmed_evidence': [
				{
					'rule': f.rule_id,
					'cookie': f.cookie_name,
					'source': f.evidence_category,
					'store_status': f.evidence.get('storeStatus'),
				}
				for f in result.confirmed_findings
			]
			if result
			else [],
			'review_rules': sorted({f.rule_id for f in result.review_findings}) if result else [],
			'collection': dict(result.collection) if result else {},
			'issues': list(result.issues) if result else [],
			'timing_ms': timing,
			'browser': browser_version.get('product'),
		}
		serialized = json.dumps(row) + (result.to_json() + result.agent_summary() if result else '')
		if site.token in serialized or TOKEN_PREFIX in serialized:
			raise AssertionError('Synthetic cookie value leaked into results')
		return row


def distribution(values: list[float]) -> dict:
	if not values:
		return {'n': 0, 'median': None, 'p95': None, 'min': None, 'max': None}
	ordered = sorted(values)
	return {
		'n': len(values),
		'median': statistics.median(values),
		'p95': ordered[math.ceil(0.95 * len(values)) - 1],
		'min': ordered[0],
		'max': ordered[-1],
	}


def summarize(rows: list[dict]) -> dict:
	"""Score against fixture ground truth; missing/incomplete evidence never counts as a detection."""
	audited = [r for r in rows if r['arm'] == 'cookieguard']
	positive = [r for r in audited if r['expected_status'] == 'FAIL']
	negative = [r for r in audited if r['expected_status'] == 'PASS']
	gaps = [r for r in audited if r['expected_status'] == 'INCOMPLETE']
	true_positive = sum(r['status'] == 'FAIL' and r['policy_blocked'] for r in positive)
	false_positive = sum(r['status'] == 'FAIL' for r in negative)
	false_negative = len(positive) - true_positive
	true_negative = sum(r['status'] == 'PASS' and not r['policy_blocked'] for r in negative)
	matched = sum(
		len(set(r['expected_rules']) & set(r['confirmed_rules']))
		for r in positive
		if r['status'] == 'FAIL' and r['policy_blocked']
	)
	expected = sum(len(r['expected_rules']) for r in positive)
	unexpected = sum(len(set(r['confirmed_rules']) - set(r['expected_rules'])) for r in audited)
	pairs = {}
	for row in rows:
		pairs.setdefault((row['repetition'], row['case']), {})[row['arm']] = row
	complete = [
		p for p in pairs.values() if set(p) == {'baseline', 'cookieguard'} and all(r['status'] != 'ERROR' for r in p.values())
	]
	paired = {}
	for key in ('workflow_ms', 'audited_workflow_ms', 'total_ms'):
		paired[key] = {
			'delta_ms': distribution([p['cookieguard']['timing_ms'][key] - p['baseline']['timing_ms'][key] for p in complete]),
			'delta_percent': distribution(
				[100 * (p['cookieguard']['timing_ms'][key] / p['baseline']['timing_ms'][key] - 1) for p in complete]
			),
		}
	return {
		'policy': {
			'positive_trials': len(positive),
			'negative_trials': len(negative),
			'true_positive': true_positive,
			'false_negative_incomplete_or_error': false_negative,
			'false_positive': false_positive,
			'true_negative': true_negative,
			'incomplete_negative_trials': sum(r['status'] == 'INCOMPLETE' for r in negative),
			'expected_rule_detections': expected,
			'matched_rule_detections': matched,
			'unexpected_confirmed_rules': unexpected,
			'gap_trials': len(gaps),
			'gaps_reported_incomplete': sum(r['status'] == 'INCOMPLETE' and r['policy_blocked'] for r in gaps),
		},
		'baseline': {'trials': len(rows) - len(audited), 'security_verdict': 'NOT_AUDITED'},
		'execution_errors': {
			arm: sum(r['status'] == 'ERROR' for r in rows if r['arm'] == arm) for arm in ('baseline', 'cookieguard')
		},
		'complete_timing_pairs': len(complete),
		'paired_overhead': paired,
		'timing_ms': {
			arm: {
				key: distribution([r['timing_ms'][key] for r in rows if r['arm'] == arm and r['status'] != 'ERROR'])
				for key in sorted({key for r in rows if r['status'] != 'ERROR' for key in r['timing_ms']})
			}
			for arm in ('baseline', 'cookieguard')
		},
	}


def validate(rows: list[dict]) -> list[str]:
	failures = []
	for r in rows:
		label = f'{r["case"]}/{r["arm"]}/{r["repetition"]}'
		if r['status'] == 'ERROR':
			failures.append(label + ': execution error at ' + r['error']['phase'])
			continue
		if r['login_succeeded'] != (r['case'] != 'missing_session'):
			failures.append(label + ': unexpected login outcome')
		if r['arm'] == 'cookieguard':
			if r['status'] != r['expected_status'] or r['confirmed_rules'] != sorted(r['expected_rules']):
				failures.append(label + ': policy differs from fixture ground truth')
			if r['policy_blocked'] != (r['expected_status'] != 'PASS'):
				failures.append(label + ': assert_policy did not enforce status')
			if r['case'] != 'missing_session' and r['collection']['setCookieResponsesForwarded'] < 1:
				failures.append(label + ': server declaration missing')
			if any(f['source'] != 'server-declaration' or f['store_status'] != 'present' for f in r['confirmed_evidence']):
				failures.append(label + ': expected server declaration and browser acceptance')
	return failures


def environment() -> dict:
	return {
		'python': platform.python_version(),
		'platform': platform.platform(),
		'node': subprocess.check_output([os.environ.get('COOKIEGUARD_NODE', 'node'), '--version'], text=True).strip(),
		'packages': {p: version(p) for p in ('browser-use', 'cookieguard-browser-use', 'cdp-use')},
		'import_locations': {
			'browser_use': str(Path(browser_use.__file__).resolve()),
			'cookieguard_browser_use': str(Path(cookieguard_browser_use.__file__).resolve()),
		},
		'harness_sha256': {
			name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
			for name in ('benchmark.py', 'local_site.py', 'test_benchmark.py')
		},
	}


async def main(args) -> int:
	cases = [c for c in CASES if not args.cases or c.name in args.cases]
	rows = []
	args.output.parent.mkdir(parents=True, exist_ok=True)
	journal = args.output.with_suffix('.jsonl')
	# An exclusive journal prevents accidental overwrite of previous measurements.
	with journal.open('x') as handle:
		handle.write(json.dumps({'environment': args.environment, 'cases': [c.name for c in cases]}) + '\n')

	async def record_trial(case, guarded, repetition):
		t = time.perf_counter()
		try:
			row = await asyncio.wait_for(run_trial(case, guarded), 90)
		except Exception as caught:
			row = {
				'case': case.name,
				'arm': 'cookieguard' if guarded else 'baseline',
				'expected_status': case.expected_status,
				'expected_rules': list(case.expected_rules),
				'login_succeeded': False,
				'status': 'ERROR',
				'policy_blocked': False,
				'confirmed_rules': [],
				'confirmed_evidence': [],
				'review_rules': [],
				'collection': {},
				'issues': [],
				'error': {'phase': 'trial_timeout_or_unhandled', 'type': type(caught).__name__},
				'timing_ms': {'total_ms': (time.perf_counter() - t) * 1000},
				'browser': None,
			}
		row['repetition'] = repetition
		with journal.open('a') as handle:
			handle.write(json.dumps(row) + '\n')
		return row

	# Warm both code paths, discard both observations, then alternate pair order.
	warmups = []
	for guarded in (False, True):
		warmups.append(await record_trial(CASES[0], guarded, 0))
	for repetition in range(1, args.repetitions + 1):
		for index, case in enumerate(cases):
			for guarded in (False, True) if (repetition + index) % 2 else (True, False):
				row = await record_trial(case, guarded, repetition)
				rows.append(row)
				print(
					f'{repetition} {case.name} {row["arm"]}: {row["status"]} ({row["timing_ms"]["total_ms"]:.1f} ms)', flush=True
				)
	failures = validate(warmups + rows)
	data = {
		'schema_version': 1,
		'recorded_at_utc': datetime.now(timezone.utc).isoformat(),
		'environment': args.environment,
		'method': {
			'driver': 'Browser Use Actor; no LLM',
			'repetitions': args.repetitions,
			'fresh_browser_per_trial': True,
			'discarded_warmup_trials': 2,
			'pair_order': 'alternating',
			'policy': {
				'auth_cookies': ['session_id'],
				'fail_on': 'medium',
				'require_explicit_same_site': True,
				'max_lifetime_days': 30,
			},
			'total_includes': 'browser construction/start, audit start, login workflow, audit finish, version probe, cleanup',
			'total_excludes': 'imports, local site startup/shutdown, serialization, assert_policy call',
		},
		'summary': summarize(rows),
		'validation_failures': failures,
		'warmups': warmups,
		'rows': rows,
	}
	args.output.write_text(json.dumps(data, indent=2) + '\n')
	print(json.dumps(data['summary']['policy'], indent=2))
	return 1 if failures else 0


if __name__ == '__main__':
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument('--repetitions', type=int, default=5)
	parser.add_argument('--cases', nargs='+', choices=[c.name for c in CASES])
	parser.add_argument('--output', type=Path, default=Path('artifacts/browser-use-upstream/benchmark.json'))
	args = parser.parse_args()
	if args.repetitions < 1:
		parser.error('--repetitions must be positive')
	if args.output.exists() or args.output.with_suffix('.jsonl').exists():
		parser.error('Output already exists; choose a new --output path to preserve earlier measurements.')
	args.environment = environment()
	raise SystemExit(asyncio.run(main(args)))
