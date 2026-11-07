// Security-gate comparison runner. Builds one workspace per cell (app variant ×
// approach × tamper mode), runs that approach's CI commands, and records the CI
// decision, the verdict, and any credential value in output a coding agent could read.
//
//   node benchmarks/security-gate/run.mjs matrix  --deps DIR --out DIR [--repeats 3]
//   node benchmarks/security-gate/run.mjs tamper  --deps DIR --out DIR
//   node benchmarks/security-gate/run.mjs privacy --deps DIR --out DIR
//   node benchmarks/security-gate/run.mjs summarize --out DIR
//   node benchmarks/security-gate/run.mjs loc
import { spawn, execFileSync } from 'node:child_process';
import { cp, mkdir, readFile, readdir, rm, stat, symlink, writeFile } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { dirname, join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parseArgs } from 'node:util';
import { randomBytes } from 'node:crypto';
import { VARIANTS, APP_FILES, variantFiles } from './variants.mjs';

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = resolve(HERE, '../..');
const FIXTURE = join(REPO, 'benchmarks/auth-testing/fixture');
const APPROACH_DIR = join(HERE, 'approaches');
export const CANARY = /\b(?:sess|tok)_[0-9a-f]{32}\b/g;
const TITLE = 'sign in and out';

const cgGate = (failOn) => ['node', ['node_modules/cookieguard-ci/bin/cookieguard-ci.js', 'gate', '--evidence', 'cookieguard-evidence',
  '--require', TITLE, '--auth-cookie', 'sid', '--auth-cookie', 'api_token', ...(failOn ? ['--fail-on', failOn] : []),
  '--require-logout', '--run-id', '$RUN_ID']];

export const APPROACHES = {
  native: { label: 'A. Native Playwright', files: { 'e2e/security.spec.js': 'native/e2e/security.spec.js' }, gate: null,
    weaken: ['httpOnly: true', 'httpOnly: expect.any(Boolean)'] },
  fixture: { label: 'B. Minimal fixture', files: { 'e2e/security.spec.js': 'fixture/e2e/security.spec.js',
    'e2e/session-security.js': 'fixture/e2e/session-security.js', 'ci/security-gate.mjs': 'fixture/ci/security-gate.mjs' },
  gate: ['node', ['ci/security-gate.mjs', 'sign-in-and-out']], weakenFile: 'e2e/session-security.js',
  weaken: ["if (!cookie.httpOnly) failures.push(`${name}: missing HttpOnly`); // POLICY", '// HttpOnly check removed'] },
  cookieguard: { label: 'C. CookieGuard', files: { 'e2e/security.spec.js': 'cookieguard/e2e/security.spec.js' },
    gate: cgGate('medium'), weaken: ["authCookies: ['sid', 'api_token']", "authCookies: ['api_token']"] },
  'cookieguard-default': { label: 'C0. CookieGuard, default policy', files: { 'e2e/security.spec.js': 'cookieguard/e2e/security.spec.js' },
    edit: ["policy: { authCookies: ['sid', 'api_token'], failOn: 'medium' }", "policy: { authCookies: ['sid', 'api_token'] }"],
    gate: cgGate(null) },
};

export const TAMPERS = ['none', 'skip', 'known-failure', 'swallow', 'filter', 'delete', 'weaken', 'forge'];
const TAMPER_NOTES = {
  none: 'unmodified', skip: 'file-level test.skip()', 'known-failure': 'file-level test.fail() (the Playwright analogue of a todo test)',
  swallow: 'test body wrapped in try/catch', filter: 'npm test runs only the other spec', delete: 'security spec deleted',
  weaken: 'the HttpOnly requirement removed from workspace test code', forge: 'test skipped and a passing verdict file planted (deliberate)',
};

async function readPristine() {
  const files = {};
  for (const file of APP_FILES) files[file] = await readFile(join(FIXTURE, file), 'utf8');
  return files;
}

