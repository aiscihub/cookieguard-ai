// Approach A: ordinary Playwright assertions, written to keep cookie values out of failure output.
import { test, expect } from '@playwright/test';
import { signIn, signOut } from './flows.js';

const CREDENTIALS = ['sid', 'api_token'];
const PROTECTED_URL = '/api/notes';

// Only attributes reach assertion messages, never values.
const attributes = cookie => cookie && { httpOnly: cookie.httpOnly, secure: cookie.secure, sameSite: cookie.sameSite };

test('sign in and out', async ({ page, context, playwright, baseURL }) => {
  // BODY-START
  await signIn(page);
  const cookies = (await context.cookies()).filter(cookie => CREDENTIALS.includes(cookie.name));
  for (const name of CREDENTIALS) {
    const cookie = cookies.find(c => c.name === name);
    expect(cookie, `${name} must be set after sign-in`).toBeDefined();
    expect.soft(attributes(cookie), `${name} must be HttpOnly, Secure, and SameSite=Lax or Strict`)
      .toEqual({ httpOnly: true, secure: true, sameSite: expect.stringMatching(/^(Lax|Strict)$/) }); // POLICY
  }
  await signOut(page);
  // Replay the credentials from before logout: the server must reject them.
  const replay = await playwright.request.newContext({ baseURL,
    extraHTTPHeaders: { cookie: cookies.map(c => `${c.name}=${c.value}`).join('; ') } });
  try {
    const response = await replay.get(PROTECTED_URL, { maxRedirects: 0 });
    expect(response.status(), 'the session must be revoked at logout').toBe(401);
  } finally { await replay.dispose(); }
  // BODY-END
});
