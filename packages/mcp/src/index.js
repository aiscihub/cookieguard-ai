import { constants } from 'node:fs';
import { open } from 'node:fs/promises';
import { join } from 'node:path';
import { McpServer } from '@modelcontextprotocol/server';
import * as z from 'zod/v4';
import { AuditError, evaluateCookiePolicy, exitCode, explain, formatJson, readEvidence, safeError, EXPLAIN_IDS } from '@aiscihub/cookieguard-core';
import { capabilities, scanUrl, validateTarget } from 'cookieguard-ci';
import { validateConfig } from './config.js';
import { mcpAuditResultSchema, mcpCapabilitiesSchema, mcpExplainResultSchema } from './schemas.js';
import manifest from '../package.json' with { type: 'json' };

export const VERSION = manifest.version;
const MAX_FINDINGS = 100;
const MAX_EVIDENCE_BYTES = 1024 * 1024;
const EVIDENCE_NAME = /^[A-Za-z0-9][A-Za-z0-9._-]{0,122}\.json$/;
const scope = [
  'HTTP response headers only: no login, JavaScript, browser attachment, or browser-acceptance check.',
  'Configuration audit only; a pass does not prove application security or validate a server session.',
  'Cookie values, response bodies, raw headers, and observed cookie names/domains/paths are not returned. Only configured authentication-cookie names are shown.',
  'The calling application must enforce the result; exposing an MCP tool does not force an agent to call it.',
];
const evidenceScope = [
  'Supplied evidence: the server did not observe this collection and cannot verify who wrote the file.',
  'Configuration audit only; a pass does not prove application security or validate a server session.',
  'Cookie values and observed cookie names/domains/paths are not returned. Only configured authentication-cookie names are shown.',
  'The calling application must enforce the result; exposing an MCP tool does not force an agent to call it.',
];
const TOOLS = [
  { name: 'cookieguard_capabilities', use: 'Read what CookieGuard checks, this server\'s fixed configuration, result semantics, and limits.' },
  { name: 'cookieguard_audit', use: 'Audit one allowed URL ({"url"}) or one sanitized evidence file ({"evidenceFile"}).' },
  { name: 'cookieguard_explain', use: 'Explain a rule ID, incomplete reason, error code, or status.' },
  { name: 'cookieguard_policy', use: 'Read the configured origins and policy (kept for 0.1.0 clients).' },
  { name: 'cookieguard_scan', use: 'Audit one allowed URL (kept for 0.1.0 clients; same as cookieguard_audit with url).' },
];
const invalid = { error: 'Invalid CookieGuard tool arguments.' };

function result(structuredContent, isError = false) {
  return { content: [{ type: 'text', text: JSON.stringify(structuredContent) }], structuredContent, isError };
}

function failure(error, limitations = scope) {
  return result({ schemaVersion: 1, status: 'incomplete', exitCode: 2,
    target: null, summary: null, issues: ['scan-not-completed'], limitations,
    findings: [], omittedFindings: 0, provenance: null, error: { code: error.code, message: error.message } }, true);
}

function project(report, code, config, provenance, limitations) {
  const ids = new Map();
  const findings = report.findings.slice(0, MAX_FINDINGS).map(finding => {
    const key = JSON.stringify(finding.cookie);
    if (!ids.has(key)) ids.set(key, `cookie-${ids.size + 1}`);
    // Remote metadata can itself contain secrets or prompt instructions. Return
    // only names explicitly supplied by the maintainer, never arbitrary names.
    return { cookieId: ids.get(key),
      cookieName: config.policy.authCookies.includes(finding.cookie.name) ? finding.cookie.name : null,
      ruleId: finding.ruleId, severity: finding.severity, status: finding.status,
      title: finding.title, why: finding.why, fix: finding.fix,
      evidenceSource: finding.evidence.source, identityBasis: finding.evidence.identityBasis };
  });
  return { schemaVersion: 1, status: report.status, exitCode: code, target: report.target,
    summary: report.summary, issues: report.issues, limitations: [...limitations, ...report.limitations],
    findings, omittedFindings: report.findings.length - findings.length, provenance, error: null };
}

