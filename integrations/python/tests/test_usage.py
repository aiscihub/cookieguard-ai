"""Usage reporting has a fixed payload and never changes audit behavior. No live HTTP."""

import asyncio
import json
import ssl
import threading
import time
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest
from conftest import assert_clean, canary, exception_text, run

from cookieguard import CookieGuardAudit, CookieGuardError, __version__, flush_usage_metrics
from cookieguard import _usage, _usage_config
from cookieguard.browser_use import _audit

TOKEN = 'phc_' + 'a' * 32
ORIGIN = 'http://127.0.0.1:3000'


@pytest.fixture(autouse=True)
def usage_environment(monkeypatch, disable_usage_metrics):
	for name in ('COOKIEGUARD_USAGE_METRICS', 'DO_NOT_TRACK', 'COOKIEGUARD_POSTHOG_PROJECT_TOKEN',
		'COOKIEGUARD_POSTHOG_REGION'):
		monkeypatch.delenv(name, raising=False)
	monkeypatch.setattr(_usage_config, 'PROJECT_TOKEN', TOKEN)
	monkeypatch.setattr(_usage_config, 'REGION', 'us')
	monkeypatch.setattr(_usage, '_reporter', None)
	# Every enabled test supplies its own fake. An accidental request cannot escape.
	def forbid_network(*args, **kwargs):
		raise AssertionError('live metrics transport forbidden')
	monkeypatch.setattr(_usage.http.client, 'HTTPSConnection', forbid_network)
	yield
	assert flush_usage_metrics(1)


@pytest.fixture
def transport(monkeypatch):
	calls = []

	class Connection:
		def __init__(self, host, **kwargs):
			self.call = {'host': host, 'options': kwargs, 'closed': False}
			calls.append(self.call)

		def request(self, method, path, *, body, headers):
			self.call.update(method=method, path=path, body=body, headers=headers)

		def getresponse(self):
			# Redirects/cookies are ignored, and response bodies are never retained.
			return SimpleNamespace(status=302, headers={'Location': 'https://attacker.invalid/',
				'Set-Cookie': 'tracking=forbidden'})

		def close(self):
			self.call['closed'] = True

	monkeypatch.setattr(_usage.http.client, 'HTTPSConnection', Connection)
	return calls


@pytest.fixture
def fake_audit_engine(monkeypatch):
	order = []
	reply = {'exitCode': 0, 'text': 'PASS', 'report': {'status': 'passed', 'findings': [],
		'issues': [], 'limitations': [], 'summary': {'failures': 0}}}

	class Engine:
		def __init__(self, *args):
			order.append('engine-created')

		async def start(self, config):
			order.append('engine-started')

		async def snapshot(self, cookies):
			return reply

		async def finish(self, cookies, baseline, *, session=None, storage=None):
			return reply

		async def close(self):
			pass

	class Collector:
		reasons = set()

		def __init__(self, *args, **kwargs):
			pass

		async def start(self, root):
			pass

		async def stop(self):
			pass

		async def healthy(self):
			return True

		def settle(self):
			pass

		async def store_cookies(self):
			return [], []

		async def storage_entries(self):
			return [], []

		def stats(self):
			return {}

	monkeypatch.setattr(_audit, 'LocalEngine', Engine)
	monkeypatch.setattr(_audit, 'CdpEvidenceCollector', Collector)
	return order


def session(**options):
	return SimpleNamespace(browser_profile=SimpleNamespace(keep_alive=True),
		cdp_client=SimpleNamespace(url='ws://127.0.0.1:9222/devtools/browser/' + canary()), **options)


@pytest.mark.parametrize('region,host', [('us', 'us.i.posthog.com'), ('eu', 'eu.i.posthog.com')])
def test_exact_payload_transport_and_fresh_identity(monkeypatch, transport, fake_audit_engine, region, host):
	monkeypatch.setenv('COOKIEGUARD_POSTHOG_REGION', region)
	monkeypatch.setenv('HTTP_PROXY', 'http://' + canary() + '.invalid')
	monkeypatch.setenv('HTTPS_PROXY', 'http://' + canary() + '.invalid')
	monkeypatch.setenv('USER', canary())
	secret = canary()

	async def exercise():
		for _ in range(2):
			audit = CookieGuardAudit(allowed_origins=['https://' + secret.lower() + '.example.test'],
				allow_nonlocal_origins=True, auth_cookies=[secret], auth_evidence=[{'name': secret}],
				usage_metrics=True)
			await audit.start(session())
			await audit.finish(baseline={'sensitive': secret})

	run(exercise())
	assert flush_usage_metrics(1)
	assert len(transport) == 2
	identities = set()
	for call in transport:
		context = call['options']['context']
		assert isinstance(context, ssl.SSLContext)
		assert context.check_hostname is True and context.verify_mode == ssl.CERT_REQUIRED
		assert {key: value for key, value in call.items() if key != 'body'} == {
			'host': host, 'options': {'timeout': 0.5, 'context': context},
			'closed': True, 'method': 'POST', 'path': '/i/v0/e/',
			'headers': {'Content-Type': 'application/json'},
		}
		payload = json.loads(call['body'])
		identity = payload.pop('distinct_id')
		assert uuid.UUID(identity).version == 4
		identities.add(identity)
		assert payload == {'api_key': TOKEN, 'event': 'cookieguard_invoked', 'properties': {
			'$process_person_profile': False, '$geoip_disable': True, '$ip': '0.0.0.0', 'schema_version': 1,
			'package': 'cookieguard', 'package_version': __version__, 'integration': 'browser-use',
		}}
		assert secret.lower().encode() not in call['body']
		assert_clean(call)
	assert len(identities) == 2


