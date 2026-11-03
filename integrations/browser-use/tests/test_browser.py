"""Real Chromium through Browser Use: deterministic, no AI model or API key."""

import asyncio

import pytest
from conftest import assert_clean, browser_session, exception_text, login, run

from cookieguard_browser_use import CookieGuardAudit, CookieGuardError
from cookieguard_browser_use.demo.app import DemoApp

pytestmark = pytest.mark.browser


def new_audit(origin, **options):
	return CookieGuardAudit(allowed_origins=[origin], auth_cookies=['session_id'], **options)


def tools_for(audit):
	from browser_use import Tools

	tools = Tools()
	audit.register_tools(tools)
	return tools


async def audited_login(mode, token, **options):
	with DemoApp(mode, token_factory=lambda: token) as app:
		async with browser_session() as session:
			audit = new_audit(app.origin, **options)
			tools = tools_for(audit)
			await audit.start(session)
			await login(tools, session, app.origin)
			agent_view = await tools.registry.execute_action('cookieguard_audit', {}, browser_session=session)
			result = await audit.finish()
			return app.logins, agent_view, result


def test_insecure_login_succeeds_but_fails_cg001(token):
	logins, agent_view, result = run(audited_login('insecure', token))
	assert logins == 1  # The server accepted the login; the cookie policy still fails.
	assert (result.status, result.exit_code) == ('FAIL', 1)
	finding = next(f for f in result.confirmed_findings if f.rule_id == 'CG001')
	assert finding.cookie_name == 'session_id' and finding.evidence_category == 'server-declaration'
	observation = result.report['cookies'][0]['observation']
	assert observation['storeStatus'] == 'present' and observation['sameSite']['declared'] == 'lax'
	assert result.collection['setCookieResponsesForwarded'] == 1 and result.collection['incompleteReasons'] == ()
	assert 'Status: FAIL' in agent_view.extracted_content and 'CG001' in agent_view.extracted_content
	assert_clean(result.to_json(), result.summary, agent_view.extracted_content, agent_view.long_term_memory)


def test_secure_login_passes(token):
	logins, agent_view, result = run(audited_login('secure', token))
	assert logins == 1 and (result.status, result.exit_code) == ('PASS', 0)
	assert not result.findings
	result.assert_policy()
	assert 'Status: PASS' in agent_view.extracted_content
	assert_clean(result.to_json(), agent_view.extracted_content)


def test_browser_observation_only_mode_is_truthful(token):
	_, _, insecure = run(audited_login('insecure', token, capture_headers=False))
	assert insecure.status == 'FAIL' and 'CG001' in {f.rule_id for f in insecure.confirmed_findings}
	_, _, secure = run(audited_login('secure', token, capture_headers=False))
	assert secure.status == 'PASS' and secure.collection['evidence'] == 'browser-store-only'
	observation = secure.report['cookies'][0]['observation']
	assert observation['source'] == 'browser' and observation['sameSite']['declared'] == 'unknown'
	assert {f.rule_id for f in secure.review_findings} == {'CG009'}


def test_audit_started_after_login_cannot_pass_without_declarations(token):
	async def scenario(mode):
		with DemoApp(mode, token_factory=lambda: token) as app:
			async with browser_session() as session:
				audit = new_audit(app.origin)
				tools = tools_for(audit)
				await login(tools, session, app.origin)
				await audit.start(session)
				return await audit.finish()
	secure = run(scenario('secure'))
	assert secure.status == 'INCOMPLETE'
	assert 'auth-cookie-declaration-not-observed' in secure.collection['incompleteReasons']
	insecure = run(scenario('insecure'))  # Observed store state still proves the violation.
	assert insecure.status == 'FAIL'


def test_origin_filtering_excludes_other_hosts(token):
	other_token = token + '_other'

	async def scenario():
		with DemoApp('secure', token_factory=lambda: token) as app, DemoApp('insecure', token_factory=lambda: other_token) as other:
			unauthorized = other.origin.replace('127.0.0.1', 'localhost')
			async with browser_session() as session:
				audit = new_audit(app.origin)
				tools = tools_for(audit)
				await audit.start(session)
				await login(tools, session, unauthorized)
				await login(tools, session, app.origin)
				cookies = await session._cdp_get_cookies()
				return audit, await audit.finish(), cookies
	audit, result, cookies = run(scenario())
	assert {c['domain'] for c in cookies} == {'127.0.0.1', 'localhost'}  # Both logins really happened.
	assert result.status == 'PASS'
	assert {entry['observation']['domain'] for entry in result.report['cookies']} == {'127.0.0.1'}
	assert {entry['observation']['origin'] for entry in result.report['cookies']} == set(audit.origins)
	assert result.collection['setCookieResponsesForwarded'] == 1
	assert_clean(result.to_json())


def test_observer_disconnection_is_incomplete(token):
	async def scenario():
		with DemoApp('secure', token_factory=lambda: token) as app:
			async with browser_session() as session:
				audit = new_audit(app.origin)
				tools = tools_for(audit)
				await audit.start(session)
				await login(tools, session, app.origin)
				await audit._collector._client.ws.close()  # Simulate the CDP connection dropping.
				result = await audit.finish()
				# Browser Use's own connection and the browser are unaffected.
				await tools.registry.execute_action('navigate', {'url': f'{app.origin}/account'}, browser_session=session)
				return result, await session.get_current_page_url()
	result, url = run(scenario())
	assert result.status == 'INCOMPLETE' and 'observer-disconnected' in result.collection['incompleteReasons']
	assert url.endswith('/account')


