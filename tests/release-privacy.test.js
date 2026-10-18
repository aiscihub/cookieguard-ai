import { test } from 'node:test';
import assert from 'node:assert/strict';
import { assertNoSentinels, SENTINELS } from '../scripts/lib/leakage.js';

test('release output guard rejects injected tokens without reflecting them in errors', () => {
  for (const value of SENTINELS) {
    for (const output of [`report: ${value}`, Buffer.from(`log: ${value}`)]) {
      assert.throws(() => assertNoSentinels(output), error => {
        assert.equal(error.message.includes(value), false);
        return error.message.includes('Output withheld');
      });
    }
  }
  assert.doesNotThrow(() => assertNoSentinels('CookieGuard CI: PASSED — no values in report.'));
});
