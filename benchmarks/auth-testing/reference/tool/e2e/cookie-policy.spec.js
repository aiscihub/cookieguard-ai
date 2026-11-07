// Reference suite (harness validation only, informational): the published Playwright
// integration with the developer's configuration, as the Agent Skill shows it.
import { test, expect } from '@playwright/test';
import { startCookieAudit, assertCookiePolicy } from '@aiscihub/cookieguard-playwright';

test('authentication cookies meet the policy', async ({ page, context }) => {
  const audit = startCookieAudit(context, {
    origins: ['http://127.0.0.1:3000'],
    policy: { authCookies: ['sid', 'api_token'], failOn: 'high' },
  });
  try {
    await page.goto('/login');
    await page.getByLabel('Username').fill('alice');
    await page.getByLabel('Password').fill('correct-horse-battery');
    await page.getByRole('button', { name: 'Sign in' }).click();
    await expect(page.locator('#notes li').first()).toBeVisible();
    assertCookiePolicy(await audit.evaluate());
  } finally {
    audit.dispose();
  }
});
