# CookieGuard CI validation

Date: **2026-10-17**. Published release: **0.1.0 public beta**. Local platform: macOS arm64.
Primary runtime: **Node v24.22.0** (LTS); development smoke runs also used
v26.10.0. Playwright **1.64.1**, Chromium **156.0.8078.4** (revision 1248),
ONNX Runtime Node **1.30.0**. All audit targets were local fixtures.
Hosted verification also passed on **Ubuntu 24.04.5 x64, Node v24.21.0**, with
the same Playwright and Chromium versions.

## Observed results

| Check | Result |
| --- | --- |
| Clean source install with exact lockfile | `npm ci` and automatic build succeeded in a new temporary source copy without node_modules or generated vendor files |
| Build / lint / public declarations | Passed |
| Node unit and integration suite | **29 passed**, no skipped tests; includes explicit extension compatibility and release-output privacy tests |
| Playwright Chromium suite | **8 passed**, including expected policy failures and browser rejection |
| CLI executable | Secure case exit 0; confirmed missing HttpOnly exit 1; expected authentication cookie absent exit 2 |
| Text and JSON output | Produced successfully; file content matches JSON stdout; CLI files mode 0600 |
| Local Action runner | Pass, fail, and incomplete outputs verified; sanitized JSON and escaped summary inspected |
| Action production installation | `--omit=dev --omit=optional --ignore-scripts` installs only three workspace packages; no ONNX/Playwright runtime; build and runner work |
| Packed consumer install | Three tarballs install offline in an empty project/cache outside the monorepo; CLI text/JSON verify exit 0/1/2 without browser/native dependencies; installed Playwright adapter verifies 0/1/2 in Chromium after adding a separately packed runtime |
| Dependency advisory query | `npm audit --json` reported **0 known vulnerabilities** at verification time |
| Dependency licenses | **121** locked package entries use reviewed expressions: MIT 70, Apache-2.0 36, BSD-2-Clause 6, ISC 5, BSD-3-Clause 2, BlueOak-1.0.0 1, MIT/CC0-1.0 1 |
| Source credential check | **155** source files checked; no supported high-confidence credential patterns found |
| Sentinel disclosure | No sentinel found in checked reports/stdout/stderr/action outputs/summaries or final generated artifacts |
| Hosted GitHub workflow | **Passed** on the feature branch and PR: clean Linux install, Chromium, packaged consumers, all three composite Action outcomes, summaries, artifact upload, and leakage checks |

The full source tree and lockfile are needed; generated engine/license files are
reconstructed during build. Package smoke verification also tests outside the
workspace dependency layout.

## Hosted evidence

