import { test as base, expect } from '@playwright/test';
import { cookieGuardFixtures } from '@aiscihub/cookieguard-playwright';

// 1. Configure once: the app's origin, its session cookie name, and a URL that needs a session.
const test = base.extend(cookieGuardFixtures({
  origins: ['http://127.0.0.1:3100'],
  policy: { authCookies: ['sid'], failOn: 'medium' },
  sessionProbe: { url: 'http://127.0.0.1:3100/api/me', requireLogout: true },
}));

// 2. Take `cookieGuard` in your existing login test. Nothing else changes.
test('sign in and out', async ({ page, cookieGuard: _audited }) => {
  await page.goto('/login');
  await page.getByLabel('Username').fill('demo');
  await page.getByLabel('Password').fill('demo-password');
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.getByRole('heading', { name: 'Signed in as demo' })).toBeVisible();
  await page.getByRole('button', { name: 'Sign out' }).click();
  await expect(page).toHaveURL(/\/login$/);
});
