# Browser Use integration

`pip install cookieguard-browser-use` (0.1.0). Tested with browser-use 0.13.14 on
Linux (Python 3.11-3.13) and macOS (Python 3.12) with Chromium-family browsers.
Node.js 24+ must be on `PATH` (or set `COOKIEGUARD_NODE`); pip does not install it.
Windows, Browser Use cloud browsers, and other Browser Use versions are untested.

## Complete pattern

```python
import asyncio
from browser_use import Agent, BrowserProfile, BrowserSession, Tools
from cookieguard_browser_use import CookieGuardAudit, CookiePolicyError

async def login_and_audit(llm) -> int:
    audit = CookieGuardAudit(allowed_origins=['http://127.0.0.1:3000'], auth_cookies=['session_id'])
    session = BrowserSession(browser_profile=BrowserProfile(
        keep_alive=True, enable_default_extensions=False,
        allowed_domains=audit.browser_allowed_domains()))
    tools = Tools()
    audit.register_tools(tools)
    try:
        await session.start()
        await audit.start(session)            # start before the login
        agent = Agent(task='Sign in at http://127.0.0.1:3000/login with username '
                           '<secret>login_user</secret> and password <secret>login_password</secret>.',
                      llm=llm, browser_session=session, tools=tools,
                      sensitive_data={'http://127.0.0.1': {'login_user': 'demo', 'login_password': '...'}})
        await agent.run(max_steps=10)
        result = await audit.finish()
    finally:
        await audit.close()
        await session.kill()
    print(result.summary)                     # value-free text
    result.write_json('cookieguard-result.json')
    try:
        result.assert_policy()
    except CookiePolicyError as error:
        print(error)
    return result.exit_code                   # 0 PASS, 1 FAIL, 2 INCOMPLETE
```

In pytest, call `result.assert_policy()` directly so FAIL and INCOMPLETE fail the test.

## Options (`CookieGuardAudit(...)`)

| Option | Default | Effect |
| --- | --- | --- |
| `allowed_origins` | required | Exact `http(s)://host[:port]` origins; loopback only unless `allow_nonlocal_origins=True`. Max 20. |
| `auth_cookies` | `[]` | Exact session-cookie names. Only these can be confirmed; a missing one makes the audit INCOMPLETE. |
| `fail_on` | `'high'` | `info`, `low`, `medium`, `high`, `critical`. |
| `allowed_same_site` | `('lax', 'strict')` | A declared SameSite outside this list is CG003. |
| `require_explicit_same_site` | `False` | A `Set-Cookie` without SameSite is CG003. |
| `require_host_only` | `False` | A `Domain=` attribute becomes a confirmed CG004. |
| `max_lifetime_days` | `30` | A longer remaining lifetime is CG005. |
| `capture_headers` | `True` | `False` keeps only browser-store evidence (SameSite declarations unknown). |
| `timeout_seconds` | `600` | Collection window; expiry makes the audit INCOMPLETE. |

## Result (`AuditResult`)

`status` (`'PASS'`/`'FAIL'`/`'INCOMPLETE'`), `exit_code`, `findings`,
`confirmed_findings`, `review_findings`, `issues`, `summary`, `to_json()`,
`write_json(path)`, `assert_policy()`. Each `Finding` has `rule_id`, `severity`,
`status` (`confirmed` or `review`), `cookie_name`, `explanation`,
`recommendation`, and `evidence_category` (`server-declaration` or
`browser-observation`).

The optional agent tool `cookieguard_audit` returns a *provisional*,
store-only check. It cannot satisfy policy; only `audit.finish()` decides.

## Smoke test without an LLM

`python -m cookieguard_browser_use.demo` runs a real Browser Use Agent with a
scripted model against a local demo app: the insecure login FAILs with CG001 and
the secure login PASSes. Exit code 0 means both matched.
