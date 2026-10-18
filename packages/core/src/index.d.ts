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
  authCookies?: string[]; authEvidence?: AuthEvidence[]; failOn?: Severity;
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
    source: Observation['source']; identityBasis: Identity['basis']; secure: boolean | null;
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
  cookies: { observation: Observation; identity: Identity }[]; findings: Finding[];
}
export interface EvaluateOptions { target?: string; mode?: Report['mode']; complete?: boolean; baseline?: unknown }
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