def test_tls_context_ignores_keylog_environment_without_disabling_verification(monkeypatch, tmp_path, transport):
	keylog = tmp_path / 'tls-secrets.log'
	monkeypatch.setenv('SSLKEYLOGFILE', str(keylog))
	_usage.report_invocation(True)
	assert flush_usage_metrics(1)
	assert len(transport) == 1
	context = transport[0]['options']['context']
	assert context.protocol == ssl.PROTOCOL_TLS_CLIENT
	assert context.check_hostname is True and context.verify_mode == ssl.CERT_REQUIRED
	assert context.keylog_filename is None
	assert not keylog.exists()
	assert _usage.os.environ['SSLKEYLOGFILE'] == str(keylog)


@pytest.mark.parametrize('flag,env,dnt', [
	(False, None, None), (False, '1', None), (True, '0', None), (None, '0', None),
	(None, None, '1'), (None, '1', '1'), (True, '1', '1'), (True, None, '1'),
	(None, '', None), (None, 'true', None), (None, 'yes', None), (None, '2', None),
])
def test_opt_out_and_unrecognized_environment_create_no_identity_worker_or_network(monkeypatch, flag, env, dnt):
	for name, value in (('COOKIEGUARD_USAGE_METRICS', env), ('DO_NOT_TRACK', dnt)):
		if value is not None:
			monkeypatch.setenv(name, value)
	calls = []
	for owner, name in ((_usage.uuid, 'uuid4'), (_usage.threading, 'Thread'),
		(_usage.ssl, 'SSLContext'), (_usage.http.client, 'HTTPSConnection')):
		monkeypatch.setattr(owner, name, lambda *args, **kwargs: calls.append((args, kwargs)))
	_usage.report_invocation(flag)
	assert flush_usage_metrics()
	assert calls == [] and _usage._reporter is None


@pytest.mark.parametrize('token,region', [
	('', 'us'), ('phx_' + 'a' * 32, 'us'), ('phc_short', 'us'), ('phc_' + 'a' * 201, 'us'),
	(TOKEN + '\n', 'us'), ('phc_' + 'é' * 32, 'us'), ('phc_' + '/' * 32, 'us'),
	(TOKEN, ''), (TOKEN, 'https://attacker.invalid'), (TOKEN, 'US'),
])
def test_invalid_configuration_is_silent_and_creates_no_worker(monkeypatch, token, region, caplog):
	monkeypatch.setenv('COOKIEGUARD_POSTHOG_PROJECT_TOKEN', token)
	monkeypatch.setenv('COOKIEGUARD_POSTHOG_REGION', region)
	calls = []
	monkeypatch.setattr(_usage.threading, 'Thread', lambda *args, **kwargs: calls.append(args))
	_usage.report_invocation(True)
	assert calls == [] and _usage._reporter is None and not caplog.records


@pytest.mark.parametrize('env', [None, '1'])
def test_default_and_environment_enable_public_config_override(monkeypatch, transport, env):
	if env is not None:
		monkeypatch.setenv('COOKIEGUARD_USAGE_METRICS', env)
	monkeypatch.setenv('COOKIEGUARD_POSTHOG_PROJECT_TOKEN', 'phc_' + 'b' * 32)
	monkeypatch.setenv('COOKIEGUARD_POSTHOG_REGION', 'eu')
	_usage.report_invocation(None)
	assert flush_usage_metrics(1)
	assert len(transport) == 1
	assert transport[0]['host'] == 'eu.i.posthog.com'
	assert json.loads(transport[0]['body'])['api_key'] == 'phc_' + 'b' * 32


@pytest.mark.parametrize('env', ['', 'true', 'yes', '2'])
def test_explicit_api_enable_preserves_override_of_unrecognized_environment(monkeypatch, transport, env):
	monkeypatch.setenv('COOKIEGUARD_USAGE_METRICS', env)
	_usage.report_invocation(True)
	assert flush_usage_metrics(1)
	assert len(transport) == 1


@pytest.mark.parametrize('options', [{}, {'usage_metrics': None}])
def test_default_reporting_starts_only_with_accepted_audit(transport, fake_audit_engine, options):
	async def exercise():
		audit = CookieGuardAudit(allowed_origins=[ORIGIN], **options)
		assert _usage._reporter is None and transport == []
		await audit.start(session())
		await audit.check()
		await audit.finish()
		await audit.close()

	run(exercise())
	assert flush_usage_metrics(1)
	assert len(transport) == 1
	assert json.loads(transport[0]['body'])['api_key'] == TOKEN


