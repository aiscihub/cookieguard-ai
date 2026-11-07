"""Policy semantics through the real local engine: the published CookieGuard core and collector."""

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest
from conftest import assert_clean, canary, exception_text, run

from cookieguard import AuditResult, CookieGuardAudit, CookieGuardError, CookiePolicyError
from cookieguard._engine import (LocalEngine, child_env, engine_dir, node_command, resolve_node,
	verify_engine_files)

ORIGIN = 'http://127.0.0.1:3000'
POLICY = CookieGuardAudit(allowed_origins=[ORIGIN], auth_cookies=['session_id']).policy


def header(token, attributes='Secure; HttpOnly; SameSite=Lax', name='session_id'):
	return f'{name}={token}; Path=/; {attributes}'


def stored(token, name='session_id', **fields):
	return {'name': name, 'value': token, 'domain': '127.0.0.1', 'path': '/', 'expires': -1, 'httpOnly': True,
		'secure': True, 'sameSite': 'Lax', 'partitioned': False, **fields}


async def _evaluate(responses, store, policy, incomplete, require_header, baseline, snapshot):
	engine = LocalEngine()
	try:
		await engine.start({'origins': [ORIGIN], 'policy': policy, 'timeoutMs': 60000, 'requireHeaderEvidence': require_header})
		for url, lines in responses:
			await engine.response(url, lines, False)
		if incomplete:
			await engine.mark_incomplete()
		reply = await (engine.snapshot(store) if snapshot else engine.finish(store, baseline))
	finally:
		await engine.close()
	return AuditResult.from_engine(reply, provisional=snapshot, collection={}), reply


def evaluate(responses=(), store=(), *, policy=None, incomplete=False, require_header=False, baseline=None, snapshot=False):
	result, reply = run(_evaluate(list(responses), None if store is None else list(store), policy or POLICY, incomplete,
		require_header, baseline, snapshot))
	assert_clean(result.to_json(), result.summary, result.agent_summary(), json.dumps(reply))
	return result


def rules(result, status=None):
	return {f.rule_id for f in result.findings if status is None or f.status == status}


def test_missing_httponly_is_a_confirmed_cg001_failure(token):
	result = evaluate([(f'{ORIGIN}/login', [header(token, 'Secure; SameSite=Lax')])], [stored(token, httpOnly=False)])
	assert (result.status, result.exit_code) == ('FAIL', 1)
	finding = next(f for f in result.findings if f.rule_id == 'CG001')
	assert finding.confirmed and finding.severity == 'high' and finding.cookie_name == 'session_id'
	assert finding.evidence_category == 'server-declaration' and finding.evidence['storeStatus'] == 'present'
	assert 'JavaScript' in finding.explanation and 'HttpOnly' in finding.recommendation
	with pytest.raises(CookiePolicyError) as error:
		result.assert_policy()
	assert error.value.exit_code == 1 and 'CG001 "session_id"' in str(error.value)


def test_missing_secure_is_a_confirmed_cg002_failure(token):
	result = evaluate([(f'{ORIGIN}/login', [header(token, 'HttpOnly; SameSite=Lax')])], [stored(token, secure=False)])
	assert result.status == 'FAIL' and 'CG002' in rules(result, 'confirmed')


def test_valid_authentication_cookie_passes(token):
	result = evaluate([(f'{ORIGIN}/login', [header(token)])], [stored(token)])
	assert (result.status, result.exit_code, result.findings) == ('PASS', 0, ())
	observation = result.report['cookies'][0]['observation']
	assert observation['source'] == 'header' and observation['sameSite'] == {'declared': 'lax', 'effective': 'lax'}
	result.assert_policy()


def test_unknown_and_candidate_identities_are_review_only(token):
	policy = {**POLICY, 'authCookies': []}
	result = evaluate([(f'{ORIGIN}/', [header(token, 'SameSite=Lax', 'auth_hint')])],
		[stored(token, name='opaque', httpOnly=False, secure=False)], policy=policy)
	assert result.status == 'PASS'
	assert 'CG008' in rules(result) and not result.confirmed_findings


