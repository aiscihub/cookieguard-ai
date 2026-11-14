#!/usr/bin/env node
// Harness for the auth-testing benchmark. See PROTOCOL.md.
//
//   matrix     list the runs for a workflow matrix
//   prepare    build a workspace for one app version and condition
//   agent      run Claude Code on the workspace
//   score      replay the agent's tests against every app version and score the transcript
//   redact     remove any credential of the harness from a run directory before upload
//   summarize  aggregate scored runs
//
// In CI the harness runs as root and every agent and test process runs as an
// unprivileged user (--user) who cannot read the repository checkout. Without --user,
// everything runs as the current user (local validation).
import { spawn, execFileSync } from 'node:child_process';
import { createWriteStream } from 'node:fs';
import { cp, mkdir, readFile, readdir, rm, writeFile } from 'node:fs/promises';
import { dirname, join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parseArgs } from 'node:util';
import { APP_FILES, FLAWED, VERSIONS, versionFiles } from './variants.mjs';
import { differential, markdown, scoreTranscript, summarize, toolInWorkspace } from './score.mjs';

const here = dirname(fileURLToPath(import.meta.url));
const repo = resolve(here, '../..');
export const PROMPT = 'Add automated tests for the login and session handling in this app. They should run as part of `npm test`. '
  + 'When you are done, summarize what the tests cover and anything they found.';
export const BASE_TOOLS = ['Bash', 'Read', 'Write', 'Edit', 'Glob', 'Grep', 'Skill'];
export const CONDITIONS = {
  A: { label: 'default workflow', tool: false },
  B: { label: 'default workflow plus the Agent Skill and the MCP server', tool: true },
};
const SKILL = 'cookieguard-browser-auth-security';
// The app's credential cookies, as the developer configured them for the MCP server.
export const AUTH_COOKIES = ['sid', 'api_token'];
const MCP_BIN = 'node_modules/@aiscihub/cookieguard-mcp/bin/cookieguard-mcp.js';
const SECRET_NAMES = ['ANTHROPIC_API_KEY', 'CLAUDE_CODE_OAUTH_TOKEN'];
const OUTPUT_LIMIT = 256 * 1024;

export function account(name) {
  if (!name) return null;
  const [, , uid, gid, , home] = execFileSync('getent', ['passwd', name], { encoding: 'utf8' }).trim().split(':');
  return { name, uid: Number(uid), gid: Number(gid), home };
}

// Only these variables reach agent and test processes; nothing from the runner leaks through.
export function childEnv(who, extra = {}) {
  return {
    HOME: who?.home ?? process.env.HOME, USER: who?.name ?? process.env.USER, LOGNAME: who?.name ?? process.env.USER,
    SHELL: '/bin/bash', PATH: process.env.PATH, LANG: 'C.UTF-8', TERM: 'dumb',
    ...(process.env.PLAYWRIGHT_BROWSERS_PATH ? { PLAYWRIGHT_BROWSERS_PATH: process.env.PLAYWRIGHT_BROWSERS_PATH } : {}),
    GIT_AUTHOR_NAME: 'Developer', GIT_AUTHOR_EMAIL: 'dev@example.invalid', GIT_COMMITTER_NAME: 'Developer', GIT_COMMITTER_EMAIL: 'dev@example.invalid',
    npm_config_update_notifier: 'false', npm_config_fund: 'false', npm_config_audit: 'false',
    ...extra,
    // Synthetic benchmark invocations must never enter package-usage metrics.
    COOKIEGUARD_USAGE_METRICS: '0', DO_NOT_TRACK: '1',
  };
}

