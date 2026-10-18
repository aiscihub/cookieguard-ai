import { test, expect } from '@playwright/test';
import { startCookieAudit, auditPage, assertCookiePolicy } from '@cookieguard/playwright';
import { formatJson, exitCode } from '@cookieguard/core';

const origins = ['http://127.0.0.1:3000'];
const policy = { authCookies: ['session_id'] };

test('A: audit an existing login workflow', async ({ context, page }) => {
  const audit = startCookieAudit(context, { origins, policy });
  try {
    await page.goto('/login');
    // Replace this fixture link with your existing sign-in steps and assertions.
    await page.getByRole('link', { name: 'Create secure demo session' }).click();
    await expect(page).toHaveURL(/\/secure$/);
    const report = await audit.evaluate();
    assertCookiePolicy(report);
    expect(report.cookies[0].observation.sameSite.declared).toBe('lax');
    expect(report.cookies[0].observation.storeStatus).toBe('present');
    expect(formatJson(report)).not.toContain('COOKIEGUARD_DEMO_SENTINEL_4e29bc7f');
  } finally { audit.dispose(); }
});

for (const [path, rule] of [['missing-httponly', 'CG001'], ['missing-secure', 'CG002']]) {
  test(`confirmed failure: ${path}`, async ({ context, page }) => {
    const audit = startCookieAudit(context, { origins, policy });
    await page.goto(`/${path}`);
    const report = await audit.evaluate();
    expect(exitCode(report)).toBe(1);
    expect(report.findings.some(f => f.ruleId === rule && f.status === 'confirmed')).toBe(true);
    expect(() => assertCookiePolicy(report)).toThrow('confirmed cookie policy violations');
  });
}

test('D/E: preference and unknown roles do not cause confirmed failures', async ({ context, page }) => {
  const audit = startCookieAudit(context, { origins });
  await page.goto('/preference');
  await page.goto('/unknown');
  const report = await audit.evaluate();
  expect(exitCode(report)).toBe(0);
  expect(report.summary.confirmedViolations).toBe(0);
  expect(report.findings.some(f => f.ruleId === 'CG008')).toBe(true);
});

test('F: already authenticated context preserves unknown declarations', async ({ page }) => {
  await page.goto('/secure');
  const report = await auditPage(page, { policy });
  expect(exitCode(report)).toBe(0);
  expect(report.cookies[0].observation.sameSite.declared).toBe('unknown');
  expect(report.cookies[0].observation.sameSite.effective).toBe('lax');
  expect(report.findings.some(f => f.ruleId === 'CG009')).toBe(true);
});

test('browser default is distinguished from a missing declaration', async ({ context, page }) => {
  const audit = startCookieAudit(context, { origins, policy });
  await page.goto('/default-samesite');
  const report = await audit.evaluate();
  expect(report.cookies[0].observation.sameSite.declared).toBe('absent');
  expect(report.cookies[0].observation.sameSite.effective).toBe('lax');
});

test('invalid prefix header remains evidence even when Chromium rejects it', async ({ context, page }) => {
  const audit = startCookieAudit(context, { origins, policy: { authCookies: ['__Host-session_id'] } });
  await page.goto('/rejected-prefix');
  const report = await audit.evaluate();
  expect((await context.cookies()).some(c => c.name === '__Host-session_id')).toBe(false);
  expect(report.cookies[0].observation.storeStatus).toBe('not-observed');
  expect(report.findings.some(f => f.ruleId === 'CG006')).toBe(true);
});

test('SameSite=None without Secure is not described as an accepted browser cookie', async ({ context, page }) => {
  const audit = startCookieAudit(context, { origins, policy });
  await page.goto('/rejected-none');
  const report = await audit.evaluate();
  expect((await context.cookies()).some(c => c.name === 'session_id')).toBe(false);
  expect(report.cookies[0].observation.storeStatus).toBe('not-observed');
  expect(report.findings.some(f => f.ruleId === 'CG009')).toBe(true);
});
