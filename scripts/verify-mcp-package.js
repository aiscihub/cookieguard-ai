import assert from 'node:assert/strict';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { mkdtemp, mkdir, writeFile, readFile, rm, stat } from 'node:fs/promises';
import { join, resolve } from 'node:path';
import { tmpdir } from 'node:os';
import { createHash } from 'node:crypto';
import { runMcpDemo } from '../examples/mcp/run.js';

const exec = promisify(execFile);
const destination = resolve('artifacts/mcp');
await mkdir(destination, { recursive: true });
await exec(process.execPath, ['scripts/build.js']);
const temp = await mkdtemp(join(tmpdir(), 'cookieguard-mcp-package-'));
try {
  const tarballs = [];
  for (const name of ['@aiscihub/cookieguard-core', 'cookieguard-ci', '@aiscihub/cookieguard-mcp']) {
    const { stdout } = await exec('npm', ['pack', '--workspace', name, '--pack-destination', destination, '--json']);
    const [pack] = JSON.parse(stdout);
    const tarball = join(destination, pack.filename);
    tarballs.push(tarball);
    if (name !== '@aiscihub/cookieguard-mcp') continue;
    for (const path of ['LICENSE', 'README.md', 'src/index.d.ts', 'src/index.js', 'src/config.js', 'bin/cookieguard-mcp.js', 'server.json']) {
      assert.ok(pack.files.some(file => file.path === path), `Missing package file: ${path}`);
    }
    assert.ok(pack.files.every(file => /^(LICENSE|README.md|package.json|server.json|src\/|bin\/)/.test(file.path)));
    const manifest = JSON.parse(await readFile('packages/mcp/package.json', 'utf8'));
    const registry = JSON.parse(await readFile('packages/mcp/server.json', 'utf8'));
    assert.equal(registry.name, manifest.mcpName);
    assert.equal(registry.version, manifest.version);
    assert.equal(registry.packages[0].version, manifest.version);
    assert.equal(registry.packages[0].identifier, manifest.name);
    const bytes = await readFile(tarball);
    const integrity = 'sha512-' + createHash('sha512').update(bytes).digest('base64');
    assert.equal(pack.integrity, integrity);
    await writeFile(join(destination, 'package.json'), JSON.stringify({ name, version: pack.version, filename: pack.filename,
      integrity, sha256: createHash('sha256').update(bytes).digest('hex') }, null, 2) + '\n');
    process.stdout.write(`MCP package: ${pack.filename}; required files and registry metadata match.\n`);
  }
  // npm ci caches locked tarballs, but need not cache the registry metadata
  // required by npm install in a new consumer. Pack the installed runtime
  // dependency closure too, and prove the install works with an empty cache.
  const lock = JSON.parse(await readFile('package-lock.json', 'utf8'));
  for (const name of ['@modelcontextprotocol/server', '@modelcontextprotocol/core', 'zod']) {
    const source = resolve('node_modules', name);
    const { stdout } = await exec('npm', ['pack', source, '--ignore-scripts', '--pack-destination', temp, '--json']);
    const [pack] = JSON.parse(stdout);
    assert.equal(pack.name, name);
    assert.equal(pack.version, lock.packages[`node_modules/${name}`].version);
    tarballs.push(join(temp, pack.filename));
  }
  await writeFile(join(temp, 'package.json'), JSON.stringify({ name: 'cookieguard-mcp-consumer', private: true, type: 'module' }));
  await exec('npm', ['install', '--offline', '--ignore-scripts', '--omit=dev', '--no-audit', '--no-fund', ...tarballs], {
    cwd: temp, env: { ...process.env, npm_config_cache: join(temp, 'npm-cache') },
  });
  process.stdout.write('Offline MCP install passed with an empty npm cache and packed locked runtime dependencies.\n');
  for (const name of ['@modelcontextprotocol/client', 'playwright-core', 'onnxruntime-node']) {
    await assert.rejects(stat(join(temp, 'node_modules', name)), { code: 'ENOENT' });
  }
  const bin = join(temp, 'node_modules/@aiscihub/cookieguard-mcp/bin/cookieguard-mcp.js');
  await exec(process.execPath, ['--input-type=module', '-e', "import { createCookieGuardServer } from '@aiscihub/cookieguard-mcp'; await createCookieGuardServer({allowedOrigins:['http://localhost:3000']}).close();"], { cwd: temp });
  await runMcpDemo(bin);
  process.stdout.write('Isolated MCP tarball consumer passed; no client SDK, browser, or native runtime installed.\n');
} finally { await rm(temp, { recursive: true, force: true }); }
