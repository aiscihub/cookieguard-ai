---
name: cookieguard
description: Audit authentication and session cookies (HttpOnly, Secure, SameSite, Domain scope, lifetime, __Host-/__Secure- prefixes) in web apps the user owns or is authorized to test. Returns PASS, FAIL, or INCOMPLETE with exit codes 0/1/2, rule IDs, and fixes, and never outputs cookie values. Use when adding a session-cookie security check to a login test, a Browser Use or other AI browser-agent login workflow, a Playwright end-to-end test, a CI pipeline or GitHub Actions job, or an MCP client, or when asked whether a login sets its session cookie securely. Not for scanning third-party sites, proving exploitability, or extracting cookies.
license: MIT
compatibility: Needs Node.js 24+. The Browser Use integration also needs Python 3.11-3.13, browser-use 0.13.x, and Chrome or Chromium. Installing needs network access to PyPI or npm.
metadata:
  project: https://github.com/aiscihub/cookieguard-ai
  packages: cookieguard-browser-use 0.1.0 (PyPI); cookieguard-ci, @aiscihub/cookieguard-playwright, @aiscihub/cookieguard-mcp 0.1.0 (npm)
---

# CookieGuard: session-cookie security checks

CookieGuard checks how an application *configures* its authentication cookies.
It runs locally, reads `Set-Cookie` headers and browser cookie-store metadata
(never values), and returns **PASS / FAIL / INCOMPLETE** with rule IDs
`CG001`–`CG009` and fixes. The decision comes from CookieGuard's engine, not
from the agent.

## 1. Before you start

1. **Authorization.** Audit only the user's own application or one they are
   authorized to test. Prefer a local instance on `127.0.0.1` or `localhost`.
   Never point CookieGuard at third-party sites.
2. **Session-cookie name.** Find the exact name in the server code: the
   `Set-Cookie` call or session settings such as `SESSION_COOKIE_NAME`,
   express-session `name`, or a `cookie_name` option. Without exact names,
   findings stay `review` and the run cannot FAIL. Ask the user if unsure.
3. **Where the session is created.** Note the login page and the request that
   sets the cookie. HTTP header scans send one GET and cannot submit a form.

## 2. Choose the integration

| Situation | Use | Install |
| --- | --- | --- |
| A Browser Use agent signs in | `cookieguard-browser-use` (Python) | `pip install cookieguard-browser-use` |
| Playwright tests sign in | `@aiscihub/cookieguard-playwright` | `npm install --save-dev @aiscihub/cookieguard-playwright@0.1.0` |
| A GET response sets the cookie, or a quick CI smoke check | `cookieguard-ci` CLI | `npx --yes cookieguard-ci@0.1.0 ...` |
| GitHub Actions | CookieGuard Action | see [CLI and CI](references/cli-and-ci.md) |
| An MCP client should run audits | `@aiscihub/cookieguard-mcp` | see [MCP](references/mcp.md) |

If the cookie appears only after submitting a login form, use Browser Use or
Playwright, not the header scan. All integrations need Node.js 24+ on `PATH`.

## 3. Integrate

**Browser Use.** It needs Python 3.11-3.13. Check `python3 --version` first: if it
is older, create the virtualenv with a newer interpreter that exists on the machine
(`python3.12 -m venv .venv`, or `python3.11` / `python3.13`), then
`.venv/bin/pip install cookieguard-browser-use`. Start the audit before the login and
enforce it after the run:

