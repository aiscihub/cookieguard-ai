// Approach B: a small reusable fixture without CookieGuard. A login test that takes
// `sessionSecurity` calls afterLogin() once signed in. When the test ends, the fixture
// checks the credential cookies, replays them after logout, writes a verdict file for
// ci/security-gate.mjs, and fails the test unless the verdict is PASS.
import { test as base } from '@playwright/test';
import { mkdirSync, writeFileSync } from 'node:fs';

const CREDENTIALS = ['sid', 'api_token'];
const PROTECTED_URL = '/api/notes';
const RESULTS_DIR = 'security-results';
export const slug = title => title.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');

export const test = base.extend({
  sessionSecurity: async ({ context, playwright, baseURL }, use, testInfo) => {
    let snapshot = null;
    await use({ afterLogin: async () => { snapshot = (await context.cookies()).filter(c => CREDENTIALS.includes(c.name)); } });
    const failures = [], missing = [];
    if (!snapshot) missing.push('afterLogin() was not reached');
    for (const name of snapshot ? CREDENTIALS : []) {
      const cookie = snapshot.find(c => c.name === name);
      if (!cookie) { missing.push(`${name} was not set`); continue; }
      if (!cookie.httpOnly) failures.push(`${name}: missing HttpOnly`); // POLICY
      if (!cookie.secure) failures.push(`${name}: missing Secure`);
      if (!['Lax', 'Strict'].includes(cookie.sameSite)) failures.push(`${name}: SameSite=${cookie.sameSite}`);
    }
    if (snapshot && !missing.length) {
      if ((await context.cookies()).some(c => CREDENTIALS.includes(c.name))) missing.push('logout was not observed');
      else {
        const replay = await playwright.request.newContext({ baseURL,
          extraHTTPHeaders: { cookie: snapshot.map(c => `${c.name}=${c.value}`).join('; ') } });
        // Errors are reduced to a fixed message: Playwright's call log would print the Cookie header.
        try { if ((await replay.get(PROTECTED_URL, { maxRedirects: 0 })).status() < 400) failures.push('session still valid after logout'); }
        catch { missing.push('the logout replay request failed'); }
        finally { await replay.dispose(); }
      }
    }
    const status = failures.length ? 'FAIL' : missing.length ? 'INCOMPLETE' : 'PASS';
    mkdirSync(RESULTS_DIR, { recursive: true });
    writeFileSync(`${RESULTS_DIR}/${slug(testInfo.title)}.json`, JSON.stringify({ status, failures, missing }, null, 2));
    if (status !== 'PASS') throw new Error(`Session security ${status}: ${[...failures, ...missing].join('; ')}`);
  },
});
