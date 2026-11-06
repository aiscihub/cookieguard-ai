---
name: cookieguard-browser-auth-security
description: Audit authentication-cookie security in AI browser automation, Browser Use agents, Playwright tests, and CI pipelines with CookieGuard, which checks session cookies for missing HttpOnly or Secure, SameSite policy, Domain scope, lifetime, and __Host-/__Secure- prefix problems and returns PASS, FAIL, or INCOMPLETE findings with fixes, without exposing cookie values to the agent. Use when asked to check whether login cookies are protected, assess session-cookie risk in a Browser Use or Playwright workflow, add authentication-security checks to browser automation or CI, or produce a browser session security report for an application the user owns or is authorized to test.
license: MIT
compatibility: Needs Node.js 24+. Browser Use also needs Python 3.11-3.13, browser-use 0.13.x, and Chrome or Chromium. Installing needs network access to PyPI or npm.
metadata:
  title: CookieGuard AI — Browser Agent Authentication Security Audit
  project: https://github.com/aiscihub/cookieguard-ai
  packages: cookieguard-browser-use 0.1.0 (PyPI); cookieguard-ci, @aiscihub/cookieguard-playwright, @aiscihub/cookieguard-mcp 0.2.0 (npm)
---

# CookieGuard AI — Browser Agent Authentication Security Audit

CookieGuard audits how an application *configures* its authentication cookies. It
observes `Set-Cookie` headers and browser cookie-store metadata during an authorized
workflow, never cookie values, and its local engine decides **PASS / FAIL / INCOMPLETE**
with rule IDs `CG001`-`CG009` and fixes. The agent's own judgment is not the verdict.

## When to use it

- "Audit my browser agent's authentication security" or "check whether login cookies are protected."
- Adding a session-cookie check to a **Browser Use** agent, a **Playwright** test, or a **CI** job.
- Reviewing `HttpOnly`, `Secure`, `SameSite`, `Domain`, lifetime, or `__Host-` settings of a login.
- Producing a browser session security report for the user's own application.

## When not to use it

- The target is a site the user does not own or is not authorized to test.
- The question is about XSS, CSRF, injection, exploitability, or server-side session
  handling (expiry, revocation, fixation). CookieGuard checks cookie attributes only.
- Authentication does not use cookies (bearer tokens in headers or `localStorage`, API keys).
- The environment is unsupported: Windows, Browser Use cloud browsers, Browser Use outside
  0.13.x, or non-Chromium browsers (untested). Say so instead of guessing.
- The user wants cookie values extracted, exported, or replayed. Decline.

## Trust boundary

| Party | Holds | Sees |
| --- | --- | --- |
| The agent (you) | Code, commands, CookieGuard results | Metadata only: rule IDs, flags, configured cookie names, origins |
| Browser automation (Browser Use, Playwright) in the user's test process | The real session cookies | Everything the browser sees |
| CookieGuard collector and local Node engine, in the same process tree | Raw values only transiently, to parse attributes, redact, and triage | Keeps no values in observations; outputs are value-free, and Browser Use refuses to return a result containing an observed value |

CookieGuard keeps values out of its own output. It cannot stop *other* commands from
exposing them: `curl -i` against a login, printing `document.cookie`, or saving Playwright
storage state all put a real token in front of the model. Results you read may be sent to
your model provider, and running locally does not make them confidential.

## Workflow

### A. Detect the environment

1. Find the integration: `browser-use` in `requirements*.txt` or `pyproject.toml`,
   `@playwright/test` in `package.json`, CI files such as `.github/workflows/*.yml`.
2. Find the exact session-cookie name in server code (the `Set-Cookie` call or session
   settings such as `SESSION_COOKIE_NAME` or express-session `name`) and the request that
   sets it. Ask the user if unsure: without the exact name, findings stay `review` and the
   audit cannot FAIL.
3. Check prerequisites: `node --version` (24+), `python3 --version` (3.11-3.13 for Browser
   Use), and whether CookieGuard is already installed (`python -m pip show
   cookieguard-browser-use`, `npm ls @aiscihub/cookieguard-playwright cookieguard-ci`).
4. Pick the pathway:

| Situation | Use | Details |
| --- | --- | --- |
| A Browser Use agent signs in | `cookieguard-browser-use` | [Browser Use](references/browser-use.md) |
| Playwright tests sign in | `@aiscihub/cookieguard-playwright` | [Playwright and CI](references/playwright-and-ci.md) |
| A GET response sets the cookie, or a CI smoke check | `cookieguard-ci` CLI or GitHub Action | [Playwright and CI](references/playwright-and-ci.md) |
| An MCP client should run audits | `@aiscihub/cookieguard-mcp` | [MCP](references/mcp.md) |

HTTP header scans send one GET and cannot submit a login form. If the cookie appears only
after signing in, use Browser Use or Playwright.

### B. Install, with the user's agreement