```python
from browser_use import Agent, BrowserProfile, BrowserSession, Tools
from cookieguard_browser_use import CookieGuardAudit

audit = CookieGuardAudit(
    allowed_origins=['http://127.0.0.1:3000'],  # exact origins you may test
    auth_cookies=['session_id'],                # the real session cookie name
    fail_on='high',
)
session = BrowserSession(browser_profile=BrowserProfile(
    keep_alive=True,                 # required: Agent.run() otherwise closes the browser
    enable_default_extensions=False,
    allowed_domains=audit.browser_allowed_domains(),
))
tools = Tools()
audit.register_tools(tools)          # optional agent-visible provisional check

await session.start()
await audit.start(session)           # before the login
agent = Agent(task=..., llm=..., browser_session=session, tools=tools,
              sensitive_data={'http://127.0.0.1': {'login_password': '...'}})
await agent.run()
result = await audit.finish()        # decided by the CookieGuard engine
await session.kill()
print(result.summary)
result.write_json('cookieguard-result.json')  # sanitized, owner-only file
result.assert_policy()               # raises CookiePolicyError on FAIL or INCOMPLETE
```

Pass credentials only through Browser Use `sensitive_data`, never in the task
text. Verify the installation without an LLM key:
`python -m cookieguard_browser_use.demo` (exit 0 means the insecure scenario
FAILed and the secure one PASSed). Details: [Browser Use](references/browser-use.md).

**Playwright.**

```js
import { test, expect } from '@playwright/test';
import { startCookieAudit, assertCookiePolicy } from '@aiscihub/cookieguard-playwright';

test('session-cookie policy', async ({ context, page }) => {
  const audit = startCookieAudit(context, {
    origins: ['http://127.0.0.1:3000'],
    policy: { authCookies: ['session_id'], failOn: 'high' },
  });
  try {
    // ...your existing sign-in steps and assertions...
    assertCookiePolicy(await audit.evaluate()); // throws on FAIL or INCOMPLETE
  } finally {
    audit.dispose();
  }
});
```

**CLI** (the app must be running; use a URL whose GET response sets the cookie):

```bash
npx --yes cookieguard-ci@0.1.0 scan http://127.0.0.1:3000/ --auth-cookie session_id --format json
```

## 4. Read the result

| Status | Exit | Meaning |
| --- | --- | --- |
| PASS | 0 | No confirmed violations at or above `failOn`. Covers only these checks. |
| FAIL | 1 | Confirmed violations, e.g. `CG001` Missing HttpOnly on the session cookie. Fix the server's `Set-Cookie`. |
| INCOMPLETE | 2 | Evidence missing or the audit failed. **Never a pass.** |

- `confirmed` findings are observed violations on a configured auth cookie.
  `review` findings are heuristic and never fail a run; do not report them as
  vulnerabilities.
- Common INCOMPLETE causes: wrong cookie name, collection started after login,
  the audited URL does not set the cookie, or a target outside the allowlist.
- Rule meanings and fixes: [rules](references/rules.md). The full
  machine-readable description: [capabilities.json](references/capabilities.json).

## 5. Rules for agents

- Never print, log, store, or paste cookie values, tokens, passwords, storage
  state, or `document.cookie`. CookieGuard output is already value-free.
- Do not loosen the policy (raising `fail_on`, removing the cookie name) to get
  a PASS. Fix the cookie flags in the server code, then rerun.
- Report precisely: "CookieGuard found no confirmed cookie-configuration
  violations for `session_id` on `http://127.0.0.1:3000`", not "the app is
  secure". CookieGuard does not test XSS, CSRF, exploitability, or server-side
  session handling.
- Enforce the result in tests or CI (`assert_policy()`, `assertCookiePolicy()`,
  exit codes). An agent's own claim of success is not evidence.

## 6. Troubleshooting

- `node` missing or older than 24: install Node.js 24+; the engine runs in a
  local Node subprocess.
- `pip` cannot find `cookieguard-browser-use` or `browser-use`: the interpreter is
  older than 3.11. Recreate the virtualenv with `python3.11`, `python3.12`, or `python3.13`.
- `TARGET` error: remove query strings and credentials from the URL; nonlocal
  origins need `--allow-origin` (CLI) or `allowed_origins` / `origins`.
- Browser Use closes the browser before `finish()`: set `keep_alive=True`.
- Run `npx --yes cookieguard-ci@0.1.0 --help` for every CLI option.
