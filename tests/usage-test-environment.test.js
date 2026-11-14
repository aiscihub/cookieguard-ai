import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';

const mock = new URL('./fixtures/usage-worker.mjs', import.meta.url).href;
const usage = new URL('../packages/core/src/usage.js', import.meta.url).href;

for (const path of ['./fixtures/disable-usage.mjs', '../examples/playwright/playwright.config.js', '../examples/ci-demo/playwright.config.js']) {
  test(`verification opt-out overrides inherited opt-in and reaches child processes: ${path}`, () => {
    const setup = new URL(path, import.meta.url).href;
    const result = spawnSync(process.execPath, ['--import', mock, '--import', setup, '--input-type=module', '-e', `
      import assert from 'node:assert/strict';
      import { spawnSync } from 'node:child_process';
      import { workers } from ${JSON.stringify(mock)};
      import { reportUsage } from ${JSON.stringify(usage)};
      assert.equal(process.env.COOKIEGUARD_USAGE_METRICS, '0');
      assert.equal(process.env.DO_NOT_TRACK, '1');
      reportUsage({ package: 'cookieguard-ci', version: '0.2.0', integration: 'cli', enabled: true });
      assert.equal(workers.length, 0);
      const child = spawnSync(process.execPath, ['-e',
        'process.stdout.write(JSON.stringify([process.env.COOKIEGUARD_USAGE_METRICS, process.env.DO_NOT_TRACK]))'], {encoding:'utf8'});
      assert.equal(child.status, 0);
      assert.deepEqual(JSON.parse(child.stdout), ['0', '1']);
    `], { env: { ...process.env, COOKIEGUARD_USAGE_METRICS: '1', DO_NOT_TRACK: '0',
      COOKIEGUARD_POSTHOG_PROJECT_TOKEN: 'phc_synthetic_test_project_token' }, encoding: 'utf8', timeout: 5000 });
    assert.equal(result.error, undefined);
    assert.equal(result.status, 0, result.stderr);
    assert.equal(result.stdout + result.stderr, '');
  });
}
