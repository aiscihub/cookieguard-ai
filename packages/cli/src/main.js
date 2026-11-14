import { parseArgs } from 'node:util';
import { constants } from 'node:fs';
import { lstat, open, rename, unlink } from 'node:fs/promises';
import { join } from 'node:path';
import { randomUUID } from 'node:crypto';
import { AuditError, safeError, normalizeCookies, normalizeLegacyResults, evaluateCookiePolicy,
  validatePolicy, formatText, formatJson, exitCode, explain, isEvidenceReport, readEvidence } from '@aiscihub/cookieguard-core';
import { reportUsage, flushUsage } from '@aiscihub/cookieguard-core/usage';
import { scanUrl, validateTarget } from './scan.js';
import { capabilities } from './capabilities.js';
import { evaluateCheck, formatGateText, gateCheckId, gateResult } from './gate.js';
import manifest from '../package.json' with { type: 'json' };

const HELP = `CookieGuard CI — Authentication Cookie Audit (${manifest.version})
Usage:
  cookieguard-ci scan URL [options]
  cookieguard-ci scan --input FILE [options]
  cookieguard-ci gate --evidence DIR --require CHECK [--require CHECK ...] [options]
  cookieguard-ci capabilities --json
  cookieguard-ci explain ID [--json]

Options:
  --auth-cookie NAME           Exact authentication-cookie name; repeatable
  --fail-on LEVEL              info|low|medium|high|critical (default: high)
  --format FORMAT              text|json (default: text)
  --json                       Same as --format json; errors are also JSON
  --output FILE                Write a sanitized report in the selected format
  --allow-origin ORIGIN        Authorize a developer-controlled nonlocal origin
  --timeout-ms NUMBER          Total HTTP deadline, 100–60000 (default: 10000)
  --allowed-samesite LIST      Comma-separated lax,strict,none (default: lax,strict)
  --require-explicit-samesite  Require a declaration where headers are observed
  --require-host-only         Forbid Domain sharing for confirmed auth cookies
  --max-lifetime-days NUMBER   Maximum remaining cookie lifetime (default: 30)
  --baseline FILE             Compare with a previous compatible JSON report
  --input FILE                JSON cookie array, legacy {cookies: [...]}, or a
                              sanitized CookieGuard/Browser Use JSON report
  --help                      Show help
  --version                   Show version

Gate options (with the policy options above):
  --evidence DIR              Directory the Playwright cookieGuard fixture wrote to
  --require CHECK             Test title (or its evidence id) that must have run
                              and passed; repeatable. Missing evidence is INCOMPLETE
  --run-id ID                 Require evidence written with COOKIEGUARD_RUN_ID=ID
  --require-session           Require session-probe evidence (CG010/CG011)
  --require-logout            Require that each test logged out (CG011 decided)

Examples (from a built checkout):
  cookieguard-ci scan http://127.0.0.1:3000/secure --auth-cookie session_id
  cookieguard-ci scan http://127.0.0.1:3000/missing-httponly --auth-cookie session_id --format json
  cookieguard-ci gate --evidence cookieguard-evidence --require "sign in and out" --auth-cookie sid

Commands:
  capabilities                Machine-readable description of checks, inputs,
                              outputs, privacy properties, and limitations
  explain ID                  Explain a rule (CG001), incomplete reason, error
                              code, or status without any cookie data

Exit codes: 0 completed/pass; 1 confirmed policy failure; 2 incomplete/invalid.
The gate decides from evidence with its own policy and ignores the test runner's result.
HTTP scanning observes headers only; it does not execute scripts or log in.
Unknown identity/evidence remains review. Loopback only unless explicitly authorized.
Do not pass credentials, tokens, URL queries, or storage-state exports.
`;

async function readJson(path) {
  let file;
  try {
    file = await open(path, constants.O_RDONLY | constants.O_NONBLOCK);
    const stat = await file.stat();
    if (!stat.isFile() || stat.size > 1024 * 1024) throw new Error();
    const buffer = Buffer.alloc(1024 * 1024 + 1);
    let bytesRead = 0;
    while (bytesRead < buffer.length) {
      const chunk = await file.read(buffer, bytesRead, buffer.length - bytesRead, bytesRead);
      if (!chunk.bytesRead) break;
      bytesRead += chunk.bytesRead;
    }
    if (bytesRead > 1024 * 1024) throw new Error();
    return JSON.parse(buffer.subarray(0, bytesRead).toString('utf8'));
  } catch { throw new AuditError('INPUT'); }
  finally { await file?.close(); }
}

