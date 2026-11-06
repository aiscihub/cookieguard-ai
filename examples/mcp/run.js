import assert from 'node:assert/strict';
import { mkdtemp, mkdir, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { Client } from '@modelcontextprotocol/client';
import { StdioClientTransport } from '@modelcontextprotocol/client/stdio';
import { runCli } from 'cookieguard-ci';
import { createDemoServer, DEMO_VALUE } from '../demo/server.js';

const TOOLS = ['cookieguard_audit', 'cookieguard_capabilities', 'cookieguard_explain', 'cookieguard_policy', 'cookieguard_scan'];

export async function runMcpDemo(bin) {
  const temp = await mkdtemp(join(tmpdir(), 'cookieguard-mcp-demo-'));
  const fixture = createDemoServer();
  const client = new Client({ name: 'cookieguard-demo', version: '1.0.0' }, { versionNegotiation: { mode: { pin: '2026-07-28' } } });
  let stderr = '';
  try {
    await new Promise((done, reject) => fixture.once('error', reject).listen(0, '127.0.0.1', done));
    const origin = `http://127.0.0.1:${fixture.address().port}`;
    const evidenceDir = join(temp, 'evidence');
    await mkdir(evidenceDir);
    const path = join(temp, 'cookieguard.json');
    await writeFile(path, JSON.stringify({ allowedOrigins: [origin], policy: { authCookies: ['session_id'] }, evidenceDir }));
    const transport = new StdioClientTransport({ command: process.execPath, args: [bin, '--config', path], cwd: temp, stderr: 'pipe' });
    transport.stderr.on('data', data => { stderr += data; });
    await client.connect(transport);
    const call = async (name, args = {}) => {
      const response = await client.callTool({ name, arguments: args });
      assert.equal(JSON.stringify(response).includes(DEMO_VALUE), false, 'Cookie value reached MCP output');
      assert.deepEqual(JSON.parse(response.content[0].text), response.structuredContent);
      return response;
    };
    const { tools } = await client.listTools();
    assert.deepEqual(tools.map(tool => tool.name).sort(), TOOLS);
    process.stdout.write(`MCP tools: ${TOOLS.join(', ')}\n`);

    // 1. Discover what the server can do and how it is configured.
    const capabilities = (await call('cookieguard_capabilities')).structuredContent;
    assert.equal(capabilities.configuration.evidenceFiles, true);
    process.stdout.write(`Capabilities: ${capabilities.checks.length} checks; allowed origins: ${capabilities.configuration.allowedOrigins.length}; evidence files: enabled\n`);

    // 2. Audit live endpoints on the allowed origin.
    for (const [endpoint, status, code] of [['secure', 'passed', 0], ['missing-httponly', 'failed', 1], ['preference', 'incomplete', 2]]) {
      const response = await call('cookieguard_audit', { url: `${origin}/${endpoint}` });
      assert.equal(response.isError, false);
      const report = response.structuredContent;
      assert.equal(report.status, status);
      assert.equal(report.exitCode, code);
      const detail = code === 1 ? ' — CG001 Missing HttpOnly' : code === 2 ? ` — ${report.issues.join(', ')}` : '';
      if (code === 1) assert.ok(report.findings.some(finding => finding.ruleId === 'CG001' && finding.status === 'confirmed'));
      process.stdout.write(`${endpoint}: ${report.status.toUpperCase()} (exitCode ${report.exitCode})${detail}\n`);
    }

    // 3. Explain the confirmed finding.
    const explanation = (await call('cookieguard_explain', { id: 'CG001' })).structuredContent.explanation;
    assert.equal(explanation.kind, 'rule');
    process.stdout.write(`Explain CG001: ${explanation.fix}\n`);

    // 4. Hand off evidence from a separate run: the CLI writes a sanitized report,
    //    and the server re-evaluates it under its own fixed policy.
    const quiet = { stdout: { write() {} }, stderr: { write() {} } };
    assert.equal(await runCli(['scan', `${origin}/missing-httponly`, '--auth-cookie', 'session_id', '--json',
      '--output', join(evidenceDir, 'login-report.json')], quiet), 1);
    const evidence = (await call('cookieguard_audit', { evidenceFile: 'login-report.json' })).structuredContent;
    assert.equal(evidence.status, 'failed');
    assert.equal(evidence.provenance.observedByServer, false);
    process.stdout.write(`Evidence login-report.json: ${evidence.status.toUpperCase()} (exitCode ${evidence.exitCode}); observed by server: no\n`);
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
