import { test as base, expect } from '@playwright/test';
import { startCookieAudit, assertCookiePolicy } from '@aiscihub/cookieguard-playwright';
import { createDemoServer } from '../demo/server.js';
import { setTimeout as pause } from 'node:timers/promises';

// A test-owned server keeps both demos isolated, including on assertion failure.
const test = base.extend({
  browserDemo: [false, { option: true }],
  baseURL: async ({ browserDemo }, use, testInfo) => {
    const server = createDemoServer({ insecureLogin: testInfo.project.name === 'insecure-login', browserDemo });
    try {
      await new Promise((resolve, reject) => server.once('error', reject).listen(0, '127.0.0.1', resolve));
      await use(`http://127.0.0.1:${server.address().port}`);
    } finally {
      server.closeAllConnections();
      if (server.listening) await new Promise(resolve => server.close(resolve));
    }
  },
});

test('successful login meets the cookie policy', async ({ context, page, baseURL, browserDemo }, testInfo) => {
  const insecure = testInfo.project.name === 'insecure-login';
  const audit = startCookieAudit(context, {
    origins: [baseURL], policy: { authCookies: ['session_id'] },
  });
  try {
    if (browserDemo) {
      // The demonstration's application requests cannot leave its fixture origin.
      await context.route('**/*', route => new URL(route.request().url()).origin === baseURL
        ? route.continue() : route.abort());
      await page.bringToFront();
    }
    // Reuse the actual link-based login from examples/playwright/login.spec.js.
    await page.goto('/login');
    const login = page.getByRole('link', {
      name: browserDemo ? 'Create demo session' : insecure ? 'Create insecure demo session' : 'Create secure demo session',
    });
    await expect(login).toBeVisible();
    if (browserDemo) {
      // These pauses are for recording only; awaited UI assertions determine readiness.
      await pause(2000);
      await login.hover();
      await pause(1000);
    }
    await login.click();
    await expect(page).toHaveURL(new URL(browserDemo ? '/account' : insecure ? '/missing-httponly' : '/secure', baseURL).href);
    if (browserDemo) {
      await expect(page.getByRole('heading', { name: 'Login succeeded.' })).toBeVisible();
      console.log('Login succeeded: /login → /session → /account (server accepted the session cookie).');
      await pause(2000);
    }

    const report = await audit.evaluate();
    const sessionPresent = report.cookies.some(({ observation, identity }) =>
      observation.name === 'session_id' && observation.storeStatus === 'present' && identity.status === 'confirmed');
    expect(sessionPresent, 'The login must create the identified authentication cookie in the browser.').toBe(true);
    console.log(browserDemo ? 'Authentication cookie observed: session_id (confirmed identity).'
      : 'Login succeeded. Authentication cookie is present in the browser.');
    for (const finding of report.findings.filter(finding => finding.status === 'confirmed')) {
      console.log(`${browserDemo ? 'CookieGuard: ' : ''}${finding.ruleId} — ${finding.title}`);
    }
    if (browserDemo) await pause(2000);

    // This is deliberately unwrapped: an insecure cookie must fail Playwright.
    assertCookiePolicy(report);
    console.log(browserDemo ? 'CookieGuard: policy passed' : 'Cookie policy passed.');
  } finally {
    audit.dispose();
    // Keep the real authenticated page visible briefly, including on policy failure.
    if (browserDemo) await pause(2000);
  }
});
