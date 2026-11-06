import * as z from 'zod/v4';
import { EXPLAIN_IDS, ERROR_CODES, ISSUE_CODES, RULES } from '@aiscihub/cookieguard-core';

// Single source of truth for CookieGuard's machine-readable output. The MCP
// server enforces these at runtime; scripts/build-schemas.js publishes them as
// JSON Schema under schemas/, and tests validate CLI and MCP output against them.
const severity = z.enum(['info', 'low', 'medium', 'high', 'critical']);
const sameSite = z.enum(['lax', 'strict', 'none']);
const status = z.enum(['passed', 'failed', 'incomplete']);
const exitCode = z.union([z.literal(0), z.literal(1), z.literal(2)]);
const ruleId = z.enum(Object.keys(RULES));
const evidenceSource = z.enum(['header', 'browser', 'fixture', 'legacy']);
const identityBasis = z.enum(['developer-name', 'validated-auth-flow', 'extension-rule-heuristic', 'extension-onnx-uncalibrated']);
const count = z.number().int().nonnegative();
const error = z.strictObject({ code: z.string(), message: z.string() });

const observation = z.strictObject({
  schemaVersion: z.literal(1), name: z.string(), domain: z.string(), path: z.string(),
  secure: z.boolean().nullable(), httpOnly: z.boolean().nullable(), hostOnly: z.boolean().nullable(),
  sameSite: z.strictObject({ declared: z.enum(['strict', 'lax', 'none', 'absent', 'invalid', 'unknown']), effective: sameSite.nullable() }),
  expiresAt: z.number().nullable(), lifetimeSeconds: z.number().nullable(), deleted: z.boolean(),
  source: evidenceSource, origin: z.string().nullable(), confidence: z.enum(['observed', 'uncertain']),
  header: z.strictObject({ prefixValid: z.boolean().nullable(), scheme: z.enum(['http', 'https']), warnings: z.array(z.string()) }).nullable(),
  storeStatus: z.enum(['present', 'not-observed', 'unverified']),
  triage: z.strictObject({ mode: z.enum(['rule', 'onnx']), label: z.enum(['authentication', 'tracking', 'preference', 'other']),
    score: z.number().min(0).max(1), origin: z.enum(['extension-rule-heuristic', 'extension-onnx-uncalibrated']) }),
});

/** A CookieGuard core report: CLI `--format json`, Playwright, Action artifact, and Browser Use `report`. */
export const reportSchema = z.strictObject({
  schemaVersion: z.literal(1), toolVersion: z.string(), mode: z.enum(['http', 'browser', 'fixture']),
  target: z.string().nullable(), status, classificationModes: z.array(z.enum(['rule', 'onnx'])),
  policy: z.strictObject({
    authCookies: z.array(z.string()), failOn: severity, allowedSameSite: z.array(sameSite), maxLifetimeDays: z.number(),
    requireExplicitSameSite: z.boolean(), requireHostOnly: z.boolean(),
    authEvidence: z.array(z.strictObject({ name: z.string(), domain: z.string(), path: z.string(), origin: z.string(),
      validation: z.literal('server-session-validated') })),
  }),
  summary: z.strictObject({ cookies: count, observations: count, confirmedAuth: count, candidateAuth: count,
    unknownIdentity: count, confirmedViolations: count, failures: count, reviewItems: count }),
  issues: z.array(z.enum(ISSUE_CODES)), limitations: z.array(z.string()),
  comparison: z.strictObject({ status: z.enum(['not-requested', 'not-comparable', 'comparable']), comparedCookies: count }),
  cookies: z.array(z.strictObject({ observation, identity: z.strictObject({
    status: z.enum(['confirmed', 'candidate', 'unknown', 'non-auth-candidate']), basis: identityBasis }) })),
  findings: z.array(z.strictObject({
    ruleId, severity, status: z.enum(['confirmed', 'review']), title: z.string(), why: z.string(), fix: z.string(),
    cookie: z.strictObject({ name: z.string(), domain: z.string(), path: z.string(), origin: z.string().nullable() }),
    evidence: z.strictObject({ source: evidenceSource, identityBasis, secure: z.boolean().nullable(), httpOnly: z.boolean().nullable(),
      hostOnly: z.boolean().nullable(), declaredSameSite: z.enum(['strict', 'lax', 'none', 'absent', 'invalid', 'unknown']),
      effectiveSameSite: sameSite.nullable(), remainingLifetimeDays: z.number().nullable(),
      storeStatus: z.enum(['present', 'not-observed', 'unverified']), headerWarnings: z.array(z.string()), changes: z.array(z.string()) }),
  })),
});

/** MCP finding: value-free, and cookie names only when they are configured authentication cookies. */
export const mcpFindingSchema = z.object({
  cookieId: z.string(), cookieName: z.string().nullable(), ruleId: z.string(), severity,
  status: z.enum(['confirmed', 'review']).describe('confirmed: observed policy violation; review: heuristic or uncertain, never fails'),
  title: z.string(), why: z.string(), fix: z.string(),
  evidenceSource: evidenceSource.optional().describe('header = server Set-Cookie declaration; browser = cookie-store observation'),
  identityBasis: identityBasis.optional().describe('Why the cookie is treated as authentication: developer evidence or uncalibrated heuristics'),
});

