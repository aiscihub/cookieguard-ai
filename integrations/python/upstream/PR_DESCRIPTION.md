# Proposed title

examples: add CookieGuard AI authentication-cookie audit demo

# Proposed body

**CookieGuard AI: Independent authentication-cookie security auditing for Browser Use workflows.**

A successful login does not establish that its session cookie meets policy.
This adds a small example using CookieGuard's existing insecure-login versus
secure-login demo, plus an entry in the community-integration list. Both logins
succeed. CookieGuard fails the missing-HttpOnly cookie with **CG001, exit 1**
and passes the secure control with **exit 0**. Baseline runs succeed without a
cookie-security verdict.

The script shows the integration points directly: start the audit before login,
optionally register its tool, run the Browser Use agent, finish before browser
cleanup, and enforce the result in developer code. It uses the external
package's disposable app and scripted model to exercise the real Agent loop
without an API key. Its six opt-in tests check those outcomes and enforcement
when the agent never calls the audit tool.

The contribution is a script, README, tests and one community-list entry,
following the integration example guidelines. CookieGuard stays maintained
externally by @aiscihub. The pinned package `cookieguard-browser-use==0.1.0`
requires Node.js 24+ alongside Python and Chromium. Browser Use's runtime files
and dependencies are unchanged. The listing makes no support or endorsement
commitment for Browser Use maintainers.

Local verification on November 4, 2026 used published wheels with Browser Use
0.13.14. The stable CookieGuard 0.1.0 wheel passed all six real-browser example
tests and 71 adapter unit tests in a fresh environment. Its 31 package files
match 0.1.0b1 except for the version string; dependency requirements are unchanged.
Earlier that day, 0.1.0b1 passed all 89 existing adapter tests, including real
Chromium and scripted `Agent.run()` tests, plus the six example and seven
benchmark-scorer tests. The full adapter browser suite was not repeated on 0.1.0.
Upstream pre-commit checks passed on the changed paths; Pyright also passed with
the optional package absent. The package's scripted demo helper needs a documented
type cast because it lacks the full static `BaseChatModel` protocol.

<!-- measured-pr-results-start -->
The separate ten-fixture comparison used CookieGuard **0.1.0b1** and completed
100 attempted runs: 50 baseline
and 50 guarded. CookieGuard detected all expected violations in **29 executed
insecure trials**, with **0 false positives across 15 controls** and **5/5 missing
sessions marked INCOMPLETE**. One of 30 insecure attempts failed during Chrome
startup before the audit attached, so the benchmark correctly exited 1. Median
paired added workflow time was **166.4 ms** (p95 200.9 ms), excluding
browser launch/kill. Startup-inclusive timing was too variable for a reliable
overall overhead percentage.
<!-- measured-pr-results-end -->

An earlier long attempt also encountered a Chrome launch failure before the
audit attached; both occurrences are retained in the evidence. The comparison
is a small synthetic policy test, not a real-world security accuracy claim.
It does not demonstrate general agent protection, XSS/CSRF detection, token-theft
prevention or production TLS safety.

The patch applies to the inspected upstream `main`, and upstream pre-commit
checks passed locally. Hosted PR checks have not run.

[Adapter and installation](https://github.com/aiscihub/cookieguard-ai/tree/main/integrations/browser-use)
· [Reproduction and raw results](https://github.com/aiscihub/cookieguard-ai/tree/39f6232d86276b6b5caaa114eab2654842f74750/integrations/browser-use/validation)
· [Stable wheel verification](https://github.com/aiscihub/cookieguard-ai/blob/39f6232d86276b6b5caaa114eab2654842f74750/integrations/browser-use/validation/evidence/stable-release.json)
· [Existing published demo and provenance](https://github.com/aiscihub/cookieguard-ai/blob/browser-use-v0.1.0b1/integrations/browser-use/docs/demo-and-tests.md)

The linked published demo is from November 3; the fresh reproducible comparison
uses a scripted model or Actor actions and makes no paid-model calls.
