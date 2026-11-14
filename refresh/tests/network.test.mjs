import assert from 'node:assert/strict';
import test from 'node:test';
import { checkRobots, requestErrorStatus, ROBOTS_STATUSES } from '../robots.mjs';
import { declaration, fetchText } from '../cmp.mjs';
import { oneSite } from '../crawl.mjs';
import { PrivacyGuard } from '../privacy.mjs';
import { response, requestContext, siteBrowser } from './fakes.mjs';

const origin = 'https://fixture.example';
const decision = async handler => checkRobots(requestContext(handler).context, origin);

test('robots 2xx parses root policy and 4xx including 401/403 permits navigation', async () => {
  assert.deepEqual(await decision(() => response(200, 'User-agent: *\nDisallow: /')), { allowed: false, status: 'disallowed' });
  for (const status of [200, 204, 206]) {
    assert.deepEqual(await decision(() => response(status)), { allowed: true, status: 'allowed' });
  }
  for (let status = 400; status < 500; status++) {
    assert.deepEqual(await decision(() => response(status)), { allowed: true, status: 'absent-4xx' });
  }
});
test('robots follows bare-domain to www and honors a policy across hosts', async () => {
  const { context, requests } = requestContext(url => url === origin + '/robots.txt'
    ? response(301, '', 'https://www.fixture.example/robots.txt') : response(200, 'User-agent: *\nDisallow: /'));
  assert.deepEqual(await checkRobots(context, origin), { allowed: false, status: 'disallowed' });
  assert.equal(requests[1].url, 'https://www.fixture.example/robots.txt');
  assert.ok(requests.every(r => r.options.timeout > 0 && r.options.timeout <= 5000 && r.options.maxRedirects === 0));
});
test('robots accepts five redirects across hosts but refuses a sixth', async () => {
  for (const redirects of [5, 6]) {
    const { context, requests } = requestContext((_url, _options, call) => call <= redirects
      ? response([301, 302, 303, 307, 308][(call - 1) % 5], '', `https://host${call}.example/robots.txt`) : response());
    assert.deepEqual(await checkRobots(context, origin), redirects === 5
      ? { allowed: true, status: 'allowed' } : { allowed: false, status: 'redirect-limit' });
    assert.equal(requests.length, 6);
  }
});
test('robots detects redirect loops, missing locations, and invalid redirect schemes', async () => {
  const loop = requestContext(url => response(302, '', url === origin + '/robots.txt' ? '/again' : '/robots.txt'));
  assert.equal((await checkRobots(loop.context, origin)).status, 'redirect-limit');
  assert.equal(loop.requests.length, 2);
  assert.equal((await decision(() => response(302))).status, 'network-error');
  assert.equal((await decision(() => response(302, '', 'file:///fixture'))).status, 'network-error');
});
test('robots reports server failures, network errors, timeouts and oversized byte bodies', async () => {
  for (const status of [500, 502, 503, 599]) {
    assert.deepEqual(await decision(() => response(status)), { allowed: false, status: 'server-error' });
  }
  for (const [message, status] of [['offline fixture', 'network-error'], ['Timeout 5000ms exceeded', 'unreachable']]) {
    assert.deepEqual(await decision(() => { throw new Error(message); }), { allowed: false, status });
  }
  assert.equal((await decision(() => response(200, 'a'.repeat(500 * 1024)))).status, 'allowed');
  assert.equal((await decision(() => response(200, 'a'.repeat(500 * 1024 + 1)))).status, 'too-large');
  assert.equal((await decision(() => response(200, 'é'.repeat(300000)))).status, 'too-large');
  for (const status of [301, 403, 503]) {
    assert.equal((await decision(() => response(status, 'a'.repeat(500 * 1024 + 1), '/redirect'))).status, 'too-large');
  }
  const bodyFailure = response(); bodyFailure.text = async () => { throw new Error('fixture timeout'); };
  assert.equal((await decision(() => bodyFailure)).status, 'unreachable');
});
test('declaration requests send Referer, permit redirects, retain 7s deadline and 5MB cap', async () => {
  const { context, requests } = requestContext(() => response(200, 'fixture declaration'));
  const referer = origin + '/consent-page';
  assert.equal(await fetchText(context, 'https://cdn.fixture.example/cc.js', referer), 'fixture declaration');
  assert.equal(requests[0].options.headers.Referer, referer);
  assert.equal(requests[0].options.timeout, 7000);
  assert.equal(requests[0].options.maxRedirects, 20);
  await assert.rejects(fetchText(requestContext(() => response(200, 'é'.repeat(2500001))).context, origin, referer), /declaration-too-large/);
  await assert.rejects(fetchText(requestContext(() => response(503)).context, origin, referer), /declaration-unavailable/);
});
test('Cookiebot and every OneTrust fetch use the page URL as Referer and record the family', async () => {
  const id = '11111111-1111-1111-1111-111111111111', rule = '22222222-2222-2222-2222-222222222222';
  const page = scripts => ({ url: () => origin + '/actual-page', locator: () => ({ evaluateAll: async () => scripts }) });
  const cb = requestContext(() => response(200, 'CookieConsentDialog.cookieTableStatistics = [["metrics_id","fixture.example"]];'));
  const seen = [];
  assert.equal((await declaration(cb.context, page([{ src: '', cbid: id }]), family => seen.push(family))).family, 'cookiebot');
  const ot = requestContext(url => response(200, JSON.stringify(url.endsWith(id + '.json')
    ? { RuleSet: [{ Id: rule, LanguageSwitcherPlaceholder: { language: 'en' } }] }
    : { DomainData: { Groups: [{ OptanonGroupId: 'C0001', FirstPartyCookies: [{ Name: 'session_id', Host: 'fixture.example' }] }] } })));
  assert.equal((await declaration(ot.context, page([{ src: 'https://cdn.cookielaw.org/script.js', ddid: id }]), family => seen.push(family))).family, 'onetrust');
  assert.deepEqual(seen, ['cookiebot', 'onetrust']);
  assert.equal(ot.requests.length, 2);
  for (const request of [...cb.requests, ...ot.requests]) assert.equal(request.options.headers.Referer, origin + '/actual-page');
});

