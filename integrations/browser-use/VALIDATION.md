# Validation record — cookieguard-browser-use 0.1.0b1

Recorded 2026-11-03 on macOS 26.6.2 (arm64), Python 3.12.12, Node.js 26.10.0,
browser-use 0.13.14, cdp-use 1.4.5, Google Chrome 156.0.8078.80 (found by Browser Use).
All runs used local loopback apps and synthetic tokens. No AI provider was called.

## Results

| Check | Command | Result |
| --- | --- | --- |
| Engine provenance | `node scripts/vendor_engine.mjs --registry` | Workspace packages byte-identical to npm `@aiscihub/cookieguard-core@0.1.0` and `@aiscihub/cookieguard-playwright@0.1.0`; hashes recorded |
| Python suite (dev install) | `.venv/bin/python -m pytest -q` | **89 passed**, 0 warnings, about 2m55s (includes the policy-option and demo command-line tests) |
| External consumer | `scripts/verify_external.py` | Wheel installed into a fresh venv outside the repository; import path verified; copied suite passed (85 at the last recorded run; CI reruns it on every push); demo FAIL/PASS |
| Fresh checkout | Copy of only the files git would commit → `npm ci` → vendor → `pip install ./integrations/browser-use[test]` | 67 non-browser tests passed; demo FAIL/PASS. This caught and verified the fix for the root `_*` ignore rule, which had excluded `__init__.py`, `_*.py`, and `_node/` |
| Demo, installed package | `python -m cookieguard_browser_use.demo` | insecure: login succeeded, agent called the tool, **FAIL CG001 (exit 1)**; secure: login succeeded, **PASS (exit 0)** |
| README demo recording | `scripts/record_demo.py --provider anthropic --out docs` | Real run with `claude-opus-5-5` (headless Chrome 156, 1280×720): insecure FAIL exit 1, secure PASS exit 0, one server login each; 29.6s and 26.8s real time, 62 and 45 screencast frames. Waits over 2s for the model are condensed and labelled. Media SHA-256 in `docs/demo-provenance.json`. No canary, password, or API key in captured text, provenance, or media bytes |
| Policy diagram | `docs/build_policy_diagram.py` | Four SVGs (light/dark × desktop/mobile). Rendered as `<img>` in Chromium: `fail_on` toggles between `'high'` and `'medium'`, and CG003/CG005 switch from reported to FAILS. The rule severities and option effects shown are each asserted by an engine test |
| Animated diagram | `docs/build_diagram.py` | Four SVGs (light/dark × desktop/mobile). Rendered as `<img>` in Chromium: steps animate in sequence. As a document under `prefers-reduced-motion: reduce`: 0 running animations, static caption and chips shown |
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

## Real model run (Anthropic)

Run on 2026-11-03 with `examples/agent_login.py --provider anthropic`: `claude-opus-5-5` through
Browser Use's `ChatAnthropic`, with adaptive thinking and a server-side fallback to
`claude-opus-4-8`. The key was loaded from an owner-only file and appears in no log or report.

| Scenario | Agent | Server logins | CookieGuard | Exit |
| --- | --- | --- | --- | --- |
| insecure | logged in with `<secret>` placeholders, called `cookieguard_audit`, reported success | 1 | FAIL, CG001 confirmed, from header evidence | 1 |
| secure | same steps | 1 | PASS | 0 |

Each run took about 36 seconds with no step retries. Both final answers relayed the
provisional status and said the final result is enforced outside the agent.

Before the fallback was enabled, one full run failed every step: Opus 5.5 returned
`stop_reason: refusal` (a safety classifier), which Browser Use reports as "Expected tool use in
response but none found". A repeat diagnostic call succeeded. CookieGuard reported both
failed runs as INCOMPLETE (exit 2), never PASS: one failed on billing, one on refusals.

## Hosted CI (GitHub Actions, ubuntu-latest)

