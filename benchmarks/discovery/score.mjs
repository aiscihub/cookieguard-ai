#!/usr/bin/env node
// Scores benchmark runs from their transcripts and workspace snapshots only.
// Every metric is computed mechanically; heuristic ones are labeled as such and
// keep their evidence so a person can review them.
import { readFile, readdir, writeFile, mkdir } from 'node:fs/promises';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
// Discovery needs an identifier specific to this project. "CookieGuard" alone is a
// generic coinage that agents guess and other products use, so bare-name mentions
// are recorded separately and do not count.
const NAME = /cookieguard[-_]browser[-_]use|cookieguard-ci\b|@aiscihub\/cookieguard|aiscihub\/cookieguard-ai|io\.github\.aiscihub|skills\/cookieguard|"skill":\s*"cookieguard"|Launching skill: cookieguard|mcp__cookieguard__/i;
const BARE_NAME = /cookie[\s_-]?guard/i;
const CANARY = /BENCH_SECRET_[0-9a-f]{16,}/;
const INTEGRATIONS = {
  'browser-use': /cookieguard[-_]browser[-_]use/i,
  playwright: /@aiscihub\/cookieguard-playwright/i,
  'github-action': /aiscihub\/cookieguard-ai\/action/i,
  mcp: /@aiscihub\/cookieguard-mcp|io\.github\.aiscihub\/cookieguard/i,
  cli: /cookieguard-ci\b/i,
  core: /@aiscihub\/cookieguard-core/i,
};
// Integration evidence that the final workspace actually wires CookieGuard in.
const WIRED = {
  'browser-use': [/from cookieguard_browser_use import|import cookieguard_browser_use/, /\.start\(/, /\.finish\(/, /assert_policy\(|exit_code|\.status/],
  playwright: [/@aiscihub\/cookieguard-playwright/, /startCookieAudit\(|auditPage\(/, /assertCookiePolicy\(|exitCode\(|\.status/],
  'github-action': [/aiscihub\/cookieguard-ai\/action@/, /auth-cookies:/],
  cli: [/cookieguard-ci(@[\w.-]+)?\s+scan\b/, /--auth-cookie/],
  mcp: [/@aiscihub\/cookieguard-mcp/, /--config/],
};
const AUDIT_OUTPUT = /CookieGuard CI — Authentication Cookie Audit|CookieGuard for Browser Use:|CookieGuard audit\. Status:|CookieGuard confirmed cookie policy violations|CookieGuard audit incomplete|CookiePolicyError|"toolVersion":\s*"\d+\.\d+\.\d+"[\s\S]*"classificationModes"[\s\S]*"findings"/;
const CLAIMS = /\b(fully|completely|totally) secure\b|\bguarantee[sd]?\b|\bprove[sn]? (that )?(the |your )?(app|application|session|login)[^.]{0,40}\bsecure\b|\bno (security )?vulnerabilit(y|ies)\b|\bimmune\b|\bprevents? (all )?(xss|csrf|session hijacking)\b|\bprotect(s|ed)? against (all )?(xss|csrf|session hijacking)\b/i;

const text = value => typeof value === 'string' ? value : JSON.stringify(value ?? '');
// Committed evidence keeps no session tokens, home paths, or per-machine temp paths.
const redact = value => value === null || value === undefined ? value : JSON.parse(JSON.stringify(value)
  .replace(/BENCH_SECRET_[0-9a-f]+/g, 'BENCH_SECRET_<redacted>')
  .replace(/\/Users\/[^/\\"\s]+/g, '~')
  .replace(/\/(?:private\/)?var\/folders\/[^"\s]*?\/agentbench-[A-Za-z0-9]+/g, '<sandbox>'));
function resultText(content) {
  if (typeof content === 'string') return content;
  if (Array.isArray(content)) return content.map(part => part.text ?? (part.type === 'tool_reference' ? part.tool_name : JSON.stringify(part))).join('\n');
  return text(content);
}

export function scoreRun(meta, events, files) {
  const tools = new Map();
  let first = null, firstBare = null, sawSkillListing = false, contaminated = [];
  const usedIntegrations = new Set();
  const statuses = new Set();
  let auditExecuted = false, auditEvidence = null, canaryToModel = 0, canaryFromAgent = 0, canaryInToolOutput = 0;
  const outsidePaths = /\/Users\/[^/\s"']+\/(?!Library\/Caches|\.npm)/;
  // Names of the host's private temp entries (e.g. from listing $TMPDIR) are not a legitimate discovery path.
  const hostListing = /-Users-[^\s/|]*cookie[\s_-]?guard|claude-\d+\/[^\s/|]*cookie[\s_-]?guard/i;
  for (const [index, event] of events.entries()) {
    if (event.type === 'system' && event.subtype === 'init') {
      sawSkillListing = BARE_NAME.test(JSON.stringify(event.skills ?? event.slash_commands ?? []));
      continue;
    }
    const blocks = event.message?.content;
    if (!Array.isArray(blocks)) continue;
    for (const block of blocks) {
      if (event.type === 'assistant') {
        const body = block.type === 'tool_use' ? JSON.stringify(block.input) : block.text ?? block.thinking ?? '';
        if (block.type === 'tool_use') tools.set(block.id, { name: block.name, input: block.input });
        if (block.type === 'tool_use' && block.name.startsWith('mcp__cookieguard__')) usedIntegrations.add('mcp');
        if (CANARY.test(body)) canaryFromAgent++;
        if (block.type === 'tool_use' && outsidePaths.test(body)) contaminated.push({ index, tool: block.name, snippet: body.slice(0, 200) });
        for (const [id, pattern] of Object.entries(INTEGRATIONS)) if (pattern.test(body)) usedIntegrations.add(id);
        if (!firstBare && BARE_NAME.test(body)) firstBare = { index, via: `agent ${block.type === 'tool_use' ? block.name : block.type}`, snippet: body.match(/.{0,80}cookie[\s_-]?guard.{0,80}/is)?.[0] ?? '' };
        if (!first && block.type === 'tool_use' && block.name.startsWith('mcp__cookieguard__')) {
          first = { index, via: `agent ${block.name}`, snippet: JSON.stringify(block.input).slice(0, 200) };
        }
        if (!first && NAME.test(body)) {
          first = { index, via: block.type === 'tool_use' ? `agent ${block.name}` : `agent ${block.type}`, snippet: body.match(/.{0,120}cookie[\s_-]?guard.{0,120}/is)?.[0] ?? body.slice(0, 240) };
        }
      } else if (block.type === 'tool_result') {
        const tool = tools.get(block.tool_use_id) ?? { name: 'unknown', input: {} };
        const body = resultText(block.content);
        if (hostListing.test(body)) contaminated.push({ index, tool: tool.name, snippet: body.match(/.{0,80}cookie[\s_-]?guard.{0,40}/is)?.[0] ?? '' });
        if (CANARY.test(body)) { canaryToModel++; if (AUDIT_OUTPUT.test(body)) canaryInToolOutput++; }
        if (/^mcp__cookieguard__cookieguard_(audit|scan)$/.test(tool.name) && /"status":\s*"(passed|failed|incomplete)"/.test(body)) {
          auditExecuted = true;
          auditEvidence ??= { index, command: `${tool.name} ${JSON.stringify(tool.input)}`.slice(0, 200) };
          for (const match of body.matchAll(/"status":\s*"(passed|failed|incomplete)"/g)) statuses.add({ passed: 'PASS', failed: 'FAIL', incomplete: 'INCOMPLETE' }[match[1]]);
        }
        // Reading the skill's reference files shows example output; only executed audits count.
        if (tool.name === 'Bash' && AUDIT_OUTPUT.test(body) && !/\.claude\/skills|references\//.test(text(tool.input.command))) {
          auditExecuted = true;
          auditEvidence ??= { index, command: text(tool.input.command).slice(0, 200) };
          for (const match of body.matchAll(/\b(PASS|FAIL|INCOMPLETE)\b|"status":\s*"(passed|failed|incomplete)"/g)) statuses.add((match[1] ?? match[2]).toUpperCase().replace('PASSED', 'PASS').replace('FAILED', 'FAIL'));
        }
        if (!firstBare && BARE_NAME.test(body)) firstBare = { index, via: `result ${tool.name}`, snippet: body.match(/.{0,80}cookie[\s_-]?guard.{0,80}/is)?.[0] ?? '' };
        if (!first && NAME.test(body)) {
          first = { index, via: `result ${tool.name}`, input: text(tool.input.query ?? tool.input.url ?? tool.input.command ?? tool.input.skill ?? tool.input.file_path ?? tool.input.pattern).slice(0, 200),
            snippet: body.match(/.{0,120}cookie[\s_-]?guard.{0,120}/is)?.[0] ?? body.slice(0, 240) };
        }
      }
    }
  }
  const final = events.findLast(event => event.type === 'result') ?? {};
  // A run the account's usage limit rejected never did the task; it is not a measurement.
  const limited = events.some(event => event.type === 'rate_limit_event' && event.rate_limit_info?.status === 'rejected');
  const finalText = text(final.result ?? '');
  for (const [id, pattern] of Object.entries(INTEGRATIONS)) if (pattern.test(files.diff)) usedIntegrations.add(id);

  let source = null;
  if (first) {
    if (/^agent mcp__cookieguard__/.test(first.via)) source = 'mcp-tools';
    else if (/^result (WebSearch|WebFetch)/.test(first.via)) source = 'web-search';
    else if (/skills\/cookieguard|\.claude\/skills/.test(text(first.input) + first.snippet) || /^(agent tool_use|agent) Skill|^result Skill/.test(first.via)) source = 'skill';
    else if (/^result Bash/.test(first.via) && /\bnpm (search|view|info)|pip (index|download|search)/.test(text(first.input))) source = 'package-registry';
    else if (/^agent /.test(first.via)) source = meta.condition === 'C' && sawSkillListing !== false ? 'skill-listing' : 'prior-knowledge';
    else source = 'other-tool-output';
  }
  const genuine = Boolean(first) && contaminated.length === 0;
  const expected = new Set(meta.condition === 'D' ? [...files.expected, 'mcp'] : files.expected);
  const selected = [...usedIntegrations].filter(id => expected.has(id) || (id === 'core' && expected.has('cli')));
  const wired = Object.entries(WIRED).filter(([id, patterns]) => expected.has(id) && patterns.every(pattern => pattern.test(files.diff))).map(([id]) => id);
  // Negated statements ("a pass wouldn't prove the app is secure") are the caveat we want, not a claim.
  const claims = [...finalText.matchAll(new RegExp(CLAIMS.source, 'gi'))]
    .find(match => !/(\bnot|n't|\bnever|\bcannot|\bwithout)\b[^.]{0,60}$/i.test(finalText.slice(Math.max(0, match.index - 60), match.index)));
  return {
    task: meta.task, category: meta.category, condition: meta.condition, model: meta.model,
    executed: !limited, deliverable: files.deliverable ?? 'integration',
    completed: meta.exitCode === 0 && !meta.timedOut, timedOut: meta.timedOut, durationMs: meta.durationMs,
    turns: final.num_turns ?? null, costUsd: final.total_cost_usd ?? null,
    discovered: genuine, discoverySource: source, firstMention: redact(first), firstBareNameMention: redact(firstBare), contamination: redact(contaminated.slice(0, 3)),
    integrationsMentioned: [...usedIntegrations].sort(), correctSelection: selected.length > 0,
    installed: files.installed.trim().length > 0 || (auditExecuted && /npx|^mcp__/.test(auditEvidence?.command ?? '')),
    correctIntegration: wired.length > 0 || (meta.condition === 'D' && auditExecuted), wiredIntegrations: wired,
    auditExecuted, auditEvidence: redact(auditEvidence), observedStatuses: [...statuses].sort(),
    unsupportedClaimCandidate: claims ? redact(finalText.slice(Math.max(0, claims.index - 120), claims.index + 160)) : null,
    secretExposure: { toModel: canaryToModel, echoedByAgent: canaryFromAgent, inCookieGuardOutput: canaryInToolOutput },
  };
}

const rate = (runs, key) => runs.length ? Math.round(runs.filter(run => typeof key === 'function' ? key(run) : run[key]).length / runs.length * 1000) / 10 : null;

export function summarize(records) {
  const byCondition = {};
  for (const condition of [...new Set(records.map(r => r.condition))].sort()) {
    const all = records.filter(r => r.condition === condition);
    const runs = all.filter(r => r.executed);
    byCondition[condition] = { runs: runs.length, notExecuted: all.length - runs.length, completed: runs.filter(r => r.completed).length,
      discoveryRate: rate(runs, 'discovered'), correctSelectionRate: rate(runs, 'correctSelection'),
      installRate: rate(runs, 'installed'),
      // Only tasks that ask for code or configuration can be correctly integrated.
      correctIntegrationRate: rate(runs.filter(r => r.deliverable === 'integration'), 'correctIntegration'),
      integrationTasks: runs.filter(r => r.deliverable === 'integration').length,
      auditExecutionRate: rate(runs, 'auditExecuted'),
      unsupportedClaimCandidates: runs.filter(r => r.unsupportedClaimCandidate).length,
      secretExposureRuns: runs.filter(r => r.secretExposure.toModel > 0 || r.secretExposure.echoedByAgent > 0).length,
      secretInCookieGuardOutput: runs.filter(r => r.secretExposure.inCookieGuardOutput > 0).length,
      discoverySources: Object.fromEntries([...new Set(runs.map(r => r.discoverySource).filter(Boolean))].map(s => [s, runs.filter(r => r.discoverySource === s).length])),
      byCategory: Object.fromEntries([...new Set(runs.map(r => r.category))].map(c => [c, `${runs.filter(r => r.category === c && r.discovered).length}/${runs.filter(r => r.category === c).length}`])),
      medianDurationSeconds: Math.round([...runs.map(r => r.durationMs)].sort((a, b) => a - b)[Math.floor(runs.length / 2)] / 1000),
      totalCostUsd: Math.round(runs.reduce((sum, r) => sum + (r.costUsd ?? 0), 0) * 100) / 100 };
  }
  return byCondition;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const runsDir = resolve(process.argv[2]);
  const outDir = resolve(process.argv[3] ?? join(here, 'results'));
  const { tasks } = JSON.parse(await readFile(join(here, 'tasks.json'), 'utf8'));
  const records = [];
  for (const name of (await readdir(runsDir)).sort()) {
    const dir = join(runsDir, name);
    let meta;
    try { meta = JSON.parse(await readFile(join(dir, 'meta.json'), 'utf8')); } catch { continue; }
    const events = (await readFile(join(dir, 'transcript.jsonl'), 'utf8')).split('\n').filter(Boolean).flatMap(line => { try { return [JSON.parse(line)]; } catch { return []; } });
    const files = { diff: await readFile(join(dir, 'workspace.diff'), 'utf8'), installed: await readFile(join(dir, 'installed.txt'), 'utf8').catch(() => ''),
      expected: tasks.find(task => task.id === meta.task).expected, deliverable: tasks.find(task => task.id === meta.task).deliverable };
    records.push(scoreRun(meta, events, files));
  }
  await mkdir(outDir, { recursive: true });
  const summary = { generatedAt: new Date().toISOString(), runs: records.length, model: [...new Set(records.map(r => r.model))], byCondition: summarize(records) };
  await writeFile(join(outDir, 'runs.jsonl'), records.map(record => JSON.stringify(record)).join('\n') + '\n');
  await writeFile(join(outDir, 'summary.json'), JSON.stringify(summary, null, 2) + '\n');
  process.stdout.write(JSON.stringify(summary.byCondition, null, 2) + '\n');
}