const site = { domain: 'fixture.example', rank: 1, siteId: 'fixture', shard: 1 };
const visit = fixture => oneSite(fixture.browser, site, { trancoListId: 'FIXTURE' }, new PrivacyGuard());
test('HTTP fallback after a pre-document HTTPS failure checks the HTTP robots origin', async () => {
  const fixture = siteBrowser({ httpsError: 'net::ERR_CONNECTION_REFUSED', robots: url => response(url.startsWith('http:') ? 403 : 200) });
  const result = await visit(fixture);
  assert.deepEqual(fixture.navigations, [origin + '/', 'http://fixture.example/']);
  assert.deepEqual(fixture.requests.map(r => r.url), [origin + '/robots.txt', 'http://fixture.example/robots.txt']);
  assert.equal(result.visited, true);
  assert.equal(result.robotsStatus, 'absent-4xx');
  assert.equal(result.cmp, 'none');
});
test('HTTP fallback never bypasses a denied HTTP robots policy', async () => {
  const fixture = siteBrowser({ httpsError: 'net::ERR_CONNECTION_REFUSED', robots: url => response(200,
    url.startsWith('http:') ? 'User-agent: *\nDisallow: /' : '') });
  const result = await visit(fixture);
  assert.equal(fixture.navigations.length, 1);
  assert.equal(result.status, 'robots-disallowed');
  assert.equal(result.robotsStatus, 'disallowed');
});
test('certificate errors and errors after a document response never fall back to HTTP', async () => {
  for (const options of [{ httpsError: 'net::ERR_CERT_AUTHORITY_INVALID' },
    { httpsError: 'SSL_PROTOCOL_ERROR' }, { httpsError: 'navigation failed', documentResponded: true }]) {
    const fixture = siteBrowser(options);
    assert.equal((await visit(fixture)).status, 'navigation-failed');
    assert.equal(fixture.navigations.length, 1);
    assert.equal(fixture.requests.length, 1);
  }
});
test('robots skips record a code and never count as visited', async () => {
  const cases = [
    [() => response(503), 'server-error'],
    [() => response(200, 'User-agent: *\nDisallow: /'), 'disallowed'],
    [() => { throw new Error('offline fixture'); }, 'network-error'],
    [url => response(302, '', url), 'redirect-limit'],
    [() => response(200, 'a'.repeat(500 * 1024 + 1)), 'too-large'],
  ];
  for (const [robots, expected] of cases) {
    const fixture = siteBrowser({ robots });
    const result = await visit(fixture);
    assert.equal(result.visited, false);
    assert.equal(result.robotsStatus, expected);
    assert.equal(result.cmp, 'none');
    assert.equal(fixture.navigations.length, 0);
  }
});

