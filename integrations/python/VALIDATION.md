# Validation record — cookieguard-browser-use

Newest release first. The 0.1.0b1 records below are kept unchanged as provenance.

## 0.1.0 publication — 2026-11-04

Published [cookieguard-browser-use 0.1.0](https://pypi.org/project/cookieguard-browser-use/0.1.0/)
from tag `browser-use-v0.1.0` (`d1b5de0`) through Trusted Publishing in
[run 41882052045](https://github.com/aiscihub/cookieguard-ai/actions/runs/41882052045).
Both `build` and `publish-pypi` succeeded after the maintainer approved the `pypi`
environment. The tag-triggered run does not use TestPyPI.

Selected actual output from the completed build log, which contains no canary-prefixed line:

```text
Vendored @aiscihub/cookieguard-core, @aiscihub/cookieguard-playwright (workspace-verified-against-npm-registry).
Checking dist/cookieguard_browser_use-0.1.0-py3-none-any.whl: PASSED
Checking dist/cookieguard_browser_use-0.1.0.tar.gz: PASSED
cookieguard_browser_use-0.1.0-py3-none-any.whl: 18 absolute links/images; 16 pinned to browser-use-v0.1.0; no relative links.
cookieguard_browser_use-0.1.0.tar.gz: 18 absolute links/images; 16 pinned to browser-use-v0.1.0; no relative links.
Built cookieguard_browser_use-0.1.0-py3-none-any.whl (35 files) and cookieguard_browser_use-0.1.0.tar.gz; engine, manifest, and licenses present.
Installed 0.1.0 into a clean Python 3.12.15 venv outside the repository (browser-use 0.13.14, cdp-use 1.4.5).
Consumer test suite: 89 passed in 73.84s (0:01:13)
  CookieGuard for Browser Use: FAIL (exit code 1); evidence: server-declarations-and-browser-store
  CookieGuard for Browser Use: PASS (exit code 0); evidence: server-declarations-and-browser-store
Installed 0.1.0 from cookieguard_browser_use-0.1.0.tar.gz (built from source); engine hashes verified. Demo:
  CookieGuard for Browser Use: FAIL (exit code 1); evidence: server-declarations-and-browser-store
  CookieGuard for Browser Use: PASS (exit code 0); evidence: server-declarations-and-browser-store
```

The files downloaded from PyPI match the SHA-256 values in PyPI's JSON API, and they are
byte-identical to the workflow's `cookieguard-browser-use-dist` artifact:

```text
d2d2987e5d46eb78dbab7c4ca4db5075a636978ff92ce424fbb334fb3e1948b6  cookieguard_browser_use-0.1.0-py3-none-any.whl
45cb596a3cb1a4cdbfa5a071df28ea97e8d292c0d90b7b6593b88c5482230e8a  cookieguard_browser_use-0.1.0.tar.gz
```

PyPI's integrity API lists one publish attestation for each file, from the GitHub publisher
`aiscihub/cookieguard-ai`, workflow `publish-browser-use.yml`, environment `pypi`.
The [GitHub release](https://github.com/aiscihub/cookieguard-ai/releases/tag/browser-use-v0.1.0)
includes both files and `SHA256SUMS`, and it is the repository's latest release.

### Fresh installs from PyPI

On macOS 26.6.2 (arm64), each Python created a new venv outside the repository and ran
`python -m pip --isolated install --disable-pip-version-check --no-cache-dir --index-url https://pypi.org/simple cookieguard-browser-use`,
with no `--pre` and no version pin. uv 0.13.7 provided CPython 3.11.18 and 3.13.18 in a
temporary directory; 3.12.12 is a local interpreter.

| Check | Python 3.11.18 | Python 3.12.12 | Python 3.13.18 |
| --- | --- | --- | --- |
| Install | Exit 0; `cookieguard-browser-use 0.1.0` | Exit 0; `0.1.0` | Exit 0; `0.1.0` |
| Dependencies | browser-use 0.13.14, cdp-use 1.4.5 | Same | Same |
| Wheel in pip's report | `files.pythonhosted.org`, SHA-256 `d2d2987e…1948b6` | Same file | Same file |
| Public API imports | `CookieGuardAudit`, `Agent`, `BrowserProfile`, `BrowserSession`, `Tools`: passed | Passed | Passed |
| Import location | The fresh venv's `site-packages` | Same | Same |
| `python -m pip check` | `No broken requirements found.` | Same | Same |
| `python -m cookieguard_browser_use.demo` | Insecure FAIL (exit 1), secure PASS (exit 0); exit 0 | Same | Same |

The demo used its scripted provider and local loopback apps, with telemetry and cloud sync
disabled. Browser Use chose the browser; Google Chrome 156.0.8078.81 was installed. No demo
output contained a canary-prefixed line. The full suite was not rerun locally; the
published files are the artifacts that passed all 89 tests in the release workflow.

### Published PyPI page

PyPI's JSON API for 0.1.0 reports version `0.1.0`, `Requires-Python >=3.11`, and a
`text/markdown` description. Every link into this repository is pinned to
`browser-use-v0.1.0`. There are no relative links, and the description mentions neither
`--pre` nor `0.1.0b1`.

The rendered page was not inspected. PyPI served its `Client Challenge` page to headless
Chrome for Testing, and also to Chrome for Testing and Google Chrome with windows when
Playwright drove them. A person's visual check remains, as tracked in [RELEASING.md](RELEASING.md#done-when-010).

## 0.1.0 release candidate — 2026-11-04

Prepared on branch `release/browser-use-0.1.0` from `main` at `6875489`. Nothing was
published, and no release tag was pushed.

Local environment: macOS 26.6.2 (arm64), Python 3.12.12, Node.js 26.10.0, browser-use 0.13.14,
cdp-use 1.4.5, pydantic 2.13.5, Google Chrome 156. All runs used loopback demo apps and synthetic
`CGBU_CANARY_*` session tokens. No AI provider was called.

| Gate | Command | Result |
| --- | --- | --- |
| Code unchanged since beta | `git diff browser-use-v0.1.0b1 -- integrations/browser-use/src packages/core packages/playwright` | Only `__version__` changed |
| Engine provenance | `node scripts/vendor_engine.mjs --registry` | Byte-identical to npm `@aiscihub/cookieguard-core@0.1.0` and `@aiscihub/cookieguard-playwright@0.1.0` |
| Python suite | `pytest -q` (fresh venv) | **89 passed**, 0 warnings, 2m44s |
| Repository release gate | `npm run release:check` | Exit 0, all steps. Source credentials (231 files), licenses (131 entries), npm advisories 0, 38/38 Node tests, 8/8 Playwright, packaged CLI/Playwright/MCP consumers, leakage |
| Wheel install | `scripts/verify_external.py` | Clean venv outside the repo: 89 passed; demo insecure FAIL (exit 1) / secure PASS (exit 0); no canary in produced files |
| Sdist install | `scripts/verify_external.py` (new sdist path) | pip built the sdist from source in a second clean venv; engine hashes verified; demo FAIL/PASS |
| Python dependency audit | `pip-audit` 2.10.1 on the 104 runtime packages of a fresh install | Advisories only in Browser Use's exact pins: anyio 4.12.1 (2), mcp 2.1.1 (4), pillow 12.3.0 (39), pypdf 6.16.2 (26). Not imported by CookieGuard; documented as inherited |

After the version change, the same gates were rerun on the 0.1.0 artifacts themselves:

| Gate | Command | Result |
| --- | --- | --- |
| Build and description | `python -m build`, `twine check --strict dist/*`, `scripts/verify_metadata.py` | Both PASSED. `Version: 0.1.0`. 18 absolute links/images, 16 pinned to `browser-use-v0.1.0`. No `--pre` or `0.1.0b1` in the description |
| Tag guard | `GITHUB_REF=refs/tags/browser-use-v0.1.0` / `…-v0.1.0b1 verify_metadata.py` | Exit 0 for the matching tag; exit 1 for a mismatched tag |
| Wheel install | `scripts/verify_external.py` | Clean venv: **89 passed**; demo FAIL (exit 1) / PASS (exit 0); no canary in produced files |
| Sdist install | `scripts/verify_external.py` | Built from source; engine hashes verified; demo FAIL / PASS |
| Docs | Link and anchor check | 143 relative links and anchors in 11 files; none broken |

Hosted CI for the release branch is recorded on its pull request.

## 0.1.0b1 beta records — 2026-11-03

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
The first automated project-page fetch returned a `Client Challenge` page. A later
Chrome inspection and fresh installs on Python 3.11 and 3.13 completed the remaining
release checks, as recorded below.

## Final release checks — 2026-11-03

Both remaining release checks passed. No full test suite was rerun and no package
was republished. The following checks used the existing PyPI `0.1.0b1` release.

### Fresh Python 3.11 and 3.13 installs

uv 0.13.7 installed CPython 3.11.18 and 3.13.18 into a temporary directory. Each
runtime created its own new venv outside the repository. For each interpreter,
`python -m pip --isolated install --pre --disable-pip-version-check --index-url https://pypi.org/simple cookieguard-browser-use`
exited 0. Separate temporary cache directories and pip JSON reports were also used.

| Check | Python 3.11.18 | Python 3.13.18 |
| --- | --- | --- |
| Installed package | `cookieguard-browser-use 0.1.0b1` | `cookieguard-browser-use 0.1.0b1` |
| Browser Use dependency | `0.13.14` | `0.13.14` |
| CDP dependency | `1.4.5` | `1.4.5` |
| Public API imports | `CookieGuardAudit`, `Agent`, `BrowserProfile`, `BrowserSession`, `Tools`: passed | Same imports: passed |
| Import location | Fresh venv's `lib/python3.11/site-packages` | Fresh venv's `lib/python3.13/site-packages` |
| `python -m pip check` | Exit 0: `No broken requirements found.` | Exit 0: `No broken requirements found.` |

Both pip reports identify the wheel downloaded from `files.pythonhosted.org`, with
SHA-256 `7661a88e0c36fa64d28772ea415cc379e0b15c5f10ba1dc2ce53ccb6aa952b84`:
the same file verified by the release workflow. Imports were checked against each
venv's resolved path to exclude an accidental import from the source checkout.
The dependency checks emitted a warning that the default pip cache was not writable;
pip disabled that cache and both checks succeeded.

Together with the Python 3.12 PyPI installation and demo above, fresh installs from
PyPI are now verified on all three supported Python minor versions.

### Published PyPI page

Opened the public [0.1.0b1 page](https://pypi.org/project/cookieguard-browser-use/0.1.0b1/)
in an ordinary, temporary Chrome session through Playwright. The page returned
HTTP 200 and rendered its project description. Desktop (1440 px) and mobile
(390 px) screenshots were inspected.

- The policy SVG loaded at its natural size of 760 × 640; the demo GIF loaded at
  1000 × 563. Two screenshots seven seconds apart confirmed the GIF changes frames.
- The page displays the version, Python `>=3.11`, MIT license, and installation
  command. The description no longer says the package is unpublished.
- All seven unique release-tagged GitHub documentation links opened successfully.
  Six returned HTTP 200 immediately. The overview initially returned HTTP 429;
  after a pause, a normal Chrome navigation returned HTTP 200. No link was changed
  to avoid the rate limit.
- The policy diagram and sampled demo frames use section numbers without leading
  zeros. The mobile page uses the scaled desktop SVG fallback because PyPI removes
  the responsive `<picture>` sources; code blocks remain horizontally scrollable.
- Two PyPI advertising requests were blocked by the browser's cross-origin policy.
  The project description, package images, and documentation links were unaffected.

Local screenshots, install logs, pip reports, link results, and inspection scripts
are saved under `artifacts/browser-use/final-release-checks/` (not distributed with
the package).

## Not verified

- The OpenAI and Browser Use Cloud branches of `examples/agent_login.py`, and models other than `claude-opus-5-5`.
- Windows, Browser Use cloud browsers, and other browser-use versions.
- Network denial inside the engine sandbox applies only on Node 25+. The tests assert
  it only there; on Node 24 the permission model does not restrict network access.

## cookieguard 0.1.0 (alias) publication — 2026-11-06

Published by `publish-cookieguard.yml` with PyPI Trusted Publishing from tag
`cookieguard-v0.1.0` (`3b6a858`, #31), run
[42261140999](https://github.com/aiscihub/cookieguard-ai/actions/runs/42261140999).

- Build job: `twine check --strict` passed for the wheel and sdist, and a clean venv
  installed the wheel against the published `cookieguard-browser-use` 0.1.0:
  `cookieguard 0.1.0 -> cookieguard-browser-use 0.1.0`.
- Two earlier deployment attempts failed without uploading anything:
  - from `main`: the `pypi` environment only deployed `browser-use-v*` tags. The
    maintainer approved adding a `cookieguard-v*` tag rule; required reviewers are unchanged.
  - from the tag, attempt 1: `invalid-publisher`, because the pending publisher did not
    exist yet. After the maintainer added it, attempt 2 succeeded.
- Uploaded files are byte-identical to the verified workflow artifact:

| File | SHA-256 |
| --- | --- |
| `cookieguard-0.1.0-py3-none-any.whl` | `5fe59bf96bbb4e979aff18f03da1b590bfa26110216e47d331548294e632f838` |
| `cookieguard-0.1.0.tar.gz` | `32edd77322d7e20c714d6584fd98f0a1f92a8894e2beeb4d2f4ed786433e0ddf` |

- `pip install cookieguard==0.1.0` from PyPI in a clean Python 3.12 venv on macOS arm64
  installed `cookieguard-browser-use` 0.1.0, and `cookieguard.CookieGuardAudit is
  cookieguard_browser_use.CookieGuardAudit` was `True`.

## cookieguard 0.2.0 and cookieguard-browser-use 0.2.0 publication — 2026-11-06

Published together by `publish-cookieguard.yml` from tag `cookieguard-v0.2.0` (`1fd52de`, #36),
run [42301325198](https://github.com/aiscihub/cookieguard-ai/actions/runs/42301325198). `main` CI
passed on that commit before tagging.

- Build job: `verify_external.py` (clean consumer, tests, real-browser demo, sdist), `twine check
  --strict`, `verify_metadata.py` (links pinned to the tag), the version-lockstep check, and
  `verify_upgrade.py` all passed.
- Attempt 1 failed at upload with `403 Invalid API Token: OIDC scoped token is not valid for project
  'cookieguard'`: the two projects' trusted publishers were not identical, so the token covered only
  `cookieguard-browser-use`. The upload stopped at the first file and published nothing. After the
  maintainer made both publishers identical (`publish-cookieguard.yml`, environment `pypi`),
  attempt 2 uploaded all four files.
- PyPI files are byte-identical to the verified workflow artifact. Both wheels have PyPI provenance
  attestations.

| File | SHA-256 |
| --- | --- |
| `cookieguard-0.2.0-py3-none-any.whl` | `46906ddcbd3396d272bb7fab564c667faef14a46f848fea4ffd5add3f3b621ed` |
| `cookieguard-0.2.0.tar.gz` | `3e08609b863a28754130a1a3fe8fabcc1fdfc6f195a78a7417f87b8953052f59` |
| `cookieguard_browser_use-0.2.0-py3-none-any.whl` | `0e433a555978e77b9b1be2c6c3627215b9230282eb347c4af60e71115ead1fea` |
| `cookieguard_browser_use-0.2.0.tar.gz` | `b4cf7bad1e937800d9bdde9a09e12e646bd3a89a7f0bc45bca41a8d67e7f71a3` |

- Fresh `pip install cookieguard==0.2.0` from PyPI on macOS arm64: Python 3.11.14 and 3.12.16
  imported it, verified the engine, and resolved `CookieGuardAudit` from `cookieguard.browser_use`.
  On 3.12 the real-browser demo returned FAIL (exit 1) for the insecure login and PASS (exit 0) for
  the secure one. Python 3.13 was covered by CI on the release commit, not by a PyPI install.
- `verify_upgrade.py` with PyPI packages only: a fresh `cookieguard-browser-use` 0.2.0 install, and
  upgrades from `cookieguard-browser-use` 0.1.0 and `cookieguard` 0.1.0. Each gave the same objects
  under both names, no stale 0.1 files, engine verification, a clean `pip check`, and a working
  `python -m cookieguard_browser_use.demo`.