async function readEvidenceFile(directory, name) {
  if (!directory || typeof name !== 'string' || !EVIDENCE_NAME.test(name) || name.includes('..')) throw new AuditError('EVIDENCE');
  let file;
  try {
    // The directory was resolved at startup and the name has no separators;
    // O_NOFOLLOW refuses a symlink planted in its place.
    file = await open(join(directory, name), constants.O_RDONLY | constants.O_NOFOLLOW | constants.O_NONBLOCK);
  } catch { throw new AuditError('EVIDENCE'); }
  try {
    const info = await file.stat();
    if (!info.isFile()) throw new AuditError('EVIDENCE');
    if (info.size > MAX_EVIDENCE_BYTES) throw new AuditError('INPUT');
    const buffer = Buffer.alloc(MAX_EVIDENCE_BYTES + 1);
    let length = 0;
    while (length < buffer.length) {
      const { bytesRead } = await file.read(buffer, length, buffer.length - length, null);
      if (!bytesRead) break;
      length += bytesRead;
    }
    if (length > MAX_EVIDENCE_BYTES) throw new AuditError('INPUT');
    return JSON.parse(buffer.subarray(0, length).toString('utf8'));
  } catch (error) { throw error instanceof AuditError ? error : new AuditError('INPUT'); }
  finally { await file.close(); }
}

