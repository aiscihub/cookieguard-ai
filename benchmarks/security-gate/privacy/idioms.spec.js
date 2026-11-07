// Common ways to assert cookie security in Playwright. Each test is run alone against
// the app version in its title and is expected to fail; the runner checks whether the
// failure output prints a credential value.
import { test, expect } from '@playwright/test';
import assert from 'node:assert/strict';
import { signIn, signOut } from './flows.js';

const sidOf = async context => (await context.cookies()).find(c => c.name === 'sid');
async function signInCapturingLogin(page) {
  const login = page.waitForResponse(r => r.url().endsWith('/login') && r.request().method() === 'POST');
  await signIn(page);
  return login;
}

test('toMatchObject on the cookie object [no-httponly]', async ({ page, context }) => {
  await signIn(page);
  expect(await sidOf(context)).toMatchObject({ httpOnly: true });
});

test('toContainEqual on context.cookies() [no-httponly]', async ({ page, context }) => {
  await signIn(page);
  expect(await context.cookies()).toContainEqual(expect.objectContaining({ name: 'sid', httpOnly: true }));
});

test('toEqual objectContaining on the cookie [no-httponly]', async ({ page, context }) => {
  await signIn(page);
  expect(await sidOf(context)).toEqual(expect.objectContaining({ httpOnly: true }));
});

test('toHaveLength(0) on credentials without HttpOnly [no-httponly]', async ({ page, context }) => {
  await signIn(page);
  expect((await context.cookies()).filter(c => ['sid', 'api_token'].includes(c.name) && !c.httpOnly)).toHaveLength(0);
});

test('toBe on the flag [no-httponly]', async ({ page, context }) => {
  await signIn(page);
  expect((await sidOf(context)).httpOnly).toBe(true);
});

test('toBe on the flag with a message [no-httponly]', async ({ page, context }) => {
  await signIn(page);
  expect((await sidOf(context)).httpOnly, 'sid must be HttpOnly').toBe(true);
});

test('toContain on the Set-Cookie header [no-httponly]', async ({ page }) => {
  const login = await signInCapturingLogin(page);
  expect(await login.headerValue('set-cookie')).toContain('HttpOnly');
});

test('toMatch on the Set-Cookie header [no-httponly]', async ({ page }) => {
  const login = await signInCapturingLogin(page);
  expect((await login.allHeaders())['set-cookie']).toMatch(/sid=[^;]*;[^\n]*HttpOnly/i);
});

test('node assert.match on the Set-Cookie header [no-httponly]', async ({ page }) => {
  const login = await signInCapturingLogin(page);
  assert.match((await login.allHeaders())['set-cookie'], /sid=[^;]*;[^\n]*HttpOnly/i);
});

test('document.cookie must not contain the token [js-token]', async ({ page }) => {
  await signIn(page);
  expect(await page.evaluate(() => document.cookie)).not.toContain('api_token=');
});

test('document.cookie names only [js-token]', async ({ page }) => {
  await signIn(page);
  const names = (await page.evaluate(() => document.cookie)).split('; ').map(part => part.split('=')[0]);
  expect(names).not.toContain('api_token');
});

test('logout replay, status assertion [logout-kept]', async ({ page, context, playwright, baseURL }) => {
  await signIn(page);
  const sid = await sidOf(context);
  await signOut(page);
  const replay = await playwright.request.newContext({ baseURL, extraHTTPHeaders: { cookie: `sid=${sid.value}` } });
  expect((await replay.get('/api/notes', { maxRedirects: 0 })).status()).toBe(401);
});

test('logout replay, not.toBeOK [logout-kept]', async ({ page, context, playwright, baseURL }) => {
  await signIn(page);
  const sid = await sidOf(context);
  await signOut(page);
  const replay = await playwright.request.newContext({ baseURL, extraHTTPHeaders: { cookie: `sid=${sid.value}` } });
  await expect(await replay.get('/api/notes', { maxRedirects: 0 })).not.toBeOK();
});

test('logout replay when the request errors [replay-error]', async ({ page, context, playwright, baseURL }) => {
  await signIn(page);
  const sid = await sidOf(context);
  await signOut(page);
  const replay = await playwright.request.newContext({ baseURL, extraHTTPHeaders: { cookie: `sid=${sid.value}` } });
  expect((await replay.get('/api/notes', { maxRedirects: 0 })).status()).toBe(401);
});
