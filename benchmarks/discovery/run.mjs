#!/usr/bin/env node
// Autonomous discovery benchmark harness. Runs real coding-agent sessions on
// realistic tasks that never name the tool under test, in three conditions:
//   A baseline      ordinary tools, no web search, no skill
//   B searchable    A plus web search and fetch
//   C agent-native  A plus the Agent Skill installed in the project
//   D mcp           A plus the MCP server already configured in the agent's client
// Every run gets a fresh sandbox outside this repository whose path carries no
// tool name, an OS sandbox that denies reads of the home directory, and network
// access limited to package registries. See README.md.
import { spawn, execFileSync } from 'node:child_process';
import { createWriteStream, existsSync, readdirSync, realpathSync, rmSync } from 'node:fs';
import { cp, mkdtemp, mkdir, readFile, readdir, rm, writeFile } from 'node:fs/promises';
import { homedir, tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parseArgs } from 'node:util';

const here = dirname(fileURLToPath(import.meta.url));
const repo = resolve(here, '../..');
const BASE_TOOLS = ['Bash', 'Read', 'Write', 'Edit', 'Glob', 'Grep', 'Skill'];
export const CONDITIONS = {
  A: { label: 'baseline', tools: BASE_TOOLS, skill: false },
  B: { label: 'searchable', tools: [...BASE_TOOLS, 'WebSearch', 'WebFetch'], skill: false },
  C: { label: 'agent-native', tools: BASE_TOOLS, skill: true },
  D: { label: 'mcp-configured', tools: BASE_TOOLS, skill: false, mcp: true },
};
const PROJECT_NAMES = { webapp: 'acme-portal', agentapp: 'acme-agent' };
const REGISTRIES = ['pypi.org', 'files.pythonhosted.org', 'registry.npmjs.org', 'playwright.azureedge.net',
  'playwright-akamai.azureedge.net', 'playwright-verizon.azureedge.net', 'cdn.playwright.dev', 'playwright.download.prss.microsoft.com'];
const BROWSERS = '~/Library/Caches/ms-playwright';

// Sandboxed commands share the host agent's per-user temp directory
// (/tmp/claude-<uid>) as $TMPDIR, so it cannot be denied as a whole. Deny every
// entry in it that belongs to this project; the scorer flags any run whose
// transcript shows those entries' names as contaminated.
export const HOST_MARKER = /cookie[\s_-]?guard/i;
export function hostPrivateDirectories(path = repo) {
  const match = /^(?:\/private)?(\/tmp\/claude-\d+)\//.exec(path);
  if (!match) return [];
  return readdirSync(`/private${match[1]}`).filter(name => HOST_MARKER.test(name))
    .flatMap(name => [`/private${match[1]}/${name}`, `${match[1]}/${name}`]);
}

export function sandboxSettings(sandbox, hidden = []) {
  return {
    sandbox: {
      enabled: true, autoAllowBashIfSandboxed: true, allowUnsandboxedCommands: false,
      filesystem: { denyRead: ['~/', ...hidden], allowRead: [sandbox, BROWSERS], allowWrite: [sandbox] },
      network: { allowLocalBinding: true, allowedDomains: REGISTRIES },
    },
    permissions: {
      deny: ['Read(~/**)', 'Edit(~/**)', ...hidden.map(path => `Read(/${path}/**)`)],
    },
  };
}

