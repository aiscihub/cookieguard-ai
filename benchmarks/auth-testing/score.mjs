// Pure scoring functions. The primary metric comes from running the agent's own test
// suite against app versions (see bench.mjs); transcript metrics are secondary, and the
// ones that read the agent's prose are labeled heuristic and keep their evidence.
import { FLAWED, VERSIONS } from './variants.mjs';

// Real credentials issued by the app: session ids and, in js-token, API tokens.
const CREDENTIAL = /\b(?:sess|tok)_[0-9a-f]{32}\b/g;
const TOOL_NAME = /cookie[\s_-]?guard|aiscihub/i;
const MCP_PREFIX = 'mcp__cookieguard__';
const WIRED_PLAYWRIGHT = [/@aiscihub\/cookieguard-playwright/, /startCookieAudit\(|auditPage\(/, /assertCookiePolicy\(|\.status\b|exitCode/];
const WIRED_CLI = [/cookieguard-ci(@[\w.-]+)?\s+scan\b/];
// Unsupported assurance in the final answer (heuristic). Negated sentences are caveats.
const CLAIMS = /\b(fully|completely|totally) secure\b|\bno (security )?(vulnerabilit(y|ies)|issues|problems) (were |was )?(found|detected)\b|\b(login|session|authentication)( handling)? (is|are) secure\b/i;
const NEGATION = /\b(not|n't|never|cannot|no guarantee|doesn't prove|does not prove)\b/i;
// Heuristic: the final answer names the seeded flaw.
const MENTIONS = {
  'no-httponly': /http-?only/i,
  'js-token': /api_token|document\.cookie|readable (by|from|to) (page )?(java)?script|javascript-readable/i,
  'open-redirect': /open[- ]redirect|(unvalidated|arbitrary|external|off-site|cross-origin) redirect/i,
};

const asText = value => typeof value === 'string' ? value : JSON.stringify(value ?? '');
function resultText(content) {
  if (typeof content === 'string') return content;
  if (Array.isArray(content)) return content.map(part => part.text ?? JSON.stringify(part)).join('\n');
  return asText(content);
}
const lowEntropy = token => new Set(token.slice(token.indexOf('_') + 1)).size < 8;

// Transcript metrics from Claude Code's stream-json events.
export function scoreTranscript(events) {
  const authored = new Set(), toModel = new Set(), echoed = new Set();
  const tools = new Map();
  let mcpCalls = 0, skillLoaded = false, toolNameSeen = null, result = null, toolCalls = 0;
  const note = (where, body) => { if (!toolNameSeen && TOOL_NAME.test(body)) toolNameSeen = { where, snippet: body.match(/.{0,80}(cookie[\s_-]?guard|aiscihub).{0,80}/is)?.[0] ?? '' }; };
  for (const event of events) {
    if (event.type === 'result') { result = event; continue; }
    const blocks = event.message?.content;
    if (!Array.isArray(blocks)) continue;
    for (const block of blocks) {
      if (event.type === 'assistant') {
        const body = block.type === 'tool_use' ? JSON.stringify(block.input) : block.text ?? '';
        if (block.type === 'tool_use') {
          toolCalls++;
          tools.set(block.id, block.name);
          if (block.name.startsWith(MCP_PREFIX)) mcpCalls++;
          if (block.name === 'Skill' && TOOL_NAME.test(JSON.stringify(block.input))) skillLoaded = true;
        }
        note(`agent ${block.type === 'tool_use' ? block.name : 'text'}`, body);
        for (const [token] of body.matchAll(CREDENTIAL)) {
          if (lowEntropy(token)) continue;
          if (toModel.has(token)) echoed.add(token);
          else authored.add(token);
        }
      } else if (block.type === 'tool_result') {
        const body = resultText(block.content);
        note(`result of ${tools.get(block.tool_use_id) ?? 'tool'}`, body);
        // A credential first seen in tool output came from the running app, not the agent.
        for (const [token] of body.matchAll(CREDENTIAL)) if (!lowEntropy(token) && !authored.has(token)) toModel.add(token);
      }
    }
  }
  const finalText = typeof result?.result === 'string' ? result.result : '';
  for (const [token] of finalText.matchAll(CREDENTIAL)) if (toModel.has(token)) echoed.add(token);
  const claim = finalText.split(/(?<=[.!?])\s+|\n+/).find(sentence => CLAIMS.test(sentence) && !NEGATION.test(sentence)) ?? null;
  const usage = result?.usage ?? {};
  return {
    completed: result?.subtype === 'success' && !result.is_error,
    resultSubtype: result?.subtype ?? null,
    numTurns: result?.num_turns ?? null,
    toolCalls,
    costUsd: result?.total_cost_usd ?? null,
    durationMs: result?.duration_ms ?? null,
    tokens: { input: usage.input_tokens ?? 0, output: usage.output_tokens ?? 0, cacheRead: usage.cache_read_input_tokens ?? 0, cacheWrite: usage.cache_creation_input_tokens ?? 0 },
    credentialsShownToModel: toModel.size,
    credentialsEchoedByAgent: echoed.size,
    toolNameSeen,
    mcpCalls,
    skillLoaded,
    finalText,
    heuristic: {
      unsupportedClaim: claim,
      mentions: Object.fromEntries(Object.entries(MENTIONS).map(([version, pattern]) => [version, pattern.test(finalText)])),
    },
  };
}

// Whether the final workspace enforces a CookieGuard check in its tests or scripts.
export function toolInWorkspace(diff) {
  return {
    mentioned: TOOL_NAME.test(diff),
    playwright: WIRED_PLAYWRIGHT.every(pattern => pattern.test(diff)),
    cli: WIRED_CLI.every(pattern => pattern.test(diff)),
  };
}

// Differential result: a flaw is caught when the suite fails on that version and passes
// on every run against the fixed version. A suite that fails on the fixed app catches nothing.
export function differential(runs, seen) {
  const fixedRuns = runs.filter(run => run.version === 'fixed');
  const passesFixed = fixedRuns.length > 0 && fixedRuns.every(run => run.exitCode === 0);
  const flaky = new Set(fixedRuns.map(run => run.exitCode === 0)).size > 1;
  const caught = {};
  for (const version of FLAWED) {
    const run = runs.find(entry => entry.version === version);
    // A timeout (exitCode null) is not a catch: the suite never reported a failure.
    caught[version] = run ? passesFixed && Number.isInteger(run.exitCode) && run.exitCode !== 0 : null;
  }
  return { passesFixed, flaky, caught, caughtSeen: seen === 'fixed' ? null : caught[seen] ?? null, caughtCount: Object.values(caught).filter(Boolean).length };
}

export function wilson(successes, n, z = 1.96) {
  if (!n) return null;
  const p = successes / n, z2 = z * z;
  const center = (p + z2 / (2 * n)) / (1 + z2 / n);
  const half = (z / (1 + z2 / n)) * Math.sqrt(p * (1 - p) / n + z2 / (4 * n * n));
  return [Math.max(0, center - half), Math.min(1, center + half)].map(value => Math.round(value * 1000) / 1000);
}

const rate = (records, test) => {
  const eligible = records.filter(record => test(record) !== null && test(record) !== undefined);
  const hits = eligible.filter(test).length;
  return { hits, n: eligible.length, ci95: wilson(hits, eligible.length) };
};
const sum = values => values.reduce((total, value) => total + (value ?? 0), 0);

export function summarize(records) {
  const conditions = [...new Set(records.map(record => record.condition))].sort();
  const byCondition = {};
  for (const condition of conditions) {
    const mine = records.filter(record => record.condition === condition);
    const scored = mine.filter(record => record.differential);
    byCondition[condition] = {
      runs: mine.length,
      scored: scored.length,
      agentCompleted: mine.filter(record => record.transcript?.completed).length,
      suitePassesFixed: rate(scored, record => record.differential.passesFixed),
      caughtSeenFlaw: Object.fromEntries(FLAWED.map(version => [version, rate(scored.filter(record => record.version === version), record => record.differential.caughtSeen)])),
      catchesAnyVersion: Object.fromEntries(FLAWED.map(version => [version, rate(scored, record => record.differential.caught[version])])),
      credentialExposureRuns: rate(mine.filter(record => record.transcript), record => record.transcript.credentialsShownToModel > 0),
      toolUsed: rate(mine.filter(record => record.transcript), record => record.transcript.mcpCalls > 0 || record.transcript.skillLoaded || record.workspace?.tool?.mentioned),
      toolEnforcedInTests: rate(mine.filter(record => record.workspace), record => record.workspace.tool.playwright || record.workspace.tool.cli),
      contaminated: condition === 'A' ? mine.filter(record => record.transcript?.toolNameSeen).length : null,
      appSourceModified: mine.filter(record => record.workspace?.appModified?.length).length,
      costUsd: Math.round(sum(mine.map(record => record.transcript?.costUsd)) * 100) / 100,
      agentMinutes: Math.round(sum(mine.map(record => record.transcript?.durationMs)) / 600) / 100,
    };
  }
  return { schemaVersion: 1, versions: Object.keys(VERSIONS), flawed: FLAWED, conditions: byCondition };
}

const cell = ({ hits, n }) => n ? `${hits}/${n}` : '—';
export function markdown(summary, records) {
  const conditions = Object.keys(summary.conditions);
  const row = (label, pick) => `| ${label} | ${conditions.map(condition => pick(summary.conditions[condition])).join(' | ')} |`;
  const lines = [
    `| Metric | ${conditions.map(condition => `${condition}`).join(' | ')} |`,
    `| --- | ${conditions.map(() => '---').join(' | ')} |`,
    row('Runs (scored)', entry => `${entry.runs} (${entry.scored})`),
    row('Agent finished normally', entry => `${entry.agentCompleted}/${entry.runs}`),
    row('Suite passes on the fixed app', entry => cell(entry.suitePassesFixed)),
    ...summary.flawed.map(version => row(`Caught the flaw it was shown: ${version}`, entry => cell(entry.caughtSeenFlaw[version]))),
    ...summary.flawed.map(version => row(`Suite catches ${version} (any run)`, entry => cell(entry.catchesAnyVersion[version]))),
    row('Runs where a real credential reached the model', entry => cell(entry.credentialExposureRuns)),
    row('Used the tool under test', entry => cell(entry.toolUsed)),
    row('Tool check enforced in the tests', entry => cell(entry.toolEnforcedInTests)),
    row('Runs that edited app source', entry => String(entry.appSourceModified)),
    row('Cost reported by the CLI (USD)', entry => entry.costUsd.toFixed(2)),
    row('Agent minutes', entry => String(entry.agentMinutes)),
    '',
    '| Run | Shown | Passes fixed | Caught (no-httponly, js-token, open-redirect) | Credential to model | Tool used | Cost |',
    '| --- | --- | --- | --- | --- | --- | --- |',
    ...records.map(record => `| ${record.id} | ${record.version} | ${record.differential ? (record.differential.passesFixed ? 'yes' : 'no') : 'not scored'} | ${record.differential ? summary.flawed.map(version => record.differential.caught[version] ? '✓' : '·').join(' ') : '—'} | ${record.transcript?.credentialsShownToModel ?? '—'} | ${record.transcript ? (record.transcript.mcpCalls || record.transcript.skillLoaded || record.workspace?.tool?.mentioned ? 'yes' : 'no') : '—'} | ${record.transcript?.costUsd?.toFixed?.(2) ?? '—'} |`),
  ];
  return lines.join('\n') + '\n';
}
