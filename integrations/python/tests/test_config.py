"""Configuration, authorization boundaries, and lifecycle preconditions (no browser launch)."""

import pytest
from conftest import assert_clean, canary, exception_text, run

from cookieguard import CookieGuardAudit, CookieGuardError


def audit(**options):
	return CookieGuardAudit(**{'allowed_origins': ['http://127.0.0.1:3000'], 'auth_cookies': ['session_id'], **options})


def test_loopback_origins_are_normalized_and_deduplicated():
	value = audit(allowed_origins=['http://127.0.0.1:3000/', 'http://127.0.0.1:3000', 'http://LOCALHOST:80',
		'http://[::1]:8080', 'https://127.0.0.2:443'])
	assert value.origins == ('http://127.0.0.1:3000', 'http://localhost', 'http://[::1]:8080', 'https://127.0.0.2')
	assert value.browser_allowed_domains() == ['http://127.0.0.1', 'http://localhost', 'http://[::1]', 'https://127.0.0.2']


def test_nonlocal_origins_require_explicit_authorization():
	with pytest.raises(CookieGuardError) as error:
		audit(allowed_origins=['https://staging.example.test'])
	assert error.value.code == 'TARGET'
	authorized = audit(allowed_origins=['https://staging.example.test'], allow_nonlocal_origins=True)
	assert authorized.origins == ('https://staging.example.test',)
	# A loopback-looking name is not loopback.
	with pytest.raises(CookieGuardError):
		audit(allowed_origins=['http://127.0.0.1.example.test'])


@pytest.mark.parametrize('origin', [
	'http://127.0.0.1:3000/login', 'http://127.0.0.1:3000/?next=1', 'http://127.0.0.1:3000/#x',
	'http://user:pass@127.0.0.1:3000', 'ftp://127.0.0.1', 'javascript:alert(1)', '127.0.0.1:3000', '',
	'http://127.0.0.1:99999', 'http://bücher.test',
])
def test_origins_must_be_exact_http_origins(origin):
	with pytest.raises(CookieGuardError):
		audit(allowed_origins=[origin], allow_nonlocal_origins=True)


def test_origin_list_is_bounded_and_not_a_string():
	with pytest.raises(CookieGuardError):
		audit(allowed_origins='http://127.0.0.1:3000')
	with pytest.raises(CookieGuardError):
		audit(allowed_origins=[])
	with pytest.raises(CookieGuardError):
		audit(allowed_origins=[f'http://127.0.0.1:{3000 + i}' for i in range(21)])


@pytest.mark.parametrize('options', [
	{'fail_on': 'hgh'}, {'auth_cookies': 'session_id'}, {'allowed_same_site': 'lax'},
	{'capture_headers': False, 'require_header_evidence': True}, {'timeout_seconds': 0},
	{'timeout_seconds': 601}, {'require_host_only': 'yes'}, {'max_lifetime_days': True}, {'auth_evidence': ['x']},
])
def test_invalid_options_are_rejected(options):
	with pytest.raises(CookieGuardError) as error:
		audit(**options)
	assert error.value.code == 'CONFIG'


def test_header_evidence_requirement_defaults_to_header_capture():
	assert audit().require_header_evidence is True
	assert audit(capture_headers=False).require_header_evidence is False


def test_errors_never_echo_input():
	secret = canary()
	for options in ({'allowed_origins': [f'http://127.0.0.1:3000/{secret}']},
		{'allowed_origins': [f'https://{secret.lower()}.example.test']}, {'fail_on': secret}):
		with pytest.raises(CookieGuardError) as error:
			audit(**options)
		assert_clean(exception_text(error.value))
		assert secret.lower() not in exception_text(error.value).lower()


def test_start_requires_keep_alive_and_a_started_session():
	from browser_use import BrowserProfile, BrowserSession

	closing = BrowserSession(browser_profile=BrowserProfile(headless=True, keep_alive=False))
	with pytest.raises(CookieGuardError) as error:
		run(audit().start(closing))
	assert error.value.code == 'KEEP_ALIVE'
	unstarted = BrowserSession(browser_profile=BrowserProfile(headless=True, keep_alive=True))
	value = audit()
	with pytest.raises(CookieGuardError) as error:
		run(value.start(unstarted))
	assert error.value.code == 'SESSION'


def test_finish_and_check_require_a_running_audit():
	value = audit()
	for call in (value.finish, value.check):
		with pytest.raises(CookieGuardError) as error:
			run(call())
		assert error.value.code == 'STATE'
	run(value.close())
	assert value.state == 'closed'


def test_tool_registration_uses_the_browser_use_registry():
	from browser_use import Tools

	tools = Tools()
	value = audit()
	value.register_tools(tools)
	action = tools.registry.registry.actions['cookieguard_audit']
	assert 'never cookie values' in action.description
	assert set(action.param_model.model_fields) == {'note'}
	custom = Tools()
	value.register_tools(custom, action_name='security_cookie_check')
	assert 'security_cookie_check' in custom.registry.registry.actions
	with pytest.raises(CookieGuardError):
		value.register_tools(Tools(), action_name='not valid')


def test_tool_before_start_returns_fixed_text():
	from browser_use import BrowserProfile, BrowserSession, Tools

	tools = Tools()
	value = audit()
	value.register_tools(tools)
	session = BrowserSession(browser_profile=BrowserProfile(headless=True, keep_alive=True))
	action = tools.registry.registry.actions['cookieguard_audit']
	result = run(action.function(params=action.param_model(), browser_session=session))
	assert result.extracted_content.startswith('CookieGuard audit is not active')


def test_demo_command_line_defaults_and_validation(capsys):
	from cookieguard.browser_use.demo.__main__ import parse_args

	assert parse_args([]).modes == ['insecure', 'secure']  # Regression: Python 3.11 rejected [] with choices.
	assert parse_args(['secure', '--headed']).modes == ['secure']
	with pytest.raises(SystemExit) as error:
		parse_args(['bogus'])
	assert error.value.code == 2 and 'unknown mode' in capsys.readouterr().err
