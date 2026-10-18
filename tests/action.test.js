import { test } from 'node:test';
import assert from 'node:assert/strict';
import { execFile } from 'node:child_process';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createDemoServer, DEMO_VALUE } from '../examples/demo/server.js';

test('action runner emits sanitized report, summary, and failure output against local app', async () => {
  const server = createDemoServer();
  const temp = await mkdtemp(join(tmpdir(), 'cookieguard-action-'));
  await new Promise((resolve, reject) => server.once('error', reject).listen(0, '127.0.0.1', resolve));
  try {
    for (const [path, expected] of [['secure', 0], ['missing-httponly', 1], ['preference', 2]]) {
      const output = join(temp, `${path}-output`);
      const summary = join(temp, `${path}-summary`);
      const result = await new Promise(resolve => execFile(process.execPath, ['action/run.js'], {
        env: { ...process.env, RUNNER_TEMP: temp, GITHUB_OUTPUT: output, GITHUB_STEP_SUMMARY: summary,
          CG_TARGET: `http://127.0.0.1:${server.address().port}/${path}`, CG_AUTH_COOKIES: 'session_id', CG_FAIL_ON: 'high' },
      }, (error, stdout, stderr) => resolve({ code: error?.code ?? 0, text: stdout + stderr })));
      assert.equal(result.code, 0); // Enforcement runs after artifact upload in the composite.
      const outputs = await readFile(output, 'utf8');
      assert.match(outputs, new RegExp(`exit-code=${expected}\\n`));
      const reportPath = outputs.match(/report-path=(.*)/)[1];
      const artifacts = result.text + outputs + await readFile(reportPath, 'utf8') + await readFile(summary, 'utf8');
      assert.equal(artifacts.includes(DEMO_VALUE), false, 'Sensitive sentinel was emitted');
    }
  } finally { await new Promise(resolve => server.close(resolve)); await rm(temp, { recursive: true, force: true }); }
});