// The fixture's dependencies plus CookieGuard: linked from this checkout, or installed from
// `npm pack` tarballs (`tarballs`) when the tests run as a user who cannot read the checkout.
export async function prepareDeps(deps, { tarballs = null } = {}) {
  const modules = join(deps, 'node_modules');
  if (!existsSync(join(modules, '@playwright/test'))) {
    await mkdir(deps, { recursive: true });
    for (const file of ['package.json', 'package-lock.json']) await cp(join(FIXTURE, file), join(deps, file));
    execFileSync('npm', ['ci', '--no-audit', '--no-fund'], { cwd: deps, stdio: 'inherit' });
  }
  if (tarballs) {
    const packed = (await readdir(tarballs)).filter(name => name.endsWith('.tgz')).map(name => join(tarballs, name));
    execFileSync('npm', ['install', '--no-save', '--no-audit', '--no-fund', ...packed], { cwd: deps, stdio: 'inherit' });
    return modules;
  }
  await mkdir(join(modules, '@aiscihub'), { recursive: true });
  for (const [link, target] of [['@aiscihub/cookieguard-playwright', 'packages/playwright'], ['@aiscihub/cookieguard-core', 'packages/core'],
    ['cookieguard-ci', 'packages/cli']]) {
    await rm(join(modules, link), { recursive: true, force: true });
    await symlink(join(REPO, target), join(modules, link));
  }
  return modules;
}

function insertBeforeFirstTest(source, line) {
  const lines = source.split('\n');
  const index = lines.findIndex(l => l.startsWith('test('));
  if (index < 0) throw new Error('no test() line');
  lines.splice(index, 0, line);
  return lines.join('\n');
}

const once = (source, find, replace) => {
  if (source.split(find).length !== 2) throw new Error(`edit does not match exactly once: ${find}`);
  return source.replace(find, () => replace);
};

export async function buildWorkspace({ dir, deps, variant, approach, tamper = 'none', files: appOverride, forged }) {
  await rm(dir, { recursive: true, force: true });
  await cp(FIXTURE, dir, { recursive: true, filter: src => !src.includes('node_modules') && !src.includes('test-results') });
  const app = appOverride ?? variantFiles(await readPristine(), variant);
  for (const [file, content] of Object.entries(app)) await writeFile(join(dir, file), content);
  await cp(join(APPROACH_DIR, 'common/e2e/flows.js'), join(dir, 'e2e/flows.js'));
  const spec = APPROACHES[approach];
  for (const [to, from] of Object.entries(spec.files)) {
    await mkdir(dirname(join(dir, to)), { recursive: true });
    await cp(join(APPROACH_DIR, from), join(dir, to));
  }
  if (spec.edit) await edit(dir, 'e2e/security.spec.js', s => once(s, ...spec.edit));
  await symlink(join(deps, 'node_modules'), join(dir, 'node_modules'));
  await applyTamper(dir, approach, tamper, forged);
}

async function edit(dir, file, fn) {
  const path = join(dir, file);
  await writeFile(path, fn(await readFile(path, 'utf8')));
}

