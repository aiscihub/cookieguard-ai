"""Session rotation (CG010), logout revocation (CG011), and Web Storage tokens (CG012) through Browser Use."""

import asyncio

import pytest
from conftest import assert_clean, browser_session, run
from session_app import STORAGE_TOKEN, SessionApp

from cookieguard import CookieGuardAudit, CookieGuardError

pytestmark = pytest.mark.browser


async def _indices(session) -> dict[str, int]:
	state = await session.get_browser_state_summary(include_screenshot=False)
	found = {}
	for index, node in state.dom_state.selector_map.items():
		attributes = node.attributes or {}
		if attributes.get('id') == 'username':
			found['username'] = index
		elif attributes.get('type') == 'password':
			found['password'] = index
		elif attributes.get('id') == 'logout':
			found['logout'] = index
		elif node.tag_name == 'button':
			found['submit'] = index
	return found


async def _wait_for(session, suffix: str) -> None:
	for _ in range(50):
		if (await session.get_current_page_url()).endswith(suffix):
			return
		await asyncio.sleep(0.1)
	raise AssertionError(f'did not reach {suffix}')


async def audited(app_options: dict, *, logout: bool = True, **audit_options):
	"""Sign in (and out) with Browser Use's own actions, as an agent would."""
	from browser_use import Tools

	with SessionApp(**app_options) as app:
		async with browser_session() as session:
			options = {'allowed_origins': [app.origin], 'auth_cookies': ['sid'], 'auth_storage_keys': ['access_token'],
				'session_probe_url': f'{app.origin}/account', 'require_logout': logout, **audit_options}
			audit = CookieGuardAudit(**options)
			tools = Tools()
			await audit.start(session)
			act = tools.registry.execute_action
			assert not (await act('navigate', {'url': f'{app.origin}/login', 'new_tab': False}, browser_session=session)).error
			fields = await _indices(session)
			for field, text in (('username', 'alice'), ('password', 'pw')):
				assert not (await act('input', {'index': fields[field], 'text': text}, browser_session=session)).error
			assert not (await act('click', {'index': fields['submit']}, browser_session=session)).error
			await _wait_for(session, '/account')
			if logout:
				await asyncio.sleep(0.3)  # Let the account page's script run before signing out.
				assert not (await act('click', {'index': (await _indices(session))['logout']}, browser_session=session)).error
				await _wait_for(session, '/login')
			return await audit.finish()


def rules(result) -> list[str]:
	return sorted(f'{f.rule_id}:{f.status}' for f in result.findings
		if f.rule_id in ('CG010', 'CG011', 'CG012') or f.confirmed)


def test_rotating_and_revoking_app_passes():
	result = run(audited({}))
	assert (result.status, result.exit_code) == ('PASS', 0), result.issues
	session = result.report['session']
	assert session['probe']['status'] == 'ok'
	assert [(c['name'], c['rotation'], c['logout']) for c in session['cookies']] == [('sid', 'rotated', 'revoked')]
	assert rules(result) == []
	assert_clean(result.to_json(), result.summary)


def test_session_id_kept_at_login_is_cg010():
	result = run(audited({'rotate': False}))
	assert result.status == 'FAIL' and rules(result) == ['CG010:confirmed']
	finding = result.confirmed_findings[0]
	assert finding.cookie_name == 'sid' and finding.evidence_category == 'session-probe'
	assert_clean(result.to_json(), result.summary, result.agent_summary())


def test_session_valid_after_logout_is_cg011():
	result = run(audited({'revoke': False}))
	assert result.status == 'FAIL' and rules(result) == ['CG011:confirmed']
	assert result.report['session']['cookies'][0]['logout'] == 'still-valid'
	assert_clean(result.to_json(), result.summary)


def test_token_in_local_storage_is_cg012_without_its_value():
	result = run(audited({'storage_token': True}))
	assert result.status == 'FAIL' and rules(result) == ['CG012:confirmed']
	finding = result.confirmed_findings[0]
	assert (finding.cookie_name, finding.evidence_category) == ('access_token', 'web-storage')
	assert result.report['storage'] == [{'schemaVersion': 1, 'origin': result.report['storage'][0]['origin'],
		'area': 'local', 'key': 'access_token', 'token': 'jwt', 'configured': True}]
	assert STORAGE_TOKEN not in result.to_json() and STORAGE_TOKEN not in result.summary
	off = run(audited({'storage_token': True}, collect_storage=False))
	assert off.report['storage'] == [] and off.status == 'PASS'


def test_required_logout_that_never_happens_is_incomplete():
	result = run(audited({}, logout=False, require_logout=True))
	assert result.status == 'INCOMPLETE' and 'logout-not-observed' in result.issues


def test_session_probe_configuration_is_validated():
	origin = 'http://127.0.0.1:3000'
	for options in ({'session_probe_url': 'http://127.0.0.1:4000/account'},  # another origin
			{'session_probe_url': f'{origin}/account?next=1'},  # query
			{'session_probe_url': f'{origin}/account', 'auth_cookies': None},  # nothing to replay
			{'session_probe_url': f'{origin}/account', 'capture_headers': False},  # values come from Set-Cookie
			{'require_logout': True}):  # no probe to judge logout
		with pytest.raises(CookieGuardError) as error:
			CookieGuardAudit(**{'allowed_origins': [origin], 'auth_cookies': ['sid'], **options})
		assert error.value.code == 'CONFIG'
