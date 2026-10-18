import { parseArgs } from 'node:util';
import { constants } from 'node:fs';
import { open, rename, unlink } from 'node:fs/promises';
import { randomUUID } from 'node:crypto';
import { AuditError, safeError, normalizeCookies, normalizeLegacyResults, evaluateCookiePolicy,
  validatePolicy, formatText, formatJson, exitCode } from '@cookieguard/core';
import { scanUrl } from './scan.js';

const HELP = `CookieGuard CI — Authentication Cookie Audit (0.1.0)
Usage:
  cookieguard-ci scan URL [options]
  cookieguard-ci scan --input cookies.json [options]

Options:
  --auth-cookie NAME           Exact authentication-cookie name; repeatable
  --fail-on LEVEL              info|low|medium|high|critical (default: high)
  --format FORMAT              text|json (default: text)
  --output FILE                Write a sanitized report in the selected format
  --allow-origin ORIGIN        Authorize a developer-controlled nonlocal origin
  --timeout-ms NUMBER          Total HTTP deadline, 100–60000 (default: 10000)
  --allowed-samesite LIST      Comma-separated lax,strict,none (default: lax,strict)
  --require-explicit-samesite  Require a declaration where headers are observed
  --require-host-only         Forbid Domain sharing for confirmed auth cookies
  --max-lifetime-days NUMBER   Maximum remaining cookie lifetime (default: 30)
  --baseline FILE             Compare with a previous compatible JSON report
  --input FILE                Local JSON cookie array or legacy {cookies: [...]}
  --help                      Show help
  --version                   Show version

Examples (from a built checkout):
  cookieguard-ci scan http://127.0.0.1:3000/secure --auth-cookie session_id
  cookieguard-ci scan http://127.0.0.1:3000/missing-httponly --auth-cookie session_id --format json

Exit codes: 0 completed/pass; 1 confirmed policy failure; 2 incomplete/invalid.
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

export async function runCli(args, io = { stdout: process.stdout, stderr: process.stderr }) {
  try {
    const { values, positionals } = parseArgs({ args, allowPositionals: true, strict: true, options: {
      help: { type: 'boolean' }, version: { type: 'boolean' },
      'auth-cookie': { type: 'string', multiple: true }, 'fail-on': { type: 'string' },
      format: { type: 'string' }, output: { type: 'string' }, input: { type: 'string' }, baseline: { type: 'string' },
      'allow-origin': { type: 'string', multiple: true }, 'timeout-ms': { type: 'string' },
      'allowed-samesite': { type: 'string' }, 'max-lifetime-days': { type: 'string' },
      'require-explicit-samesite': { type: 'boolean' }, 'require-host-only': { type: 'boolean' },
    } });
    if (values.help) { io.stdout.write(HELP); return 0; }
    if (values.version) { io.stdout.write('0.1.0\n'); return 0; }
    if (positionals[0] !== 'scan' || positionals.length !== (values.input ? 1 : 2)) throw new AuditError('CONFIG');
    const format = values.format ?? 'text';
    if (!['json', 'text'].includes(format)) throw new AuditError('CONFIG');
    const policy = validatePolicy({ authCookies: values['auth-cookie'] ?? [], failOn: values['fail-on'],
      allowedSameSite: values['allowed-samesite']?.split(','), maxLifetimeDays: values['max-lifetime-days'] === undefined ? undefined : Number(values['max-lifetime-days']),
      requireExplicitSameSite: values['require-explicit-samesite'], requireHostOnly: values['require-host-only'] });
    const timeoutMs = Number(values['timeout-ms'] ?? 10000);
    if (!Number.isInteger(timeoutMs) || timeoutMs < 100 || timeoutMs > 60000) throw new AuditError('CONFIG');
    const baseline = values.baseline ? await readJson(values.baseline) : undefined;
    let collection;
    if (values.input) {
      if (values['allow-origin']) throw new AuditError('CONFIG');
      const input = await readJson(values.input);
      collection = { observations: Array.isArray(input) ? normalizeCookies(input) : normalizeLegacyResults(input), mode: 'fixture', complete: true };
    } else {
      collection = await scanUrl(positionals[1], { allowOrigins: values['allow-origin'], timeoutMs });
    }
    const report = evaluateCookiePolicy(collection.observations, policy, { ...collection, baseline });
    const contents = format === 'json' ? formatJson(report) : formatText(report);
    if (values.output) await writeReport(values.output, contents);
    io.stdout.write(contents);
    return exitCode(report);
  } catch (error) {
    // parseArgs errors can echo credentials; only fixed messages leave the process.
    const safe = error instanceof AuditError ? safeError(error) : new AuditError('CONFIG');
    io.stderr.write(`CookieGuard CI: ${safe.code} — ${safe.message}\nResult: INCOMPLETE\n`);
    return 2;
  }
}
