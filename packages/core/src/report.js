import { trustedReport } from './policy.js';

export function formatJson(report) {
  return JSON.stringify(trustedReport(report), null, 2) + '\n';
}

export function formatText(report) {
  const r = trustedReport(report);
  const lines = ['CookieGuard CI — Authentication Cookie Audit',
    `Target: ${r.target ?? 'local fixture'}`, `Mode: ${r.mode}; classification: ${r.classificationModes.join(', ') || 'none'}`,
    `Cookies inspected: ${r.summary.cookies} (${r.summary.observations} observations)`,
    `Authentication cookies: ${r.summary.confirmedAuth} confirmed, ${r.summary.candidateAuth} candidate, ${r.summary.unknownIdentity} unknown`, '', 'Findings:'];
  for (const f of r.findings) {
    lines.push(`${f.status === 'review' ? 'REVIEW' : f.severity.toUpperCase()} ${f.ruleId} — ${JSON.stringify(f.cookie.name)}: ${f.title}`);
    lines.push(`  Fix: ${f.fix}`);
  }
  if (!r.findings.length) lines.push('No observed policy violations.');
  lines.push('', `Result: ${r.status.toUpperCase()} — ${r.summary.failures} confirmed violations at or above ${r.policy.failOn}`);
  for (const issue of r.issues) lines.push(`Incomplete: ${issue}`);
  for (const limitation of r.limitations) lines.push(`Scope: ${limitation}`);
  return lines.join('\n') + '\n';
}

export function formatMarkdown(report) {
  // HTML escaping prevents cookie names from injecting markup or closing the block.
  const escaped = formatText(report).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;');
  return `<pre>${escaped}</pre>\n`;
}
