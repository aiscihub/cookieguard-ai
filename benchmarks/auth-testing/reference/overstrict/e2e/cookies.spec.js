// Reference suite (harness validation only): flags the readable decoy cookies, so it
// fails on the fixed app and must not be credited with catching anything.
import { test, expect } from '@playwright/test';

test('every cookie is HttpOnly', async ({ page, context }) => {
  await page.goto('/login');
  await page.getByLabel('Username').fill('alice');
  await page.getByLabel('Password').fill('correct-horse-battery');
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page).toHaveURL(/\/notes$/);
  for (const cookie of await context.cookies()) expect(cookie.httpOnly, cookie.name).toBe(true);
});
