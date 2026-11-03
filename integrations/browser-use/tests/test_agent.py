"""A real Browser Use Agent loop, driven by a scripted stand-in model (no AI provider, no API key)."""

import json
import os
import subprocess
import sys
import textwrap

import pytest
from conftest import CANARY_PREFIX, assert_clean, run

from cookieguard_browser_use.demo.app import DEMO_PASSWORD
from cookieguard_browser_use.demo.scripted import ScriptedLoginModel, run_scenario

pytestmark = pytest.mark.browser


def test_agent_insecure_login_fails_and_secure_login_passes(token, capfd):
	insecure = run(run_scenario('insecure', token_factory=lambda: token))
	secure = run(run_scenario('secure', token_factory=lambda: token))
	assert insecure.login_succeeded and secure.login_succeeded
	assert insecure.agent_called_audit and secure.agent_called_audit
	assert 'provisional status: FAIL' in insecure.agent_final_text
	assert (insecure.result.status, secure.result.status) == ('FAIL', 'PASS')
	assert 'CG001' in {f.rule_id for f in insecure.result.confirmed_findings}
	assert insecure.result.collection['agentChecks'] == 1
	captured = capfd.readouterr()
	assert_clean(captured.out, captured.err, insecure.result.to_json(), secure.result.to_json(), insecure.agent_final_text)
	assert DEMO_PASSWORD not in captured.out + captured.err  # sensitive_data placeholders are logged instead.


def test_enforcement_does_not_depend_on_the_agent_calling_the_tool(token):
	outcome = run(run_scenario('insecure', call_audit_tool=False, token_factory=lambda: token))
	assert outcome.login_succeeded and not outcome.agent_called_audit
	assert outcome.result.status == 'FAIL' and outcome.result.collection['agentChecks'] == 0


class ClaimsSuccessWithoutLoggingIn(ScriptedLoginModel):
	def _decide(self, messages, text):
		return {'evaluation_previous_goal': 'ok', 'memory': 'ok', 'next_goal': 'done',
			'action': [{'done': {'text': 'Logged in and CookieGuard passed.', 'success': True}}]}


def test_agent_claims_cannot_produce_a_pass(token):
	model = ClaimsSuccessWithoutLoggingIn('http://127.0.0.1:1')
	outcome = run(run_scenario('secure', model=model, token_factory=lambda: token))
	assert not outcome.login_succeeded and 'passed' in outcome.agent_final_text
	assert outcome.result.status == 'INCOMPLETE'
	assert 'expected-auth-cookie-not-observed' in outcome.result.issues


def test_model_visible_messages_contain_no_cookie_values_or_credentials(token):
	model_holder = {}

	class Recording(ScriptedLoginModel):
		def __init__(self, origin, **kwargs):
			super().__init__(origin, **kwargs)
			model_holder['model'] = self

	async def scenario():
		from cookieguard_browser_use.demo import scripted
		original = scripted.ScriptedLoginModel
		scripted.ScriptedLoginModel = Recording
		try:
			return await run_scenario('insecure', token_factory=lambda: token)
		finally:
			scripted.ScriptedLoginModel = original
	outcome = run(scenario())
	messages = '\n'.join(model_holder['model'].observed_messages)
	assert outcome.result.status == 'FAIL'
	assert 'CookieGuard provisional check' in messages  # The model did receive the sanitized audit.
	assert_clean(messages)
	assert DEMO_PASSWORD not in messages


@pytest.mark.parametrize('level', ['info', 'debug'])
def test_process_output_contains_no_cookie_values(level, tmp_path):
	"""Run the whole agent workflow in a fresh process and inspect everything it prints."""
	(tmp_path / 'scripts').mkdir()
	workdir = tmp_path / 'work'
	workdir.mkdir()
	script = tmp_path / 'scripts' / 'run_demo.py'  # Kept outside the scanned working directory.
	script.write_text(textwrap.dedent(f'''
		import asyncio, json, secrets
		from cookieguard_browser_use.demo.scripted import run_scenario
		tokens = iter(f'{CANARY_PREFIX}{{secrets.token_hex(12)}}' for _ in range(10))
		async def main():
			out = {{}}
			for mode in ('insecure', 'secure'):
				outcome = await run_scenario(mode, token_factory=lambda: next(tokens))
				print(outcome.result.summary)
				print(outcome.result.agent_summary())
				outcome.result.write_json('result-' + mode + '.json')
				out[mode] = outcome.result.status
			print(json.dumps(out))
		asyncio.run(main())
	'''))
	env = {**os.environ, 'BROWSER_USE_LOGGING_LEVEL': level, 'ANONYMIZED_TELEMETRY': 'false', 'BROWSER_USE_CLOUD_SYNC': 'false'}
	completed = subprocess.run([sys.executable, str(script)], capture_output=True, text=True, cwd=workdir, env=env, timeout=240)
	assert completed.returncode == 0, 'demo subprocess failed'
	assert json.loads(completed.stdout.strip().splitlines()[-1]) == {'insecure': 'FAIL', 'secure': 'PASS'}
	assert_clean(completed.stdout, completed.stderr)
	written = [path for path in workdir.rglob('*') if path.is_file()]
	assert {path.name for path in written} >= {'result-insecure.json', 'result-secure.json'}
	for path in written:
		assert_clean(path.read_text(errors='replace'))
	assert DEMO_PASSWORD not in completed.stdout + completed.stderr