// Runs a command in its own process group; the whole group is killed when it exits or times out.
export function launch(command, args, { who = null, env, cwd, timeoutMs = 0, stdout = null, stderr = null } = {}) {
  return new Promise((done, fail) => {
    const started = Date.now();
    const child = spawn(command, args, { cwd, env, detached: true, stdio: ['ignore', 'pipe', 'pipe'], ...(who ? { uid: who.uid, gid: who.gid } : {}) });
    let output = '';
    const keep = chunk => { if (output.length < OUTPUT_LIMIT) output += chunk.toString(); };
    child.stdout.on('data', keep);
    child.stderr.on('data', keep);
    if (stdout) child.stdout.pipe(stdout);
    if (stderr) child.stderr.pipe(stderr);
    let timedOut = false;
    const timer = timeoutMs ? setTimeout(() => {
      timedOut = true;
      try { process.kill(-child.pid, 'SIGTERM'); } catch { /* exited */ }
      setTimeout(() => { try { process.kill(-child.pid, 'SIGKILL'); } catch { /* exited */ } }, 10000).unref();
    }, timeoutMs) : null;
    child.on('error', fail);
    child.on('close', code => {
      if (timer) clearTimeout(timer);
      try { process.kill(-child.pid, 'SIGKILL'); } catch { /* group gone */ }
      done({ code: timedOut ? null : code, timedOut, output, durationMs: Date.now() - started });
    });
  });
}

// Servers or browsers left running (possibly detached into their own groups).
export function cleanup(who, workspace) {
  if (who) {
    try { execFileSync('pkill', ['-KILL', '-u', who.name], { stdio: 'ignore' }); } catch { /* none left */ }
    return;
  }
  let listing = '';
  try { listing = execFileSync('lsof', ['-a', '-d', 'cwd', '-Fpn'], { encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }); } catch (error) { listing = error.stdout ?? ''; }
  let pid = null;
  for (const line of listing.split('\n')) {
    if (line.startsWith('p')) pid = Number(line.slice(1));
    else if (line.startsWith('n') && pid && pid !== process.pid && line.slice(1).startsWith(workspace)) {
      try { process.kill(pid, 'SIGKILL'); } catch { /* gone */ }
    }
  }
}

function chownTree(path, who) {
  if (who) execFileSync('chown', ['-R', `${who.uid}:${who.gid}`, path]);
}

export async function readApp(directory) {
  const files = {};
  for (const file of APP_FILES) {
    try { files[file] = await readFile(join(directory, file), 'utf8'); } catch { files[file] = null; }
  }
  return files;
}

async function writeApp(directory, files, who) {
  for (const [file, content] of Object.entries(files)) {
    const path = join(directory, file);
    if (content === null) { await rm(path, { force: true }); continue; }
    await mkdir(dirname(path), { recursive: true });
    await writeFile(path, content);
  }
  chownTree(directory, who);
}

async function must(command, args, options) {
  const result = await launch(command, args, options);
  if (result.code !== 0) throw new Error(`${command} ${args.join(' ')} failed (${result.code}):\n${result.output.slice(-2000)}`);
  return result;
}

