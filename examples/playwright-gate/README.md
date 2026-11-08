# Fail-closed login gate for Playwright

This example adds a CookieGuard check to an existing Playwright login test, and a CI gate
that blocks the merge unless that check ran and passed. The check runs whether or not a
coding agent decides to use CookieGuard: it is part of your test setup.

> Needs `@aiscihub/cookieguard-playwright` and `cookieguard-ci` 0.3.0 or later.

## Run it

From the repository root, with Node 24 and Chromium installed
(`npx --no-install playwright install chromium`):

```bash
cd examples/playwright-gate
npx playwright test && npx cookieguard-ci gate --evidence cookieguard-evidence \
  --require "sign in and out" --auth-cookie sid --fail-on medium --require-logout
```

Both pass. Now break the app and run it again:

```bash
FLAW=httponly npx playwright test   # the session cookie loses HttpOnly
FLAW=logout npx playwright test     # logout keeps the server session alive
```

The test fails with only what blocks, and no cookie value:

```text
CookiePolicyError: CookieGuard FAIL for "sign-in-and-out" (http://127.0.0.1:3100)
  HIGH CG011 "sid": Session still valid after logout
    Observed: HttpOnly=true, Secure=true, SameSite=lax; deleted-at-logout, accepted-after-logout
    Fix: Invalidate the session on the server at logout, not only by clearing the browser cookie.
```

## Add it to your app

1. Install: `npm install --save-dev @aiscihub/cookieguard-playwright@0.3.0 cookieguard-ci@0.3.0`.
2. Extend your Playwright `test` once, as in [`login.spec.js`](login.spec.js):
   - `origins`: your test app's origin;
   - `policy.authCookies`: the exact session cookie names;
   - `sessionProbe.url`: a URL that answers 401, 403, or a redirect without a session.
3. Add `cookieGuard` to the parameters of the login test that signs in and out. The fixture
   audits the whole test, writes `cookieguard-evidence/<test-title>.json`, and fails the test
   unless the verdict is PASS.
4. In CI, run the gate after the tests, even when they fail:

   ```yaml
   - run: npx playwright test
     env: { COOKIEGUARD_RUN_ID: "${{ github.run_id }}-${{ github.run_attempt }}" }
   - if: always()
     run: >-
       npx cookieguard-ci gate --evidence cookieguard-evidence --require "sign in and out"
       --auth-cookie sid --fail-on medium --require-logout
       --run-id "${{ github.run_id }}-${{ github.run_attempt }}"
   ```

The gate decides from the evidence under the policy on its own command line. It ignores
the test runner's exit code and the policy in the test file. A required check with no fresh
evidence is INCOMPLETE (exit 2), which blocks just as FAIL (exit 1) does.

## What the gate does and does not stop

Measured in [`benchmarks/security-gate`](../../benchmarks/security-gate):

| Change made in the workspace | Plain Playwright test | CookieGuard gate |
| --- | --- | --- |
| `test.skip()`, test filtered out, or spec deleted | passes CI | blocked: INCOMPLETE |
| `test.fail()` (known failure), body in `try`/`catch` | passes CI | blocked: FAIL |
| policy in the test file weakened | passes CI | blocked: the gate uses its own policy |
| fake evidence file written with the current run ID | n/a | **passes CI** |

The gate stops a check from being dropped by accident or lazily. It does not stop a
deliberate forgery by code that can write to the workspace. Protect the parts that decide:

- **Workflow:** keep the gate command, and its policy flags, in the CI workflow file.
- **Ownership:** make the workflow file, the security spec, and `playwright.config.*`
  CODEOWNERS-reviewed, so agent-authored changes to them need human review.
- **Required check:** make the gate's job a required status check under branch protection.
- **Fresh evidence:** set `COOKIEGUARD_RUN_ID` per run and pass `--run-id`.

## Scope

- **Checks:** the configured session cookies' HttpOnly, Secure, SameSite, Domain, lifetime,
  and prefix, plus, with `sessionProbe`, session rotation at login and revocation at logout.
- **Not checked:** XSS, CSRF, or authorization logic.
- **Tested with:** Chromium and Playwright 1.64.1 only.
- **Values:** the session probe sends the session cookie only to `sessionProbe.url`, from the
  test process.
- **Your other test code** can still print cookie values. CookieGuard's own output does not.