function cleanEnv(sandbox, project) {
  const env = {};
  for (const [key, value] of Object.entries(process.env)) {
    // Never forward IDE, agent-session, or API-key variables to the nested agent.
    if (/^(CLAUDE|VSCODE_|ELECTRON_|MCP_|ANTHROPIC_|__CF)/.test(key) || key === 'CLAUDECODE') continue;
    env[key] = value;
  }
  return { ...env, SHELL: '/bin/bash', TMPDIR: join(sandbox, 'tmp'), GIT_CONFIG_GLOBAL: join(sandbox, 'gitconfig'),
    npm_config_userconfig: join(sandbox, 'npmrc'), npm_config_cache: join(sandbox, 'npm-cache'), npm_config_update_notifier: 'false',
    // pip's default truststore check needs the macOS trust service, which the sandbox
    // blocks; the bundled CA file works and changes nothing else.
    PIP_CONFIG_FILE: '/dev/null', PIP_CACHE_DIR: join(sandbox, 'pip-cache'), PIP_USE_DEPRECATED: 'legacy-certs',
    PIP_DISABLE_PIP_VERSION_CHECK: '1', PLAYWRIGHT_BROWSERS_PATH: join(homedir(), 'Library/Caches/ms-playwright'),
    XDG_CONFIG_HOME: join(sandbox, 'xdg-config'), XDG_CACHE_HOME: join(sandbox, 'xdg-cache'),
    BROWSER_USE_CONFIG_DIR: join(sandbox, 'browseruse'), ANONYMIZED_TELEMETRY: 'false', BROWSER_USE_CLOUD_SYNC: 'false',
    COOKIEGUARD_USAGE_METRICS: '0', DO_NOT_TRACK: '1', PWD: project };
}

async function prepare(task, condition, slot, run) {
  // Real path: the OS sandbox matches resolved paths (/var -> /private/var on macOS).
  const sandbox = realpathSync(await mkdtemp(join(tmpdir(), 'agentbench-')));
  const project = join(sandbox, PROJECT_NAMES[task.fixture]);
  await cp(join(here, 'fixtures', task.fixture), project, { recursive: true });
  const port = 3100 + slot * 10;
  for (const file of await listFiles(project)) {
    const text = await readFile(file, 'utf8');
    if (text.includes('{{')) await writeFile(file, text.replaceAll('{{PORT}}', String(port)).replaceAll('{{TEST_PORT}}', String(port + 5)));
  }
  await writeFile(join(project, '.gitignore'), 'node_modules/\n.venv/\nvenv/\n__pycache__/\ntest-results/\nplaywright-report/\n');
  if (CONDITIONS[condition].skill) await cp(join(repo, 'skills/cookieguard-browser-auth-security'), join(project, '.claude/skills/cookieguard-browser-auth-security'), { recursive: true });
  for (const directory of ['tmp', 'xdg-config', 'xdg-cache', 'browseruse']) await mkdir(join(sandbox, directory));
  await writeFile(join(sandbox, 'gitconfig'), '[user]\n\tname = Developer\n\temail = dev@example.invalid\n[init]\n\tdefaultBranch = main\n');
  await writeFile(join(sandbox, 'npmrc'), 'fund=false\naudit=false\n');
  const env = cleanEnv(sandbox, project);
  for (const args of [['init', '-q'], ['add', '-A'], ['commit', '-qm', 'Initial commit']]) execFileSync('git', args, { cwd: project, env });
  // Kept with the run record, outside anything the nested agent can read.
  const settings = join(run, 'settings.json');
  await writeFile(settings, JSON.stringify(sandboxSettings(sandbox, hostPrivateDirectories()), null, 2));
  let mcpConfig = null;
  if (CONDITIONS[condition].mcp) {
    // The developer has configured the local server for this app; the agent is not told about it.
    const serverConfig = join(run, 'mcp-server.json');
    await writeFile(serverConfig, JSON.stringify({ allowedOrigins: [`http://127.0.0.1:${port}`, `http://localhost:${port}`],
      policy: { authCookies: [task.fixture === 'agentapp' ? 'sid' : 'session'] } }));
    mcpConfig = join(run, 'mcp.json');
    await writeFile(mcpConfig, JSON.stringify({ mcpServers: { cookieguard: { command: process.execPath,
      args: [join(repo, 'packages/mcp/bin/cookieguard-mcp.js'), '--config', serverConfig],
      env: { COOKIEGUARD_USAGE_METRICS: '0', DO_NOT_TRACK: '1' } } } }));
  }
  return { sandbox, project, settings, env, port, mcpConfig };
}

async function listFiles(directory) {
  const entries = await readdir(directory, { withFileTypes: true, recursive: true });
  return entries.filter(entry => entry.isFile()).map(entry => join(entry.parentPath, entry.name));
}

