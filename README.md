# CookieGuard AI

**A successful agent login is not a secure session cookie.** CookieGuard for
[Browser Use](https://github.com/browser-use/browser-use) checks the authentication
cookies your agent receives and returns **PASS / FAIL / INCOMPLETE**, with rule IDs,
explanations, and fixes. Your local policy decides the result.

[Browser Use](#browser-use-agents) · [Browser extension](#browser-extension) · [CI tools](#ci-tools)

## Browser Use agents

### How it works

<picture>
  <source media="(max-width: 600px) and (prefers-color-scheme: dark)" srcset="integrations/browser-use/docs/how-it-works-dark-mobile.svg">
  <source media="(max-width: 600px)" srcset="integrations/browser-use/docs/how-it-works-light-mobile.svg">
  <source media="(prefers-color-scheme: dark)" srcset="integrations/browser-use/docs/how-it-works-dark.svg">
  <img alt="Your test starts CookieGuard and the Browser Use agent. The agent, guided by any AI model, logs in through Chromium. The app responds with Set-Cookie. A separate CookieGuard observer reads the same browser over its own CDP connection. It sends the evidence to a local CookieGuard engine, which returns PASS, FAIL, or INCOMPLETE to your test. The agent's optional cookieguard_audit tool is read-only, and cookie values never reach the model." src="integrations/browser-use/docs/how-it-works-light.svg" width="100%">
</picture>

CookieGuard observes the agent's browser, checks the evidence with the local policy
engine, and returns a result for your code to enforce.

`fail_on` sets the line: a confirmed finding at or above it fails the run; anything
below it is reported. Identify your session cookies with `auth_cookies`.
See the [policy options](integrations/browser-use/docs/policy.md).

### See it run

![A Browser Use agent logs in to two local apps. Both logins succeed. CookieGuard fails the first with CG001 Missing HttpOnly (exit 1) and passes the second (exit 0).](integrations/browser-use/docs/cookieguard-browser-use-demo.gif)

Claude (`claude-opus-5-5`) drives a real Browser Use agent through the same login twice.
The insecure app's cookie lacks `HttpOnly`: **FAIL — CG001** (exit 1).
The secure app gets **PASS** (exit 0).
[Recording and test evidence](integrations/browser-use/docs/demo-and-tests.md).

### Add it to your agent

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

`assert_policy()` raises on FAIL or INCOMPLETE even if the agent never called the
audit tool, or reported success. CookieGuard enforces the result outside the model.

Needs **Python 3.11+, Node.js 24+, and Chrome or Chromium**.
`cookieguard-browser-use` **0.1.0b1 is a pre-release, not yet on PyPI**; use the
[from-source installation](integrations/browser-use/docs/install.md#from-source).
This is a community integration, not an official Browser Use package.

[Install](integrations/browser-use/docs/install.md) · [Policy](integrations/browser-use/docs/policy.md) · [How it works](integrations/browser-use/docs/how-it-works.md) · [Results](integrations/browser-use/docs/results.md) · [Limits & privacy](integrations/browser-use/docs/limits-and-privacy.md) · [Demo & tests](integrations/browser-use/docs/demo-and-tests.md)

## Browser extension

Inspect cookies interactively in Chrome with the original CookieGuard AI extension.
Its classifier and explanations run in your browser, with no backend required.

1. Download or clone this repository.
2. Open `chrome://extensions/` and enable **Developer mode**.
3. Select **Load unpacked**, then choose the `extension-standalone/` folder.
4. Open a site you are authorized to inspect, click CookieGuard AI, and select **Scan Cookies**.

The popup shows **AI Engine Ready** or **Rule-Based Mode**.

![CookieGuard AI browser extension](resource/screenshot_3.0.png)

Extension JSON exports can include cookie values; review them before sharing.
[Extension and research background](docs/ORIGINAL_README.md) · [Privacy](PRIVACY.md).

## CI tools

Use CookieGuard CI to check cookie policy in your tests and build pipeline.
The CLI, Playwright adapter, and GitHub Action are available in the
[v0.1.0 public beta](https://github.com/aiscihub/cookieguard-ai/releases/tag/ci-v0.1.0).
They use the same published policy engine as the Browser Use integration.

| Tool | Use it for | Get started |
| --- | --- | --- |
| Playwright | Cookies created during login or a browser workflow | [Playwright quickstart](docs/CI_GUIDE.md#quick-start-playwright) |
| CLI | `Set-Cookie` response headers from a running test app | [CLI quickstart](docs/CI_GUIDE.md#quick-start-cli) |
| GitHub Action | Header checks, a build summary, and a sanitized report artifact | [Action quickstart](docs/CI_GUIDE.md#quick-start-github-actions) |

With **Node.js 24+**, scan a local endpoint that sets your authentication cookie:

```bash
npx cookieguard-ci@0.1.0 scan http://localhost:3000 --auth-cookie session_id
```

The CLI and Action do not log in or execute JavaScript. Use the Playwright adapter
for authenticated browser workflows. CookieGuard exits **0** for a completed pass,
**1** for a confirmed policy failure, or **2** for an incomplete audit.

[Full CI guide](docs/CI_GUIDE.md) · [Playwright demo](docs/CI_GUIDE.md#watch-the-playwright-demo) · [Validation](docs/CI_VALIDATION.md) · [Architecture](docs/CI_ARCHITECTURE.md)

## Supported checks

Browser Use and CI check HttpOnly, Secure, SameSite, domain scope, lifetime, cookie
prefixes, and protection regressions. Unknown identity or ambiguous evidence stays
in review. See the [CG001–CG009 rule table](docs/CI_GUIDE.md#supported-checks) and
[policy limits](integrations/browser-use/docs/limits-and-privacy.md).
A passing audit covers the configured cookie checks; it does not prove an application is secure.

## Project and contributing

The original CookieGuard AI extension won the **Girls Who Code Challenge 2026**:
[award announcement](https://girlswhocode.com/news/gwc-challenge-2026-winners) ·
[original demo](https://www.youtube.com/watch?v=_PhzLN31C04).
The [project summary](PROJECT_SUMMARY.md), [historical report](https://aiscihub.github.io/cookieguard-ai/report.html),
and [research documentation](docs/ORIGINAL_README.md) remain available.

[Contributing](CONTRIBUTING.md) · [Troubleshooting](docs/CI_GUIDE.md#contributing-and-troubleshooting) · [Security](SECURITY.md) · [Privacy](PRIVACY.md) · [Release notes](CHANGELOG.md) · [MIT license](LICENSE).
