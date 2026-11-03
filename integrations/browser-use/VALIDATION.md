# Validation record — cookieguard-browser-use 0.1.0b1

Recorded 2026-11-03 on macOS 26.6.2 (arm64), Python 3.12.12, Node.js 26.10.0,
browser-use 0.13.14, cdp-use 1.4.5, Google Chrome 156.0.8078.80 (found by Browser Use).
All runs used local loopback apps and synthetic tokens. No AI provider was called.

## Results

| Check | Command | Result |
| --- | --- | --- |
| Engine provenance | `node scripts/vendor_engine.mjs --registry` | Workspace packages byte-identical to npm `@aiscihub/cookieguard-core@0.1.0` and `@aiscihub/cookieguard-playwright@0.1.0`; hashes recorded |
| Python suite (dev install) | `.venv/bin/python -m pytest -q` | **85 passed**, 0 warnings, about 2m45s |
| External consumer | `scripts/verify_external.py` | Wheel (35 files) installed into a fresh venv outside the repository; import path verified; copied suite **85 passed**; demo FAIL/PASS |
| Fresh checkout | Copy of only the files git would commit → `npm ci` → vendor → `pip install ./integrations/browser-use[test]` | 67 non-browser tests passed; demo FAIL/PASS. This caught and verified the fix for the root `_*` ignore rule, which had excluded `__init__.py`, `_*.py`, and `_node/` |
| Demo, installed package | `python -m cookieguard_browser_use.demo` | insecure: login succeeded, agent called the tool, **FAIL CG001 (exit 1)**; secure: login succeeded, **PASS (exit 0)** |
| Example, scripted provider | `examples/agent_login.py --mode insecure` / `--mode secure` | exit **1** with `CG001 "session_id"` / exit **0**; JSON written `0600` |
| Existing toolkit | `npm run check` | build, lint, typecheck, **29/29** Node tests, **8/8** Playwright tests |
| Existing packages | `node scripts/verify-packages.js` | Packed CLI/Playwright consumers exit 0/1/2 verified |
| Existing CI demos | `npm run demo:ci:fail` / `demo:ci:pass` | CG001, 1 failed (intended) / 1 passed |
| Artifact leakage | `node scripts/check-artifacts.js` | 233–235 generated files, including `artifacts/browser-use/`; no sentinels |

`npm run release:check` passes all 7 steps: source credentials (193 files),
licenses (122 entries), advisories (0), toolkit tests, installed tarballs,
benchmark, and output leakage. It first failed on moderate advisory GHSA-g3hv-75wg-m249
(published 2026-10-30) in `minimatch` <11.0.1, which came in only through the `eslint` dev dependency.
eslint 10.14.0 still requires `^10.2.6`, so a scoped npm override pins eslint's minimatch to 11.0.4.
eslint uses only the `Minimatch` constructor and `match()` with `{ dot: true }`, which v11 keeps.
Probes confirmed that deliberate errors in `.js`/`.mjs` files are still caught and ignored
paths stay ignored. No published package is affected. Remove the override when eslint
moves to minimatch 11.

## What the tests establish

- **Policy semantics** come from the real engine, not a Python copy:
  - confirmed findings: CG001 and CG002;
  - PASS for a valid cookie;
  - review-only results for unknown or candidate identities and for ambiguous or partitioned evidence;
  - INCOMPLETE for a missing expected cookie, no evidence, an unavailable store, or collection failure;
  - SameSite and lifetime thresholds; baseline regression (CG007); validated `auth_evidence`;
  - invalid configuration rejected by core validation.
- **Server declarations versus browser state:**
  - the store's effective SameSite is never reported as declared, and an unspecified value stays unknown;
  - a header rejected by the browser is `not-observed`;
  - with header evidence required, a store-only PASS becomes INCOMPLETE, but a FAIL is not hidden.
- **Set-Cookie attribution** holds for both observed Chromium event orders, ExtraInfo
  arriving before the request, cross-origin redirects (only authorized hops forwarded),
  cached hops, and mid-flight attachment. Status mismatches give INCOMPLETE; unattributable
  headers are dropped and counted.
- **Real Chromium:**
  - insecure login FAIL with header evidence (`declared: lax`, `storeStatus: present`); secure login PASS;
  - browser-observation-only mode; audit started after login;
  - origin filtering (a `localhost` login excluded from a `127.0.0.1` audit);
  - a login in a genuinely new tab; two concurrent sessions with no shared evidence; a tool call from the wrong session refused;
  - observer websocket closed (INCOMPLETE, while Browser Use's own connection keeps working); browser closed before finish (INCOMPLETE);
  - cleanup (engine process exited, observer closed, reuse rejected); engine killed mid-audit (fixed `ENGINE` error).
- **Agent independence:**
  - a real `Agent.run()` with a scripted model gives FAIL/PASS;
  - an agent that never calls the tool still gets FAIL;
  - an agent that falsely claims "logged in and CookieGuard passed" without logging in gets INCOMPLETE.
- **Privacy:** random `CGBU_CANARY_*` session tokens are absent from:
  - agent-visible tool output and model-visible messages;
  - stdout and stderr of a fresh process at Browser Use log levels `info` and `debug`;
  - written JSON, exception messages and chains, engine replies, and malformed-input error paths.

  The demo password is absent from model-visible messages and process output. The engine
  subprocess is denied file writes and child processes under its permission flags.
  Its environment drops `NODE_OPTIONS` and API keys, and a tampered vendored engine is refused.

## Not verified

- No real LLM-driven run. `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, and `BROWSER_USE_API_KEY`
  were unset. The provider branches of `examples/agent_login.py` are unexecuted.
- Python 3.11 and 3.13, Node 24, Linux, Windows, Chromium builds other than Chrome 156,
  Browser Use cloud browsers, and other browser-use versions.
- The new `browser-use` job in `.github/workflows/cookieguard-ci.yml` has not run on
  GitHub-hosted runners.
- Network denial inside the engine sandbox applies only on Node 25+. The tests assert
  it only there; on Node 24 the permission model does not restrict network access.