Tell the user which package you will add and where, then install it as a test or
development dependency: Python packages in a virtualenv, npm packages with `--save-dev`.
Do not install globally or change unrelated dependencies.

```bash
python3.12 -m venv .venv && .venv/bin/pip install cookieguard-browser-use==0.1.0
npm install --save-dev @aiscihub/cookieguard-playwright@0.2.0
npx --yes cookieguard-ci@0.2.0 --version
```

Version requirements and verification: [installation](references/installation.md).

### C. Run the audit

Start collection **before** the login and enforce the result after the workflow.
Pass credentials only through the framework's secret mechanism (Browser Use
`sensitive_data`), never in prompts, task text, or logs.

**Browser Use**

```python
from browser_use import Agent, BrowserProfile, BrowserSession
from cookieguard_browser_use import CookieGuardAudit

audit = CookieGuardAudit(allowed_origins=['http://127.0.0.1:3000'], auth_cookies=['session_id'])
session = BrowserSession(browser_profile=BrowserProfile(
    keep_alive=True, enable_default_extensions=False,
    allowed_domains=audit.browser_allowed_domains()))
await session.start()
await audit.start(session)                  # before the login
agent = Agent(task=..., llm=..., browser_session=session,
              sensitive_data={'http://127.0.0.1': {'login_password': '...'}})
await agent.run()
result = await audit.finish()               # decided by the CookieGuard engine
await session.kill()
result.write_json('cookieguard-result.json')  # sanitized, owner-only file
result.assert_policy()                      # raises CookiePolicyError on FAIL or INCOMPLETE
```

**Playwright**

```js
import { startCookieAudit, assertCookiePolicy } from '@aiscihub/cookieguard-playwright';

const audit = startCookieAudit(context, {
  origins: ['http://127.0.0.1:3000'],
  policy: { authCookies: ['session_id'], failOn: 'high' },
});
try {
  // ...the existing sign-in steps...
  assertCookiePolicy(await audit.evaluate()); // throws on FAIL or INCOMPLETE
} finally {
  audit.dispose();
}
```

**CLI** (the running app must set the cookie on a GET):

```bash
npx --yes cookieguard-ci@0.2.0 scan http://127.0.0.1:3000/ --auth-cookie session_id --format json
```

### D. Interpret the result

| Result | Meaning |
| --- | --- |
| PASS, exit 0 | No confirmed violations at or above `failOn`. Covers only the checks that ran. |
| FAIL, exit 1 | Confirmed violations, such as `CG001` Missing HttpOnly on the session cookie. |
| INCOMPLETE, exit 2 | Evidence missing or the audit failed. **Never a pass.** |
| Not run | Unsupported environment, missing prerequisite, or no authorization. Report it as not assessed. |

- `confirmed` findings are observed violations on a configured authentication cookie.
  `review` findings are heuristic or uncertain; report them as items to check, not as
  vulnerabilities.
- Read `issues` for INCOMPLETE causes, such as `expected-auth-cookie-not-observed`.
- Rule details: [security checks](references/security-checks.md). Fields, issue codes,
  and error codes: [findings](references/findings.md).

### E. Report

Use this structure; [findings](references/findings.md) has the full template and
[an example](examples/authentication-audit.md) shows a real audit.

1. Environment and integration.
2. Scope: origins, cookie names, policy, and the workflow audited.
3. Checks executed, and checks that could not run.
4. Findings: rule ID, severity, confirmed or review, cookie name, safe evidence.
5. Recommended fixes in the server's cookie configuration.
6. Limitations and unverified items.
7. Overall assessment: PASS, FAIL, INCOMPLETE, or not assessed.

## Rules

- Never print, log, store, or paste cookie values, session IDs, authorization headers,
  bearer tokens, passwords, storage-state files, or `document.cookie`. Leave values out of
  reports even if you encounter them.
- Audit only loopback or explicitly authorized origins.
- Do not loosen the policy (raising `failOn`, dropping the cookie name) to get a PASS.
  Fix the cookie flags in the server code and rerun.
- Report precisely: "no confirmed cookie-configuration violations for `session_id` on
  `http://127.0.0.1:3000`", never "the application is secure."
- Enforce results in tests or CI (`assert_policy()`, `assertCookiePolicy()`, exit codes).
  An agent's claim of success is not evidence.

## Troubleshooting

- `node` missing or older than 24: install Node.js 24+; the engine runs as a local Node process.
- `pip` cannot find `cookieguard-browser-use` or `browser-use`: the interpreter is older
  than 3.11; create the virtualenv with `python3.11`, `python3.12`, or `python3.13`.
- `TARGET` error: remove query strings and credentials from the URL; allow nonlocal origins explicitly.
- Browser Use closes the browser before `finish()`: set `keep_alive=True`.
- Any rule, issue, or error code: `npx --yes cookieguard-ci@0.2.0 explain ID`.
