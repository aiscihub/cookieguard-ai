# Example: auditing a Browser Use agent's login

**User request:** "Check whether the session cookie our Browser Use agent gets at login
is protected."

## What the agent does

An illustrative walkthrough; the output below is from a real run.

1. **Detect.** `requirements.txt` pins `browser-use`, the login handler sets a cookie
   named `session_id`, and `python3.12` and Node.js 24+ are available.
2. **Install, after telling the user.** Run `python3.12 -m venv .venv` and
   `.venv/bin/pip install cookieguard==0.2.0` as a test dependency.
3. **Audit.** Wrap the existing agent run with `CookieGuardAudit(allowed_origins=[...],
   auth_cookies=['session_id'])`, starting collection before the login and calling
   `finish()` afterwards. The password stays in Browser Use `sensitive_data`.
4. **Interpret** the engine's result, shown next.
5. **Report** without any cookie value.

## CookieGuard output

This is the output of the demo (`python -m cookieguard.browser_use.demo` since 0.2.0), insecure
scenario, recorded with the `cookieguard-browser-use` 0.1.0 wheel from PyPI, the same engine
and code that `cookieguard` 0.2.0 ships, Browser Use 0.13.14, Python 3.12, and
Node.js 26 on macOS. A real Browser Use `Agent`, driven by a scripted stand-in for the
model, signed in through a real browser while CookieGuard observed it:

```text
CookieGuard CI — Authentication Cookie Audit
Target: http://127.0.0.1:61978
Mode: browser; classification: rule
Cookies inspected: 1 (1 observations)
Authentication cookies: 1 confirmed, 0 candidate, 0 unknown
Findings:
HIGH CG001 — "session_id": Missing HttpOnly
  Fix: Set HttpOnly on the authentication cookie at the server.
Result: FAILED — 1 confirmed violations at or above high
Scope: Configuration audit only; no exploit or server-session validation is performed.
Scope: Rule and ONNX classification are uncalibrated triage; only developer evidence confirms authentication identity.
CookieGuard for Browser Use: FAIL (exit code 1); evidence: server-declarations-and-browser-store
```

The output names the configured cookie but contains no value.

## The report the agent returns

```markdown
## Browser session cookie audit

**Overall:** FAIL (CookieGuard 0.1.0 engine)

**Environment:** Browser Use 0.13.14, Chromium-family browser, macOS; integration: Browser Use
**Scope:** origin http://127.0.0.1:61978; authentication cookie `session_id`; policy failOn=high,
allowedSameSite=lax,strict, maxLifetimeDays=30; workflow: the agent's form login

**Checks executed:** CG001-CG009 on 1 observed cookie, with Set-Cookie header and browser-store evidence.
**Not executed:** none for this workflow.

| Rule | Severity | Status | Cookie | Evidence | Fix |
| --- | --- | --- | --- | --- | --- |
| CG001 | high | confirmed | session_id | Set-Cookie without HttpOnly | Set HttpOnly on the session cookie in the login handler |

**Limitations:** configuration audit only. JavaScript could read this cookie if script
execution were compromised; this audit does not show that an XSS exists. CSRF and server-side
session handling were not tested.
```

In the demo's secure scenario, which sets HttpOnly, the same run reported
`CookieGuard for Browser Use: PASS (exit code 0)` with "No observed policy violations."

## Same check in Playwright

The [Playwright example](../references/playwright-and-ci.md#playwright), run unchanged
against a form login that set `session=...; Path=/; SameSite=Lax; Max-Age=2592000`,
logged `failed CG001:confirmed CG002:confirmed`. The test failed with `CookiePolicyError`.
After adding `Secure; HttpOnly`, it logged `passed` and the test passed.
