import type { BrowserContext, Page } from 'playwright-core';
import type { Policy, Report, Observation, EvaluateOptions, SessionSummary, StorageObservation } from '@aiscihub/cookieguard-core';
import type { OnnxClassifier } from '@aiscihub/cookieguard-core/onnx';
export interface SessionProbeOptions {
  /** A protected URL on an allowed origin: 401, 403, or a redirect for anonymous requests; 2xx when authenticated. */
  url: string;
  /** Report INCOMPLETE unless the workflow logs out (CG011 needs a logout to judge). */
  requireLogout?: boolean; maxProbes?: number; timeoutMs?: number;
}
export interface AuditOptions {
  origins: string[]; policy?: Policy; timeoutMs?: number; maxObservations?: number;
  classifier?: OnnxClassifier;
  /** Content-free invocation reporting. Enabled by default; false or environment opt-outs disable it. Null follows the default/environment setting. */
  usageMetrics?: boolean | null;
  /** Opt-in: replay the configured authentication cookies to one protected URL to check rotation (CG010) and logout (CG011). */
  sessionProbe?: SessionProbeOptions;
  /** Read localStorage and sessionStorage of allowed origins for tokens (CG012). Default true. */
  storage?: boolean;
}
export interface Collection {
  observations: Observation[]; complete: boolean; mode: 'browser'; target?: string;
  session: SessionSummary | null; storage: StorageObservation[];
}
export interface CookieAuditCollector {
  /** Stops observation and captures the current store once. Call after the awaited login workflow. */
  collect(policy?: Policy): Promise<Collection>;
  /** Stops collection and evaluates the captured evidence. */
  evaluate(policy?: Policy, options?: Pick<EvaluateOptions, 'baseline'>): Promise<Report>;
  dispose(): void;
}
export function startCookieAudit(context: BrowserContext, options: AuditOptions): CookieAuditCollector;
/** Store-only audit of an already authenticated page; declaration evidence remains unknown. */
export function auditPage(page: Page, options?: Partial<AuditOptions>): Promise<Report>;
export interface GateOptions extends AuditOptions {
  /** Where evidence files are written. Default: $COOKIEGUARD_EVIDENCE_DIR, else ./cookieguard-evidence. */
  evidenceDir?: string;
  /** Fail the test unless the verdict is PASS. Default true. The gate enforces the verdict either way. */
  enforce?: boolean;
}
export interface CookieGuardCheck {
  /** The evidence id: the test title in lower case, other characters as `-`. */
  id: string;
  /** Stops collection and evaluates now; the fixture otherwise evaluates when the test ends. */
  evaluate(): Promise<Report>;
}
/** Fixtures for `test.extend()`: a test that takes `cookieGuard` is audited and writes evidence for `cookieguard-ci gate`. */
export function cookieGuardFixtures(options: GateOptions): {
  cookieGuard: (args: { context: BrowserContext }, use: (check: CookieGuardCheck) => Promise<void>, testInfo: { title: string }) => Promise<void>;
};
export function checkId(title: string): string;
export const EVIDENCE_INTEGRATION: 'cookieguard-playwright-check';
export { evaluateCookiePolicy, assertCookiePolicy } from '@aiscihub/cookieguard-core';