def test_start_admission_deduplication_provisional_checks_and_alias(monkeypatch, transport, fake_audit_engine):
	alias_source = Path(__file__).resolve().parents[1] / 'compat' / 'cookieguard-browser-use' / 'src'
	if alias_source.is_dir():
		monkeypatch.syspath_prepend(str(alias_source))
	alias = pytest.importorskip('cookieguard_browser_use')
	assert alias.CookieGuardAudit is CookieGuardAudit
	assert alias.flush_usage_metrics is flush_usage_metrics
	report = _audit.report_invocation

	def record(flag):
		fake_audit_engine.append('usage')
		report(flag)

	monkeypatch.setattr(_audit, 'report_invocation', record)

	async def exercise():
		audit = alias.CookieGuardAudit(allowed_origins=[ORIGIN])
		for invalid, code in ((SimpleNamespace(), 'KEEP_ALIVE'),
			(SimpleNamespace(browser_profile=SimpleNamespace(keep_alive=True), cdp_client=None), 'SESSION')):
			with pytest.raises(CookieGuardError) as error:
				await audit.start(invalid)
			assert error.value.code == code
		assert fake_audit_engine == []
		browser = session()
		results = await asyncio.gather(audit.start(browser), audit.start(browser), return_exceptions=True)
		assert sum(isinstance(result, CookieGuardError) and result.code == 'STATE' for result in results) == 1
		await audit.check()
		await audit.check()
		await audit._agent_check(browser)
		await audit.finish()
		await audit.close()
		with pytest.raises(CookieGuardError):
			await audit.start(browser)

	run(exercise())
	assert flush_usage_metrics(1)
	assert fake_audit_engine[:3] == ['usage', 'engine-created', 'engine-started']
	assert len(transport) == 1


def test_engine_failure_still_counts_one_accepted_invocation(monkeypatch, transport, fake_audit_engine):
	async def fail(self, config):
		raise CookieGuardError('ENGINE')
	monkeypatch.setattr(_audit.LocalEngine, 'start', fail)
	audit = CookieGuardAudit(allowed_origins=[ORIGIN])
	with pytest.raises(CookieGuardError) as error:
		run(audit.start(session()))
	assert error.value.code == 'ENGINE' and audit.state == 'closed'
	with pytest.raises(CookieGuardError):
		run(audit.start(session()))
	assert flush_usage_metrics(1) and len(transport) == 1


@pytest.mark.parametrize('failure', [OSError, TimeoutError])
def test_network_failures_and_timeouts_do_not_change_audits(monkeypatch, fake_audit_engine, failure, caplog, capsys):
	calls = []
	def fail(host, body):
		calls.append(host)
		raise failure(canary())
	monkeypatch.setattr(_usage, '_send', fail)

	async def exercise(flag):
		audit = CookieGuardAudit(allowed_origins=[ORIGIN], usage_metrics=flag)
		await audit.start(session())
		return (await audit.finish()).to_dict()

	baseline = run(exercise(False))
	assert run(exercise(True)) == baseline
	assert flush_usage_metrics(1)
	assert len(calls) == 1 and not caplog.records
	assert capsys.readouterr() == ('', '')


def test_queue_is_bounded_nonblocking_and_flush_is_bounded(monkeypatch):
	entered, release = threading.Event(), threading.Event()
	calls = []
	def block(host, body):
		calls.append(body)
		entered.set()
		release.wait(3)
	monkeypatch.setattr(_usage, '_send', block)
	try:
		_usage.report_invocation(True)
		assert entered.wait(1)
		started = time.monotonic()
		for _ in range(100):
			_usage.report_invocation(True)
		assert time.monotonic() - started < 0.5
		assert _usage._reporter.worker.daemon
		assert _usage._reporter.queue.maxsize == 16 and _usage._reporter.queue.qsize() == 16
		started = time.monotonic()
		assert not flush_usage_metrics(0.02)
		assert time.monotonic() - started < 0.5
	finally:
		release.set()
	assert flush_usage_metrics(1)
	assert len(calls) == 17  # One in flight and at most sixteen queued; excess events were dropped.


def test_worker_creation_failure_is_silent(monkeypatch, fake_audit_engine, caplog):
	def fail(*args, **kwargs):
		raise RuntimeError(canary())
	monkeypatch.setattr(_usage.threading.Thread, 'start', fail)
	audit = CookieGuardAudit(allowed_origins=[ORIGIN], usage_metrics=True)
	run(audit.start(session()))
	run(audit.finish())
	assert _usage._reporter is None and not caplog.records


def test_invalid_usage_flag_is_a_sanitized_config_error():
	with pytest.raises(CookieGuardError) as error:
		CookieGuardAudit(allowed_origins=[ORIGIN], usage_metrics=canary())
	assert error.value.code == 'CONFIG'
	assert_clean(exception_text(error.value))
