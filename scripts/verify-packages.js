import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { mkdir, mkdtemp, writeFile, readFile, rm, stat } from 'node:fs/promises';
import { join, resolve } from 'node:path';
import { tmpdir } from 'node:os';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { createDemoServer } from '../examples/demo/server.js';
import { assertNoSentinels } from './lib/leakage.js';

const exec = promisify(execFile);
const fromRegistry = process.argv[2] === '--registry';
if (process.argv.length > (fromRegistry ? 3 : 2)) throw new Error('Usage: node scripts/verify-packages.js [--registry]');
const names = ['@aiscihub/cookieguard-core', 'cookieguard-ci', '@aiscihub/cookieguard-playwright'];
const destination = resolve('artifacts/packages');
await mkdir(destination, { recursive: true });
const tarballs = [];
const manifest = [];
if (!fromRegistry) await exec(process.execPath, ['scripts/build.js']);
for (const name of fromRegistry ? [] : names) {
  const { stdout } = await exec('npm', ['pack', '--workspace', name, '--pack-destination', destination, '--json']);
  const [result] = JSON.parse(stdout);
  assert.equal(result.name, name);
  assert.equal(result.version, '0.1.0');
  const paths = result.files.map(file => file.path);
  assert.ok(paths.includes('LICENSE') && paths.includes('src/index.d.ts') && paths.includes('README.md'));
  if (name === '@aiscihub/cookieguard-core') assert.ok(paths.includes('vendor/engine.cjs'));
  assert.ok(paths.every(path => !/\.(onnx|node|wasm|dylib|so|dll)$/.test(path)));
  const tarball = join(destination, result.filename);
  const contents = await readFile(tarball);
  const integrity = 'sha512-' + createHash('sha512').update(contents).digest('base64');
  assert.equal(integrity, result.integrity);
  tarballs.push(tarball);
  manifest.push({ name, version: result.version, filename: result.filename, integrity,
    sha256: createHash('sha256').update(contents).digest('hex') });
  process.stdout.write(`${name}: ${result.size} bytes packed; exports, declarations, and license present.\n`);
}
const temporary = await mkdtemp(join(tmpdir(), 'cookieguard-packages-'));
const server = createDemoServer();
const proof = resolve(fromRegistry ? 'artifacts/published' : 'artifacts/packaged');
await mkdir(proof, { recursive: true });
const outcomes = [];
try {
  await writeFile(join(temporary, 'package.json'), JSON.stringify({ name: 'cookieguard-package-smoke', private: true, type: 'module' }));
  const sources = fromRegistry ? names.map(name => `${name}@0.1.0`) : tarballs;
  const network = fromRegistry ? ['--registry=https://registry.npmjs.org'] : ['--offline'];
  await exec('npm', ['install', ...network, '--ignore-scripts', '--no-audit', '--no-fund', ...sources], {
    cwd: temporary, env: { ...process.env, npm_config_cache: join(temporary, 'npm-cache') },
  });
  const bin = join(temporary, 'node_modules/.bin/cookieguard-ci');
  const version = await exec(bin, ['--version'], { cwd: temporary });
  assert.equal(version.stdout.trim(), '0.1.0');
  await exec(process.execPath, ['--input-type=module', '-e', `
    import { normalizeCookie, evaluateCookiePolicy, exitCode } from '@aiscihub/cookieguard-core';
    import { startCookieAudit } from '@aiscihub/cookieguard-playwright';
    import { createOnnxClassifier } from '@aiscihub/cookieguard-core/onnx';
    if (typeof startCookieAudit !== 'function' || typeof createOnnxClassifier !== 'function') process.exit(2);
    const report = evaluateCookiePolicy([normalizeCookie({name:'theme',value:'dark'})]);
    if (exitCode(report) !== 0) process.exit(2);
  `], { cwd: temporary });
  await new Promise((resolve, reject) => server.once('error', reject).listen(0, '127.0.0.1', resolve));
  for (const [path, expected] of [['secure', 0], ['missing-httponly', 1], ['preference', 2]]) {
    for (const format of ['text', 'json']) {
      let result;
      const output = join(temporary, `${path}.${format}`);
      try {
        result = { ...await exec(bin, ['scan', `http://127.0.0.1:${server.address().port}/${path}`,
          '--auth-cookie', 'session_id', '--format', format, '--output', output], { cwd: temporary }), code: 0 };
      } catch (error) { result = error; }
      assertNoSentinels((result.stdout ?? '') + (result.stderr ?? ''));
      assert.equal(result.code, expected);
      const contents = await readFile(output, 'utf8');
      assertNoSentinels(contents);
      assert.equal(contents, result.stdout);
      if (format === 'json') {
        const report = JSON.parse(contents);
        assert.equal(report.status, ['passed', 'failed', 'incomplete'][expected]);
        if (expected === 2) assert.ok(report.issues.includes('expected-auth-cookie-not-observed'));
      }
      await writeFile(join(proof, `${path}.${format}`), contents, { mode: 0o600 });
      outcomes.push({ integration: 'cli', scenario: path, format, expectedExitCode: expected, observedExitCode: result.code });
    }
  }
  // npm ls includes empty entries for uninstalled optional peers. Verify the
  // filesystem itself rather than mistaking those declarations for binaries.
  for (const name of ['onnxruntime-node', 'onnxruntime-common', 'playwright-core']) {
    await assert.rejects(stat(join(temporary, 'node_modules', name)), { code: 'ENOENT' });
  }
  process.stdout.write(`Isolated ${fromRegistry ? 'registry' : 'offline tarball'} CLI install: exit 0/1/2, text/JSON, files/stdout/stderr, and sentinel checks passed; no native or browser runtime installed.\n`);

  // Give the isolated consumer an ordinary Playwright dependency, also packed
  // locally. Its CookieGuard imports resolve only inside the isolated consumer.
  const runtime = await exec('npm', ['pack', resolve('node_modules/playwright-core'), '--ignore-scripts', '--pack-destination', temporary, '--json']);
  const runtimeTarball = join(temporary, JSON.parse(runtime.stdout)[0].filename);
  await exec('npm', ['install', '--offline', '--ignore-scripts', '--no-audit', '--no-fund', runtimeTarball], {
    cwd: temporary, env: { ...process.env, npm_config_cache: join(temporary, 'npm-cache') },
  });
  let browserResult;
  try {
    browserResult = await exec(process.execPath, ['--input-type=module', '-e', `
      import { writeFile } from 'node:fs/promises';
      import { chromium } from 'playwright-core';
      import { startCookieAudit } from '@aiscihub/cookieguard-playwright';
      import { formatJson, exitCode } from '@aiscihub/cookieguard-core';
      const browser = await chromium.launch();
      try {
        for (const [path, expected] of [['secure', 0], ['missing-httponly', 1], ['preference', 2]]) {
          const context = await browser.newContext({serviceWorkers:'block'});
          try {
            const audit = startCookieAudit(context, {origins:[process.env.CG_PACKAGED_ORIGIN],policy:{authCookies:['session_id']}});
            const page = await context.newPage();
            await page.goto(process.env.CG_PACKAGED_ORIGIN + '/' + path);
            const report = await audit.evaluate();
            if (exitCode(report) !== expected) throw new Error('Packaged Playwright policy outcome mismatch.');
            await writeFile('browser-' + path + '.json', formatJson(report), {mode:0o600});
          } finally {await context.close();}
        }
      } finally {await browser.close();}
      process.stdout.write('Installed Playwright adapter: exit 0/1/2 verified.\\n');
    `], { cwd: temporary, env: { ...process.env, CG_PACKAGED_ORIGIN: `http://127.0.0.1:${server.address().port}` } });
  } catch (error) {
    assertNoSentinels((error.stdout ?? '') + (error.stderr ?? ''));
    throw new Error('Isolated Playwright consumer failed. Check the Chromium installation and package exports.');
  }
  assertNoSentinels(browserResult.stdout + browserResult.stderr);
  process.stdout.write(browserResult.stdout);
  for (const [path, expected] of [['secure', 0], ['missing-httponly', 1], ['preference', 2]]) {
    const contents = await readFile(join(temporary, `browser-${path}.json`), 'utf8');
    assertNoSentinels(contents);
    await writeFile(join(proof, `browser-${path}.json`), contents, { mode: 0o600 });
    outcomes.push({ integration: 'playwright', scenario: path, expectedExitCode: expected, observedExitCode: expected });
  }
  await writeFile(join(proof, 'results.json'), JSON.stringify({ installSource: fromRegistry ? 'npm-registry' : 'local-tarballs',
    installedFromTarballs: !fromRegistry, outcomes, sentinelLeaks: 0 }, null, 2) + '\n');
  if (!fromRegistry) await writeFile(join(destination, 'manifest.json'), JSON.stringify({ version: '0.1.0', packages: manifest }, null, 2) + '\n');
} finally {
  if (server.listening) await new Promise(resolve => server.close(resolve));
  await rm(temporary, { recursive: true, force: true });
}
