import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { mkdir, writeFile } from 'node:fs/promises';
import { assertNoSentinels } from './lib/leakage.js';

const exec = promisify(execFile);
await mkdir('artifacts/release', { recursive: true });
const steps = [
  ['source-credentials', process.execPath, ['scripts/check-source-secrets.js']],
  ['dependency-licenses', process.execPath, ['scripts/check-licenses.js']],
  ['dependency-advisories', 'npm', ['audit', '--audit-level=low', '--json']],
  ['toolkit-tests', 'npm', ['run', 'check']],
  ['installed-tarballs', process.execPath, ['scripts/verify-packages.js']],
  ['controlled-benchmark', 'npm', ['run', 'benchmark']],
  ['output-leakage', process.execPath, ['scripts/check-artifacts.js']],
];
const results = [];
try {
  for (const [name, command, args] of steps) {
    process.stdout.write(`Release gate: ${name}\n`);
    let result;
    try {
      result = { ...await exec(command, args, { maxBuffer: 16 * 1024 * 1024, timeout: 8 * 60 * 1000 }), code: 0 };
    } catch (error) { result = { stdout: error.stdout ?? '', stderr: error.stderr ?? '', code: error.code ?? 2 }; }
    const output = result.stdout + result.stderr;
    assertNoSentinels(output); // Check before writing files or exposing CI logs.
    await writeFile(`artifacts/release/${name}.log`, output, { mode: 0o600 });
    process.stdout.write(output);
    results.push({ name, exitCode: result.code });
    if (result.code !== 0) throw new Error('A release check failed. Inspect its sanitized log.');
  }
  await writeFile('artifacts/release/results.json', JSON.stringify({ version: '0.1.0', channel: 'public-beta', results }, null, 2) + '\n');
  process.stdout.write('All local public-beta release gates passed. Hosted Action checks must also pass before merge.\n');
} catch {
  process.stderr.write('Release gate failed. Unsafe output, if any, was withheld.\n');
  process.exitCode = 1;
}
