"""Set-Cookie attribution from synthetic CDP event orderings (no browser)."""

import asyncio

from conftest import canary

from cookieguard_browser_use._collector import CdpEvidenceCollector

APP = 'http://127.0.0.1:3000'
IDP = 'http://127.0.0.2:4000'
SID = 'session-1'


class RecordingEngine:
	def __init__(self):
		self.forwarded = []

	async def response(self, url, lines, from_service_worker):
		self.forwarded.append((url, list(lines)))


def collector(origins=(APP,)):
	engine = RecordingEngine()
	return CdpEvidenceCollector(tuple(origins), engine, capture_headers=True), engine


def request(rid, url, redirect=None):
	event = {'requestId': rid, 'request': {'url': url}}
	if redirect:
		event['redirectResponse'] = redirect
	return event


def extra(rid, status, *lines):
	return {'requestId': rid, 'statusCode': status, 'headers': {'set-cookie': '\n'.join(lines)} if lines else {'content-type': 'text/html'}}


def response(rid, url, status, **flags):
	return {'requestId': rid, 'response': {'url': url, 'status': status, **flags}}


def play(c, events):
	async def go():
		for kind, event in events:
			handler = {'request': c._on_request, 'extra': c._on_extra_info, 'response': c._on_response,
				'cache': c._on_served_from_cache, 'done': c._on_loading_done}[kind]
			result = handler(event, SID)
			if asyncio.iscoroutine(result):
				await result
	asyncio.run(go())


def test_redirect_set_cookie_is_attributed_to_its_hop_in_either_order():
	token = canary()
	line = f'session_id={token}; Path=/; HttpOnly'
	orders = [
		# Observed Chromium order: redirect requestWillBeSent precedes the redirect's ExtraInfo.
		[('request', request('r', f'{APP}/session')), ('request', request('r', f'{APP}/account', {'url': f'{APP}/session', 'status': 303})),
			('extra', extra('r', 303, line)), ('extra', extra('r', 200)), ('response', response('r', f'{APP}/account', 200))],
		[('request', request('r', f'{APP}/session')), ('extra', extra('r', 303, line)),
			('request', request('r', f'{APP}/account', {'url': f'{APP}/session', 'status': 303})),
			('response', response('r', f'{APP}/account', 200)), ('extra', extra('r', 200))],
		# ExtraInfo can arrive before requestWillBeSent.
		[('extra', extra('r', 200, line)), ('request', request('r', f'{APP}/login')), ('response', response('r', f'{APP}/login', 200))],
	]
	for events in orders:
		c, engine = collector()
		play(c, events)
		assert len(engine.forwarded) == 1 and engine.forwarded[0][1] == [line]
		assert engine.forwarded[0][0].startswith(APP) and not c.reasons
		assert c.header_cookie_names == {'session_id'}


def test_cross_origin_redirect_forwards_only_authorized_hops():
	idp_line, app_line = f'idp_sid={canary()}; Path=/', f'session_id={canary()}; Path=/; HttpOnly'
	c, engine = collector()
	play(c, [('request', request('r', f'{IDP}/authorize')),
		('request', request('r', f'{APP}/callback', {'url': f'{IDP}/authorize', 'status': 302})),
		('extra', extra('r', 302, idp_line)), ('extra', extra('r', 200, app_line)),
		('response', response('r', f'{APP}/callback', 200))])
	assert engine.forwarded == [(f'{APP}/callback', [app_line])]
	assert not c.reasons


def test_cached_hops_do_not_shift_attribution():
	line = f'session_id={canary()}; Path=/'
	c, engine = collector()
	play(c, [('request', request('r', f'{IDP}/old')),
		('request', request('r', f'{APP}/login', {'url': f'{IDP}/old', 'status': 301, 'fromDiskCache': True})),
		('extra', extra('r', 200, line)), ('response', response('r', f'{APP}/login', 200))])
	assert engine.forwarded == [(f'{APP}/login', [line])]


def test_status_mismatch_is_incomplete_not_misattributed():
	line = f'session_id={canary()}; Path=/'
	c, engine = collector()
	play(c, [('request', request('r', f'{APP}/login')), ('extra', extra('r', 302, line)),
		('response', response('r', f'{APP}/login', 200))])
	assert 'header-attribution-mismatch' in c.reasons


def test_unrelated_origins_are_never_forwarded():
	c, engine = collector()
	play(c, [('request', request('r', 'https://tracker.example.test/pixel')), ('extra', extra('r', 200, f'_t={canary()}')),
		('response', response('r', 'https://tracker.example.test/pixel', 200))])
	assert engine.forwarded == [] and not c.reasons


def test_unattributable_set_cookie_is_dropped_and_counted():
	c, engine = collector()
	play(c, [('extra', extra('orphan', 200, f'session_id={canary()}')), ('extra', extra('orphan', 302))])
	c.settle()
	assert engine.forwarded == [] and c.stats()['unattributedSetCookieResponses'] == 1
	assert all(not request.pending for request in c._requests.values())


def test_mid_flight_attach_uses_the_redirect_response_url():
	line = f'session_id={canary()}; Path=/'
	c, engine = collector()
	play(c, [('extra', extra('r', 302, f'idp={canary()}')),
		('request', request('r', f'{APP}/account', {'url': f'{IDP}/authorize', 'status': 302})),
		('extra', extra('r', 200, line)), ('response', response('r', f'{APP}/account', 200))])
	assert engine.forwarded == [(f'{APP}/account', [line])]


def test_service_worker_responses_make_collection_incomplete():
	c, _ = collector()
	play(c, [('request', request('r', f'{APP}/')), ('response', response('r', f'{APP}/', 200, fromServiceWorker=True))])
	assert 'service-worker-response' in c.reasons


def test_bounds_mark_incomplete():
	c, engine = collector()
	play(c, [('request', request('r', f'{APP}/')), ('extra', extra('r', 200, 'session_id=' + 'x' * 17000))])
	assert 'oversized-set-cookie' in c.reasons and engine.forwarded == []
	c, engine = collector()
	c._forwarded = 1000
	play(c, [('request', request('r', f'{APP}/')), ('extra', extra('r', 200, 'a=b'))])
	assert 'response-limit' in c.reasons


def test_handler_exceptions_are_contained():
	c, _ = collector()
	wrapped = c._guard(lambda event, session_id: event['missing'])
	wrapped({}, SID)
	assert 'collector-error' in c.reasons