export async function writeReport(path, contents) {
  const temporary = `${path}.${randomUUID()}.tmp`;
  let file;
  try {
    file = await open(temporary, 'wx', 0o600);
    await file.writeFile(contents);
    await file.close(); file = null;
    await rename(temporary, path); // Replaces symlinks, never follows them.
  } catch { throw new AuditError('OUTPUT'); }
  finally { await file?.close().catch(() => {}); await unlink(temporary).catch(() => {}); }
}

// Decide on the error format without parsing: parseArgs errors can echo input.
function wantsJson(args) {
  return args.some((arg, i) => arg === '--json' || arg === '--format=json' || (arg === '--format' && args[i + 1] === 'json'));
}

function errorJson(safe) {
  return JSON.stringify({ schemaVersion: 1, status: 'incomplete', exitCode: 2, error: { code: safe.code, message: safe.message } }, null, 2) + '\n';
}

function explanationText(entry) {
  const lines = [`${entry.id} — ${entry.title}${entry.severity ? ` (${entry.severity})` : ''}`, `Meaning: ${entry.meaning}`];
  if (entry.confirmedWhen) lines.push(`Confirmed when: ${entry.confirmedWhen}`, `Review when: ${entry.reviewWhen}`);
  if (entry.exitCode !== undefined) lines.push(`Exit code: ${entry.exitCode}`);
  if (entry.fix) lines.push(`Fix: ${entry.fix}`);
  if (entry.secureExample) lines.push(`Example: ${entry.secureExample}`);
  return lines.join('\n') + '\n';
}

function policyOf(values) {
  return validatePolicy({ authCookies: values['auth-cookie'] ?? [], failOn: values['fail-on'],
    allowedSameSite: values['allowed-samesite']?.split(','), maxLifetimeDays: values['max-lifetime-days'] === undefined ? undefined : Number(values['max-lifetime-days']),
    requireExplicitSameSite: values['require-explicit-samesite'], requireHostOnly: values['require-host-only'] });
}

async function readEvidenceFile(path) {
  try { await lstat(path); } catch (error) {
    if (error?.code === 'ENOENT') return null;
    return {};
  }
  try { return await readJson(path); } catch { return {}; }
}

async function runGate(values, positionals, format, io, onInvoked) {
  if (positionals.length !== 1 || !values.evidence || !values.require?.length || values.require.length > 100
    || ['input', 'baseline', 'allow-origin', 'timeout-ms'].some(key => values[key] !== undefined)) throw new AuditError('CONFIG');
  const runId = values['run-id'];
  if (runId !== undefined && !/^[A-Za-z0-9._-]{1,128}$/.test(runId)) throw new AuditError('CONFIG');
  const policy = policyOf(values);
  if (!policy.authCookies.length && !policy.authEvidence.length) throw new AuditError('CONFIG');
  const ids = [...new Set(values.require.map(gateCheckId))];
  onInvoked();
  const checks = [];
  for (const id of ids) {
    const input = await readEvidenceFile(join(values.evidence, `${id}.json`));
    checks.push(evaluateCheck(id, input, { policy, runId: runId ?? null,
      requireSession: values['require-session'] === true, requireLogout: values['require-logout'] === true }));
  }
  const result = gateResult(checks, policy);
  const contents = format === 'json' ? JSON.stringify(result, null, 2) + '\n' : formatGateText(result);
  if (values.output) await writeReport(values.output, contents);
  io.stdout.write(contents);
  return result.exitCode;
}