def test_missing_expected_auth_cookie_is_incomplete(token):
	result = evaluate([(f'{ORIGIN}/', ['theme=light; Path=/; SameSite=Lax'])], [stored('light', name='theme')])
	assert (result.status, result.exit_code) == ('INCOMPLETE', 2)
	assert 'expected-auth-cookie-not-observed' in result.issues
	with pytest.raises(CookiePolicyError) as error:
		result.assert_policy()
	assert error.value.exit_code == 2


def test_no_evidence_at_all_is_incomplete():
	result = evaluate([], [])
	assert result.status == 'INCOMPLETE' and 'no-cookies-observed' in result.issues


def test_ambiguous_header_attributes_are_review_not_confirmed(token):
	result = evaluate([(f'{ORIGIN}/', [header(token, 'Secure; Secure=false; SameSite=Lax')])], [stored(token, httpOnly=False)])
	header_findings = [f for f in result.findings if f.evidence_source == 'header']
	assert header_findings and all(not f.confirmed for f in header_findings)


def test_browser_state_never_becomes_a_server_declaration(token):
	result = evaluate([], [stored(token)])
	observation = result.report['cookies'][0]['observation']
	assert observation['source'] == 'browser'
	assert observation['sameSite'] == {'declared': 'unknown', 'effective': 'lax'}
	assert 'CG009' in rules(result, 'review') and result.status == 'PASS'
	assert any('does not establish the original declaration' in item for item in result.limitations)


def test_unspecified_store_samesite_stays_unknown(token):
	cookie = stored(token)
	del cookie['sameSite']
	observation = evaluate([], [cookie]).report['cookies'][0]['observation']
	assert observation['sameSite'] == {'declared': 'unknown', 'effective': None}


def test_partitioned_store_cookie_is_uncertain(token):
	result = evaluate([], [stored(token, httpOnly=False, partitioned=True)])
	assert result.report['cookies'][0]['observation']['confidence'] == 'uncertain'
	assert 'CG001' in rules(result, 'review') and result.status == 'PASS'


def test_rejected_header_is_not_reported_as_an_accepted_cookie(token):
	result = evaluate([(f'{ORIGIN}/', [header(token, 'SameSite=None')])], [])
	observation = result.report['cookies'][0]['observation']
	assert observation['source'] == 'header' and observation['storeStatus'] == 'not-observed'


def test_severity_threshold_controls_failure(token):
	responses = [(f'{ORIGIN}/', [header(token, 'Secure; HttpOnly; SameSite=None')])]
	store = [stored(token, sameSite='None')]
	assert evaluate(responses, store).status == 'PASS'
	medium = evaluate(responses, store, policy={**POLICY, 'failOn': 'medium'})
	assert medium.status == 'FAIL' and 'CG003' in rules(medium, 'confirmed')
	allowed = evaluate(responses, store, policy={**POLICY, 'failOn': 'medium', 'allowedSameSite': ['none']})
	assert allowed.status == 'PASS'


def test_lifetime_policy(token):
	expires = time.time() + 31 * 86400
	result = evaluate([(f'{ORIGIN}/', [header(token, 'Secure; HttpOnly; SameSite=Lax; Max-Age=2678400')])],
		[stored(token, expires=expires)], policy={**POLICY, 'failOn': 'medium'})
	assert result.status == 'FAIL' and 'CG005' in rules(result, 'confirmed')


def test_collection_failure_is_incomplete_even_with_violations(token):
	result = evaluate([(f'{ORIGIN}/', [header(token, 'Secure; SameSite=Lax')])], [stored(token, httpOnly=False)], incomplete=True)
	assert result.status == 'INCOMPLETE' and 'collection-incomplete' in result.issues


def test_unavailable_cookie_store_is_incomplete(token):
	result = evaluate([(f'{ORIGIN}/', [header(token)])], None)
	assert result.status == 'INCOMPLETE'