[PR #4](https://github.com/aiscihub/cookieguard-ai/pull/4) initially passed its
[hosted release gate](https://github.com/aiscihub/cookieguard-ai/actions/runs/39087460202)
for source commit `3a7e3ae044c0a164007ac09ff30680b7b366d8f2` on October 17, 2026
Pacific time (October 18 UTC). Both push and pull-request runs passed. Any later
PR commit must pass again before merge.

The hosted suite passed 29 Node tests and 8 Chromium tests. Installed tarballs
passed all nine CLI text/JSON and Playwright scenario checks. The composite Action
uploaded reports with statuses `passed`, `failed`, and `incomplete`; its policy
steps returned 0, 1, and 2 respectively. The workflow explicitly asserted the two
expected failures rather than treating an incomplete audit as success.

The downloaded reports and release evidence were inspected. Missing HttpOnly
produced confirmed rule CG001, and the incomplete report contained
`expected-auth-cookie-not-observed`. The hosted advisory query reported zero
known vulnerabilities, and its 121-entry license inventory matched the local
review. The complete 150,406-byte hosted log and downloaded artifacts contained
no sentinel values. Artifact retention is seven days; the linked run and source
identify the reproducible validation even after artifacts expire.

## Published release verification

[PR #6](https://github.com/aiscihub/cookieguard-ai/pull/6) finalized the npm names
and release procedure. Its
[hosted release gate](https://github.com/aiscihub/cookieguard-ai/actions/runs/39097092319)
passed for source commit `32f39f489517031d9895801b435d391f740cc335`; the merged
commit `12a09fe322b135ac2a5aec45cae1f880b717575f` has the same source tree and
[passed on main](https://github.com/aiscihub/cookieguard-ai/actions/runs/39097181292).
Both runs passed 29 Node tests, 8 Chromium tests, the nine packaged-consumer
outcomes, and the composite Action's 0/1/2 checks. Dependency advisories remained
at zero, the 121-entry license inventory passed review, and credential and
sentinel checks passed. Downloaded Action reports confirmed the expected
`passed`, `failed`, and `incomplete` statuses.

The exact tested tarballs were published as `@aiscihub/cookieguard-core@0.1.0`,
`cookieguard-ci@0.1.0`, and `@aiscihub/cookieguard-playwright@0.1.0`, with the
`beta` dist-tag. Registry integrity values match the local and hosted tarballs.
The [GitHub public beta](https://github.com/aiscihub/cookieguard-ai/releases/tag/ci-v0.1.0)
tags the merged source commit above and includes those tarballs, SHA-256 checksums,
and a release manifest. The extension's existing stable release is preserved.

After publication, `node scripts/verify-packages.js --registry` installed all
three packages in a fresh project/cache outside the monorepo. It passed all nine
outcomes: CLI text and JSON exits 0/1/2, plus Chromium adapter exits 0/1/2. The
initial CLI install contained no native model or browser runtime. Reports,
stdout, and stderr contained no sentinel values. Evidence is recorded in
`artifacts/published/results.json` and its companion reports.

A separate empty project, empty npm user configuration, and fresh cache verified
unauthenticated `npx cookieguard-ci@beta --version` as `0.1.0`. Scanning the local
secure, missing-HttpOnly, and absent-authentication-cookie fixtures with that
installed executable returned 0, 1, and 2. Its JSON reports also passed sentinel
checks. All targets were controlled local fixtures.

## Independent consumer repository

[aiscihub/cookieguard-ci-consumer](https://github.com/aiscihub/cookieguard-ci-consumer)
is a separate Git repository containing fixtures, an independent npm lockfile,
and consumer checks. Its
[GitHub-hosted Linux run](https://github.com/aiscihub/cookieguard-ci-consumer/actions/runs/39099078667)
passed all three jobs at commit `7ef51b1386f1bc44d28cac8e51734bedbf877439`.
The npm packages and Action remain in the original toolkit repository.

| Consumer check | Observed result |
| --- | --- |
| Public npm installation | Exact `0.1.0` packages install with `--omit=dev --omit=optional --ignore-scripts`. No browser, ONNX, TypeScript, or ESLint runtime is installed. CLI text/JSON return 0/1/2 for secure, missing-HttpOnly, and absent-authentication cases. |
| Login-page limitation | Fetching a page whose JavaScript creates the session returns exit 2 in both CLI formats; the CLI does not execute that login flow. |
| Production source build and packaging | A clean checkout of `ci-v0.1.0` installs with the same omission flags and builds successfully. All three packed tarballs exactly match published integrities, install offline into another empty project/cache, and repeat the CLI outcomes. |
| Published Playwright adapter | Ordinary npm Playwright and Chromium complete the fixture's JavaScript login and session assertions. Separate browser processes return 0/1/2 with the published adapter. |
| Remote released Action | The workflow uses `aiscihub/cookieguard-ai/action@12a09fe322b135ac2a5aec45cae1f880b717575f`, verifies actual failure enforcement for exits 1/2, and uploads all three reports. |

There are **30 checked outcomes**: eight CLI text/JSON cases for each of the
registry, production source, and offline tarball installs, three Chromium
processes, and three remote Action invocations. All matched their expected
results. The complete hosted log and all **39 downloaded artifact files** were
checked for both the consumer sentinel and the toolkit's original sentinels;
none were found. Downloaded tarballs match the release's SHA-256 checksums.
Hosted artifacts have seven-day retention.

The consumer's locked dependencies comprise three MIT and two Apache-2.0 entries;
the local advisory query returned zero known vulnerabilities. Its source
credential check passed. These consumer checks also passed locally on Node 24
before the repository was published.

During this README review, public npm metadata confirmed all three package names,
version `0.1.0`, the `beta` tag, and maintainer `aiscihub`. The current README's
relative file links resolve, and the tracked source contains no editor-specific
resource URIs. Historical research data remains unchanged. Consumer outcomes
measure controlled cookie-policy behavior, independently of model research metrics.

## Controlled benchmark

`scripts/benchmark.js` independently specifies six expected cases. It does not
reuse the original synthetic training dataset. The recorded measurements are in
[CI_BENCHMARK.json](CI_BENCHMARK.json).

| Case | Expected / observed exit | Confirmed violations | Review items |
| --- | --- | --- | --- |
| A: Secure, HttpOnly, declared Strict; identified auth | 0 / 0 | 0 | 0 |
| B: Identified auth missing HttpOnly | 1 / 1 | 1 | 0 |
| C: Identified auth missing Secure | 1 / 1 | 1 | 0 |
| D: Preference cookie | 0 / 0 | 0 | 0 |
| E: Unconfirmed auth hint | 0 / 0 | 0 | 4 |
| F: Store-only identified auth, declaration unknown | 0 / 0 | 0 | 1 |

All six expectations matched. Two independently specified flag violations were
confirmed. The single non-authentication control produced zero confirmed false
positives. The hint remained a candidate, and the store-only case retained an
unknown declaration. Reordered identical inputs produced identical JSON. Both
text and JSON were searched for sentinel session tokens.

Twenty in-process HTTP scans alternated secure and missing-HttpOnly endpoints:
minimum **0.464 ms**, median **0.637 ms**, p95 **1.209 ms**, maximum **7.253 ms**.
These timings include HTTP scanning and policy evaluation, exclude Node/browser
startup and login, and are illustrative local measurements, not a throughput SLA.
Re-running the benchmark will change timings. This tiny controlled set cannot
establish real-world precision, recall, or generalization.

## Commands actually exercised

With Node 24 first on PATH:

```bash
ONNXRUNTIME_NODE_INSTALL=skip npm ci --no-audit --no-fund
npx --no-install playwright install chromium
npm run check
npm run release:check
npm run benchmark
node scripts/verify-packages.js
node scripts/verify-packages.js --registry
node scripts/check-artifacts.js
npm audit --json
git diff --check
```

`npm run check` runs build, ESLint, public API type checking, `npm test`, and
`npm run test:playwright`. The workstation's browser cache contained the exact
pinned Chromium revision; the documented installation command completed without
requiring a new browser download. The hosted Linux workflow downloaded the pinned
Chromium revision and successfully installed its OS dependencies with `--with-deps`.

The actual verification used a temporary Node 24 binary because the workstation
default is Node 26. No system Node installation was modified. A separate clean
copy also exercised these production-only commands:

```bash
npm ci --omit=dev --omit=optional --ignore-scripts --no-audit --no-fund
node scripts/build.js
```

With `npm run demo` running in another terminal, these CLI commands were exercised:

```bash
npx --no-install cookieguard-ci scan http://127.0.0.1:3000/secure --auth-cookie session_id
npx --no-install cookieguard-ci scan http://127.0.0.1:3000/missing-httponly --auth-cookie session_id
npx --no-install cookieguard-ci scan http://127.0.0.1:3000/missing-secure --auth-cookie session_id --format json --output artifacts/demo-report.json
```

The first passed; the other two deliberately returned 1. The Action entry point
was also run with production-only dependencies against the missing-HttpOnly app:
it emitted `exit-code=1` after writing its report and summary. Unit tests execute
all three Action outcomes, including an absent expected authentication cookie.
The composite YAML and example workflow parsed
successfully. The hosted run separately verified setup, all three policy outcomes,
report uploads, and summary generation.

## Regression and privacy coverage

- Original extension fixtures exercise browser-global versus Node feature values,
  feature-vector ordering, and rule classification. Metadata verifies all 38
  names. Only a guarded export is added to the engine; popup, model weights,
  Python code, evaluation files, and archived original README are preserved.
- A real ONNX inference exercises the unchanged model. Mode/uncalibrated origin,
  candidate-only decisions, telemetry opt-out, fixed error messages, and absence
  of fallback are checked. No runtime session files are generated after disabling
  telemetry. Native runtimes initialized by callers before the adapter remain a
  caller responsibility; set `ORT_DISABLE_TELEMETRY=1` at process startup.
- Header parsing covers separate fields, Expires/Max-Age precedence, deletion,
  malformed/duplicate attributes, strict SameSite declaration syntax, and prefixes.
  Chromium tests confirm rejected prefix and None-without-Secure instructions are
  retained as header evidence rather than described as accepted store cookies.
- Collector tests cover existing authenticated contexts, scoped/path cookies,
  conflicting headers, context closure, overflow, timeouts, and throwing header/
  store reads. Exceptions containing sentinels are replaced with fixed failures.
- CLI tests cover loopback-only defaults, unsupported schemes, credentials/query
  rejection, exact-origin authorization validation, private-address rejection,
  redirect boundaries/loops, timeout, status failures, oversized/invalid fixtures,
  nested legacy input, report permissions, and real process exit codes.
- Report tests reject arbitrary render inputs and ignore injected nested fields
  or post-evaluation mutations. Action outputs contain only numeric status and a
  generated sanitized report path; summaries escape metadata.

## Issues found and resolved during verification

The execution sandbox initially prohibited loopback binding (`EPERM`), so local
server/browser checks were run with the required execution permission. An initial
Playwright demo path was resolved relative to the config directory and corrected.
A later test run correctly refused port 3000 while a manual demo was running;
the demo was stopped before rerunning. Tests were not weakened or set to reuse
an unrelated server.

The current ONNX runtime's default telemetry was discovered during the first
smoke test and disabled before native initialization. Production-only npm install
initially retained optional peers from the workspace lockfile; adding
`--omit=optional` removed them. A packaging assertion initially mistook npm's
empty optional-peer declarations for installed binaries; it now directly checks
that the runtime directories are absent. Final checks passed after these fixes.

## Limits and release gates

No real-world labeled auth dataset was available. No public site was scanned.
The original extension UI was not manually inspected in Chrome during this task;
its unchanged UI sources and automated engine regressions provide compatibility
evidence, not a full UI certification. Firefox, WebKit, and Windows remain
unverified. Hosted Linux and Chromium are verified as described above.

HTTP mode cannot authenticate or prove browser acceptance. Cookie metadata does
not establish exploitability, CSRF defenses, server revocation, or original
session lifetime. Prefix transport checks recognize the tested loopback exception.
There is no public-suffix validation; malformed, partitioned, or uncertain scopes
are conservative. The collector does not sandbox caller navigation or capture
APIRequestContext headers. Comparisons exclude ambiguous/changed scopes. Future
releases must repeat the gates in [CI_RELEASE.md](CI_RELEASE.md).
