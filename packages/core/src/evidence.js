import { AuditError, limitArray, originOf } from './safety.js';
import { cleanObservation } from './normalize.js';

const modes = ['http', 'browser', 'fixture'];

/** True for a sanitized CookieGuard core report or a cookieguard-browser-use result. */
export function isEvidenceReport(input) {
  return Boolean(input && typeof input === 'object' && !Array.isArray(input) && input.schemaVersion === 1
    && (input.integration === 'cookieguard-browser-use'
      || (modes.includes(input.mode) && Array.isArray(input.cookies) && Array.isArray(input.issues))));
}

/**
 * Rebuilds value-free observations from a previously written CookieGuard report
 * so they can be evaluated again under the caller's own policy. Every observation
 * is reconstructed field by field; unknown fields, including any cookie value,
 * are dropped. Provisional or incomplete collections stay incomplete.
 */
export function readEvidence(input) {
  try {
    let report = input, producer = 'cookieguard-report', provisional = false;
    if (input?.integration === 'cookieguard-browser-use') {
      if (input.schemaVersion !== 1 || typeof input.provisional !== 'boolean') throw new Error();
      producer = 'cookieguard-browser-use'; provisional = input.provisional; report = input.report;
    }
    if (!report || typeof report !== 'object' || report.schemaVersion !== 1 || !modes.includes(report.mode)
      || !Array.isArray(report.issues) || report.issues.length > 20) throw new Error();
    const observations = limitArray(report.cookies).map(entry => cleanObservation(entry?.observation));
    const target = report.target === null || report.target === undefined ? null : originOf(report.target);
    const complete = !provisional && !report.issues.includes('collection-incomplete');
    return { observations, mode: report.mode, target, complete, supplied: true, producer };
  } catch { throw new AuditError('INPUT'); }
}