def test_required_header_evidence_blocks_a_store_only_pass_but_not_a_failure(token):
	missing = evaluate([], [stored(token)], require_header=True)
	assert missing.status == 'INCOMPLETE' and 'collection-incomplete' in missing.issues
	failure = evaluate([], [stored(token, httpOnly=False)], require_header=True)
	assert failure.status == 'FAIL' and 'CG001' in rules(failure, 'confirmed')
	present = evaluate([(f'{ORIGIN}/', [header(token)])], [stored(token)], require_header=True)
	assert present.status == 'PASS'


def test_provisional_snapshot_is_store_only_and_never_satisfies_policy(token):
	result = evaluate([(f'{ORIGIN}/', [header(token)])], [stored(token)], snapshot=True)
	assert result.provisional and result.status == 'PASS'
	assert result.report['cookies'][0]['observation']['source'] == 'browser'
	with pytest.raises(CookiePolicyError) as error:
		result.assert_policy()
	assert error.value.exit_code == 2


def test_baseline_detects_a_protection_regression(token):
	baseline = evaluate([(f'{ORIGIN}/', [header(token)])], [stored(token)]).report
	current = evaluate([(f'{ORIGIN}/', [header(token, 'Secure; SameSite=Lax')])], [stored(token, httpOnly=False)], baseline=baseline)
	regression = next(f for f in current.findings if f.rule_id == 'CG007')
	assert regression.confirmed and list(regression.evidence['changes']) == ['httpOnly']


def test_core_policy_validation_rejects_bad_configuration():
	for policy in ({**POLICY, 'authCookies': ['bad name']}, {**POLICY, 'allowedSameSite': ['bogus']},
		{**POLICY, 'maxLifetimeDays': -1}, {**POLICY, 'unknownKey': True},
		{**POLICY, 'authEvidence': [{'name': 'session_id', 'domain': '127.0.0.1', 'path': '/', 'origin': ORIGIN,
			'validation': 'appeared-during-login'}]}):
		with pytest.raises(CookieGuardError) as error:
			evaluate([], [], policy=policy)
		assert error.value.code == 'CONFIG'


def test_explicit_validated_auth_evidence_confirms_identity(token):
	evidence = {'name': 'sid', 'domain': '127.0.0.1', 'path': '/', 'origin': ORIGIN, 'validation': 'server-session-validated'}
	policy = {**POLICY, 'authCookies': [], 'authEvidence': [evidence]}
	result = evaluate([(f'{ORIGIN}/', [header(token, 'Secure; SameSite=Lax', 'sid')])], [stored(token, name='sid', httpOnly=False)],
		policy=policy)
	assert result.status == 'FAIL' and 'CG001' in rules(result, 'confirmed')


# ----- engine process boundary ----------------------------------------------


def test_vendored_engine_matches_manifest_and_published_versions():
	# Releases vendor the pinned npm engine; development builds vendor the workspace packages.
	# The suite also runs from a copy outside the repository, so read versions from the manifest.
	manifest = json.loads((engine_dir() / 'manifest.json').read_text())
	expected = '0.1.0' if manifest['source'] == 'npm-registry' else manifest['packages'][0]['version']
	assert verify_engine_files() == {'@aiscihub/cookieguard-core': expected, '@aiscihub/cookieguard-playwright': expected}


def test_tampered_engine_is_refused(tmp_path):
	copy = tmp_path / 'engine'
	shutil.copytree(engine_dir(), copy)
	policy = copy / 'node_modules/@aiscihub/cookieguard-core/src/policy.js'
	policy.write_text(policy.read_text().replace("severity: 'high'", "severity: 'info'"))
	with pytest.raises(CookieGuardError) as error:
		verify_engine_files(copy)
	assert error.value.code == 'ENGINE'


