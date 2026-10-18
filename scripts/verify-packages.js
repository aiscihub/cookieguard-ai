import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { mkdir, mkdtemp, writeFile, readFile, rm, stat } from 'node:fs/promises';
import { join, resolve } from 'node:path';
import { tmpdir } from 'node:os';
import assert from 'node:assert/strict';
import { createDemoServer } from '../examples/demo/server.js';
import { assertNoSentinels } from './lib/leakage.js';

const exec = promisify(execFile);
await exec(process.execPath, ['scripts/build.js']);
const destination = resolve('artifacts/packages');
await mkdir(destination, { recursive: true });
const tarballs = [];
for (const name of ['@cookieguard/core', 'cookieguard-ci', '@cookieguard/playwright']) {
  const { stdout } = await exec('npm', ['pack', '--workspace', name, '--pack-destination', destination, '--json']);
  const [result] = JSON.parse(stdout);
  const paths = result.files.map(file => file.path);
  assert.ok(paths.includes('LICENSE') && paths.includes('src/index.d.ts') && paths.includes('README.md'));
  if (name === '@cookieguard/core') assert.ok(paths.includes('vendor/engine.cjs'));
  assert.ok(paths.every(path => !/\.(onnx|node|wasm|dylib|so|dll)$/.test(path)));
  tarballs.push(join(destination, result.filename));
  process.stdout.write(`${name}: ${result.size} bytes packed; exports, declarations, and license present.\n`);
}
const temporary = await mkdtemp(join(tmpdir(), 'cookieguard-packages-'));
const server = createDemoServer();
const proof = resolve('artifacts/packaged');
await mkdir(proof, { recursive: true });
const outcomes = [];
try {
  await writeFile(join(temporary, 'package.json'), JSON.stringify({ name: 'cookieguard-package-smoke', private: true, type: 'module' }));
  await exec('npm', ['install', '--offline', '--ignore-scripts', '--no-audit', '--no-fund', ...tarballs], {
    cwd: temporary, env: { ...process.env, npm_config_cache: join(temporary, 'npm-cache') },
  });
  const bin = join(temporary, 'node_modules/.bin/cookieguard-ci');
  const version = await exec(bin, ['--version'], { cwd: temporary });
  assert.equal(version.stdout.trim(), '0.1.0');
  await exec(process.execPath, ['--input-type=module', '-e', `
    import { normalizeCookie, evaluateCookiePolicy, exitCode } from '@cookieguard/core';
    import { startCookieAudit } from '@cookieguard/playwright';
    import { createOnnxClassifier } from '@cookieguard/core/onnx';
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
  process.stdout.write('Isolated offline CLI install: exit 0/1/2, text/JSON, files/stdout/stderr, and sentinel checks passed; no native or browser runtime installed.\n');

  // Give the isolated consumer an ordinary Playwright dependency, also packed
  // locally. Its CookieGuard imports still resolve only to the installed tarballs.
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
      import { startCookieAudit } from '@cookieguard/playwright';
      import { formatJson, exitCode } from '@cookieguard/core';
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
  await writeFile(join(proof, 'results.json'), JSON.stringify({ installedFromTarballs: true, outcomes, sentinelLeaks: 0 }, null, 2) + '\n');
} finally {
  if (server.listening) await new Promise(resolve => server.close(resolve));
  await rm(temporary, { recursive: true, force: true });
}
