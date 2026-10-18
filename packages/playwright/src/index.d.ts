import type { BrowserContext, Page } from 'playwright-core';
import type { Policy, Report, Observation, EvaluateOptions } from '@cookieguard/core';
import type { OnnxClassifier } from '@cookieguard/core/onnx';
export interface AuditOptions {
  origins: string[]; policy?: Policy; timeoutMs?: number; maxObservations?: number;
  classifier?: OnnxClassifier;
}
export interface Collection { observations: Observation[]; complete: boolean; mode: 'browser'; target?: string }
export interface CookieAuditCollector {
  /** Stops observation and captures the current store once. Call after the awaited login workflow. */
  collect(): Promise<Collection>;
  /** Stops collection and evaluates the captured evidence. */
  evaluate(policy?: Policy, options?: Pick<EvaluateOptions, 'baseline'>): Promise<Report>;
  dispose(): void;
}
export function startCookieAudit(context: BrowserContext, options: AuditOptions): CookieAuditCollector;
/** Store-only audit of an already authenticated page; declaration evidence remains unknown. */
export function auditPage(page: Page, options?: Partial<AuditOptions>): Promise<Report>;
export { evaluateCookiePolicy, assertCookiePolicy } from '@cookieguard/core';
