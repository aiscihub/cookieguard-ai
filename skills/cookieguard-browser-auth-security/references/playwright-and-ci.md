# Playwright and CI

## Playwright

`@aiscihub/cookieguard-playwright` 0.4.0 observes `Set-Cookie` responses and the
browser cookie store of a Playwright `BrowserContext` during your existing login test.
Verified with Chromium; other browsers are untested.

```js
// tests/session-cookie.spec.js
import { test, expect } from '@playwright/test';
import { startCookieAudit, assertCookiePolicy } from '@aiscihub/cookieguard-playwright';

const ORIGIN = process.env.APP_ORIGIN ?? 'http://127.0.0.1:3000';

test('login sets a protected session cookie', async ({ context, page }) => {
  const audit = startCookieAudit(context, {
    origins: [ORIGIN],
    policy: { authCookies: ['session'], failOn: 'high' },
  });
  try {
    await page.goto(`${ORIGIN}/login`);
    await page.getByLabel('Username').fill(process.env.TEST_USER ?? 'demo');
    await page.getByLabel('Password').fill(process.env.TEST_PASSWORD ?? '');
    await page.getByRole('button', { name: 'Sign in' }).click();
    await expect(page).toHaveURL(/\/account$/);
    const report = await audit.evaluate();          // stops collection; call once
    console.log(report.status, report.findings.map(f => `${f.ruleId}:${f.status}`).join(' '));
    assertCookiePolicy(report);                     // throws on FAIL or INCOMPLETE
  } finally {
    audit.dispose();
  }
});
```

Replace the selectors, the post-login URL, and the cookie name with your application's.
Read the test password from the environment or your test secret store, never from code.

- `startCookieAudit(context, { origins, policy, timeoutMs, maxObservations })` must run
  before navigation. It observes only the listed origins and does not restrict the test's
  own network access.
- `audit.evaluate(policy?)` returns the report; `audit.dispose()` stops observing.
- For a page that is already signed in, `auditPage(page, { policy })` audits the cookie
  store only, so the original SameSite declaration stays unknown (CG009 review item).
- To keep a sanitized report, install `@aiscihub/cookieguard-core` and write
  `formatJson(report)` to a file. Never save Playwright storage state as evidence.

## CLI

`cookieguard-ci` 0.4.0 needs only Node.js 24+. It sends one GET (plus same-origin
redirects), with no cookies or authorization headers, and audits `Set-Cookie`.
It cannot log in or run JavaScript.

```bash
npx --yes cookieguard-ci@0.4.0 scan http://127.0.0.1:3000/ --auth-cookie session_id
npx --yes cookieguard-ci@0.4.0 scan http://127.0.0.1:3000/ --auth-cookie session_id --format json --output cookieguard.json
```

| Option | Effect |
| --- | --- |
| `--auth-cookie NAME` | Exact session-cookie name; repeatable. Needed to confirm failures. |
| `--fail-on LEVEL` | `info`, `low`, `medium`, `high` (default), `critical`. |
| `--format json` | Sanitized JSON report on stdout (schema: `report.schema.json`). |
| `--output FILE` | Also write the report with owner-only permissions. |
| `--allow-origin ORIGIN` | Authorize a nonlocal origin you control. Loopback needs none. |
| `--require-explicit-samesite`, `--require-host-only`, `--max-lifetime-days N`, `--allowed-samesite lax,strict` | Stricter policy. |
| `--baseline FILE` | Compare with an earlier JSON report; removed protections become CG007. |
| `--input FILE` | Audit a JSON cookie array, or re-evaluate a sanitized CookieGuard or Browser Use JSON report under this policy. |
| `--json` | Same as `--format json`; errors are JSON on stdout too. |

Exit codes: `0` PASS, `1` FAIL, `2` INCOMPLETE or error. Treat any nonzero exit
as a failed gate; never retry with a looser policy to get 0.

## Any CI system

Start the application, wait until it answers, then run the CLI and keep its exit code:

```bash
npx --yes cookieguard-ci@0.4.0 scan "$APP_URL" --auth-cookie session_id --format json --output cookieguard.json
```

## GitHub Actions

```yaml
permissions:
  contents: read
steps:
  # ...check out and start the application on the runner...
  - uses: aiscihub/cookieguard-ai/action@12a09fe322b135ac2a5aec45cae1f880b717575f # ci-v0.1.0
    with:
      target: http://127.0.0.1:3000/
      auth-cookies: session_id
      fail-on: high
```

The Action writes a Step Summary and a sanitized JSON artifact, then exits with
the audit's code. Do not pass credentials or tokens as inputs.

## Machine-readable help

`npx --yes cookieguard-ci@0.4.0 capabilities --json` prints every check, operation,
output schema, exit code, and limitation. `npx --yes cookieguard-ci@0.4.0 explain CG001 --json`
explains a rule ID, incomplete reason (such as `expected-auth-cookie-not-observed`),
error code, or status.