/** Result of cookieguard_scan and cookieguard_audit. */
export const mcpAuditResultSchema = z.object({
  schemaVersion: z.literal(1), status, exitCode,
  target: z.string().nullable(), summary: z.record(z.string(), z.number()).nullable(),
  issues: z.array(z.string()), limitations: z.array(z.string()),
  findings: z.array(mcpFindingSchema), omittedFindings: count,
  provenance: z.object({ source: z.enum(['http-scan', 'evidence-file']),
    producer: z.enum(['cookieguard-http-scan', 'cookieguard-report', 'cookieguard-browser-use']),
    observedByServer: z.boolean().describe('false when the evidence was collected elsewhere and supplied as a file') }).nullable().optional(),
  error: error.nullable(),
});

export const explanationSchema = z.strictObject({
  id: z.enum(EXPLAIN_IDS), kind: z.enum(['rule', 'issue', 'error', 'status']), title: z.string(), meaning: z.string(),
  fix: z.string().optional(), severity: severity.optional(), confirmedWhen: z.string().optional(), reviewWhen: z.string().optional(),
  secureExample: z.string().optional(), status: status.optional(), label: z.enum(['PASS', 'FAIL', 'INCOMPLETE']).optional(),
  exitCode: exitCode.optional(),
});

export const mcpExplainResultSchema = z.object({
  schemaVersion: z.literal(1), explanation: explanationSchema.nullable(), knownIds: z.array(z.string()), error: error.nullable(),
});

/** `cookieguard-ci ... --json` output when the command cannot complete. */
export const cliErrorSchema = z.strictObject({
  schemaVersion: z.literal(1), status: z.literal('incomplete'), exitCode: z.literal(2),
  error: z.strictObject({ code: z.enum(ERROR_CODES), message: z.string() }),
});

const integration = z.strictObject({
  id: z.string(), kind: z.enum(['python-package', 'npm-package', 'github-action', 'mcp-server', 'agent-skill']),
  registry: z.enum(['pypi', 'npm']).optional(), package: z.string(), version: z.string(),
  mcpRegistryName: z.string().optional(), transport: z.literal('stdio').optional(),
  install: z.string(), entryPoint: z.string(), requires: z.array(z.string()), tested: z.array(z.string()), documentation: z.url(),
});

/** `cookieguard-ci capabilities --json` and cookieguard.capabilities.json. */
export const capabilitiesSchema = z.strictObject({
  $schema: z.url(), schemaVersion: z.literal(1),
  tool: z.strictObject({ id: z.literal('cookieguard'), name: z.string(), version: z.string(), license: z.string(),
    repository: z.url(), documentation: z.url(), capabilitiesUrl: z.url() }),
  summary: z.string(), useWhen: z.array(z.string()), doNotUseWhen: z.array(z.string()),
  integrations: z.array(integration),
  operations: z.array(z.strictObject({ id: z.string(), availability: z.enum(['released', 'unreleased']),
    surfaces: z.array(z.string()), description: z.string(), inputs: z.array(z.string()), permissions: z.array(z.string()),
    evidence: z.array(z.string()), network: z.string() })),
  checks: z.array(z.strictObject({ ruleId, title: z.string(), severity, checks: z.string(),
    confirmedWhen: z.string(), reviewWhen: z.string(), fix: z.string() })),
  results: z.strictObject({
    statuses: z.array(z.strictObject({ status, label: z.enum(['PASS', 'FAIL', 'INCOMPLETE']), exitCode, meaning: z.string() })),
    failOnLevels: z.array(severity), defaultFailOn: severity,
    findingStatuses: z.array(z.strictObject({ status: z.enum(['confirmed', 'review']), meaning: z.string() })),
    evidenceSources: z.array(z.strictObject({ source: evidenceSource, category: z.string(), meaning: z.string() })),
    identityBases: z.array(identityBasis), issueCodes: z.array(z.string()), errorCodes: z.array(z.string()),
    schemas: z.record(z.string(), z.url()), exitCodes: z.record(z.string(), z.string()),
  }),
  privacy: z.array(z.string()), authorization: z.array(z.string()),
  evidenceRequirements: z.array(z.string()), limitations: z.array(z.string()),
});

/** Result of the cookieguard_capabilities MCP tool. */
export const mcpCapabilitiesSchema = z.object({
  schemaVersion: z.literal(1), server: z.object({ name: z.string(), version: z.string() }),
  configuration: z.object({ allowedOrigins: z.array(z.string()), policy: z.record(z.string(), z.unknown()),
    timeoutMs: z.number(), evidenceFiles: z.boolean() }),
  tools: z.array(z.object({ name: z.string(), use: z.string() })),
  checks: z.array(z.object({ ruleId: z.string(), title: z.string(), severity })),
  results: z.object({ statuses: z.array(z.object({ status, label: z.string(), exitCode, meaning: z.string() })),
    findingStatuses: z.array(z.object({ status: z.string(), meaning: z.string() })) }),
  integrations: z.array(z.object({ id: z.string(), package: z.string(), version: z.string(), install: z.string(), documentation: z.string() })),
  privacy: z.array(z.string()), authorization: z.array(z.string()), evidenceRequirements: z.array(z.string()),
  limitations: z.array(z.string()), capabilitiesUrl: z.string(),
});

export const PUBLISHED_SCHEMAS = Object.freeze({
  'capabilities.schema.json': capabilitiesSchema,
  'report.schema.json': reportSchema,
  'mcp-audit-result.schema.json': mcpAuditResultSchema,
  'explanation.schema.json': explanationSchema,
  'cli-error.schema.json': cliErrorSchema,
});