def test_missing_or_old_node_is_an_engine_error(tmp_path):
	with pytest.raises(CookieGuardError) as error:
		run(LocalEngine(str(tmp_path / 'missing-node')).start({}))
	assert error.value.code == 'ENGINE'
	fake = tmp_path / 'node'
	fake.write_text('#!/bin/sh\necho v20.11.0\n')
	fake.chmod(0o755)
	with pytest.raises(CookieGuardError) as error:
		run(LocalEngine(str(fake)).start({}))
	assert error.value.code == 'ENGINE'


def test_child_environment_is_minimal(monkeypatch):
	monkeypatch.setenv('NODE_OPTIONS', '--require=/tmp/inject.js')
	monkeypatch.setenv('OPENAI_API_KEY', canary())
	env = child_env()
	assert 'NODE_OPTIONS' not in env and 'OPENAI_API_KEY' not in env
	assert set(env) <= {'PATH', 'NODE_NO_WARNINGS', 'NODE_DISABLE_COLORS', 'ORT_DISABLE_TELEMETRY', 'SYSTEMROOT', 'WINDIR'}


def test_engine_sandbox_denies_writes_and_child_processes(tmp_path):
	copy = tmp_path / 'engine'
	shutil.copytree(engine_dir(), copy)
	target = tmp_path / 'written.txt'
	(copy / 'probe.mjs').write_text(f'''
import {{ writeFileSync }} from 'node:fs';
import {{ execFileSync }} from 'node:child_process';
const out = {{}};
try {{ writeFileSync({json.dumps(str(target))}, 'x'); out.write = 'allowed'; }} catch (e) {{ out.write = e.code; }}
try {{ execFileSync('true'); out.child = 'allowed'; }} catch (e) {{ out.child = e.code; }}
const net = await import('node:net');
await new Promise(resolve => {{
  try {{ const s = net.connect(9, '127.0.0.1'); s.on('error', e => {{ out.net = e.code; resolve(); }}); s.on('connect', () => {{ out.net = 'allowed'; s.destroy(); resolve(); }}); }}
  catch (e) {{ out.net = e.code; resolve(); }}
}});
console.log(JSON.stringify(out));
''')
	completed = subprocess.run(node_command(resolve_node(), copy.resolve(), 'probe.mjs'), capture_output=True, text=True,
		env=child_env(), timeout=30)
	out = json.loads(completed.stdout)
	assert out['write'] == 'ERR_ACCESS_DENIED' and out['child'] == 'ERR_ACCESS_DENIED'
	assert not target.exists()
	major = int(subprocess.run([resolve_node(), '--version'], capture_output=True, text=True).stdout[1:].split('.')[0])
	if major >= 25:
		assert out['net'] == 'ERR_ACCESS_DENIED'


def _raw_bridge(data: bytes) -> subprocess.CompletedProcess:
	directory = engine_dir()
	return subprocess.run(node_command(resolve_node(), directory), input=data, capture_output=True, env=child_env(),
		cwd=directory, timeout=30)


