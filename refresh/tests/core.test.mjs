import assert from 'node:assert/strict';
import test from 'node:test';
import { rootAllowed } from '../robots.mjs';
import { PrivacyGuard, structural, buildMatcher, crossScan } from '../privacy.mjs';
import { normalizeName } from '../common.mjs';
import { selectFrame, parseRanking } from '../frame.mjs';
import { parseCookiebot, parseOneTrust, matchDeclaration, valueShape } from '../cmp.mjs';

test('robots wildcard root blocks; specific paths do not; matching allow wins tie', () => {
  assert.equal(rootAllowed('User-agent: *\nDisallow: /'), false);
  assert.equal(rootAllowed('User-agent: *\nDisallow: /private'), true);
  assert.equal(rootAllowed('User-agent: *\nDisallow: /*'), false);
  assert.equal(rootAllowed('User-agent: *\nDisallow: /$'), false);
  assert.equal(rootAllowed('User-agent: *\nDisallow: /\nAllow: /'), true);
  assert.equal(rootAllowed('User-agent: specific\nDisallow: /\nUser-agent: *\nDisallow:'), true);
});
test('frame is deterministic, without replacement, excludes all historical domains', () => {
  const csv = Array.from({ length: 100000 }, (_, i) => `${i + 1},site${i + 1}.example`).join('\n');
  const excluded = new Set(['site1.example', 'site2.example']);
  const a = selectFrame(csv, excluded, 100, 202611), b = selectFrame(csv, excluded, 100, 202611);
  assert.deepEqual(a, b);
  assert.equal(new Set(a.map(s => s.domain)).size, 100);
  assert.ok(a.every(s => !excluded.has(s.domain) && s.rank <= 100000));
  assert.notDeepEqual(a, selectFrame(csv, excluded, 100, 202612));
  assert.throws(() => parseRanking(csv.replace('100000,site100000.example', '1,duplicate.example')));
});
test('privacy catches a later cookie string in an earlier batch without saving it', () => {
  const guard = new PrivacyGuard(), fixture = ['local', 'fixture', 'sentinel'].join('-');
  guard.check({ earlier: fixture });
  guard.observe([{ value: fixture }]);
  assert.throws(() => guard.check({ earlier: fixture }));
  assert.equal(structural({ nested: [{ value: 'x' }] }), false);
  assert.equal(structural({ valueLength: 1, valueCharacterSet: 'other' }), true);
  assert.equal(structural({ name: 'phc_' + 'q'.repeat(30) }), false);
  assert.doesNotThrow(() => guard.check({ name: fixture }));
});
test('multi-pattern scanner handles suffix overlaps, nested keys, and unicode', () => {
  const patterns = new Set(['abcdefgh', 'bcdefghi', 'cdefghij', '😀fixture']);
  const matcher = buildMatcher(patterns);
  for (const text of ['xabcdefghij', 'x😀fixturex', 'independent text', 'abcdefg']) {
    assert.equal(matcher.count(text) > 0, [...patterns].some(p => text.includes(p)));
  }
  assert.ok(crossScan({ ['prefixabcdefgh']: 'safe' }, patterns).bad > 0);
  assert.equal(crossScan({ name: 'xabcdefgh' }, patterns).bad, 0);
  const many = new Set(Array.from({ length: 5000 }, (_, i) => `private-fixture-${i}-end`));
  const bulk = buildMatcher(many);
  assert.equal(bulk.count('private-fixture-4999-end'), 1);
  assert.equal(bulk.count('independent metadata'), 0);
});
test('CMP parsers retain declarations, resolve conflicts conservatively and match exact names', () => {
  const cb = parseCookiebot('CookieConsentDialog.cookieTableStatistics = [["metrics_id",".fixture.example"]];');
  assert.equal(cb[0].label, 'tracker');
  const ot = parseOneTrust({ DomainData: { Groups: [
    { OptanonGroupId: 'C0001', FirstPartyCookies: [{ Name: 'session_id', Host: 'fixture.example' }] },
    { OptanonGroupId: 'C0004', Hosts: [{ Host: 'fixture.example', Cookies: [{ Name: 'session_id' }] }] }
  ] } });
  assert.equal(matchDeclaration({ name: 'session_id', domain: '.sub.fixture.example' }, ot).label, 'tracker');
  assert.equal(matchDeclaration({ name: 'Session_id', domain: 'fixture.example' }, ot), null);
  assert.equal(matchDeclaration({ name: 'session_id', domain: 'evilfixture.example' }, ot), null);
  assert.deepEqual(valueShape('12'), { valueLength: 2, valueCharacterSet: 'digits' });
  assert.equal(normalizeName('a12345_99'), '#_0');
});
