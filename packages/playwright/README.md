# @cookieguard/playwright (proposed 0.1.0)

Passive cookie auditing for an existing Playwright BrowserContext. Not published.
See the runnable `examples/playwright` example. The adapter does not import or
launch Playwright. Tested with Playwright 1.64.1 / Chromium; the structural API
supports 1.51+ but older versions and other browsers are not certified.

```js
const audit = startCookieAudit(context, {
  origins: ['https://your-controlled-app.example'],
  policy: { authCookies: ['session_id'] },
});
try {
  // Await your existing login workflow and successful session assertions.
  assertCookiePolicy(await audit.evaluate());
} finally {
  audit.dispose();
}
```

`collect()` stops the listener and returns value-free observations; `evaluate()`
stops and evaluates. Repeated calls reuse that snapshot. Start a new collector
for another workflow. `auditPage(page, {policy})` audits an already-authenticated
context without navigating or recovering earlier headers. `evaluateCookiePolicy`
and `assertCookiePolicy` are re-exported.

Origins must be explicit HTTP(S) origins without paths, credentials, or queries.
They restrict observations, not navigation. The caller controls network
authorization. The collector never accepts passwords, creates storage state,
takes screenshots, or enables traces/HAR. Caller-enabled traces are outside its
control.

Headers precede browser normalization. A unique store cookie is associated only
when name/domain/path/origin, flags, SameSite, and expiry agree. Multiple
instructions, partitioned cookies, or uncertain matching retain separate
observations and unknown store declarations. `not-observed` means no unambiguous
current match, not proven rejection: replacement/expiry can also explain absence.
Header findings describe server instructions even if the browser rejects them.

A cookie appearing or rotating during login does not validate its role. Supply
exact names or scoped `authEvidence` from server-session assertions. The adapter
does not intercept `context.request`/`APIRequestContext` responses; their cookies
are observed later in the store with unknown declarations.

Defaults: 120-second observation window, 1,000 observations/responses, 64 pending
header reads, five-second header/store-read deadlines. `timeoutMs` and
`maxObservations` can reduce limits. Overflow, timeouts, header-read failures,
service-worker responses, or context closure mark collection incomplete. Await
the workflow before snapshotting and block service workers for reliable evidence.

Pass `classifier` from `createOnnxClassifier` for optional original-model triage.
Values are transient, results are labeled `onnx`, and failures mark collection
incomplete without fallback. Dispose of the model after the collector.
