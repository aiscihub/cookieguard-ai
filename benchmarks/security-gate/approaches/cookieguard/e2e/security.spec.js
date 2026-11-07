// Approach C: CookieGuard's Playwright fixture. The gate in CI re-checks the evidence.
import { test as base } from '@playwright/test';
import { cookieGuardFixtures } from '@aiscihub/cookieguard-playwright';
import { signIn, signOut } from './flows.js';

const test = base.extend(cookieGuardFixtures({
  origins: ['http://127.0.0.1:3000'],
  policy: { authCookies: ['sid', 'api_token'], failOn: 'medium' }, // POLICY
  sessionProbe: { url: 'http://127.0.0.1:3000/api/notes', requireLogout: true },
}));

test('sign in and out', async ({ page, cookieGuard: _audited }) => {
  // BODY-START
  await signIn(page);
  await signOut(page);
  // BODY-END
});
