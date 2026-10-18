# A successful login can still fail CI

These opt-in demonstrations run the real CookieGuard implementation against the
same link-based login and local server fixture used by
[the eight integration tests](../playwright/login.spec.js). Both modes confirm
that the browser completed the workflow and received the developer-identified
`session_id` cookie. Both then call the same `assertCookiePolicy(report)` directly.

For **headed Chromium with real browser video**, use `npm run demo:browser:fail`
and `npm run demo:browser:pass`. They reuse this test with an opt-in browser
presentation. See the [browser and terminal recording guide](../browser-demo/README.md).

## Setup

Use Git, Node 24 or newer (Node 24 is the tested runtime), and npm. From a fresh
checkout:

```bash
git clone https://github.com/aiscihub/cookieguard-ai.git
cd cookieguard-ai
npm ci
npx --no-install playwright install chromium
```

On Linux, install Chromium's system dependencies with
`npx --no-install playwright install --with-deps chromium`.
These headless commands do not need a graphical desktop, FFmpeg, credentials,
or a manually started server. `npm ci` builds the workspace packages during
installation. The policy checks do not use the optional ONNX model runtime.

Run the commands below separately from the repository root. Both check that
the login workflow completed and the identified authentication cookie is in the
browser. CookieGuard's subsequent assertion checks its security attributes:
authentication succeeding does not imply the cookie policy passes.

## Insecure cookie: a real failed test

```bash
npm run demo:ci:fail
```

The login succeeds, but the server omits HttpOnly. The real policy assertion
throws `CookiePolicyError`, Playwright reports **1 failed**, and npm exits **1**.
Look for these lines in the terminal:

```text
Login succeeded. Authentication cookie is present in the browser.
CG001 — Missing HttpOnly
```

This failure is intentional. It is not caught or marked as an expected failure.

## Secure cookie: the same assertion passes

```bash
npm run demo:ci:pass
```

The corresponding login sets `Secure; HttpOnly; SameSite=Lax`. The same policy
assertion succeeds, the terminal prints `Cookie policy passed.`, Playwright shows
**1 passed**, and npm exits **0**.

Each command creates its own loopback server on an available temporary port and
closes it during fixture teardown, including after a failed assertion. There is
no manual server command and no fixed-port conflict with the regular demo.
Demo logging includes fixed progress messages and actual rule IDs/titles. Cookie
values are not logged; traces, screenshots, and videos are disabled.
Playwright's output stays in separate `artifacts/ci-demo/fail` and
`artifacts/ci-demo/pass` directories, outside the normal suite's output directory.

The scenarios share one test in `login.demo.js`, selected by separate projects in
their own config. The `.demo.js` suffix is excluded from default Playwright test
discovery, and this directory is outside the normal suite's `testDir`.
`npm run test:playwright` and the existing CI workflow continue running the
original eight integration tests. To run this deliberate failure, opt in with
`demo:ci:fail`.

## Record a 20–30-second terminal demonstration

Install dependencies and Chromium before recording. Use a bash/zsh terminal
about 120 columns wide and 40 rows high so the login, finding, and failure summary
fit together. Clear conflicting color settings with `unset NO_COLOR FORCE_COLOR`
before recording. Record the following as separate commands; `--silent` hides
only npm's script header. Do not join the fail and pass commands with `&&`.

```bash
clear
npm run --silent demo:ci:fail
echo "exit: $?"

npm run --silent demo:ci:pass
echo "exit: $?"
```

- **0–10 seconds:** run the failing command. Pause on `Login succeeded`,
  `CG001 — Missing HttpOnly`, `1 failed`, and `exit: 1`.
- **10–20 seconds:** run the passing command. Pause on `Cookie policy passed`,
  `1 passed`, and `exit: 0`.
- **20–30 seconds:** explain: “The login succeeded in both cases. CookieGuard
  failed CI for the insecure authentication cookie. Adding HttpOnly made the
  same security assertion pass.”

These are controlled fixture scenarios, not measurements of model accuracy or
proof of an exploitable vulnerability. All application traffic stays on loopback.