function killLeftovers(sandbox) {
  // Servers or browsers the agent started in the background still have their cwd inside the sandbox.
  let output = '';
  try { output = execFileSync('lsof', ['-a', '-d', 'cwd', '-Fpn'], { encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }); } catch (error) { output = error.stdout ?? ''; }
  let pid = null;
  const victims = new Set();
  for (const line of output.split('\n')) {
    if (line.startsWith('p')) pid = Number(line.slice(1));
    else if (line.startsWith('n') && pid && line.slice(1).startsWith(sandbox)) victims.add(pid);
  }
  for (const victim of victims) { try { process.kill(victim, 'SIGKILL'); } catch { /* already gone */ } }
  return victims.size;
}

function removeSessionState(sandbox) {
  // Claude Code may create a per-project directory; remove only the one for this sandbox.
  const projects = join(homedir(), '.claude', 'projects');
  const marker = sandbox.split('/').pop();
  if (!existsSync(projects)) return;
  for (const name of readdirSync(projects)) if (name.includes(marker)) rmSync(join(projects, name), { recursive: true, force: true });
}

async function snapshot(project, out) {
  const git = args => { try { return execFileSync('git', args, { cwd: project, encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 }); } catch (error) { return error.stdout ?? ''; } };
  git(['add', '-A']);
  await writeFile(join(out, 'files.txt'), git(['diff', '--cached', '--name-status', 'HEAD']));
  await writeFile(join(out, 'workspace.diff'), git(['diff', '--cached', 'HEAD', '--', '.', ':(exclude)package-lock.json', ':(exclude)**/package-lock.json']).slice(0, 2 * 1024 * 1024));
  let installed = '';
  try { installed = execFileSync('find', [project, '-maxdepth', '7', '(', '-path', '*site-packages/cookieguard_browser_use', '-o', '-path', '*node_modules/@aiscihub/cookieguard-*', '-o', '-path', '*node_modules/cookieguard-ci', ')', '-prune', '-print'], { encoding: 'utf8' }); } catch { /* none */ }
  await writeFile(join(out, 'installed.txt'), installed.replaceAll(project, '.'));
}

// Shared across workers: the account's reported 5-hour usage, so a benchmark never
// exhausts the operator's plan (rejected runs are not executions and are rescored as such).
export const usage = { fiveHour: 0, rejected: false };
function trackUsage(line) {
  if (!line.includes('"rate_limit_event"')) return;
  try {
    const info = JSON.parse(line).rate_limit_info ?? {};
    usage.fiveHour = Math.max(usage.fiveHour, info.unifiedWindows?.five_hour?.utilization ?? info.utilization ?? 0);
    if (info.status === 'rejected') usage.rejected = true;
  } catch { /* partial line */ }
}

