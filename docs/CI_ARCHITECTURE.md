# CookieGuard CI architecture

## Audit of the original project

The starting point is commit `c497718`. The standalone extension is the source of
truth for the existing JavaScript classifier. No training data, model weights,
evaluation files, Python code, or popup behavior are changed by this work.

| Component | Reuse / boundary |
| --- | --- |
| `extension-standalone/engine.js`: `extractFeatures`, `featuresToArray`, `classifyRuleBased` | Reuse unchanged, through a guarded CommonJS export. A build copies the canonical file into the core package; no hand-maintained classifier fork. |
| `scoreRisk`, `explainPrediction`, `simulateAttacks` | Remain available to the extension. Their probability gate and attack claims are unsuitable for CI policy enforcement. CI has independent, deterministic configuration rules and conservative explanations, not a second classification algorithm. |
| `loadModel`, `classifyWithONNX` | Depend on the `ort` browser global, `chrome.runtime.getURL`, fetch, and logging. Node uses an explicit optional ONNX Runtime Node adapter, with the same 38-feature order and shipped model. No silent fallback. |
| `analyzeAllCookies` | Returns `cookie.value` and the supplied `context`, including arbitrary nested fields. Never called or serialized by CI. Legacy result imports read only each `cookie` through the normalization allowlist. |
| `popup.js` | Chrome cookies/storage/tabs/runtime APIs and DOM integration; stays in the extension. Its legacy JSON export includes values. CI never invokes that export and does not claim to fix its historical privacy limitations. |
| `backend/` | Python implementation includes scaling, calibration, and named-cookie overrides. Node matches the extension pipeline, not Python's extra calibration. No backend is required. |
| `models/` and `extension-standalone/model/` | Preserve research artifacts. Synthetic metrics and inconsistent historical evaluation versions are not CI detection accuracy. |
| `test/` | Existing JSON exports provide feature/classification regression inputs. Dates are historical, so they are not modern lifetime-policy ground truth. Browser tester and Python harness remain available. |

Value-derived model features are length, entropy bucket, JWT/hex/base64 shape,
padding, numeric shape, and length bucket. They can be calculated transiently;
neither values nor feature vectors need to enter an audit report. JavaScript
garbage collection does not provide cryptographic memory erasure.

## Small package structure

- `@cookieguard/core`: normalization, existing-engine triage, policy, comparable
  baseline checks, sanitized text/JSON reporting; no runtime dependencies.
- `cookieguard-ci`: bounded HTTP response-header scanner and fixture CLI; no
  browser or model download needed. It does not execute JavaScript or log in.
- `@cookieguard/playwright`: passive collector on a caller-owned browser context.
  Login, credentials, browser installation, and network authorization belong to
  the existing test. The collector does not navigate or export storage state.
- `action/`: composite action using the local CLI, JSON artifact, and escaped
  Step Summary. Inputs enter the runner via environment variables, not shell
  interpolation. The action does not need a GitHub token.

JavaScript ESM with maintained public declarations avoids a compilation framework.
Node 24 LTS is the supported baseline. Build copies only the canonical engine and
license into distributable packages and validates package entry points. npm
workspaces and an exact lockfile supply reproducible installation.

## Evidence and decisions

Normalization emits a new allowlisted, value-free object. Cookie-store SameSite
is an **effective value**; the declaration is unknown unless a matching response
header was observed. A header is evidence of a server instruction, not proof of
browser acceptance. Header observations and current browser-store observations
remain distinguishable; rejected/deleted instructions must not be described as
active sessions. Ambiguous/duplicate attributes receive review, not invented
certainty. Partitioned cookies and uncertain matching are handled conservatively.

Only exact developer-supplied authentication names or explicit, scope-matched
developer validation of an authentication flow confirm identity. Seeing a cookie
appear or rotate during login is insufficient by itself. Existing rules and
optional ONNX outputs supply labeled, uncalibrated triage only. Tracking/preference
triage never creates confirmed authentication failures. Unknown identity creates
a review item. Missing flags mean exposure or policy violation, not demonstrated
XSS, CSRF, or subdomain takeover.

Policies are explicit: HttpOnly/Secure required, allowed declared SameSite values,
maximum lifetime, optional host-only scope, and failure severity. Missing SameSite
declaration is review unless explicit-declaration policy is enabled and headers
prove absence. Domain sharing is review by default. Expiry means remaining client
lifetime, not server session validity. Prefix checks require header evidence.
Baselines compare matching origin, name, domain, path, source, confirmed identity,
and compatible policy; unknown or unmatched evidence is not a security regression.

## Scan and privacy boundaries

HTTP CLI accepts HTTP(S) loopback literals or exactly `localhost` by default;
localhost is pinned to loopback. Nonlocal access requires the exact origin in
`--allow-origin`, representing the developer's authorization. Redirects stay on
the initial origin, even when another origin was authorized. DNS is resolved once
per scan and pinned; nonlocal names resolving to private/special addresses are
rejected. No cookies, credentials, or authorization headers are sent. There is no
page crawler. Time, redirects, headers, fixture bytes, and cookie counts are
bounded. Errors are fixed messages; URLs are reported as origins only. A missing
expected auth cookie, invalid input, or incomplete collection returns exit 2.

Reports contain only selected metadata, classifications, policy evidence, and
fixed explanations. No input object spreading, arbitrary exception text, raw
headers, telemetry, HAR, traces, or browser storage exports. Text/Markdown escapes
untrusted metadata. Report files are created with owner-only permissions.
Cookie metadata itself can identify an application; review artifacts before
sharing. Caller-enabled Playwright traces and application logs are outside this
tool's control.

## Verification and limits

Independent local fixtures cover secure/missing flags/non-auth/unknown/store-only
cases, malformed and rejected headers, scope, expiry, policy thresholds, baseline
comparability, scan boundaries, and sentinel-token non-disclosure. Extension
regressions compare browser-global and CommonJS feature vectors and classifiers
on original fixtures. Optional model tests verify feature ordering and real
inference without treating synthetic results as real-world accuracy.

The header scanner cannot establish actual authentication or browser acceptance.
The Playwright collector is a passive observer, not a network sandbox. There is
no public suffix inference or automatic CSRF assessment. No real-world labeled
validation set is available for this release. See `CI_VALIDATION.md` for measured
results and remaining release checks.

References: [Node release schedule](https://github.com/nodejs/Release),
[Playwright response headers](https://playwright.dev/docs/api/class-response#response-headers-array),
[ONNX Runtime Node](https://onnxruntime.ai/docs/get-started/with-javascript/node.html),
[ONNX 1.30 telemetry opt-out](https://github.com/microsoft/onnxruntime/blob/v1.30.0/docs/Privacy.md),
[HTTP cookie processing](https://www.rfc-editor.org/rfc/rfc6265).
