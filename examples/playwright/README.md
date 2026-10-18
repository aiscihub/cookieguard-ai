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

The fixture login uses a link. Replace it with an existing login test, retain its
session assertions, and supply the real cookie **name**. Do not commit credentials
or browser storage exports. Traces, screenshots, and video are disabled.
