# cookieguard-ci

Bounded local HTTP cookie-policy scanner. Node 24+, ESM. Version 0.3.0, which adds `gate`. Against
your running local test application:

```bash
npx cookieguard-ci@0.3.0 scan http://localhost:3000 --auth-cookie session_id
npx cookieguard-ci@0.3.0 capabilities --json   # machine-readable description
npx cookieguard-ci@0.3.0 explain CG001          # what a rule means and how to fix it
npx cookieguard-ci@0.3.0 --help
```

To try the controlled demo, clone
[the repository](https://github.com/aiscihub/cookieguard-ai), run `npm ci`, then:

```bash
npm run demo
# In another terminal:
npx --no-install cookieguard-ci scan http://127.0.0.1:3000/secure --auth-cookie session_id
npx --no-install cookieguard-ci --help
```

### Gate (0.3.0)

After a Playwright run that used `cookieGuardFixtures()` from
`@aiscihub/cookieguard-playwright`, the gate decides from the written evidence and the
policy on its own command line, not from the test runner's exit code:

```bash
npx cookieguard-ci@0.3.0 gate --evidence cookieguard-evidence --require "sign in and out" \
  --auth-cookie sid --fail-on medium --require-logout --run-id "$COOKIEGUARD_RUN_ID"
```

A required check without fresh, valid evidence is INCOMPLETE (exit 2). A confirmed
violation is FAIL (exit 1) even when another check was inconclusive.

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