test('request errors map to fixed reachability, TLS or protocol codes without returning messages', async () => {
  const groups = {
    unreachable: [
      'getaddrinfo ENOTFOUND fixture.example', 'getaddrinfo EAI_AGAIN fixture.example',
      'getaddrinfo ENOTFOUND certificate.example', 'getaddrinfo ENOTFOUND tls-fixture.example',
      'net::ERR_NAME_NOT_RESOLVED', 'DNS failure', 'name or service not known',
      'connect ECONNREFUSED', 'net::ERR_CONNECTION_REFUSED', 'read ECONNRESET', 'socket hang up',
      'connect ENETUNREACH', 'connect EHOSTUNREACH', 'net::ERR_ADDRESS_UNREACHABLE', 'no route to host',
      'connection reset', 'connection unreachable', 'Timeout 5000ms exceeded', 'request timed out',
      'connect ETIMEDOUT', 'ESOCKETTIMEDOUT', 'net::ERR_TIMED_OUT',
    ],
    'tls-error': [
      'net::ERR_CERT_AUTHORITY_INVALID', 'CERT_HAS_EXPIRED', 'certificate has expired',
      'self signed certificate', 'DEPTH_ZERO_SELF_SIGNED_CERT', 'SELF_SIGNED_CERT_IN_CHAIN',
      'UNABLE_TO_VERIFY_LEAF_SIGNATURE', 'UNABLE_TO_GET_ISSUER_CERT_LOCALLY',
      'ERR_SSL_PROTOCOL_ERROR', 'ERR_TLS_CERT_ALTNAME_INVALID', 'SSL routines: handshake failure',
      'Client network socket disconnected before secure TLS connection was established',
      'TLS handshake timeout ECONNRESET',
    ],
    'network-error': ['unexpected response parser failure', 'Invalid URL', 'unknown request error'],
  };
  for (const [status, messages] of Object.entries(groups)) {
    assert.ok(ROBOTS_STATUSES.includes(status));
    for (const message of messages) {
      const error = new Error(message);
      assert.equal(requestErrorStatus(error), status);
      const result = await decision(() => { throw error; });
      assert.deepEqual(result, { allowed: false, status });
      assert.equal(JSON.stringify(result).includes(message), false);
    }
  }
});
test('an expired robots redirect budget is unreachable', async t => {
  let now = 0;
  t.mock.method(Date, 'now', () => now);
  const fixture = requestContext(() => { now = 5000; return response(301, '', '/next'); });
  assert.deepEqual(await checkRobots(fixture.context, origin), { allowed: false, status: 'unreachable' });
  assert.equal(fixture.requests.length, 1);
});
test('unreachable HTTPS robots checks HTTP robots and starts navigation only over HTTP', async () => {
  for (const error of ['connect ECONNREFUSED', 'getaddrinfo ENOTFOUND fixture.example', 'Timeout 5000ms exceeded']) {
    const fixture = siteBrowser({ robots: url => {
      if (url.startsWith('https:')) throw new Error(error);
      return response(403);
    } });
    const result = await visit(fixture);
    assert.deepEqual(fixture.requests.map(r => r.url), [origin + '/robots.txt', 'http://fixture.example/robots.txt']);
    assert.deepEqual(fixture.navigations, ['http://fixture.example/']);
    assert.equal(result.robotsStatus, 'absent-4xx');
    assert.equal(result.visited, true);
    assert.equal(result.status, 'no-supported-cmp');
  }
});
test('unreachable HTTPS never bypasses an unavailable or disallowed HTTP robots policy', async () => {
  for (const [httpReply, expected] of [
    [() => { throw new Error('request timed out'); }, 'unreachable'],
    [() => response(200, 'User-agent: *\nDisallow: /'), 'disallowed'],
    [() => response(503), 'server-error'],
  ]) {
    const fixture = siteBrowser({ robots: url => {
      if (url.startsWith('https:')) throw new Error('connect ECONNREFUSED');
      return httpReply();
    } });
    const result = await visit(fixture);
    assert.equal(result.robotsStatus, expected);
    assert.equal(result.visited, false);
    assert.equal(fixture.requests.length, 2);
    assert.equal(fixture.navigations.length, 0);
  }
});
test('HTTPS robots TLS errors never fall back or start a page navigation', async () => {
  for (const error of ['CERT_HAS_EXPIRED', 'TLS handshake failure', 'ERR_SSL_PROTOCOL_ERROR']) {
    const fixture = siteBrowser({ robots: () => { throw new Error(error); } });
    const result = await visit(fixture);
    assert.equal(result.robotsStatus, 'tls-error');
    assert.equal(result.visited, false);
    assert.equal(result.status, 'robots-unavailable');
    assert.equal(fixture.requests.length, 1);
    assert.equal(fixture.navigations.length, 0);
  }
});
test('HTTP chosen after an unreachable HTTPS robots origin is not retried on navigation failure', async () => {
  const fixture = siteBrowser({ httpError: 'connect ECONNRESET', robots: url => {
    if (url.startsWith('https:')) throw new Error('connect ECONNREFUSED');
    return response();
  } });
  const result = await visit(fixture);
  assert.equal(result.status, 'navigation-failed');
  assert.equal(fixture.requests.length, 2);
  assert.deepEqual(fixture.navigations, ['http://fixture.example/']);
});
test('a TLS navigation failure uses the same no-fallback classifier as robots', async () => {
  const fixture = siteBrowser({ httpsError: 'TLS handshake failure' });
  assert.equal((await visit(fixture)).status, 'navigation-failed');
  assert.equal(fixture.requests.length, 1);
  assert.deepEqual(fixture.navigations, [origin + '/']);
});