export async function prepare({ id, version, condition, repeat = 1, workspace, run, who = null, toolsDir = null, install = true }) {
  if (!VERSIONS[version]) throw new Error(`Unknown version ${version}`);
  if (!CONDITIONS[condition]) throw new Error(`Unknown condition ${condition}`);
  await rm(workspace, { recursive: true, force: true });
  await cp(join(here, 'fixture'), workspace, { recursive: true });
  await writeApp(workspace, versionFiles(await readApp(join(here, 'fixture')), version), null);
  await writeFile(join(workspace, '.gitignore'), 'node_modules/\ntest-results/\nplaywright-report/\n');
  if (CONDITIONS[condition].tool) await cp(join(repo, 'skills', SKILL), join(workspace, '.claude/skills', SKILL), { recursive: true });
  chownTree(workspace, who);
  const options = { who, env: childEnv(who), cwd: workspace, timeoutMs: 300000 };
  for (const args of [['init', '-q', '-b', 'main'], ['add', '-A'], ['commit', '-qm', 'Initial commit']]) await must('git', args, options);
  if (install) await must('npm', ['ci', '--no-audit', '--no-fund'], options);
  let mcpConfig = null;
  if (CONDITIONS[condition].tool) {
    if (!toolsDir) throw new Error('Condition B needs --tools-dir with the MCP server installed');
    // The developer installed and configured the server for this app; the prompt does not mention it.
    const serverConfig = join(toolsDir, 'server-config.json');
    await writeFile(serverConfig, JSON.stringify({ allowedOrigins: ['http://127.0.0.1:3000', 'http://localhost:3000'], policy: { authCookies: AUTH_COOKIES } }, null, 2));
    mcpConfig = join(toolsDir, 'mcp.json');
    await writeFile(mcpConfig, JSON.stringify({ mcpServers: { cookieguard: { command: process.execPath,
      args: [join(toolsDir, MCP_BIN), '--config', serverConfig],
      env: { COOKIEGUARD_USAGE_METRICS: '0', DO_NOT_TRACK: '1' } } } }, null, 2));
  }
  await mkdir(run, { recursive: true });
  // In CI the harness runs as root on a checkout owned by the runner user.
  const fixture = execFileSync('git', ['-c', 'safe.directory=*', 'log', '-1', '--format=%H', '--', relative(repo, here)], { cwd: repo, encoding: 'utf8' }).trim();
  await writeFile(join(run, 'meta.json'), JSON.stringify({ id: id ?? `${version}-${condition}-${repeat}`, version, condition, repeat,
    conditionLabel: CONDITIONS[condition].label, prompt: PROMPT, benchmarkCommit: fixture, mcpConfig, preparedAt: new Date().toISOString() }, null, 2) + '\n');
}

export async function agent({ run, workspace, who = null, model, timeoutMinutes, maxBudgetUsd, claude }) {
  const metaPath = join(run, 'meta.json');
  const meta = JSON.parse(await readFile(metaPath, 'utf8'));
  const tool = CONDITIONS[meta.condition].tool;
  const allowed = tool ? [...BASE_TOOLS, 'mcp__cookieguard'] : BASE_TOOLS;
  const args = ['-p', PROMPT, '--output-format', 'stream-json', '--verbose', '--model', model,
    '--tools', BASE_TOOLS.join(','), '--allowedTools', allowed.join(','), '--permission-mode', 'dontAsk',
    '--setting-sources', 'project', '--strict-mcp-config', '--no-session-persistence', '--max-budget-usd', String(maxBudgetUsd)];
  if (tool) args.push('--mcp-config', meta.mcpConfig);
  const secrets = Object.fromEntries(SECRET_NAMES.filter(name => process.env[name]).map(name => [name, process.env[name]]));
  if (!Object.keys(secrets).length) throw new Error(`Set ${SECRET_NAMES.join(' or ')}`);
  const env = childEnv(who, { ...secrets, DISABLE_AUTOUPDATER: '1' });
  const version = (await launch(claude, ['--version'], { who, env: childEnv(who), cwd: workspace, timeoutMs: 60000 })).output.trim();
  const transcript = createWriteStream(join(run, 'transcript.jsonl'));
  const errors = createWriteStream(join(run, 'stderr.log'));
  const startedAt = new Date().toISOString();
  const result = await launch(claude, args, { who, env, cwd: workspace, timeoutMs: timeoutMinutes * 60000, stdout: transcript, stderr: errors });
  cleanup(who, workspace);
  meta.agent = { model, claudeVersion: version, exitCode: result.code, timedOut: result.timedOut, durationMs: result.durationMs, startedAt, maxBudgetUsd };
  await writeFile(metaPath, JSON.stringify(meta, null, 2) + '\n');
  process.stdout.write(`${meta.id}: agent exit ${result.code}${result.timedOut ? ' (timed out)' : ''} in ${Math.round(result.durationMs / 1000)}s\n`);
}

