# CookieGuard CI validation

Date: **2026-10-17**. Release target: **0.1.0 public beta**. Local platform: macOS arm64.
Primary runtime: **Node v24.22.0** (LTS); development smoke runs also used
v26.10.0. Playwright **1.64.1**, Chromium **156.0.8078.4** (revision 1248),
ONNX Runtime Node **1.30.0**. All audit targets were local fixtures.

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
| Hosted GitHub workflow | Pending feature-branch and PR runs; merge is gated on passing Linux, Chromium, packaged-consumer, and composite Action checks |

The full source tree and lockfile are needed; generated engine/license files are
reconstructed during build. Package smoke verification also tests outside the
workspace dependency layout.

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
node scripts/check-artifacts.js
npm audit --json
git diff --check
```

`npm run check` runs build, ESLint, public API type checking, `npm test`, and
`npm run test:playwright`. The workstation's browser cache contained the exact
pinned Chromium revision; the documented installation command completed without
requiring a new browser download. Linux `--with-deps` installation is specified
in the workflow but was not executed on this macOS host.

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
successfully. This does not verify GitHub's hosted upload service or runner UI.

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
No npm publication, release tag, or repository setting has been changed.
The original extension UI was not manually inspected in Chrome during this task;
its unchanged UI sources and automated engine regressions provide compatibility
evidence, not a full UI certification. Firefox, WebKit, Windows, and hosted Linux
workflow execution remain unverified until the hosted gate completes.

HTTP mode cannot authenticate or prove browser acceptance. Cookie metadata does
not establish exploitability, CSRF defenses, server revocation, or original
session lifetime. Prefix transport checks recognize the tested loopback exception.
There is no public-suffix validation; malformed, partitioned, or uncertain scopes
are conservative. The collector does not sandbox caller navigation or capture
APIRequestContext headers. Comparisons exclude ambiguous/changed scopes. Before
publication, complete the gates in [CI_RELEASE.md](CI_RELEASE.md).