The merged [PR #13](https://github.com/aiscihub/cookieguard-ai/pull/13) passed the toolkit
job and Browser Use jobs on Python 3.11, 3.12, and 3.13 on 2026-11-03 (head `720235d`).
These are the existing hosted results; they were inspected without requesting a rerun.

The `browser-use` job passed in run 41702699563 (commit `01b1fef`) on Python 3.12, Node 24.22.1,
and Playwright Chromium 156.0.8078.4 with its sandbox enabled. Results:
- **No-browser tests:** 67 passed.
- **Real-browser and Agent tests:** 18 passed.
- **External consumer:** the wheel installed into a fresh environment outside the repository, the copied suite passed (85), and the demo gave FAIL/PASS.
- **Leakage:** none in the job log or saved evidence.

Local runs also passed on Node 24.22.2: all 85 Python tests and the toolkit `npm run check`.

Two problems found on the way, both fixed:
- **Chromium exited at launch.** Ubuntu 24.04 sets `kernel.apparmor_restrict_unprivileged_userns=1`,
  which blocks Chromium's sandbox, and Browser Use prefers Playwright's Chromium. The job now
  allows the namespaces rather than using `--no-sandbox`.
- **The first run hung silently for 29 minutes.** The test helper did not kill a session
  whose launch failed, and `asyncio.run` then waited forever to cancel Browser Use's tasks.
  Reproduced locally with a browser that exits immediately, then fixed.


## PyPI release preparation — 2026-11-03

Packaging checks for the release-preparation branch used Python 3.12.12, build 1.6.1,
Twine 7.0.0, hatch-fancy-pypi-readme 25.1.0, and actionlint 1.7.12. The commands below
ran from `integrations/browser-use`, except actionlint and the Git checks, which ran
from the repository root. `python` and `actionlint` came from the temporary tooling
environment `/tmp/cookieguard-release-tools-ncx5f_t7`. Application tests and
`verify_external.py` were not rerun locally: the maintainer requested reuse of the
completed test results. CI still runs its normal checks when the branch is pushed.

`python -m build` (exit 0):

```text
* Creating isolated environment: venv+pip...
* Installing packages in isolated environment:
  - hatch-fancy-pypi-readme==25.1.0
  - hatchling>=1.27
* Getting build dependencies for sdist...
* Installed build dependency versions:
  - hatch-fancy-pypi-readme==25.1.0
  - hatchling==1.33.0
* Building sdist...
* Building wheel from sdist
* Creating isolated environment: venv+pip...
* Installing packages in isolated environment:
  - hatch-fancy-pypi-readme==25.1.0
  - hatchling>=1.27
* Getting build dependencies for wheel...
* Installed build dependency versions:
  - hatch-fancy-pypi-readme==25.1.0
  - hatchling==1.33.0
* Building wheel...
Successfully built cookieguard_browser_use-0.1.0b1.tar.gz and cookieguard_browser_use-0.1.0b1-py3-none-any.whl
```

`python -m twine check --strict dist/*` (exit 0):

```text
Checking dist/cookieguard_browser_use-0.1.0b1-py3-none-any.whl: PASSED
Checking dist/cookieguard_browser_use-0.1.0b1.tar.gz: PASSED
```

`python scripts/verify_metadata.py` (exit 0):

```text
cookieguard_browser_use-0.1.0b1-py3-none-any.whl: 16 absolute links/images; 15 pinned to browser-use-v0.1.0b1; no relative links.
cookieguard_browser_use-0.1.0b1.tar.gz: 16 absolute links/images; 15 pinned to browser-use-v0.1.0b1; no relative links.
```

`actionlint .github/workflows/publish-browser-use.yml` and `git diff --check` both
exited 0 with no output. The actionlint download was checked against its published
SHA-256 (`aba9ced2dee8d27fecca3dc7feb1a7f9a52caefa1eb46f3271ea66b6e0e6953f`).
`git diff --name-only origin/main -- packages integrations/browser-use/src/cookieguard_browser_use/_node package.json package-lock.json`
exited 0 with no output: the engine and npm packages are unchanged.

The runbook's link-checking logic, with a count and a nonzero exit for broken paths,
plus a read of the exported SVG section labels, produced (exit 0):

```text
Checked 67 relative links/images in 7 Markdown files: no broken paths.
policy-dark-mobile.svg: section labels 1, 2, 3; no leading zeros.
policy-dark.svg: section labels 1, 2, 3; no leading zeros.
policy-light-mobile.svg: section labels 1, 2, 3; no leading zeros.
policy-light.svg: section labels 1, 2, 3; no leading zeros.
```

The first temporary tooling environment failed during `ensurepip` with `SIGABRT`
when `venv.create(..., with_pip=True)` copied the macOS interpreter. Creating a new
environment with `symlinks=True` succeeded; the packaging commands above all ran
there. No package verification failure was suppressed.

The `testpypi` and `pypi` GitHub environments were absent when inspected. The
maintainer must complete step 1 of [RELEASING.md](RELEASING.md) before any upload.
The release tag has not been created, so tagged links cannot yet be checked live.
No merge, tag, workflow dispatch, or upload was performed during these checks.

## PyPI publication — 2026-11-03

Published [cookieguard-browser-use 0.1.0b1](https://pypi.org/project/cookieguard-browser-use/0.1.0b1/)
from tag `browser-use-v0.1.0b1` (`ff3e27b`) through Trusted Publishing in
[run 41725841083](https://github.com/aiscihub/cookieguard-ai/actions/runs/41725841083).
Both `build` and `publish-pypi` succeeded. The maintainer approved omitting TestPyPI.

The release build ran `node integrations/browser-use/scripts/vendor_engine.mjs --registry`,
`python -m build`, `python -m twine check --strict dist/*`,
`python scripts/verify_metadata.py`, and `python scripts/verify_external.py`.
Selected actual output from the completed build log:

```text
Vendored @aiscihub/cookieguard-core, @aiscihub/cookieguard-playwright (workspace-verified-against-npm-registry).
Checking dist/cookieguard_browser_use-0.1.0b1-py3-none-any.whl: PASSED
Checking dist/cookieguard_browser_use-0.1.0b1.tar.gz: PASSED
cookieguard_browser_use-0.1.0b1-py3-none-any.whl: 16 absolute links/images; 15 pinned to browser-use-v0.1.0b1; no relative links.
cookieguard_browser_use-0.1.0b1.tar.gz: 16 absolute links/images; 15 pinned to browser-use-v0.1.0b1; no relative links.
Built cookieguard_browser_use-0.1.0b1-py3-none-any.whl (35 files) and cookieguard_browser_use-0.1.0b1.tar.gz; engine, manifest, and licenses present.
Installed 0.1.0b1 into a clean Python 3.12.16 venv outside the repository (browser-use 0.13.14, cdp-use 1.4.5).
Consumer test suite: 89 passed in 65.86s (0:01:05)
```

After publication, the PyPI JSON API's SHA-256 values matched the downloaded workflow
artifacts byte for byte:

```text
7661a88e0c36fa64d28772ea415cc379e0b15c5f10ba1dc2ce53ccb6aa952b84  cookieguard_browser_use-0.1.0b1-py3-none-any.whl
d5973e3cea04b73b2cf8f57618716f38893ad6152aba98d505da8ec1b3661ae0  cookieguard_browser_use-0.1.0b1.tar.gz
```

The [GitHub pre-release](https://github.com/aiscihub/cookieguard-ai/releases/tag/browser-use-v0.1.0b1)
includes both files and `SHA256SUMS`.

The wheel's manifest records `workspace-verified-against-npm-registry` and bundles
`@aiscihub/cookieguard-core@0.1.0` and `@aiscihub/cookieguard-playwright@0.1.0`.
`git diff ci-v0.1.0 browser-use-v0.1.0b1 -- packages/core packages/cli packages/playwright`
exited 0 with no output. No npm package changed or needs a coordinated release.

For a new Python 3.12.12 venv outside the repository,
`python -m pip --isolated install --disable-pip-version-check --index-url https://pypi.org/simple cookieguard-browser-use==0.1.0b1`
exited 0. Import verification and `python -m cookieguard_browser_use.demo` produced:

```text
Imported cookieguard-browser-use 0.1.0b1 from /tmp/cookieguard-pypi-release-206lrek1/consumer/lib/python3.12/site-packages/cookieguard_browser_use/__init__.py
Python 3.12.12; browser-use 0.13.14; cdp-use 1.4.5
CookieGuard for Browser Use: FAIL (exit code 1); evidence: server-declarations-and-browser-store
CookieGuard for Browser Use: PASS (exit code 0); evidence: server-declarations-and-browser-store
Demo exit code: 0
```

The demo used its scripted provider and local loopback apps, with telemetry and cloud
sync disabled. The full suite was not rerun locally after publication; the published
files match the artifacts that passed all 89 tests in the release workflow.
Fresh installs from PyPI on Python 3.11 and 3.13 remain unverified; those versions
passed the earlier integration CI. The automated project-page fetch returned a
`Client Challenge` page, so visual rendering still needs a browser check. The PyPI
JSON API and package downloads were available and verified successfully.

## Not verified

- The OpenAI and Browser Use Cloud branches of `examples/agent_login.py`, and models other than `claude-opus-5-5`.
- Windows, Browser Use cloud browsers, and other browser-use versions.
- Network denial inside the engine sandbox applies only on Node 25+. The tests assert
  it only there; on Node 24 the permission model does not restrict network access.