async function runOne({ task, condition, slot, out, model, timeoutMinutes, claude, keep }) {
  const run = join(out, `${task.id}-${condition}`);
  await mkdir(run, { recursive: true });
  const prepared = await prepare(task, condition, slot, run);
  const started = Date.now();
  const args = ['-p', task.prompt, '--output-format', 'stream-json', '--verbose', '--model', model,
    '--tools', CONDITIONS[condition].tools.join(','), '--allowedTools', CONDITIONS[condition].tools.join(','),
    '--permission-mode', 'dontAsk', '--setting-sources', 'project', '--strict-mcp-config',
    '--no-session-persistence', '--settings', prepared.settings];
  if (prepared.mcpConfig) args.splice(args.indexOf('--allowedTools') + 1, 1, [...CONDITIONS[condition].tools, 'mcp__cookieguard'].join(','), '--mcp-config', prepared.mcpConfig);
  const transcript = createWriteStream(join(run, 'transcript.jsonl'));
  const errors = createWriteStream(join(run, 'stderr.log'));
  const child = spawn(claude, args, { cwd: prepared.project, env: prepared.env, detached: true, stdio: ['ignore', 'pipe', 'pipe'] });
  child.stdout.pipe(transcript);
  let pending = '';
  child.stdout.on('data', chunk => {
    const lines = (pending + chunk).split('\n');
    pending = lines.pop();
    for (const line of lines) trackUsage(line);
  });
  child.stderr.pipe(errors);
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    try { process.kill(-child.pid, 'SIGTERM'); } catch { /* exited */ }
    setTimeout(() => { try { process.kill(-child.pid, 'SIGKILL'); } catch { /* exited */ } }, 10000).unref();
  }, timeoutMinutes * 60000);
  const exitCode = await new Promise(done => child.on('close', code => done(code)));
  clearTimeout(timer);
  const killed = killLeftovers(prepared.sandbox);
  await snapshot(prepared.project, run);
  await writeFile(join(run, 'meta.json'), JSON.stringify({ task: task.id, category: task.category, condition,
    conditionLabel: CONDITIONS[condition].label, model, tools: CONDITIONS[condition].tools, exitCode, timedOut,
    durationMs: Date.now() - started, leftoverProcessesKilled: killed, startedAt: new Date(started).toISOString(),
    sandboxName: prepared.sandbox.split('/').pop(), port: prepared.port }, null, 2) + '\n');
  removeSessionState(prepared.sandbox);
  if (!keep) await rm(prepared.sandbox, { recursive: true, force: true });
  process.stdout.write(`${task.id}-${condition}: exit ${exitCode}${timedOut ? ' (timed out)' : ''} in ${Math.round((Date.now() - started) / 1000)}s\n`);
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const { values } = parseArgs({ options: {
    tasks: { type: 'string' }, conditions: { type: 'string', default: 'A,B,C' }, model: { type: 'string', default: 'sonnet' },
    parallel: { type: 'string', default: '3' }, 'timeout-minutes': { type: 'string', default: '15' },
    out: { type: 'string' }, claude: { type: 'string', default: process.env.BENCH_AGENT_CLI ?? 'claude' }, keep: { type: 'boolean' },
    runs: { type: 'string' }, 'max-utilization': { type: 'string', default: '0.7' },
  } });
  const { tasks } = JSON.parse(await readFile(join(here, 'tasks.json'), 'utf8'));
  const selected = values.tasks ? tasks.filter(task => values.tasks.split(',').includes(task.id)) : tasks;
  const conditions = values.conditions.split(',');
  const out = resolve(values.out ?? join(here, 'runs', new Date().toISOString().replace(/[:.]/g, '-')));
  await mkdir(out, { recursive: true });
  // Interleave conditions so time-dependent effects (rate limits, search index) spread evenly.
  const queue = values.runs
    ? values.runs.split(',').map(id => { const [taskId, condition] = id.split('-'); return { task: tasks.find(task => task.id === taskId), condition }; })
    : selected.flatMap(task => conditions.map(condition => ({ task, condition })));
  if (queue.some(job => !job.task || !CONDITIONS[job.condition])) throw new Error('Unknown task or condition in --runs');
  const limit = Number(values['max-utilization']);
  // Nested agents share the host temp directory as $TMPDIR; remove what they leave there.
  const hostTmp = hostPrivateDirectories()[0]?.split('/').slice(0, 4).join('/');
  const before = new Set(hostTmp ? readdirSync(hostTmp) : []);
  const workers = Array.from({ length: Number(values.parallel) }, async (_, slot) => {
    while (queue.length) {
      if (usage.rejected || usage.fiveHour >= limit) {
        process.stdout.write(`Stopping: 5-hour usage ${Math.round(usage.fiveHour * 100)}%${usage.rejected ? ' (rejected)' : ''}; ${queue.length} runs not started.\n`);
        queue.length = 0;
        break;
      }
      const job = queue.shift();
      try {
        await runOne({ ...job, slot, out, model: values.model, timeoutMinutes: Number(values['timeout-minutes']), claude: values.claude, keep: values.keep });
      } catch (error) { process.stderr.write(`${job.task.id}-${job.condition}: harness error ${error.message}\n`); }
    }
  });
  await Promise.all(workers);
  if (hostTmp) {
    const removed = readdirSync(hostTmp).filter(name => !before.has(name) && !HOST_MARKER.test(name));
    for (const name of removed) rmSync(join(hostTmp, name), { recursive: true, force: true });
    process.stdout.write(`Removed ${removed.length} temporary entries left by nested agents.\n`);
  }
  process.stdout.write(`Runs written to ${out}\n`);
}
