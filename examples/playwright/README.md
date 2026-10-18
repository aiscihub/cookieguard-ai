# Running login-flow example

From the repository root with Node 24:

```bash
npm ci
npx --no-install playwright install chromium
npm run test:playwright
```

The config starts/stops the local fixture. Port 3000 must be free. The example
audits a successful login and asserts that insecure configurations fail policy.
The suite passes when those expected failures occur. It also verifies unknown
identity, late collection, defaults, prefix rejection, and SameSite=None rejection.

For a visible **1 failed → 1 passed** demonstration using an unwrapped policy
assertion, run `npm run demo:ci:fail` and `npm run demo:ci:pass`. See the
[isolated CI demo and recording instructions](../ci-demo/README.md). Those
deliberately failing scenarios are excluded from this integration suite.
For headed Chromium and real browser video, use `npm run demo:browser:fail` and
`npm run demo:browser:pass`; see the [browser recording guide](../browser-demo/README.md).

The fixture login uses a link. Replace it with an existing login test, retain its
session assertions, and supply the real cookie **name**. Do not commit credentials
or browser storage exports. Traces, screenshots, and video are disabled.