export async function runCli(args, io = { stdout: process.stdout, stderr: process.stderr }) {
  let auditInvoked = false;
  const onInvoked = () => {
    reportUsage({ package: manifest.name, version: manifest.version, integration: 'cli' });
    auditInvoked = true;
  };
  try {
    const { values, positionals } = parseArgs({ args, allowPositionals: true, strict: true, options: {
      help: { type: 'boolean' }, version: { type: 'boolean' }, json: { type: 'boolean' },
      'auth-cookie': { type: 'string', multiple: true }, 'fail-on': { type: 'string' },
      format: { type: 'string' }, output: { type: 'string' }, input: { type: 'string' }, baseline: { type: 'string' },
      'allow-origin': { type: 'string', multiple: true }, 'timeout-ms': { type: 'string' },
      'allowed-samesite': { type: 'string' }, 'max-lifetime-days': { type: 'string' },
      'require-explicit-samesite': { type: 'boolean' }, 'require-host-only': { type: 'boolean' },
      evidence: { type: 'string' }, require: { type: 'string', multiple: true }, 'run-id': { type: 'string' },
      'require-session': { type: 'boolean' }, 'require-logout': { type: 'boolean' },
    } });
    if (values.help) { io.stdout.write(HELP); return 0; }
    if (values.version) { io.stdout.write(`${manifest.version}\n`); return 0; }
    if (values.json && values.format && values.format !== 'json') throw new AuditError('CONFIG');
    const format = values.json ? 'json' : values.format ?? 'text';
    if (!['json', 'text'].includes(format)) throw new AuditError('CONFIG');
    const gateOnly = ['evidence', 'require', 'run-id', 'require-session', 'require-logout'];
    if (positionals[0] !== 'gate' && gateOnly.some(key => values[key] !== undefined)) throw new AuditError('CONFIG');
    if (positionals[0] === 'gate') return await runGate(values, positionals, format, io, onInvoked);
    const scanOnly = ['auth-cookie', 'fail-on', 'output', 'input', 'baseline', 'allow-origin', 'timeout-ms',
      'allowed-samesite', 'max-lifetime-days', 'require-explicit-samesite', 'require-host-only'];
    if (['capabilities', 'explain'].includes(positionals[0])) {
      if (scanOnly.some(key => values[key] !== undefined)) throw new AuditError('CONFIG');
      if (positionals[0] === 'capabilities') {
        if (positionals.length !== 1 || values.format === 'text') throw new AuditError('CONFIG');
        io.stdout.write(JSON.stringify(capabilities(), null, 2) + '\n');
        return 0;
      }
      const entry = positionals.length === 2 ? explain(positionals[1]) : null;
      if (!entry) throw new AuditError('CONFIG');
      io.stdout.write(format === 'json' ? JSON.stringify(entry, null, 2) + '\n' : explanationText(entry));
      return 0;
    }
    if (positionals[0] !== 'scan' || positionals.length !== (values.input ? 1 : 2)) throw new AuditError('CONFIG');
    const policy = policyOf(values);
    const timeoutMs = Number(values['timeout-ms'] ?? 10000);
    if (!Number.isInteger(timeoutMs) || timeoutMs < 100 || timeoutMs > 60000) throw new AuditError('CONFIG');
    if (values.input && values['allow-origin']) throw new AuditError('CONFIG');
    const target = values.input ? undefined : validateTarget(positionals[1], values['allow-origin']).href;
    onInvoked();
    const baseline = values.baseline ? await readJson(values.baseline) : undefined;
    let collection;
    if (values.input) {
      const input = await readJson(values.input);
      collection = isEvidenceReport(input) ? readEvidence(input)
        : { observations: Array.isArray(input) ? normalizeCookies(input) : normalizeLegacyResults(input), mode: 'fixture', complete: true };
    } else {
      collection = await scanUrl(target, { allowOrigins: values['allow-origin'], timeoutMs });
    }
    const report = evaluateCookiePolicy(collection.observations, policy, { ...collection, baseline });
    const contents = format === 'json' ? formatJson(report) : formatText(report);
    if (values.output) await writeReport(values.output, contents);
    io.stdout.write(contents);
    return exitCode(report);
  } catch (error) {
    // parseArgs errors can echo credentials; only fixed messages leave the process.
    const safe = error instanceof AuditError ? safeError(error) : new AuditError('CONFIG');
    if (wantsJson(args)) io.stdout.write(errorJson(safe));
    io.stderr.write(`CookieGuard CI: ${safe.code} — ${safe.message}\nResult: INCOMPLETE\n`);
    return 2;
  } finally {
    if (auditInvoked) await flushUsage();
  }
}
