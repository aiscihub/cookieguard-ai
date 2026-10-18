# @cookieguard/core (proposed 0.1.0)

Local normalization, existing-engine triage, evidence-aware policy, and value-free
reports. ESM, Node 24+, maintained TypeScript declarations. Not yet published.
Build/install from the repository README or local tarballs. No runtime
dependencies for rule mode.

```js
import { parseSetCookie, evaluateCookiePolicy, formatText, exitCode } from '@cookieguard/core';
const cookie = parseSetCookie(
  'session_id=synthetic; Path=/; Secure; SameSite=Lax',
  'https://your-controlled-app.example/login',
);
const report = evaluateCookiePolicy([cookie], { authCookies: ['session_id'] });
console.log(formatText(report));
process.exitCode = exitCode(report); // 1: missing HttpOnly
```

`normalizeCookie`/`normalizeCookies` accept Playwright-compatible metadata.
`normalizeLegacyResults` accepts the original engine's `{cookies}` result but
discards values, contexts, explanations, and nested unrecognized data.
`parseSetCookie` accepts one header field, never comma-combined cookies. All
normalizers return new value-free observations. Browser and fixture inputs have
`sameSite.declared: 'unknown'`, even if their effective SameSite is Lax.

Only normalized observations should enter `evaluateCookiePolicy`. Inputs are
developer-owned evidence, not authenticated remote attestations. Reports include
policy, summary, normalized observations, identity basis, findings, evidence,
limitations, and comparison status. Optional `now` is epoch milliseconds for
deterministic fixtures. Expiration timestamps use epoch seconds.

Policy fields: `authCookies`, `authEvidence`, `failOn` (high), `allowedSameSite`
(lax/strict), `requireExplicitSameSite` (false), `requireHostOnly` (false),
`maxLifetimeDays` (30). Unknown keys are errors. An `authEvidence` entry must
specify exact `name`, `domain`, `path`, `origin`, and
`validation: 'server-session-validated'`: the developer's attestation from a
validated server-session test, not an inference from cookie changes. Missing
expected names/scopes make the report incomplete.

```js
const report = evaluateCookiePolicy(observations, policy, {
  mode: 'browser', target: 'https://your-controlled-app.example',
  complete: true, baseline: previousJsonReport,
});
```

Baseline comparison requires the same target, mode, policy, scope, source, and
confirmed identity, with unambiguous observations. It checks removed
Secure/HttpOnly, Lax/Strict to None, newly shared domain scope, and a lifetime
crossing the configured limit. Missing/unmatched evidence is not a regression.
Version 0.1 does not correlate renamed cookies or changed domains/paths.

Use `formatText`, `formatJson`, `formatMarkdown`, `exitCode`, or
`assertCookiePolicy` on the **original report returned by evaluation**. A private
immutable allowlisted copy prevents caller mutations from injecting raw data.
Parsed JSON is accepted as a baseline, not as an arbitrary renderable report.
JavaScript memory is garbage-collected; secure erasure is not promised.

## Optional original ONNX model

The full contributor installation includes `onnxruntime-node@1.30.0` as a dev
dependency. A consuming app can install this optional peer separately. Core/CLI
tarballs contain neither native binaries nor the model. Use the existing model:

```js
import { createOnnxClassifier } from '@cookieguard/core/onnx';
import { normalizeCookie, evaluateCookiePolicy } from '@cookieguard/core';
const classifier = await createOnnxClassifier({
  modelPath: 'extension-standalone/model/cookieguard_model.onnx',
  metadataPath: 'extension-standalone/model/model_meta.json',
});
try {
  const cookie = { name: 'session_id', value: 'synthetic', secure: true, httpOnly: true };
  const triage = await classifier.classify(cookie);
  const observation = normalizeCookie(cookie, { triage });
  const report = evaluateCookiePolicy([observation]);
  // classificationModes is ['onnx']; identity is never confirmed by ML.
} finally {
  await classifier.dispose();
}
```

The adapter uses the same 38-feature order and RandomForest model, validates
metadata, disables telemetry before native import, and requests CPU inference.
If another component initializes ONNX first, set `ORT_DISABLE_TELEMETRY=1` at
process startup. Scores are labeled uncalibrated, not the Python pipeline's
calibrated outputs. The model is not retrained, replaced, or used to gate CI.
Failures return a fixed `MODEL` error, never a silent fallback. Do not supply
untrusted models.