def test_browser_closed_before_finish_is_incomplete(token):
	async def scenario():
		with DemoApp('insecure', token_factory=lambda: token) as app:
			async with browser_session() as session:
				audit = new_audit(app.origin)
				tools = tools_for(audit)
				await audit.start(session)
				await login(tools, session, app.origin)
				await session.kill()
				return await audit.finish()
	result = run(scenario())
	assert result.status == 'INCOMPLETE' and 'cookie-store-unavailable' in result.collection['incompleteReasons']
	assert_clean(result.to_json())


def test_cleanup_releases_engine_and_observer_and_rejects_reuse(token):
	async def scenario():
		with DemoApp('secure', token_factory=lambda: token) as app:
			async with browser_session() as session:
				audit = new_audit(app.origin)
				tools = tools_for(audit)
				await audit.start(session)
				engine, collector = audit._engine, audit._collector
				process = engine._process
				await login(tools, session, app.origin)
				await audit.finish()
				assert process.returncode is not None and collector._client is None and not collector._tasks
				assert audit.state == 'finished' and audit._session is None
				for call in (audit.finish(), audit.start(session)):
					with pytest.raises(CookieGuardError) as error:
						await call
					assert error.value.code == 'STATE'
				after = await tools.registry.execute_action('cookieguard_audit', {}, browser_session=session)
				assert after.extracted_content.startswith('CookieGuard audit is not active')
				# A new audit on the same browser starts with empty header evidence.
				second = new_audit(app.origin)
				await second.start(session)
				return await second.finish()
	second = run(scenario())
	assert second.status == 'INCOMPLETE' and second.collection['setCookieResponsesForwarded'] == 0


def test_close_without_finish_stops_everything(token):
	async def scenario():
		with DemoApp('secure', token_factory=lambda: token) as app:
			async with browser_session() as session:
				async with new_audit(app.origin) as audit:
					await audit.start(session)
					process, collector = audit._engine._process, audit._collector
				assert audit.state == 'closed' and process.returncode is not None and collector._client is None
	run(scenario())


def test_concurrent_sessions_do_not_share_evidence(token):
	async def scenario():
		with DemoApp('insecure', token_factory=lambda: token + '_a') as insecure_app, \
				DemoApp('secure', token_factory=lambda: token + '_b') as secure_app:
			async with browser_session() as first, browser_session() as second:
				insecure_audit, secure_audit = new_audit(insecure_app.origin), new_audit(secure_app.origin)
				insecure_tools, secure_tools = tools_for(insecure_audit), tools_for(secure_audit)
				await insecure_audit.start(first)
				await secure_audit.start(second)
				await asyncio.gather(login(insecure_tools, first, insecure_app.origin), login(secure_tools, second, secure_app.origin))
				wrong = await insecure_tools.registry.execute_action('cookieguard_audit', {}, browser_session=second)
				return await insecure_audit.finish(), await secure_audit.finish(), wrong
	insecure, secure, wrong = run(scenario())
	assert insecure.status == 'FAIL' and secure.status == 'PASS'
	assert insecure.collection['setCookieResponsesForwarded'] == secure.collection['setCookieResponsesForwarded'] == 1
	assert wrong.extracted_content.startswith('CookieGuard is attached to a different browser session')


def test_login_in_a_new_tab_is_observed(token):
	async def scenario():
		with DemoApp('insecure', token_factory=lambda: token) as app:
			async with browser_session() as session:
				audit = new_audit(app.origin)
				tools = tools_for(audit)
				await audit.start(session)
				# Leave the first tab on a page so Browser Use opens a genuinely new target.
				await tools.registry.execute_action('navigate', {'url': f'{app.origin}/start'}, browser_session=session)
				await login(tools, session, app.origin, new_tab=True)
				assert len(await session.get_tabs()) == 2
				return await audit.finish()
	result = run(scenario())
	assert result.status == 'FAIL' and result.collection['targetsObserved'] >= 2
	assert result.report['cookies'][0]['observation']['source'] == 'header'


def test_failure_paths_do_not_leak(token, capfd):
	async def scenario():
		with DemoApp('insecure', token_factory=lambda: token) as app:
			async with browser_session() as session:
				audit = new_audit(app.origin)
				tools = tools_for(audit)
				await audit.start(session)
				await login(tools, session, app.origin)
				audit._engine._process.kill()  # Engine dies mid-audit.
				await asyncio.sleep(0.2)
				agent_view = await tools.registry.execute_action('cookieguard_audit', {}, browser_session=session)
				with pytest.raises(CookieGuardError) as error:
					await audit.finish()
				return agent_view, error.value
	agent_view, error = run(scenario())
	assert error.code == 'ENGINE' and 'could not complete' in agent_view.extracted_content
	captured = capfd.readouterr()
	assert_clean(exception_text(error), agent_view.extracted_content, captured.out, captured.err)