async function applyTamper(dir, approach, tamper, forged) {
  const spec = APPROACHES[approach];
  switch (tamper) {
    case 'none': return;
    case 'skip': return edit(dir, 'e2e/security.spec.js', s => insertBeforeFirstTest(s, "test.skip(true, 'Flaky in CI; tracked separately.');"));
    case 'known-failure': return edit(dir, 'e2e/security.spec.js', s => insertBeforeFirstTest(s, "test.fail(true, 'Known issue: tracked separately.');"));
    case 'swallow': return edit(dir, 'e2e/security.spec.js', s => once(once(s, '  // BODY-START', '  try {'), '  // BODY-END', '  } catch { /* tracked separately */ }'));
    case 'filter': return edit(dir, 'package.json', s => once(s, '&& playwright test"', '&& playwright test e2e/login-page.spec.js"'));
    case 'delete': return rm(join(dir, 'e2e/security.spec.js'));
    case 'weaken': return edit(dir, spec.weakenFile ?? 'e2e/security.spec.js', s => once(s, ...spec.weaken));
    case 'forge': {
      await edit(dir, 'e2e/security.spec.js', s => insertBeforeFirstTest(s, "test.skip(true, 'Flaky in CI; tracked separately.');"));
      if (approach === 'fixture') {
        await mkdir(join(dir, 'security-results'), { recursive: true });
        await writeFile(join(dir, 'security-results/sign-in-and-out.json'), JSON.stringify({ status: 'PASS', failures: [], missing: [] }));
      } else if (approach.startsWith('cookieguard') && forged) {
        await mkdir(join(dir, 'cookieguard-evidence'), { recursive: true });
        // The forger copies evidence from a passing run and writes the current run ID into it.
        await writeFile(join(dir, 'cookieguard-evidence/sign-in-and-out.json'), forged.replace(/"runId": "[^"]*"/, '"runId": "$RUN_ID"'));
      }
      return;
    }
    default: throw new Error(`Unknown tamper ${tamper}`);
  }
}

function run(cmd, args, { cwd, env, timeoutMs = 180000, who = null }) {
  return new Promise(resolvePromise => {
    const started = Date.now();
    const child = spawn(cmd, args, { cwd, env, detached: true, stdio: ['ignore', 'pipe', 'pipe'], ...(who ? { uid: who.uid, gid: who.gid } : {}) });
    let out = '';
    child.stdout.on('data', d => { out += d; });
    child.stderr.on('data', d => { out += d; });
    let timedOut = false;
    const timer = setTimeout(() => { timedOut = true; try { process.kill(-child.pid, 'SIGKILL'); } catch { /* gone */ } }, timeoutMs);
    child.on('close', code => { clearTimeout(timer); resolvePromise({ exitCode: timedOut ? null : code, timedOut, ms: Date.now() - started, output: out }); });
  });
}

async function textFiles(dir, roots) {
  const found = [];
  async function walk(path) {
    let info;
    try { info = await stat(path); } catch { return; }
    if (info.isDirectory()) { for (const name of await readdir(path)) await walk(join(path, name)); return; }
    if (info.size > 2_000_000) return;
    const content = await readFile(path);
    if (content.includes(0)) return; // binary (traces, screenshots)
    found.push({ path: relative(dir, path), content: content.toString('utf8') });
  }
  for (const root of roots) await walk(join(dir, root));
  return found;
}

const exposures = text => [...new Set(text.match(CANARY) ?? [])].length;

export async function runCell({ dir, approach, env: extraEnv = {}, who = null }) {
  const runId = `run-${randomBytes(6).toString('hex')}`;
  const env = { PATH: process.env.PATH, HOME: who?.home ?? process.env.HOME, CI: '1', COOKIEGUARD_RUN_ID: runId, FORCE_COLOR: '0',
    ...(process.env.PLAYWRIGHT_BROWSERS_PATH ? { PLAYWRIGHT_BROWSERS_PATH: process.env.PLAYWRIGHT_BROWSERS_PATH } : {}), ...extraEnv };
  // A planted evidence file gets the run ID the forger read from the environment.
  for (const file of ['cookieguard-evidence/sign-in-and-out.json']) {
    const path = join(dir, file);
    if (existsSync(path)) await writeFile(path, (await readFile(path, 'utf8')).replaceAll('$RUN_ID', runId));
  }
  const steps = [['npm', ['test']]];
  const gate = APPROACHES[approach].gate;
  if (gate) steps.push([gate[0], gate[1].map(a => (a === '$RUN_ID' ? runId : a))]);
  const results = [];
  for (const [cmd, args] of steps) results.push({ cmd: [cmd, ...args].join(' '), ...(await run(cmd, args, { cwd: dir, env, who })) });
  const files = await textFiles(dir, ['test-results', 'cookieguard-evidence', 'security-results', 'playwright-report']);
  const consoleText = results.map(r => r.output).join('\n');
  return { runId, results, files, exposure: { console: exposures(consoleText), files: files.filter(f => exposures(f.content)).map(f => f.path) } };
}

function verdictOf(approach, cell) {
  const [test, gate] = cell.results;
  if (test.timedOut || gate?.timedOut) return 'TIMEOUT';
  const code = gate ? gate.exitCode : test.exitCode;
  return code === 0 ? 'PASS' : gate ? (code === 1 ? 'FAIL' : 'INCOMPLETE') : 'FAIL';
}

function record(meta, cell) {
  const accepted = cell.results.every(r => r.exitCode === 0);
  const verdict = verdictOf(meta.approach, cell);
  return { ...meta, accepted, verdict, testExit: cell.results[0].exitCode, gateExit: cell.results[1]?.exitCode ?? null,
    ms: cell.results.reduce((a, r) => a + r.ms, 0), exposure: cell.exposure,
    output: cell.results.map(r => `$ ${r.cmd}\n${r.output}`).join('\n').slice(-12000) };
}

async function appendJsonl(path, row) { await writeFile(path, JSON.stringify(row) + '\n', { flag: 'a' }); }

async function matrix({ deps, out, repeats, approaches = Object.keys(APPROACHES) }) {
  await prepareDeps(deps);
  const path = join(out, 'matrix.jsonl');
  const work = join(out, 'work');
  for (let repeat = 1; repeat <= repeats; repeat++) {
    for (const approach of approaches) {
      for (const variant of Object.keys(VARIANTS)) {
        const dir = join(work, `${approach}-${variant}`);
        await buildWorkspace({ dir, deps, variant, approach });
        const cell = await runCell({ dir, approach });
        const row = record({ approach, variant, tamper: 'none', repeat, expected: VARIANTS[variant].expected }, cell);
        await appendJsonl(path, row);
        console.log(`${repeat} ${approach.padEnd(19)} ${variant.padEnd(16)} accepted=${row.accepted} verdict=${row.verdict} expected=${row.expected} leak=${row.exposure.console}/${row.exposure.files.length} ${row.ms}ms`);
      }
    }
  }
}

async function forgedEvidence(deps, work) {
  const dir = join(work, 'forge-source');
  await buildWorkspace({ dir, deps, variant: 'fixed', approach: 'cookieguard' });
  const cell = await runCell({ dir, approach: 'cookieguard' });
  if (!cell.results.every(r => r.exitCode === 0)) throw new Error('forge source run did not pass');
  return readFile(join(dir, 'cookieguard-evidence/sign-in-and-out.json'), 'utf8');
}

async function tamper({ deps, out }) {
  await prepareDeps(deps);
  const path = join(out, 'tamper.jsonl');
  const work = join(out, 'work');
  const forged = await forgedEvidence(deps, work);
  for (const variant of ['no-httponly', 'fixed']) {
    for (const approach of ['native', 'fixture', 'cookieguard']) {
      for (const mode of TAMPERS) {
        if (mode === 'forge' && approach === 'native') continue;
        if (variant === 'fixed' && !['none', 'known-failure', 'swallow'].includes(mode)) continue;
        const dir = join(work, `tamper-${approach}-${variant}-${mode}`);
        await buildWorkspace({ dir, deps, variant, approach, tamper: mode, forged });
        const cell = await runCell({ dir, approach });
        const row = record({ approach, variant, tamper: mode, note: TAMPER_NOTES[mode], expected: VARIANTS[variant].expected }, cell);
        await appendJsonl(path, row);
        console.log(`${approach.padEnd(12)} ${variant.padEnd(12)} ${mode.padEnd(14)} accepted=${row.accepted} verdict=${row.verdict}`);
      }
    }
  }
}

// Common native assertion idioms, each run alone against a flawed app, to see which
// print a credential value when they fail. CookieGuard's failure paths are in the matrix.
async function privacy({ deps, out }) {
  await prepareDeps(deps);
  const path = join(out, 'privacy.jsonl');
  const work = join(out, 'work');
  const source = await readFile(join(HERE, 'privacy/idioms.spec.js'), 'utf8');
  const idioms = [...source.matchAll(/^test\('([^']+)'/gm)].map(m => m[1]);
  for (const idiom of idioms) {
    const variant = idiom.match(/\[([a-z-]+)\]$/)[1];
    const dir = join(work, `idiom-${idioms.indexOf(idiom)}`);
    await buildWorkspace({ dir, deps, variant, approach: 'native' });
    await rm(join(dir, 'e2e/security.spec.js'));
    await cp(join(HERE, 'privacy/idioms.spec.js'), join(dir, 'e2e/idioms.spec.js'));
    // Run only this idiom.
    const only = await run('npx', ['playwright', 'test', 'e2e/idioms.spec.js', '-g', `${idiom.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}$`], { cwd: dir, env: { PATH: process.env.PATH, HOME: process.env.HOME, CI: '1', FORCE_COLOR: '0',
      ...(process.env.PLAYWRIGHT_BROWSERS_PATH ? { PLAYWRIGHT_BROWSERS_PATH: process.env.PLAYWRIGHT_BROWSERS_PATH } : {}) } });
    const files = await textFiles(dir, ['test-results']);
    const row = { idiom, variant, exitCode: only.exitCode, ran: /\b1 failed\b/.test(only.output), exposure: { console: exposures(only.output), files: files.filter(f => exposures(f.content)).map(f => f.path) },
      output: only.output.slice(-6000) };
    await appendJsonl(path, row);
    console.log(`${idiom.padEnd(70)} exit=${only.exitCode} ran=${row.ran} leak=${row.exposure.console}/${row.exposure.files.length}`);
  }
}

// Security-specific lines of code per approach: non-blank lines that are not only comments.
export async function loc() {
  const count = async rel => (await readFile(join(APPROACH_DIR, rel), 'utf8')).split('\n')
    .filter(l => l.trim() && !/^\s*\/\//.test(l)).length;
  const result = {};
  for (const [id, spec] of Object.entries(APPROACHES)) {
    const files = {};
    for (const from of Object.values(spec.files)) files[from] = await count(from);
    const gateCommand = spec.gate ? 1 : 0;
    result[id] = { files, total: Object.values(files).reduce((a, b) => a + b, 0), ciLines: gateCommand };
  }
  result.sharedLoginSteps = await count('common/e2e/flows.js');
  return result;
}

const pct = (k, n) => (n ? `${k}/${n}` : '—');

async function readJsonl(path) {
  try { return (await readFile(path, 'utf8')).split('\n').filter(Boolean).map(l => JSON.parse(l)); } catch { return []; }
}

export async function summarize({ out }) {
  const rows = await readJsonl(join(out, 'matrix.jsonl'));
  const tampers = await readJsonl(join(out, 'tamper.jsonl'));
  const idioms = await readJsonl(join(out, 'privacy.jsonl'));
  const lines = ['# Security-gate comparison results', ''];
  const approaches = [...new Set(rows.map(r => r.approach))];
  const variants = [...new Set(rows.map(r => r.variant))];
  if (rows.length) {
    lines.push('## CI decision by app version (correct decisions / runs)', '',
      `| Version | Expected | ${approaches.map(a => APPROACHES[a].label).join(' | ')} |`, `| --- | --- | ${approaches.map(() => '---').join(' | ')} |`);
    for (const v of variants) {
      const cells = approaches.map(a => {
        const rs = rows.filter(r => r.approach === a && r.variant === v);
        const ok = rs.filter(r => r.accepted === (r.expected === 'PASS')).length;
        const verdicts = [...new Set(rs.map(r => r.verdict))].join('/');
        return `${pct(ok, rs.length)} (${verdicts})`;
      });
      lines.push(`| ${v} | ${VARIANTS[v].expected} | ${cells.join(' | ')} |`);
    }
    lines.push('', '## Totals', '', '| Measure | ' + approaches.map(a => APPROACHES[a].label).join(' | ') + ' |', '| --- | ' + approaches.map(() => '---').join(' | ') + ' |');
    const by = a => rows.filter(r => r.approach === a);
    const measure = (name, fn) => lines.push(`| ${name} | ${approaches.map(a => fn(by(a))).join(' | ')} |`);
    measure('Flawed versions blocked', rs => { const f = rs.filter(r => VARIANTS[r.variant].kind === 'flaw'); return pct(f.filter(r => !r.accepted).length, f.length); });
    measure('Secure versions accepted', rs => { const f = rs.filter(r => VARIANTS[r.variant].kind === 'secure'); return pct(f.filter(r => r.accepted).length, f.length); });
    measure('Missing-evidence versions blocked', rs => { const f = rs.filter(r => VARIANTS[r.variant].kind === 'evidence'); return pct(f.filter(r => !r.accepted).length, f.length); });
    measure('…reported as INCOMPLETE, not as a flaw', rs => { const f = rs.filter(r => VARIANTS[r.variant].kind === 'evidence'); return pct(f.filter(r => r.verdict === 'INCOMPLETE').length, f.length); });
    measure('Runs with a credential value in console output', rs => pct(rs.filter(r => r.exposure.console).length, rs.length));
    measure('Runs with a credential value in written files', rs => pct(rs.filter(r => r.exposure.files.length).length, rs.length));
    measure('Inconsistent cells across repeats', rs => {
      const cells = [...new Set(rs.map(r => r.variant))];
      return `${cells.filter(v => new Set(rs.filter(r => r.variant === v).map(r => `${r.accepted}${r.verdict}`)).size > 1).length}/${cells.length}`;
    });
    measure('Median CI time (s)', rs => { const t = rs.map(r => r.ms).sort((a, b) => a - b); return (t[Math.floor(t.length / 2)] / 1000).toFixed(1); });
  }
  if (tampers.length) {
    const tApproaches = [...new Set(tampers.map(r => r.approach))];
    lines.push('', '## Neutralized checks on the `no-httponly` app (does CI still block?)', '',
      `| Workspace edit | ${tApproaches.map(a => APPROACHES[a].label).join(' | ')} |`, `| --- | ${tApproaches.map(() => '---').join(' | ')} |`);
    for (const mode of TAMPERS) {
      const cells = tApproaches.map(a => {
        const r = tampers.find(t => t.approach === a && t.tamper === mode && t.variant === 'no-httponly');
        return r ? `${r.accepted ? '**accepted**' : 'blocked'} (${r.verdict})` : 'n/a';
      });
      lines.push(`| ${mode}: ${TAMPER_NOTES[mode]} | ${cells.join(' | ')} |`);
    }
    const fixedRows = tampers.filter(t => t.variant === 'fixed');
    if (fixedRows.length) lines.push('', `Same edits on the secure app: ${fixedRows.filter(r => r.accepted).length}/${fixedRows.length} accepted (${fixedRows.filter(r => !r.accepted).map(r => `${r.approach}/${r.tamper}`).join(', ') || 'no false blocks'}).`);
  }
  if (idioms.length) {
    lines.push('', '## Native assertion idioms: does the failure output contain the credential value?', '', '| Idiom [app version] | Test failed | Value in console | Value in files |', '| --- | --- | --- | --- |');
    for (const r of idioms) lines.push(`| ${r.idiom} | ${r.ran ? 'yes' : '**did not run**'} | ${r.exposure.console ? '**yes**' : 'no'} | ${r.exposure.files.length ? '**yes**' : 'no'} |`);
  }
  const l = await loc();
  lines.push('', '## Security-specific code (non-blank, non-comment lines)', '', '| Approach | Test-side code | CI gate | Files |', '| --- | --- | --- | --- |');
  for (const id of ['native', 'fixture', 'cookieguard']) lines.push(`| ${APPROACHES[id].label} | ${l[id].total} | ${id === 'fixture' ? `${l.fixture.files['fixture/ci/security-gate.mjs']} (script) + 1 command` : id === 'cookieguard' ? '1 command' : 'none'} | ${Object.keys(l[id].files).join(', ')} |`);
  lines.push(`\nShared login steps used unchanged by all approaches: ${l.sharedLoginSteps} lines.`);
  const text = lines.join('\n') + '\n';
  await writeFile(join(out, 'SUMMARY.md'), text);
  return text;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const { values, positionals } = parseArgs({ allowPositionals: true, options: {
    deps: { type: 'string' }, out: { type: 'string' }, repeats: { type: 'string', default: '3' }, approaches: { type: 'string' } } });
  const command = positionals[0];
  const out = values.out && resolve(values.out);
  if (out) await mkdir(out, { recursive: true });
  const deps = values.deps && resolve(values.deps);
  if (command === 'matrix') await matrix({ deps, out, repeats: Number(values.repeats), ...(values.approaches ? { approaches: values.approaches.split(',') } : {}) });
  else if (command === 'tamper') await tamper({ deps, out });
  else if (command === 'privacy') await privacy({ deps, out });
  else if (command === 'summarize') process.stdout.write(await summarize({ out }));
  else if (command === 'loc') console.log(JSON.stringify(await loc(), null, 2));
  else { console.error('usage: run.mjs matrix|tamper|privacy|summarize|loc --deps DIR --out DIR'); process.exit(2); }
}
