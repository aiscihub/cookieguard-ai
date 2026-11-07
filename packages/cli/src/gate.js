import { AuditError, evaluateCookiePolicy, readEvidence } from '@aiscihub/cookieguard-core';

// The gate decides the security verdict from evidence files alone, under its own policy.
// It does not read the test runner's exit code or the policy the test was written with,
// and it requires positive evidence: a required check without a fresh, valid evidence
// file is INCOMPLETE, so skipping, filtering, or deleting the check cannot pass.

export const EVIDENCE_INTEGRATION = 'cookieguard-playwright-check';
const ID = /^[a-z0-9][a-z0-9-]{0,119}$/;

export function gateCheckId(value) {
  const id = String(value).toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 120);
  if (!ID.test(id)) throw new AuditError('CONFIG');
  return id;
}

const incomplete = (id, issue) => ({ id, status: 'incomplete', issues: [issue], findings: [], session: null });

/**
 * Evaluates one required check. `input` is the parsed evidence file, or null when it is missing.
 * Options: policy (validated), runId (string or null), requireSession, requireLogout.
 */
export function evaluateCheck(id, input, options) {
  if (input === null) return incomplete(id, 'evidence-missing');
  if (!input || typeof input !== 'object' || input.schemaVersion !== 1 || input.integration !== EVIDENCE_INTEGRATION
    || input.check !== id) return incomplete(id, 'evidence-invalid');
  if (options.runId && input.runId !== options.runId) return incomplete(id, 'evidence-stale');
  let collection;
  try { collection = readEvidence(input.report); } catch { return incomplete(id, 'evidence-invalid'); }
  const extra = [];
  if ((options.requireSession || options.requireLogout) && !collection.session) extra.push('session-check-not-run');
  // The gate, not the test, decides whether a logout was required.
  if (options.requireLogout && collection.session) collection.session.probe.requireLogout = true;
  const report = evaluateCookiePolicy(collection.observations, options.policy, collection);
  const issues = [...report.issues, ...extra];
  // A confirmed violation is FAIL even when other evidence was inconclusive.
  const status = report.summary.failures ? 'failed' : issues.length ? 'incomplete' : 'passed';
  return { id, status, issues,
    findings: report.findings.map(f => ({ ruleId: f.ruleId, severity: f.severity, status: f.status, cookie: f.cookie.name,
      title: f.title, fix: f.fix })),
    session: report.session ? report.session.cookies.map(c => ({ cookie: c.name, rotation: c.rotation, logout: c.logout })) : null,
    limitations: report.limitations };
}

/** Combines checks: FAIL if any check confirmed a violation, else INCOMPLETE if any is incomplete, else PASS. */
export function gateResult(checks, policy) {
  if (!checks.length) throw new AuditError('CONFIG');
  const status = checks.some(c => c.status === 'failed') ? 'failed' : checks.some(c => c.status === 'incomplete') ? 'incomplete' : 'passed';
  return { schemaVersion: 1, kind: 'cookieguard-gate', status, exitCode: status === 'failed' ? 1 : status === 'incomplete' ? 2 : 0,
    policy, checks };
}

const REASONS = {
  'evidence-missing': 'no evidence file: the check did not run (skipped, filtered out, renamed, or deleted)',
  'evidence-invalid': 'the evidence file is not valid CookieGuard check evidence',
  'evidence-stale': 'the evidence file is from a different run',
  'session-check-not-run': 'the gate requires session checks, but the test ran without a session probe',
};

export function formatGateText(result) {
  const lines = [`CookieGuard gate — ${result.checks.length} required check${result.checks.length === 1 ? '' : 's'}`];
  for (const check of result.checks) {
    lines.push('', `[${check.status === 'passed' ? 'PASS' : check.status === 'failed' ? 'FAIL' : 'INCOMPLETE'}] ${check.id}`);
    for (const f of check.findings.filter(f => f.status === 'confirmed')) {
      lines.push(`  ${f.severity.toUpperCase()} ${f.ruleId} — ${JSON.stringify(f.cookie)}: ${f.title}`, `    Fix: ${f.fix}`);
    }
    for (const c of check.session ?? []) lines.push(`  Session ${JSON.stringify(c.cookie)}: rotation ${c.rotation}; logout ${c.logout}`);
    for (const issue of check.issues) lines.push(`  Incomplete: ${issue}${REASONS[issue] ? ` — ${REASONS[issue]}` : ''}`);
  }
  lines.push('', `Result: ${result.status === 'passed' ? 'PASS' : result.status === 'failed' ? 'FAIL' : 'INCOMPLETE'}`,
    'Exit codes: 0 PASS; 1 FAIL (confirmed violation); 2 INCOMPLETE (missing or inconclusive evidence). Both 1 and 2 block.');
  return lines.join('\n') + '\n';
}
