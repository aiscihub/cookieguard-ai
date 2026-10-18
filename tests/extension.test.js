import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { runInNewContext } from 'node:vm';
import { classifyCookie, extractCookieFeatures, FEATURE_NAMES } from '@aiscihub/cookieguard-core';

test('extension browser-global behavior and canonical Node feature order match original fixtures', async () => {
  const code = await readFile(new URL('../extension-standalone/engine.js', import.meta.url), 'utf8');
  const window = {};
  runInNewContext(code, { window, Float32Array, Date });
  const metadata = JSON.parse(await readFile(new URL('../extension-standalone/model/model_meta.json', import.meta.url), 'utf8'));
  assert.deepEqual(FEATURE_NAMES, metadata.feature_names);
  for (const fixture of ['sample-secure.json', 'sample-insecure.json', 'sample-before-login.json', 'sample-after-login.json']) {
    const input = JSON.parse(await readFile(new URL(`../test/${fixture}`, import.meta.url), 'utf8'));
    for (const cookie of input.cookies) {
      const browser = window.CookieGuardEngine.extractFeatures(cookie);
      const node = extractCookieFeatures(cookie);
      assert.deepEqual(Object.fromEntries(Object.entries(browser)), node);
      assert.equal(window.CookieGuardEngine.classifyRuleBased(browser).type, classifyCookie(cookie).label);
      assert.deepEqual([...window.CookieGuardEngine.featuresToArray(browser)], FEATURE_NAMES.map(name => Math.fround(node[name] || 0)));
    }
  }
});
