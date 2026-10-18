import { appendFile, mkdtemp } from 'node:fs/promises';
import { join } from 'node:path';
import { scanUrl } from 'cookieguard-ci';
import { AuditError, evaluateCookiePolicy, validatePolicy, exitCode, formatJson, formatMarkdown, formatText, safeError } from '@aiscihub/cookieguard-core';
import { writeReport } from '../packages/cli/src/main.js';

const list = value => (value ?? '').split(',').map(item => item.trim()).filter(Boolean);

async function main() {
  let code = 2, json, summary;
  try {
    const policy = validatePolicy({ authCookies: list(process.env.CG_AUTH_COOKIES), failOn: process.env.CG_FAIL_ON || 'high' });
    const collection = await scanUrl(process.env.CG_TARGET, { allowOrigins: list(process.env.CG_ALLOW_ORIGINS) });
    const report = evaluateCookiePolicy(collection.observations, policy, collection);
    code = exitCode(report); json = formatJson(report); summary = formatMarkdown(report);
    process.stdout.write(formatText(report));
  } catch (error) {
    const safe = safeError(error);
    json = JSON.stringify({ schemaVersion: 1, status: 'incomplete', error: { code: safe.code, message: safe.message } }, null, 2) + '\n';
    summary = '<pre>CookieGuard CI: INCOMPLETE. Check target authorization, configuration, and application availability.</pre>\n';
    process.stdout.write(`CookieGuard CI: INCOMPLETE (${safe.code}).\n`);
  }
  if (!process.env.RUNNER_TEMP || !process.env.GITHUB_OUTPUT || !process.env.GITHUB_STEP_SUMMARY) throw new AuditError('CONFIG');
  const directory = await mkdtemp(join(process.env.RUNNER_TEMP, 'cookieguard-'));
  const path = join(directory, 'report.json');
  await writeReport(path, json);
  await appendFile(process.env.GITHUB_STEP_SUMMARY, summary, { mode: 0o600 });
  await appendFile(process.env.GITHUB_OUTPUT, `exit-code=${code}\nreport-path=${path}\n`, { mode: 0o600 });
}

try { await main(); }
catch { process.stderr.write('CookieGuard CI: unable to write action results. Audit incomplete.\n'); process.exitCode = 2; }
