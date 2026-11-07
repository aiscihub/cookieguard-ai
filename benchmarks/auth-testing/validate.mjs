#!/usr/bin/env node
// Validates the harness before any paid run. Reference test suites with known behavior
// are replayed against every app version through the same code that scores agent runs.
// Exits non-zero if the scorer disagrees with what a suite is built to do. Needs npm,
// network access to the npm registry, and Playwright's Chromium.
import { cp, mkdir, mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parseArgs } from 'node:util';
import { childEnv, launch, prepare, replay } from './bench.mjs';
import { differential } from './score.mjs';
import { FLAWED } from './variants.mjs';

const here = dirname(fileURLToPath(import.meta.url));
const none = Object.fromEntries(FLAWED.map(version => [version, false]));
const EXPECTED = {
  strong: { passesFixed: true, caught: Object.fromEntries(FLAWED.map(version => [version, true])) },
  naive: { passesFixed: true, caught: none },
  overstrict: { passesFixed: false, caught: none },
  tool: null, // Informational: what the published integration catches with the developer's configuration.
};
const TOOL_PACKAGE = '@aiscihub/cookieguard-playwright@0.2.0';

const { values } = parseArgs({ options: { dir: { type: 'string' }, keep: { type: 'boolean' }, suites: { type: 'string', default: Object.keys(EXPECTED).join(',') }, out: { type: 'string' } } });
const base = resolve(values.dir ?? tmpdir());
await mkdir(base, { recursive: true });
const report = {};
let failed = false;
for (const suite of values.suites.split(',')) {
  const root = await mkdtemp(join(base, `validate-${suite}-`));
  const workspace = join(root, 'app');
  await prepare({ id: `validate-${suite}`, version: 'fixed', condition: 'A', workspace, run: join(root, 'run') });
  await cp(join(here, 'reference', suite), workspace, { recursive: true });
  if (suite === 'tool') {
    const installed = await launch('npm', ['install', '--save-dev', '--no-audit', '--no-fund', TOOL_PACKAGE], { env: childEnv(null), cwd: workspace, timeoutMs: 300000 });
    if (installed.code !== 0) throw new Error(`Installing ${TOOL_PACKAGE} failed:\n${installed.output.slice(-2000)}`);
  }
  const runs = await replay(workspace, { logs: join(root, 'logs') });
  const result = differential(runs, 'fixed');
  const expected = EXPECTED[suite];
  const ok = !expected || (result.passesFixed === expected.passesFixed && FLAWED.every(version => result.caught[version] === expected.caught[version]));
  report[suite] = { exitCodes: Object.fromEntries(runs.map((run, index) => [`${index}-${run.version}`, run.exitCode])), passesFixed: result.passesFixed, caught: result.caught, flaky: result.flaky, expected, ok };
  process.stdout.write(`${ok ? 'ok  ' : 'FAIL'} ${suite}: passes fixed ${result.passesFixed}; caught ${FLAWED.filter(version => result.caught[version]).join(', ') || 'nothing'}${expected ? '' : ' (informational)'}\n`);
  if (!ok) { failed = true; process.stdout.write(`     logs: ${join(root, 'logs')}\n`); }
  else if (!values.keep) await rm(root, { recursive: true, force: true });
}
if (values.out) await writeFile(resolve(values.out), JSON.stringify(report, null, 2) + '\n');
process.exitCode = failed ? 1 : 0;
