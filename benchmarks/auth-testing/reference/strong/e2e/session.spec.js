// Reference suite (harness validation only): catches every seeded flaw.
import { test, expect } from '@playwright/test';

async function signIn(page) {
  await page.goto('/login');
  await page.getByLabel('Username').fill('alice');
  await page.getByLabel('Password').fill('correct-horse-battery');
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page).toHaveURL(/\/notes$/);
  await expect(page.locator('#notes li').first()).toBeVisible();
}

test('session cookie is HttpOnly', async ({ page, context }) => {
  await signIn(page);
  const sid = (await context.cookies()).find(cookie => cookie.name === 'sid');
  expect(sid?.httpOnly).toBe(true);
});

test('no cookie readable by page script grants API access', async ({ page, playwright, baseURL }) => {
  await signIn(page);
  const readable = await page.evaluate(() => document.cookie.split('; ').filter(Boolean).map(part => part.split('=')[0]));
  const jar = await page.context().cookies();
  for (const name of readable) {
    const cookie = jar.find(entry => entry.name === name);
    const api = await playwright.request.newContext({ baseURL, extraHTTPHeaders: { cookie: `${name}=${cookie.value}` } });
    const response = await api.get('/api/notes');
    expect(response.status(), `readable cookie ${name}`).toBe(401);
    await api.dispose();
  }
});
