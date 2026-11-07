export type Severity = 'info' | 'low' | 'medium' | 'high' | 'critical';
export type SameSite = 'lax' | 'strict' | 'none';
export interface CookieInput {
  name: string; value?: string; domain?: string; path?: string;
  secure?: boolean; httpOnly?: boolean; sameSite?: string; hostOnly?: boolean;
  expires?: number; expirationDate?: number;
}
export interface Triage {
  mode: 'rule' | 'onnx'; label: 'authentication' | 'tracking' | 'preference' | 'other';
  /** Uncalibrated triage score, never identity confirmation. */
  score: number; origin: 'extension-rule-heuristic' | 'extension-onnx-uncalibrated';
}
export interface Observation {
  schemaVersion: 1; name: string; domain: string; path: string;
  secure: boolean | null; httpOnly: boolean | null; hostOnly: boolean | null;
  sameSite: { declared: SameSite | 'absent' | 'invalid' | 'unknown'; effective: SameSite | null };
  expiresAt: number | null; lifetimeSeconds: number | null; deleted: boolean;
  source: 'header' | 'browser' | 'fixture' | 'legacy'; origin: string | null;
  confidence: 'observed' | 'uncertain';
  header: { prefixValid: boolean | null; scheme: 'http' | 'https'; warnings: string[] } | null;
  storeStatus: 'present' | 'not-observed' | 'unverified'; triage: Triage;
}
export interface NormalizeOptions {
  source?: 'browser' | 'fixture' | 'legacy'; origin?: string; now?: number; triage?: Triage;
}
export interface AuthEvidence {
  name: string; domain: string; path: string; origin: string;
  /** Caller attests the server uses this scoped cookie for the validated session. */
  validation: 'server-session-validated';
}
export interface Policy {
  authCookies?: string[]; authEvidence?: AuthEvidence[];
  /** Exact localStorage or sessionStorage keys that hold the application's own authentication token (CG012). */
  authStorageKeys?: string[]; failOn?: Severity;
  allowedSameSite?: SameSite[]; requireExplicitSameSite?: boolean;
  requireHostOnly?: boolean; maxLifetimeDays?: number;
}
export interface Identity {
  status: 'confirmed' | 'candidate' | 'unknown' | 'non-auth-candidate';
  basis: 'developer-name' | 'validated-auth-flow' | Triage['origin'];
}
export interface Finding {
  ruleId: string; severity: Severity; status: 'confirmed' | 'review';
  cookie: Pick<Observation, 'name' | 'domain' | 'path' | 'origin'>;
  title: string; why: string; fix: string;
  evidence: {
    /** probe: session replay (CG010, CG011); storage: Web Storage entry (CG012), whose key is in cookie.name. */
    source: Observation['source'] | 'probe' | 'storage'; identityBasis: Identity['basis']; secure: boolean | null;
    httpOnly: boolean | null; hostOnly: boolean | null;
    declaredSameSite: Observation['sameSite']['declared']; effectiveSameSite: SameSite | null;
    remainingLifetimeDays: number | null; storeStatus: Observation['storeStatus'];
    headerWarnings: string[]; changes: string[];
  };
}
export interface Report {
  schemaVersion: 1; toolVersion: string; mode: 'http' | 'browser' | 'fixture'; target: string | null;
  status: 'passed' | 'failed' | 'incomplete'; classificationModes: Triage['mode'][];
  policy: Required<Policy>;
  summary: { cookies: number; observations: number; confirmedAuth: number; candidateAuth: number;
    unknownIdentity: number; confirmedViolations: number; failures: number; reviewItems: number };
  issues: string[]; limitations: string[];
  comparison: { status: 'not-requested' | 'not-comparable' | 'comparable'; comparedCookies: number };
  session: SessionSummary | null; storage: StorageObservation[];
  cookies: { observation: Observation; identity: Identity }[]; findings: Finding[];
}
export interface SessionSummary {
  probe: { url: string; anonymousStatus: number | null; status: 'ok' | 'inconclusive';
    reason: 'probe-error' | 'unprotected-url' | 'probe-limit' | 'no-authenticated-state' | null;
    probes: number; requireLogout: boolean };
  cookies: (Pick<Observation, 'name' | 'domain' | 'path'> & { origin: string;
    rotation: 'rotated' | 'not-rotated' | 'inconclusive';
    logout: 'not-observed' | 'revoked' | 'still-valid' | 'inconclusive' })[];
}
export interface StorageObservation {
  schemaVersion: 1; origin: string; area: 'local' | 'session'; key: string;
  token: 'jwt' | 'token-in-json' | 'token-key' | 'configured'; configured: boolean;
}
type ProbeCookie = Pick<Observation, 'name' | 'domain' | 'path'> & { origin: string };
type ProbeResult = { status: number; location: string | null } | { error: true };
/** Value-free session timeline reported by an adapter; values appear only as opaque ids such as "v1". */
export interface SessionTimeline {
  url: string; anonymous: ProbeResult; truncated?: boolean; requireLogout?: boolean;
  events: ({ type: 'issued'; cookie: ProbeCookie; valueId: string; method: string | null }
    | { type: 'deleted'; cookie: ProbeCookie; valueId: string }
    | { type: 'probe'; phase: 'issued' | 'navigation' | 'final' | 'replay'; values: { cookie: ProbeCookie; valueId: string }[]; result: ProbeResult })[];
}
export function summarizeSession(timeline: SessionTimeline): SessionSummary;
export function cleanSession(input: unknown): SessionSummary | null;
export function probeUrl(url: string, origins: string[]): string;
export function probeLocation(location: string | null | undefined, base: string): string | null;
export function classifyStorageEntry(key: string, value: string): 'jwt' | 'token-in-json' | 'token-key' | null;
export function storageObservation(entry: { origin: string; area: 'local' | 'session'; key: string; value: string }, policy?: Policy): StorageObservation | null;
export function safeStorageKey(key: string, value?: string): string;
export interface EvaluateOptions {
  target?: string; mode?: Report['mode']; complete?: boolean; baseline?: unknown;
  /** Value-free session summary from summarizeSession (CG010, CG011). */
  session?: SessionSummary | null;
  /** Value-free Web Storage observations from storageObservation (CG012). */
  storage?: StorageObservation[];
  /** Adds a limitation stating that the evidence came from a supplied file. */
  supplied?: boolean;
}
export class AuditError extends Error { readonly code: string; constructor(code?: string) }
export function safeError(error: unknown): AuditError;
export function normalizeCookie(input: CookieInput, options?: NormalizeOptions): Observation;
export function normalizeCookies(inputs: CookieInput[], options?: NormalizeOptions): Observation[];
export function normalizeLegacyResults(input: unknown, options?: NormalizeOptions): Observation[];
export function parseSetCookie(header: string, responseUrl: string, options?: Pick<NormalizeOptions, 'now' | 'triage'>): Observation;
export function classifyCookie(input: CookieInput): Triage;
export function extractCookieFeatures(input: CookieInput): Record<string, number>;
export const FEATURE_NAMES: readonly string[];
export const RULES: Readonly<Record<string, { title: string; severity: Severity; why: string; fix: string }>>;
export function validatePolicy(policy?: Policy): Required<Policy>;
export function evaluateCookiePolicy(observations: Observation[], policy?: Policy, options?: EvaluateOptions): Report;
/** Renderers and decision helpers require the original report returned by evaluateCookiePolicy. */
export function formatText(report: Report): string;
export function formatJson(report: Report): string;
export function formatMarkdown(report: Report): string;
export function exitCode(report: Report): 0 | 1 | 2;
export function assertCookiePolicy(report: Report): void;
export interface Evidence {
  observations: Observation[]; mode: Report['mode']; target: string | null; complete: boolean;
  supplied: true; producer: 'cookieguard-report' | 'cookieguard-browser-use';
  session: SessionSummary | null; storage: StorageObservation[];
}
/** True for a sanitized CookieGuard report or a cookieguard-browser-use result. */
export function isEvidenceReport(input: unknown): boolean;
/** Rebuilds value-free observations from a sanitized report for re-evaluation. Throws AuditError('INPUT'). */
export function readEvidence(input: unknown): Evidence;
export interface Explanation {
  id: string; kind: 'rule' | 'issue' | 'error' | 'status'; title: string; meaning: string;
  fix?: string; severity?: Severity; confirmedWhen?: string; reviewWhen?: string; secureExample?: string;
  status?: Report['status']; label?: string; exitCode?: 0 | 1 | 2;
}
export interface RuleEntry {
  ruleId: string; title: string; severity: Severity; checks: string;
  confirmedWhen: string; reviewWhen: string; why: string; fix: string;
}
/** Static explanation of a rule ID, incomplete reason, error code, or status; null if unknown. */
export function explain(id: string): Explanation | null;
export function ruleCatalog(): RuleEntry[];
export function statusCatalog(): { status: Report['status']; label: 'PASS' | 'FAIL' | 'INCOMPLETE'; exitCode: 0 | 1 | 2; meaning: string }[];
export const EXPLAIN_IDS: readonly string[];
export const ERROR_CODES: readonly string[];
export const ISSUE_CODES: readonly string[];
