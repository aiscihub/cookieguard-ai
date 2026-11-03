# CookieGuard for Browser Use

**A successful agent login is not a secure session cookie.** CookieGuard for
Browser Use watches the browser your [Browser Use](https://github.com/browser-use/browser-use)
agent drives, checks the authentication cookies it receives, and returns
**PASS / FAIL / INCOMPLETE** with rule IDs, explanations, and fixes. The agent
does the authorized workflow; the decision comes from the local
[CookieGuard](../../README.md) policy engine, never from the model.

Status: `0.1.0b1` pre-release, tested with browser-use 0.13.14. It is not yet on
PyPI. This is a community integration, not an official Browser Use package.

```text
Browser Use Agent ──(its own CDP connection)──► Chromium ◄──(separate CDP observer)── CookieGuard
        │ optional read-only tool: cookieguard_audit                                  │
        ▼                                                                             ▼
   LLM provider (task, page text, sanitized tool output)        local Node engine (stdin pipe, sandboxed)
                                                                 @aiscihub/cookieguard-core 0.1.0 rules CG001–CG009
                                                                                      │
                                         your code: result = await audit.finish(); result.assert_policy()
```

- **Server declarations:** `Set-Cookie` lines from `Network.responseReceivedExtraInfo`,
  attributed to their redirect hop and filtered to your authorized origins.
- **Browser state:** `Storage.getCookies` (HttpOnly, Secure, SameSite, domain, path, expiry, partitioning).
- **Evaluation:** the published `@aiscihub/cookieguard-core` and `@aiscihub/cookieguard-playwright`
  0.1.0 packages, vendored unchanged and hash-verified. No Python copy of the rules.
- **Enforcement:** `audit.finish()` and `assert_policy()` in your code. The agent tool is optional,
  read-only, and cannot stop collection or change the result.

## Requirements and installation

- Python 3.11+ (tested on 3.12.12), browser-use `>=0.13.14,<0.14`.
- Node.js 24+ on `PATH` (or set `COOKIEGUARD_NODE`) for the local engine. Tested on Node 26.10.
- Chrome or Chromium. Browser Use finds an installed browser or `uvx playwright install chromium`.

Until a PyPI release exists, install from this repository:

```bash
git clone https://github.com/aiscihub/cookieguard-ai && cd cookieguard-ai
npm ci
node integrations/browser-use/scripts/vendor_engine.mjs --registry  # copies the published npm engine
pip install ./integrations/browser-use
```

The vendor step requires the workspace packages to be byte-identical to the npm
release (`--registry`) and records SHA-256 hashes that are checked before Node starts.

## Add it to an existing Browser Use agent

```python
from browser_use import Agent, BrowserProfile, BrowserSession, Tools
from cookieguard_browser_use import CookieGuardAudit

audit = CookieGuardAudit(
    allowed_origins=['http://127.0.0.1:3000'],  # exact origins you are authorized to test
    auth_cookies=['session_id'],                # the real session cookie name(s)
    fail_on='high',
)
session = BrowserSession(browser_profile=BrowserProfile(
    keep_alive=True,                            # required: Agent.run() otherwise closes the browser
    enable_default_extensions=False,            # avoid the bundled cookie-consent extension
    allowed_domains=audit.browser_allowed_domains(),
))
tools = Tools()
audit.register_tools(tools)                     # optional agent-visible check

await session.start()
await audit.start(session)                      # before the login
agent = Agent(task=..., llm=..., browser_session=session, tools=tools,
              sensitive_data={'http://127.0.0.1': {'login_password': '...'}})
await agent.run()
result = await audit.finish()                   # decided by the CookieGuard engine
await session.kill()

print(result.summary)
result.assert_policy()                          # raises CookiePolicyError on FAIL or INCOMPLETE
```

`assert_policy()` raises even if the agent never called the tool, or reported
success. `CookieGuardAudit` is also an async context manager; `close()` stops
collection without a result. One instance audits one workflow.

## Run the demonstration

A loopback-only app with a real login form. The two modes differ only in `HttpOnly`.

```bash
python -m cookieguard_browser_use.demo            # both scenarios, headless; add --headed to watch
```

This runs the real Browser Use `Agent` loop with a scripted stand-in model (no
AI provider or API key). The stand-in reads the browser state and logs in with
`sensitive_data` placeholders. The agent calls `cookieguard_audit`, then CookieGuard enforces:

| Scenario | Login | Agent's provisional check | Final CookieGuard result | Exit |
| --- | --- | --- | --- | --- |
| `insecure` | succeeds (server accepted the cookie) | FAIL | **FAIL — CG001 Missing HttpOnly** | 1 |
| `secure` | succeeds | PASS | **PASS** | 0 |

To try a real model, see [`examples/agent_login.py`](examples/agent_login.py):

```bash
python examples/agent_login.py --mode insecure                           # scripted
ANTHROPIC_API_KEY=... python examples/agent_login.py --provider anthropic --mode insecure
```

The Anthropic, OpenAI, and Browser Use Cloud provider paths are provided as
opt-in examples. **They have not been run in this repository's validation**,
because no provider credentials were available. The scripted paths have.

## Reading results

| Status | Exit | Meaning |
| --- | --- | --- |
| `PASS` | 0 | Evidence complete; no confirmed violation at or above `fail_on`. Review items may remain. |
| `FAIL` | 1 | A confirmed violation at or above `fail_on`. |
| `INCOMPLETE` | 2 | Evidence missing or unreliable: expected cookie absent, observer disconnected, store unreadable, unattributable headers, limits exceeded. Never a pass. |

Each `Finding` has `rule_id`, `severity`, `status`, `cookie_name`/`domain`/`path`/`origin`,
`title`, `explanation`, `recommendation`, `evidence_category`, and sanitized `evidence`.
The `status` is either `confirmed` (a policy violation of a cookie you identified) or `review` (uncertain).
`evidence_category` is either `server-declaration` (an observed `Set-Cookie`) or `browser-observation` (cookie store).
`result.collection` explains how evidence was gathered, including `incompleteReasons`.
`result.to_json()` / `write_json(path)` produce a value-free report (files are `0600`).
`result.report` is the CookieGuard core JSON report (schemaVersion 1).

Only names in `auth_cookies` (or validated `auth_evidence`) can produce confirmed
failures. Other cookies that look like sessions are review items (`CG008`).
Rules: CG001 HttpOnly, CG002 Secure, CG003 SameSite policy, CG004 Domain sharing,
CG005 lifetime, CG006 prefixes, CG007 baseline regression (`finish(baseline=old.report)`),
CG008 unconfirmed role, CG009 evidence review. See the [main README](../../README.md#supported-checks).

| Option | Default | Notes |
| --- | --- | --- |
| `allowed_origins` | required | Exact `http(s)://host[:port]`; loopback only unless `allow_nonlocal_origins=True`. Max 20. |
| `auth_cookies` | `[]` | Exact names; missing ones make the audit INCOMPLETE. |
| `fail_on` | `high` | `info`, `low`, `medium`, `high`, `critical`. |
| `allowed_same_site`, `require_explicit_same_site`, `require_host_only`, `max_lifetime_days` | `lax,strict`, off, off, 30 | Core policy options. |
| `capture_headers` | `True` | `False` = browser-observation-only mode (declarations stay unknown). |
| `require_header_evidence` | `= capture_headers` | An otherwise passing audit without a `Set-Cookie` for each expected cookie is INCOMPLETE. Never hides a FAIL. |
| `timeout_seconds` | 600 | Collection window (max 600); expiry makes the audit INCOMPLETE. |

## What it cannot observe

- **Browser state is not a server declaration.** A store cookie's SameSite is the
  effective value. If Chromium reports none, it stays unknown. Declarations come
  only from captured `Set-Cookie` lines.
- **Header capture can miss requests** made before the observer attaches to a
  new tab or iframe, or made by other browser contexts and service workers. Responses served
  by a service worker make the audit INCOMPLETE. Missing headers only remove
  declaration evidence. With the default `require_header_evidence`, they cannot produce a PASS.
- **JavaScript-set cookies** (`document.cookie`) have no header. Their store flags
  are still checked, so a missing HttpOnly still fails.
- Store cookies do not reveal host-only scope, so `CG004` and prefix checks rely on headers.
  Cookies are scoped by host, not port, so another app on the same loopback host
  shares the jar.
- It is a configuration audit. It does not validate server sessions, demonstrate
  XSS/CSRF, or prove an application is secure. Tested only on Chromium with local
  browsers; Browser Use cloud browsers are untested.

## Privacy and authorization

- **Audit only applications you are authorized to test.** Nonlocal origins
  require `allow_nonlocal_origins=True`. Origins limit evidence, not navigation.
  Use `allowed_domains` to keep the agent on the app. CookieGuard never navigates.
- **CookieGuard outputs never contain cookie values.** Values go only to the local
  engine over a stdin pipe; they are never put in argv, files, logs, or exceptions. The engine runs with
  Node's permission model (read-only access to its own files, no writes or child
  processes; Node 25+ also blocks network). As a last check, a result containing
  an observed store cookie value (12+ characters, not purely alphabetic) is refused.
  Python memory is not securely erased.
- **The model is outside CookieGuard's boundary.** Your LLM provider receives the
  task, page content, and the sanitized tool output. Pass credentials through
  Browser Use `sensitive_data` with distinctive values. Browser Use masks every
  occurrence of a secret's value and logs typed text in clear otherwise.
- **Browser Use defaults to check:** anonymized telemetry (task, URLs, actions,
  final answer) is on unless `ANONYMIZED_TELEMETRY=false`. Cloud sync follows it
  (`BROWSER_USE_CLOUD_SYNC`). A configured `storage_state` path, HAR recording
  (`record_har_path`), traces, or a persistent `user_data_dir` can write cookie
  values to disk. These are outside CookieGuard's control.

## Tests

```bash
cd integrations/browser-use
python -m venv .venv && .venv/bin/pip install -e ".[test]" build
.venv/bin/python -m pytest -q          # 85 tests, real Chromium, about 3 minutes, no API key
.venv/bin/python scripts/verify_external.py   # wheel → fresh venv outside the repo → tests + demo
```

Coverage includes:
- **Policy semantics** through the real engine: CG001–CG009, thresholds, lifetime, baseline, unknown identity, missing cookies, and ambiguous or partitioned evidence.
- **Set-Cookie attribution** across redirect orderings and cross-origin redirects.
- **Real-browser flows:** login, store-only mode, origin filtering, new tabs, concurrent sessions, observer disconnection, browser closure, cleanup, and engine death.
- **The real `Agent.run()` loop**, including an agent that skips the tool and one that falsely claims success.
- **Privacy:** synthetic canary tokens are checked across agent-visible text, stdout/stderr at info and debug log levels, saved JSON, and exception chains. See [VALIDATION.md](VALIDATION.md) for recorded results.
