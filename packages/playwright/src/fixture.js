import { mkdir, open, rename, unlink } from 'node:fs/promises';
import { join, resolve } from 'node:path';
import { randomUUID } from 'node:crypto';
import { AuditError, formatJson, exitCode, explain } from '@aiscihub/cookieguard-core';
import { startCookieAudit } from './index.js';

export const EVIDENCE_INTEGRATION = 'cookieguard-playwright-check';

/** The evidence file name for a check: its test title in lower case, with runs of other characters as `-`. */
export function checkId(title) {
  const id = String(title).toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 120);
  if (!id) throw new AuditError('CONFIG');
  return id;
}

function runId() {
  const value = process.env.COOKIEGUARD_RUN_ID;
  return typeof value === 'string' && /^[A-Za-z0-9._-]{1,128}$/.test(value) ? value : null;
}

async function writeEvidence(dir, id, contents) {
  try { await mkdir(dir, { recursive: true }); } catch { throw new AuditError('OUTPUT'); }
  const path = join(dir, `${id}.json`);
  const temporary = `${path}.${randomUUID()}.tmp`;
  let file;
  try {
    file = await open(temporary, 'wx', 0o600);
    await file.writeFile(contents);
    await file.close(); file = null;
    await rename(temporary, path); // Replaces symlinks, never follows them.
  } catch { throw new AuditError('OUTPUT'); }
  finally { await file?.close().catch(() => {}); await unlink(temporary).catch(() => {}); }
}

const LEVELS = ['info', 'low', 'medium', 'high', 'critical'];

/**
 * The failure message a test runner (and a coding agent reading it) sees: only what blocks,
 * with the fix. Review items are counted, not listed, so they are not mistaken for required
 * changes. Every field comes from the value-free report.
 */
export function failureMessage(id, report) {
  const blocking = report.findings.filter(f => f.status === 'confirmed' && LEVELS.indexOf(f.severity) >= LEVELS.indexOf(report.policy.failOn));
  const lines = [`CookieGuard ${blocking.length ? 'FAIL' : 'INCOMPLETE'} for "${id}" (${report.target ?? 'browser'})`];
  for (const f of blocking) {
    const e = f.evidence;
    lines.push(`  ${f.severity.toUpperCase()} ${f.ruleId} ${JSON.stringify(f.cookie.name)}: ${f.title}`,
      `    Observed: HttpOnly=${e.httpOnly}, Secure=${e.secure}, SameSite=${e.declaredSameSite}${e.changes?.length ? `; ${e.changes.join(', ')}` : ''}`,
      `    Fix: ${f.fix}`);
  }
  for (const issue of report.issues) lines.push(`  Incomplete: ${issue} — ${explain(issue)?.meaning ?? ''}`, `    Fix: ${explain(issue)?.fix ?? ''}`);
  for (const c of report.session?.cookies ?? []) lines.push(`  Session ${JSON.stringify(c.name)}: rotation ${c.rotation}; logout ${c.logout}`);
  const review = report.findings.filter(f => f.status === 'review').length;
  if (review) lines.push(`  Not shown: ${review} review item${review === 1 ? '' : 's'}, which do not block and need no change to pass.`);
  lines.push(`  Explain a rule: npx cookieguard-ci explain ${blocking[0]?.ruleId ?? report.issues[0] ?? 'CG001'}`);
  return lines.join('\n');
}

/**
 * Playwright fixtures for a login test. Every test that takes `cookieGuard` is audited
 * from before its first navigation to its end, whether or not it calls anything on the
 * fixture. At the end, the fixture writes value-free evidence for `cookieguard-ci gate`
 * and fails the test unless the verdict is PASS. A test that is skipped, filtered out, or
 * deleted writes no evidence, so a gate that requires it reports INCOMPLETE.
 *
 *   export const test = base.extend(cookieGuardFixtures({ origins, policy, sessionProbe }));
 *   test('sign in', async ({ page, cookieGuard }) => { ...your existing login steps... });
 */
export function cookieGuardFixtures(options = {}) {
  if (!options || typeof options !== 'object' || Array.isArray(options)) throw new AuditError('CONFIG');
  const { evidenceDir, enforce = true, ...auditOptions } = options;
  if (typeof enforce !== 'boolean' || (evidenceDir !== undefined && (typeof evidenceDir !== 'string' || !evidenceDir))) throw new AuditError('CONFIG');
  return {
    cookieGuard: async ({ context }, use, testInfo) => {
      const id = checkId(testInfo.title);
      const audit = startCookieAudit(context, auditOptions);
      let reportPromise;
      const evaluate = () => (reportPromise ??= audit.evaluate());
      try {
        await use({ id, evaluate });
        const report = await evaluate();
        const dir = resolve(evidenceDir ?? process.env.COOKIEGUARD_EVIDENCE_DIR ?? 'cookieguard-evidence');
        const evidence = { schemaVersion: 1, integration: EVIDENCE_INTEGRATION, check: id, runId: runId(),
          status: report.status, report: JSON.parse(formatJson(report)) };
        await writeEvidence(dir, id, JSON.stringify(evidence, null, 2) + '\n');
        const code = exitCode(report);
        if (enforce && code) {
          // Rule IDs, cookie names, flags and fixes from the value-free report; never values.
          const error = new Error(failureMessage(id, report));
          error.name = 'CookiePolicyError';
          error.exitCode = code;
          error.stack = `${error.name}: ${error.message}`;
          throw error;
        }
      } finally { audit.dispose(); }
    },
  };
}
