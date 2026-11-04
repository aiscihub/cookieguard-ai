import assert from 'node:assert/strict';
import { mkdtemp, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { Client } from '@modelcontextprotocol/client';
import { StdioClientTransport } from '@modelcontextprotocol/client/stdio';
import { createDemoServer, DEMO_VALUE } from '../demo/server.js';

export async function runMcpDemo(bin) {
  const temp = await mkdtemp(join(tmpdir(), 'cookieguard-mcp-demo-'));
  const fixture = createDemoServer();
  const client = new Client({ name: 'cookieguard-demo', version: '1.0.0' }, { versionNegotiation: { mode: { pin: '2026-07-28' } } });
  let stderr = '';
  try {
    await new Promise((done, reject) => fixture.once('error', reject).listen(0, '127.0.0.1', done));
    const origin = `http://127.0.0.1:${fixture.address().port}`;
    const path = join(temp, 'cookieguard.json');
    await writeFile(path, JSON.stringify({ allowedOrigins: [origin], policy: { authCookies: ['session_id'] } }));
    const transport = new StdioClientTransport({ command: process.execPath, args: [bin, '--config', path], cwd: temp, stderr: 'pipe' });
    transport.stderr.on('data', data => { stderr += data; });
    await client.connect(transport);
    const { tools } = await client.listTools();
    assert.deepEqual(tools.map(tool => tool.name).sort(), ['cookieguard_policy', 'cookieguard_scan']);
    process.stdout.write('MCP tools: cookieguard_policy, cookieguard_scan\n');
    for (const [endpoint, status, code] of [['secure', 'passed', 0], ['missing-httponly', 'failed', 1], ['preference', 'incomplete', 2]]) {
      const response = await client.callTool({ name: 'cookieguard_scan', arguments: { url: `${origin}/${endpoint}` } });
      assert.equal(JSON.stringify(response).includes(DEMO_VALUE), false, 'Cookie value reached MCP output');
      assert.equal(response.isError, false);
      const report = response.structuredContent;
      assert.equal(report.status, status);
      assert.equal(report.exitCode, code);
      assert.deepEqual(JSON.parse(response.content[0].text), report);
      if (code === 1) assert.ok(report.findings.some(finding => finding.ruleId === 'CG001'));
      process.stdout.write(`${endpoint}: ${report.status.toUpperCase()} (exitCode ${report.exitCode})${code === 1 ? ' — CG001 Missing HttpOnly' : ''}\n`);
    }
  } finally {
    await client.close();
    fixture.closeAllConnections();
    if (fixture.listening) await new Promise(done => fixture.close(done));
    await rm(temp, { recursive: true, force: true });
  }
  assert.equal(stderr, '', 'Unexpected server diagnostics (details withheld)');
  process.stdout.write('MCP demo passed; cookie-value canary absent from results and diagnostics.\n');
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  await runMcpDemo(fileURLToPath(new URL('../../packages/mcp/bin/cookieguard-mcp.js', import.meta.url)));
}
