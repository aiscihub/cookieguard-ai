import { McpServer } from '@modelcontextprotocol/server';
import * as z from 'zod/v4';
import { AuditError, evaluateCookiePolicy, exitCode, formatJson, safeError } from '@aiscihub/cookieguard-core';
import { scanUrl, validateTarget } from 'cookieguard-ci';
import { validateConfig } from './config.js';
import manifest from '../package.json' with { type: 'json' };

export const VERSION = manifest.version;
const MAX_FINDINGS = 100;
const scope = [
  'HTTP response headers only: no login, JavaScript, browser attachment, or browser-acceptance check.',
  'Configuration audit only; a pass does not prove application security or validate a server session.',
  'Cookie values, response bodies, raw headers, and observed cookie names/domains/paths are not returned. Only configured authentication-cookie names are shown.',
  'The calling application must enforce the result; exposing an MCP tool does not force an agent to call it.',
];
const invalid = { error: 'Invalid CookieGuard tool arguments.' };
const findingSchema = z.object({
  cookieId: z.string(), cookieName: z.string().nullable(),
  ruleId: z.string(), severity: z.enum(['info', 'low', 'medium', 'high', 'critical']),
  status: z.enum(['confirmed', 'review']), title: z.string(), why: z.string(), fix: z.string(),
});
const resultSchema = z.object({
  schemaVersion: z.literal(1), status: z.enum(['passed', 'failed', 'incomplete']),
  exitCode: z.union([z.literal(0), z.literal(1), z.literal(2)]),
  target: z.string().nullable(), summary: z.record(z.string(), z.number()).nullable(),
  issues: z.array(z.string()), limitations: z.array(z.string()),
  findings: z.array(findingSchema), omittedFindings: z.number().int().nonnegative(),
  error: z.object({ code: z.string(), message: z.string() }).nullable(),
});

function result(structuredContent, isError = false) {
  return { content: [{ type: 'text', text: JSON.stringify(structuredContent) }], structuredContent, isError };
}

function failure(error) {
  return result({ schemaVersion: 1, status: 'incomplete', exitCode: 2,
    target: null, summary: null, issues: ['scan-not-completed'], limitations: scope,
    findings: [], omittedFindings: 0, error: { code: error.code, message: error.message } }, true);
}

function project(report, code, config) {
  const ids = new Map();
  const findings = report.findings.slice(0, MAX_FINDINGS).map(finding => {
    const key = JSON.stringify(finding.cookie);
    if (!ids.has(key)) ids.set(key, `cookie-${ids.size + 1}`);
    // Remote metadata can itself contain secrets or prompt instructions. Return
    // only names explicitly supplied by the maintainer, never arbitrary names.
    return { cookieId: ids.get(key),
      cookieName: config.policy.authCookies.includes(finding.cookie.name) ? finding.cookie.name : null,
      ruleId: finding.ruleId, severity: finding.severity, status: finding.status,
      title: finding.title, why: finding.why, fix: finding.fix };
  });
  return { schemaVersion: 1, status: report.status, exitCode: code, target: report.target,
    summary: report.summary, issues: report.issues, limitations: [...scope, ...report.limitations],
    findings, omittedFindings: report.findings.length - findings.length, error: null };
}

export function createCookieGuardServer(options) {
  const config = validateConfig(options);
  let scanning = false;
  const server = new McpServer({ name: 'cookieguard', version: VERSION }, {
    maxToolInputElements: 8,
    instructions: 'CookieGuard audits configured HTTP origins. Read cookieguard_policy for scope. Check status and exitCode; review items are not confirmed failures. Never interpret a pass as proof of application security.',
  });
  server.registerTool('cookieguard_policy', {
    description: 'Read the maintainer-configured origins, cookie policy, timeout, and HTTP-only scope. This tool cannot change them.',
    inputSchema: z.strictObject({}, invalid),
    annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false },
  }, () => result({ ...structuredClone(config), limitations: scope }));
  server.registerTool('cookieguard_scan', {
    description: 'GET a URL on a configured origin and audit Set-Cookie headers with the fixed policy. Returns passed, failed, or incomplete (exitCode 0/1/2). Makes network requests; use authorized test endpoints. No login or browser cookies are collected.',
    inputSchema: z.strictObject({ url: z.string(invalid).min(1).max(2048).describe('HTTP(S) URL on a configured origin, without credentials, query, or fragment. Do not include secrets in the path.') }, invalid),
    outputSchema: resultSchema,
    // A GET can have application side effects. Do not promise read-only behavior.
    annotations: { readOnlyHint: false, destructiveHint: true, idempotentHint: false, openWorldHint: true },
  }, async ({ url }) => {
    if (scanning) return failure({ code: 'BUSY', message: 'Another CookieGuard scan is in progress. Retry after it completes.' });
    scanning = true;
    try {
      const target = validateTarget(url, config.allowedOrigins);
      // The CLI allows arbitrary loopback by default; MCP requires an exact
      // startup allowlist even for loopback, including scheme and port.
      if (!config.allowedOrigins.includes(target.origin)) throw new AuditError('TARGET');
      const collected = await scanUrl(target.href, { allowOrigins: config.allowedOrigins, timeoutMs: config.timeoutMs });
      const report = evaluateCookiePolicy(collected.observations, config.policy, collected);
      return result(project(JSON.parse(formatJson(report)), exitCode(report), config));
    } catch (error) { return failure(safeError(error)); }
    finally { scanning = false; }
  });
  return server;
}
