import assert from 'node:assert/strict';
import test from 'node:test';
import { chromium } from '@playwright/test';
import { oneSite } from '../crawl.mjs';
import { PrivacyGuard } from '../privacy.mjs';

test('isolated browser fixture exercises consent, reload, matching, 38 features and privacy', { timeout: 40000 }, async () => {
  const browser = await chromium.launch({ headless: true });
  const contents = ['synthetic', 'local', 'fixture'].join('-');
  const html = '<html><body>Local fixture<script data-cbid="11111111-1111-1111-1111-111111111111">' +
    'window.Cookiebot={submitCustomConsent(){document.cookie="metrics_id=' + contents + '; Path=/; Secure";}};' +
    '</script></body></html>';
  // All HTTP operations are fulfilled in memory, including robots and declarations.
  // This test contacts no domain and adds no public site to the dry run.
  const fixtureBrowser = { async newContext(options) {
    const context = await browser.newContext(options);
    return new Proxy(context, { get(target, key) {
      if (key === 'request') return { get: async url => ({ status: () => 200, ok: () => true,
        text: async () => url.endsWith('/robots.txt') ? 'User-agent: *\nAllow: /' :
          'CookieConsentDialog.cookieTableStatistics = [["metrics_id","fixture.example"]];' }) };
      if (key === 'newPage') return async () => {
        const page = await context.newPage();
        return new Proxy(page, { get(p, k) {
          if (k === 'route') return (pattern, handler) => page.route(pattern, route => handler({
            request: () => route.request(), abort: () => route.abort(),
            continue: () => route.fulfill({ status: 200, contentType: 'text/html', body: html })
          }));
          return typeof p[k] === 'function' ? p[k].bind(p) : p[k];
        } });
      };
      return typeof target[key] === 'function' ? target[key].bind(target) : target[key];
    } });
  } };
  try {
    const guard = new PrivacyGuard();
    const result = await oneSite(fixtureBrowser, { rank: 1, domain: 'fixture.example', siteId: 'fixture', shard: 1 },
                                 { trancoListId: 'FIXTURE' }, guard);
    assert.equal(result.status, 'usable');
    assert.equal(result.visited, true);
    assert.equal(result.robotsStatus, 'allowed');
    assert.equal(result.cmp, 'cookiebot');
    assert.equal(result.rows.length, 1);
    assert.equal(result.rows[0].features.length, 38);
    assert.equal(result.rows[0].label, 'tracker');
    assert.equal(result.rows[0].valueLength, contents.length);
    assert.equal(JSON.stringify(result).includes(contents), false);
    assert.doesNotThrow(() => guard.check(result));
  } finally { await browser.close(); }
});
