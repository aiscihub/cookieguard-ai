import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, mkdir, readFile, rm } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { configureUsageMetrics } from '../scripts/configure-usage-metrics.js';

test('maintainer configuration synchronizes both languages and rejects secrets or code before writes', async () => {
  const root = await mkdtemp(join(tmpdir(), 'cookieguard-usage-config-'));
  const nodeDir = join(root, 'packages/core/src');
  const pythonDir = join(root, 'integrations/python/src/cookieguard');
  try {
    await mkdir(nodeDir, { recursive: true });
    await mkdir(pythonDir, { recursive: true });
    const token = 'phc_public_test_token_not_a_real_project';
    await configureUsageMetrics({ root, token, region: 'eu' });
    const node = await readFile(join(nodeDir, 'usage-config.js'), 'utf8');
    const python = await readFile(join(pythonDir, '_usage_config.py'), 'utf8');
    assert.ok(node.includes(`PROJECT_TOKEN = '${token}'`));
    assert.ok(python.includes(`PROJECT_TOKEN = "${token}"`));
    assert.ok(node.includes("REGION = 'eu'"));
    assert.ok(python.includes('REGION = "eu"'));
    for (const bad of [undefined, '', 'phx_personal_api_key', 'phc_short', `${token}\n`, `${token}';throw new Error()`, `phc_${'x'.repeat(201)}`]) {
      await assert.rejects(configureUsageMetrics({ root, token: bad }), /public phc_/);
    }
    await assert.rejects(configureUsageMetrics({ root, token, region: 'https://example.test' }), /us or eu/);
    assert.equal(await readFile(join(nodeDir, 'usage-config.js'), 'utf8'), node);
    assert.equal(await readFile(join(pythonDir, '_usage_config.py'), 'utf8'), python);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});
