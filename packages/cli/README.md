# cookieguard-ci (proposed 0.1.0)

Bounded local HTTP cookie-policy scanner. Node 24+, ESM. Not yet published.
Build and install this repository with `npm ci`, then:

```bash
npm run demo
# In another terminal:
npx --no-install cookieguard-ci scan http://127.0.0.1:3000/secure --auth-cookie session_id
npx --no-install cookieguard-ci --help
```

Exit 0: completed/pass. Exit 1: confirmed policy failure at the configured severity.
Exit 2: incomplete/invalid. Review findings do not fail. Empty observations or
missing expected names are incomplete.

`scanUrl(target, { allowOrigins, timeoutMs })` exposes the typed HTTP collector.
It returns `{observations, target, mode, complete}` for `evaluateCookiePolicy`,
and throws fixed `AuditError` messages. The CLI catches errors without printing
raw values, headers, URLs, or stacks. Reports print target origins only.

No browser, JavaScript execution, credentials, cookie forwarding, crawler,
telemetry, or native inference dependency. Loopback is allowed by default; exact
`--allow-origin` authorization is needed for a developer-controlled nonlocal
test endpoint. See the repository README for flags and boundaries.