// Runs the workspace's `npm test` against the fixed app (first and last) and each flawed
// version, with the agent's own app edits set aside, then restores the workspace.
export async function replay(workspace, { who = null, timeoutSeconds = 300, logs = null } = {}) {
  const pristine = await readApp(join(here, 'fixture'));
  const agentFiles = await readApp(workspace);
  const runs = [];
  try {
    for (const [index, version] of ['fixed', ...FLAWED, 'fixed'].entries()) {
      await writeApp(workspace, versionFiles(pristine, version), who);
      const result = await launch('npm', ['test'], { who, env: childEnv(who, { CI: '1', FORCE_COLOR: '0' }), cwd: workspace, timeoutMs: timeoutSeconds * 1000 });
      cleanup(who, workspace);
      if (logs) {
        await mkdir(logs, { recursive: true });
        await writeFile(join(logs, `${index}-${version}.log`), result.output);
      }
      runs.push({ version, exitCode: result.code, timedOut: result.timedOut, durationMs: result.durationMs });
    }
  } finally {
    await writeApp(workspace, agentFiles, who);
  }
  return runs;
}

export async function score({ run, workspace, who = null, timeoutSeconds = 300 }) {
  cleanup(who, workspace);
  const meta = JSON.parse(await readFile(join(run, 'meta.json'), 'utf8'));
  const options = { who, env: childEnv(who), cwd: workspace, timeoutMs: 120000 };
  await launch('git', ['add', '-A'], options);
  const diff = (await launch('git', ['diff', '--cached', 'HEAD', '--', '.', ':(exclude)package-lock.json'], options)).output;
  const files = (await launch('git', ['diff', '--cached', '--name-status', 'HEAD'], options)).output;
  await writeFile(join(run, 'workspace.diff'), diff);
  await writeFile(join(run, 'files.txt'), files);
  const seen = versionFiles(await readApp(join(here, 'fixture')), meta.version);
  const current = await readApp(workspace);
  const appModified = APP_FILES.filter(file => current[file] !== seen[file]);
  const runs = await replay(workspace, { who, timeoutSeconds, logs: join(run, 'tests') });
  let events = [];
  try {
    events = (await readFile(join(run, 'transcript.jsonl'), 'utf8')).split('\n').filter(Boolean).flatMap(line => { try { return [JSON.parse(line)]; } catch { return []; } });
  } catch { /* the agent never started */ }
  const record = {
    id: meta.id, version: meta.version, condition: meta.condition, repeat: meta.repeat, agent: meta.agent ?? null,
    differential: differential(runs, meta.version), testRuns: runs, transcript: events.length ? scoreTranscript(events) : null,
    workspace: { appModified, changedFiles: files.split('\n').filter(Boolean).length, tool: toolInWorkspace(diff) },
  };
  await writeFile(join(run, 'score.json'), JSON.stringify(record, null, 2) + '\n');
  process.stdout.write(`${meta.id}: passes fixed ${record.differential.passesFixed}; caught ${JSON.stringify(record.differential.caught)}\n`);
  return record;
}

// Removes the harness's own credentials from every file in a run directory.
export async function redact(run) {
  const values = SECRET_NAMES.map(name => process.env[name]).filter(value => value && value.length >= 16);
  let count = 0;
  for (const entry of await readdir(run, { recursive: true, withFileTypes: true })) {
    if (!entry.isFile()) continue;
    const path = join(entry.parentPath, entry.name);
    let text = await readFile(path, 'utf8');
    const before = text;
    for (const value of values) text = text.split(value).join('[REDACTED]');
    text = text.replace(/sk-ant-[A-Za-z0-9_-]{20,}/g, '[REDACTED]');
    if (text !== before) { count++; await writeFile(path, text); }
  }
  const metaPath = join(run, 'meta.json');
  try {
    const meta = JSON.parse(await readFile(metaPath, 'utf8'));
    meta.filesRedacted = count;
    await writeFile(metaPath, JSON.stringify(meta, null, 2) + '\n');
  } catch { /* no meta */ }
  process.stdout.write(`Redacted harness credentials from ${count} file(s).\n`);
}

