# cookieguard

`pip install cookieguard` installs
[`cookieguard-browser-use`](https://pypi.org/project/cookieguard-browser-use/), CookieGuard's
authentication-cookie policy checks for [Browser Use](https://github.com/browser-use/browser-use)
agents, and makes its API importable as `cookieguard`:

```python
from cookieguard import CookieGuardAudit  # same object as cookieguard_browser_use.CookieGuardAudit
```

CookieGuard checks how your application configures its session cookies (HttpOnly, Secure,
SameSite, Domain scope, lifetime, and `__Host-`/`__Secure-` prefixes) during an authorized
browser workflow. It returns PASS, FAIL, or INCOMPLETE with exit codes 0/1/2 and never
outputs cookie values. Requires Python 3.11+, Node.js 24+, and Chrome or Chromium.

- Documentation and examples: [Browser Use integration](https://github.com/aiscihub/cookieguard-ai/tree/main/integrations/browser-use)
- CLI, Playwright, GitHub Action, and MCP server: [CookieGuard on GitHub](https://github.com/aiscihub/cookieguard-ai)

On npm, the official packages are `cookieguard-ci`, `@aiscihub/cookieguard-core`,
`@aiscihub/cookieguard-playwright`, and `@aiscihub/cookieguard-mcp`. The npm package named
`cookieguard` is an unrelated project.

## Releasing

Publish with the `Publish cookieguard alias` workflow (`.github/workflows/publish-cookieguard.yml`)
through PyPI Trusted Publishing. Widen the `cookieguard-browser-use` range in `pyproject.toml`
and bump this version when a new `cookieguard-browser-use` minor version is released.
