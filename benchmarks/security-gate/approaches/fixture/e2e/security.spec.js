import { test } from './session-security.js';
import { signIn, signOut } from './flows.js';

test('sign in and out', async ({ page, sessionSecurity }) => {
  // BODY-START
  await signIn(page);
  await sessionSecurity.afterLogin();
  await signOut(page);
  // BODY-END
});