const PUBLIC_REDACTIONS = [[/\b(sess|tok)_[0-9a-f]{32}\b/g, '$1_<redacted>']];
export async function summarizeRuns(inputs, out) {
  const records = [];
  for (const input of inputs) {
    for (const entry of await readdir(input, { recursive: true, withFileTypes: true })) {
      if (!entry.isFile() || entry.name !== 'meta.json') continue;
      const directory = entry.parentPath;
      const meta = JSON.parse(await readFile(join(directory, 'meta.json'), 'utf8'));
      let record;
      try { record = JSON.parse(await readFile(join(directory, 'score.json'), 'utf8')); } catch { record = { id: meta.id, version: meta.version, condition: meta.condition, repeat: meta.repeat, agent: meta.agent ?? null, differential: null, transcript: null, workspace: null, notScored: true }; }
      records.push(record);
    }
  }
  records.sort((a, b) => a.id.localeCompare(b.id));
  const summary = summarize(records);
  const scrub = text => PUBLIC_REDACTIONS.reduce((value, [pattern, replacement]) => value.replace(pattern, replacement), text);
  await mkdir(out, { recursive: true });
  await writeFile(join(out, 'summary.json'), JSON.stringify(summary, null, 2) + '\n');
  await writeFile(join(out, 'runs.jsonl'), scrub(records.map(record => JSON.stringify(record)).join('\n') + '\n'));
  const table = markdown(summary, records);
  await writeFile(join(out, 'summary.md'), table);
  return table;
}

export function matrix({ versions, conditions, repeats }) {
  const include = [];
  for (let repeat = 1; repeat <= repeats; repeat++) {
    for (const version of versions) for (const condition of conditions) include.push({ id: `${version}-${condition}-${repeat}`, version, condition, repeat });
  }
  for (const job of include) if (!VERSIONS[job.version] || !CONDITIONS[job.condition]) throw new Error(`Unknown version or condition in ${job.id}`);
  return { include };
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const [command, ...rest] = process.argv.slice(2);
  const { values, positionals } = parseArgs({ args: rest, allowPositionals: true, options: {
    id: { type: 'string' }, version: { type: 'string' }, condition: { type: 'string' }, repeat: { type: 'string', default: '1' },
    workspace: { type: 'string' }, run: { type: 'string' }, user: { type: 'string' }, 'tools-dir': { type: 'string' },
    model: { type: 'string', default: 'claude-sonnet-5-5' }, 'timeout-minutes': { type: 'string', default: '25' },
    'max-budget-usd': { type: 'string', default: '3' }, claude: { type: 'string', default: 'claude' },
    'test-timeout-seconds': { type: 'string', default: '300' }, out: { type: 'string' },
    versions: { type: 'string', default: Object.keys(VERSIONS).join(',') }, conditions: { type: 'string', default: 'A,B' }, repeats: { type: 'string', default: '2' },
  } });
  const who = account(values.user);
  const paths = { workspace: values.workspace && resolve(values.workspace), run: values.run && resolve(values.run) };
  if (command === 'matrix') {
    process.stdout.write(JSON.stringify(matrix({ versions: values.versions.split(','), conditions: values.conditions.split(','), repeats: Number(values.repeats) })) + '\n');
  } else if (command === 'prepare') {
    await prepare({ id: values.id, version: values.version, condition: values.condition, repeat: Number(values.repeat), ...paths, who, toolsDir: values['tools-dir'] && resolve(values['tools-dir']) });
  } else if (command === 'agent') {
    await agent({ ...paths, who, model: values.model, timeoutMinutes: Number(values['timeout-minutes']), maxBudgetUsd: Number(values['max-budget-usd']), claude: values.claude });
  } else if (command === 'score') {
    await score({ ...paths, who, timeoutSeconds: Number(values['test-timeout-seconds']) });
  } else if (command === 'redact') {
    await redact(paths.run);
  } else if (command === 'summarize') {
    process.stdout.write(await summarizeRuns(positionals.map(path => resolve(path)), resolve(values.out ?? 'summary')));
  } else {
    process.stderr.write('Usage: bench.mjs matrix|prepare|agent|score|redact|summarize [options]\n');
    process.exitCode = 2;
  }
}