export function createCookieGuardServer(options) {
  const config = validateConfig(options);
  let busy = false;
  const server = new McpServer({ name: 'cookieguard', version: VERSION }, {
    maxToolInputElements: 8,
    instructions: 'CookieGuard audits authentication-cookie configuration for origins the maintainer configured. Start with cookieguard_capabilities. Use cookieguard_audit for one allowed URL or one sanitized evidence file, and cookieguard_explain for rule IDs and error codes. Check isError, status, and exitCode; review items are not confirmed failures and INCOMPLETE is never a pass. Never interpret a pass as proof of application security.',
  });

  const guarded = async (run, limitations = scope) => {
    if (busy) return failure({ code: 'BUSY', message: 'Another CookieGuard audit is in progress. Retry after it completes.' }, limitations);
    busy = true;
    try { return await run(); }
    catch (error) { return failure(safeError(error), limitations); }
    finally { busy = false; }
  };
  const scan = url => guarded(async () => {
    const target = validateTarget(url, config.allowedOrigins);
    // The CLI allows arbitrary loopback by default; MCP requires an exact
    // startup allowlist even for loopback, including scheme and port.
    if (!config.allowedOrigins.includes(target.origin)) throw new AuditError('TARGET');
    const collected = await scanUrl(target.href, { allowOrigins: config.allowedOrigins, timeoutMs: config.timeoutMs });
    const report = evaluateCookiePolicy(collected.observations, config.policy, collected);
    return result(project(JSON.parse(formatJson(report)), exitCode(report), config,
      { source: 'http-scan', producer: 'cookieguard-http-scan', observedByServer: true }, scope));
  });
  const auditEvidence = name => guarded(async () => {
    const evidence = readEvidence(await readEvidenceFile(config.evidenceDir, name));
    // Evidence stays within the same authorization scope as live scans.
    const origins = [evidence.target, ...evidence.observations.map(observation => observation.origin)].filter(Boolean);
    if (origins.some(origin => !config.allowedOrigins.includes(origin))) throw new AuditError('TARGET');
    const report = evaluateCookiePolicy(evidence.observations, config.policy, evidence);
    return result(project(JSON.parse(formatJson(report)), exitCode(report), config,
      { source: 'evidence-file', producer: evidence.producer, observedByServer: false }, evidenceScope));
  }, evidenceScope);

  server.registerTool('cookieguard_capabilities', {
    description: 'Describe CookieGuard: the cookie checks it runs, this server\'s fixed origins and policy, result and exit-code semantics, integrations for authenticated browser workflows, privacy properties, and limitations. Takes no arguments and makes no network requests.',
    inputSchema: z.strictObject({}, invalid),
    outputSchema: mcpCapabilitiesSchema,
    annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false },
  }, () => {
    const document = capabilities();
    return result({ schemaVersion: 1, server: { name: 'cookieguard', version: VERSION },
      configuration: { allowedOrigins: [...config.allowedOrigins], policy: structuredClone(config.policy),
        timeoutMs: config.timeoutMs, evidenceFiles: config.evidenceDir !== null },
      tools: TOOLS, checks: document.checks.map(({ ruleId, title, severity }) => ({ ruleId, title, severity })),
      results: { statuses: document.results.statuses, findingStatuses: document.results.findingStatuses },
      integrations: document.integrations.map(({ id, package: name, version, install, documentation }) =>
        ({ id, package: name, version, install, documentation })),
      privacy: document.privacy, authorization: document.authorization,
      evidenceRequirements: document.evidenceRequirements, limitations: document.limitations,
      capabilitiesUrl: document.tool.capabilitiesUrl });
  });
  server.registerTool('cookieguard_audit', {
    description: 'Audit authentication-cookie configuration with the fixed startup policy. Pass exactly one of: url (GET one URL on a configured origin and audit its Set-Cookie headers; makes network requests, sends no cookies or credentials) or evidenceFile (re-evaluate a sanitized CookieGuard JSON report that your own Browser Use, Playwright, or CLI run wrote to the configured evidence directory). Returns passed, failed, or incomplete (exitCode 0/1/2) with rule IDs and fixes, never cookie values.',
    inputSchema: z.strictObject({
      url: z.string(invalid).min(1).max(2048).optional().describe('HTTP(S) URL on a configured origin, without credentials, query, or fragment. Do not include secrets in the path.'),
      evidenceFile: z.string(invalid).min(6).max(128).optional().describe('Plain file name such as login-report.json inside the configured evidence directory. No paths.'),
    }, invalid),
    outputSchema: mcpAuditResultSchema,
    // A GET can have application side effects. Do not promise read-only behavior.
    annotations: { readOnlyHint: false, destructiveHint: true, idempotentHint: false, openWorldHint: true },
  }, async ({ url, evidenceFile }) => {
    if ((url === undefined) === (evidenceFile === undefined)) {
      return failure({ code: 'CONFIG', message: 'Pass exactly one of url or evidenceFile.' });
    }
    return url !== undefined ? scan(url) : auditEvidence(evidenceFile);
  });
  server.registerTool('cookieguard_explain', {
    description: 'Explain a CookieGuard rule ID (CG001-CG009), incomplete reason, error code, or status (passed/failed/incomplete): what it means, when it is confirmed versus review, and how to fix it. Static text only; no network or cookie data.',
    inputSchema: z.strictObject({ id: z.string(invalid).min(1).max(64).regex(/^[A-Za-z0-9_-]+$/, invalid).describe('For example CG001, expected-auth-cookie-not-observed, TARGET, or incomplete.') }, invalid),
    outputSchema: mcpExplainResultSchema,
    annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false },
  }, ({ id }) => {
    const explanation = explain(id);
    // Unknown identifiers are not reflected back.
    return result({ schemaVersion: 1, explanation, knownIds: [...EXPLAIN_IDS],
      error: explanation ? null : { code: 'UNKNOWN_ID', message: 'Unknown identifier. Use one of knownIds.' } }, !explanation);
  });
  server.registerTool('cookieguard_policy', {
    description: 'Read the maintainer-configured origins, cookie policy, timeout, and HTTP-only scope. This tool cannot change them.',
    inputSchema: z.strictObject({}, invalid),
    annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false },
  }, () => result({ ...structuredClone(config), limitations: scope }));
  server.registerTool('cookieguard_scan', {
    description: 'GET a URL on a configured origin and audit Set-Cookie headers with the fixed policy. Returns passed, failed, or incomplete (exitCode 0/1/2). Makes network requests; use authorized test endpoints. No login or browser cookies are collected. Same as cookieguard_audit with url.',
    inputSchema: z.strictObject({ url: z.string(invalid).min(1).max(2048).describe('HTTP(S) URL on a configured origin, without credentials, query, or fragment. Do not include secrets in the path.') }, invalid),
    outputSchema: mcpAuditResultSchema,
    annotations: { readOnlyHint: false, destructiveHint: true, idempotentHint: false, openWorldHint: true },
  }, ({ url }) => scan(url));
  return server;
}
