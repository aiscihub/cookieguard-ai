"""Regression checks for the scorer: an incomplete check is neither PASS nor a detection."""

from copy import deepcopy

from benchmark import summarize, validate


def pair(expected, actual, expected_rules=(), actual_rules=(), blocked=None):
	base = {
		'case': 'fixture',
		'repetition': 1,
		'arm': 'baseline',
		'expected_status': expected,
		'expected_rules': list(expected_rules),
		'status': 'NOT_AUDITED',
		'confirmed_rules': [],
		'confirmed_evidence': [],
		'collection': {'setCookieResponsesForwarded': 1},
		'policy_blocked': False,
		'login_succeeded': True,
		'timing_ms': {'workflow_ms': 100, 'audited_workflow_ms': 100, 'total_ms': 1000},
	}
	guarded = deepcopy(base)
	guarded.update(
		arm='cookieguard',
		status=actual,
		confirmed_rules=list(actual_rules),
		policy_blocked=actual != 'PASS' if blocked is None else blocked,
	)
	guarded['timing_ms'] = {'workflow_ms': 110, 'audited_workflow_ms': 160, 'total_ms': 1060}
	return [base, guarded]


def test_incomplete_positive_is_not_a_detection():
	rows = pair('FAIL', 'INCOMPLETE', ('CG001',), ('CG001',))
	metrics = summarize(rows)['policy']
	assert metrics['true_positive'] == 0
	assert metrics['false_negative_incomplete_or_error'] == 1
	assert metrics['matched_rule_detections'] == 0
	assert validate(rows)


def test_false_positive_and_unexpected_rules_are_counted():
	metrics = summarize(pair('PASS', 'FAIL', (), ('CG001',)))['policy']
	assert metrics['false_positive'] == 1
	assert metrics['unexpected_confirmed_rules'] == 1
	assert metrics['true_negative'] == 0


def test_incomplete_negative_is_not_a_true_negative():
	metrics = summarize(pair('PASS', 'INCOMPLETE'))['policy']
	assert metrics['true_negative'] == 0
	assert metrics['incomplete_negative_trials'] == 1


def test_policy_failure_without_enforcement_is_not_a_true_positive():
	rows = pair('FAIL', 'FAIL', ('CG001',), ('CG001',), blocked=False)
	assert summarize(rows)['policy']['true_positive'] == 0
	assert validate(rows)


def test_overhead_uses_pairs_and_separates_workflow_from_audit_cost():
	metrics = summarize(pair('PASS', 'PASS'))['paired_overhead']
	assert metrics['workflow_ms']['delta_ms']['median'] == 10
	assert metrics['audited_workflow_ms']['delta_ms']['median'] == 60
	assert metrics['total_ms']['delta_ms']['median'] == 60


def test_missing_detection_and_unexpected_detection_do_not_cancel_out():
	metrics = summarize(pair('FAIL', 'FAIL', ('CG001',), ('CG002',)))['policy']
	assert metrics['expected_rule_detections'] == 1
	assert metrics['matched_rule_detections'] == 0
	assert metrics['unexpected_confirmed_rules'] == 1


def test_startup_failure_is_retained_and_excluded_from_timing_pairs():
	rows = pair('FAIL', 'ERROR', ('CG001',), blocked=False)
	rows[1]['error'] = {'phase': 'browser_start', 'type': 'RuntimeError'}
	metrics = summarize(rows)
	assert metrics['execution_errors']['cookieguard'] == 1
	assert metrics['complete_timing_pairs'] == 0
	assert metrics['policy']['false_negative_incomplete_or_error'] == 1
	assert metrics['paired_overhead']['total_ms']['delta_ms']['n'] == 0
	assert validate(rows) == ['fixture/cookieguard/1: execution error at browser_start']