def test_bridge_rejects_malformed_and_oversized_input_without_echo():
	secret = canary()
	start = json.dumps({'protocol': 1, 'type': 'start', 'origins': [ORIGIN], 'policy': POLICY, 'timeoutMs': 60000,
		'requireHeaderEvidence': False})
	cases = {
		'malformed-json': f'{{"protocol":1,"type":"response","url":"{secret}\n'.encode(),
		'before-start': json.dumps({'protocol': 1, 'type': 'response', 'url': secret, 'setCookie': [], 'fromServiceWorker': False}).encode() + b'\n',
		'unknown-start-key': json.dumps({'protocol': 1, 'type': 'start', 'origins': [ORIGIN], 'policy': {}, 'timeoutMs': 60000,
			'requireHeaderEvidence': False, 'extra': secret}).encode() + b'\n',
		'oversized-line': (start + '\n').encode() + secret.encode() * (5 * 1024 * 1024 // len(secret)),
		'bad-store-cookie': (start + '\n' + json.dumps({'protocol': 1, 'type': 'finish', 'id': 1,
			'cookies': [{'name': secret, 'value': secret * 2000}]}) + '\n').encode(),
	}
	for name, data in cases.items():
		completed = _raw_bridge(data)
		assert_clean(completed.stdout.decode(), completed.stderr.decode())
		replies = [json.loads(line) for line in completed.stdout.decode().splitlines()]
		errors = [reply for reply in replies if reply['type'] == 'error']
		assert errors and errors[-1]['fatal'] and errors[-1]['code'] in {'INPUT', 'CONFIG'}, name
		assert all(set(reply) <= {'type', 'protocol', 'code', 'fatal', 'id'} for reply in replies), name


def test_engine_errors_never_include_values(token):
	async def scenario():
		engine = LocalEngine()
		try:
			await engine.start({'origins': [ORIGIN], 'policy': POLICY, 'timeoutMs': 60000, 'requireHeaderEvidence': False})
			await engine.finish([{'name': 'session_id', 'value': token * 2000, 'domain': '127.0.0.1', 'path': '/'}])
		finally:
			await engine.close()
	with pytest.raises(CookieGuardError) as error:
		run(scenario())
	assert_clean(exception_text(error.value))


def test_killed_engine_is_reported_without_details(token):
	async def scenario():
		engine = LocalEngine()
		try:
			await engine.start({'origins': [ORIGIN], 'policy': POLICY, 'timeoutMs': 60000, 'requireHeaderEvidence': False})
			await engine.response(f'{ORIGIN}/', [header(token)], False)
			engine._process.kill()
			await engine._process.wait()
			await engine.finish([stored(token)])
		finally:
			await engine.close()
	with pytest.raises(CookieGuardError) as error:
		run(scenario())
	assert error.value.code == 'ENGINE'
	assert_clean(exception_text(error.value))


def test_result_json_is_written_owner_only(tmp_path, token):
	result = evaluate([(f'{ORIGIN}/', [header(token, 'Secure; SameSite=Lax')])], [stored(token, httpOnly=False)])
	path = result.write_json(tmp_path / 'cookieguard.json')
	assert os.stat(path).st_mode & 0o777 == 0o600
	data = json.loads(Path(path).read_text())
	assert data['status'] == 'FAIL' and data['exitCode'] == 1 and data['report']['schemaVersion'] == 1
	assert_clean(Path(path).read_text())
	assert list(tmp_path.iterdir()) == [path]


def test_explicit_samesite_requirement(token):
	responses = [(f'{ORIGIN}/', [header(token, 'Secure; HttpOnly')])]  # No SameSite attribute at all.
	store = [stored(token, sameSite='Lax')]
	default = evaluate(responses, store, policy={**POLICY, 'failOn': 'medium'})
	assert default.status == 'PASS' and 'CG003' not in rules(default)
	strict = evaluate(responses, store, policy={**POLICY, 'failOn': 'medium', 'requireExplicitSameSite': True})
	assert strict.status == 'FAIL' and 'CG003' in rules(strict, 'confirmed')


def test_host_only_requirement(token):
	responses = [(f'{ORIGIN}/', [header(token, 'Secure; HttpOnly; SameSite=Lax; Domain=127.0.0.1')])]
	default = evaluate(responses, [], policy={**POLICY, 'failOn': 'medium'})
	assert default.status == 'PASS' and 'CG004' in rules(default, 'review')
	strict = evaluate(responses, [], policy={**POLICY, 'failOn': 'medium', 'requireHostOnly': True})
	assert strict.status == 'FAIL' and 'CG004' in rules(strict, 'confirmed')


def test_audit_options_map_to_the_core_policy():
	audit = CookieGuardAudit(allowed_origins=[ORIGIN], auth_cookies=['s'], fail_on='medium', allowed_same_site=('strict',),
		require_explicit_same_site=True, require_host_only=True, max_lifetime_days=7)
	assert audit.policy == {'authCookies': ['s'], 'failOn': 'medium', 'allowedSameSite': ['strict'],
		'requireExplicitSameSite': True, 'requireHostOnly': True, 'maxLifetimeDays': 7, 'authEvidence': [], 'authStorageKeys': []}
