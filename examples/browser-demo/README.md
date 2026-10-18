# A successful browser login can still fail CI

These commands open **real, headed Chromium**, perform the existing fixture's
link-based login with Playwright, and call the real CookieGuard policy assertion.
Both scenarios use [the same test](../ci-demo/login.demo.js), login page, navigation,
and `authCookies: ['session_id']` policy. Only the server's HttpOnly setting changes.

**[Watch the combined 25-second demo](https://aiscihub.github.io/cookieguard-ai/examples/browser-demo/cookieguard-ci-demo-25s.mp4)**
or open the [included MP4](cookieguard-ci-demo-25s.mp4). It shows real browser
recordings beside captured output from their matching Playwright runs.

## Run the before and after

Complete the [fresh-checkout setup](../ci-demo/README.md#setup), then run these
commands separately from the repository root with a graphical desktop:

```bash
npm run demo:browser:fail
npm run demo:browser:pass
```

The first deliberately exits **1**. Do not join them with `&&`. FFmpeg is only
needed for MP4 conversion and composition, not for running either demonstration.

| Command | Real browser workflow | CookieGuard / Playwright | Exit |
| --- | --- | --- | --- |
| `npm run demo:browser:fail` | Login succeeds; `session_id` is accepted | `CG001 — Missing HttpOnly`; **1 failed** | **1** |
| `npm run demo:browser:pass` | Same login succeeds | `policy passed`; **1 passed** | **0** |

The browser opens `/login`, Playwright clicks **Create demo session**, and
`/session` sets the cookie and redirects to `/account`. That page checks the
incoming cookie before showing **Login succeeded.** Without the session it
redirects back to login. Both modes set `Secure; SameSite=Lax`; the passing mode
also sets `HttpOnly`. The browser page makes no claim about the policy outcome:
read the live terminal for that result.

CookieGuard starts collecting before navigation, matches the real Set-Cookie
declaration with the browser's cookie store, then evaluates the declared policy.
The failing `assertCookiePolicy(report)` is unwrapped. Its exception reaches
Playwright and produces the failure stack. The small command launcher preserves
Playwright's output and exit status and prints that actual status as `Exit code`.

## Recordings

Each command records the actual browser viewport using
[Playwright video recording](https://playwright.dev/docs/videos). After Playwright
closes the context, the command saves a clearly named copy:

- `artifacts/browser-demo/insecure.webm`
- `artifacts/browser-demo/secure.webm`

Both the viewport and recordings are **1280 × 720**. Each scenario takes about
10–15 seconds including browser startup. There are recording-only pauses after
the login page is ready (2 seconds), while hovering over the login link (1 second),
after authenticated navigation (2 seconds), before the assertion (2 seconds),
and before closing the page (2 seconds). Readiness checks and awaited navigation,
not the pauses, determine whether the workflow succeeded.

Recordings contain the browser page only. To show the **real terminal result
alongside Chromium**, use the screen-recording instructions below. The `.webm`
files alone do not show the failed or passed Playwright summary.

If FFmpeg is installed, convert the real recordings without changing their speed:

```bash
ffmpeg -y -i artifacts/browser-demo/insecure.webm -c:v libx264 -crf 18 -pix_fmt yuv420p -movflags +faststart artifacts/browser-demo/insecure.mp4
ffmpeg -y -i artifacts/browser-demo/secure.webm -c:v libx264 -crf 18 -pix_fmt yuv420p -movflags +faststart artifacts/browser-demo/secure.mp4
```

The matching scenario's `.webm` is replaced on each run; rerun FFmpeg to refresh
its MP4. All output is under the git-ignored `artifacts/` directory; no recordings
are published automatically.

## Create the 25-second launch video

With the MP4 files above, their matching `fail.log` / `pass.log`, and FFmpeg plus
FFprobe installed, run:

```bash
node examples/browser-demo/compose-video.js
```

The output is `artifacts/browser-demo/cookieguard-ci-demo-25s.mp4`: a silent
1920 × 1080 video at 25 fps. Its timeline is:

| Time | Contents |
| --- | --- |
| 0–11 seconds | Actual insecure browser clip beside captured `CG001`, `CookiePolicyError`, **1 failed**, and exit 1 |
| 11–22 seconds | Actual secure browser clip beside captured policy success, **1 passed**, and exit 0 |
| 22–25 seconds | `github.com/aiscihub/cookieguard-ai` closing card |

The output panel displays verbatim excerpts from the matching real run logs and
is labeled **Captured Playwright output**. The browser footage plays at its
original speed. Each segment trims its closing idle time or holds its last frame
to fit 11 seconds. Source hashes, exact excerpts, and edit timing are saved in
`artifacts/browser-demo/final/manifest.json`.

The committed `examples/browser-demo/cookieguard-ci-demo-25s.mp4` is the reviewed
launch recording. Rebuilding writes only to `artifacts/`; replacing the public
copy is a separate, reviewed change. GitHub Pages serves the committed copy from
`main` after its normal deployment.

To refresh the source logs and recordings, run these separately, then repeat the
MP4 conversions above and the composition command. The first command still exits
1 intentionally; redirection preserves its real output and status.

```bash
mkdir -p artifacts/browser-demo
npm run demo:browser:fail > artifacts/browser-demo/fail.log 2>&1
npm run demo:browser:pass > artifacts/browser-demo/pass.log 2>&1
```

## Record Chromium and Terminal side by side on macOS

1. Install dependencies before recording. Open Terminal in the repository root.
   Run `unset NO_COLOR FORCE_COLOR` to avoid conflicting color settings, and
   choose a readable font. Leave room for the failure stack and test summary.
2. Position Terminal beside the space where Chromium opens. A screen wide enough
   for the 1280-pixel browser viewport and terminal works best. Use a rehearsal
   run to arrange them; keep the browser out of full-screen mode.
3. Press **Command–Shift–5**, select **Record Selected Portion**, and include
   both windows. Under **Options**, select a microphone if narrating. See
   [Apple's screen-recording instructions](https://support.apple.com/en-us/102618).
4. Start recording, then execute these as separate commands:

   ```bash
   clear
   npm run --silent demo:browser:fail
   npm run --silent demo:browser:pass
   ```

   `--silent` hides npm's script header only. Both real Playwright summaries and
   exit codes remain visible. Let the failure result sit for 2–3 seconds before
   running the passing command; pause briefly on the passing result too.
5. Stop with the menu-bar recording button. Trim idle time at the beginning or
   end to make a roughly 30-second clip; retain the real login and test results.

Suggested narration: “The login succeeds, but its authentication cookie is missing
HttpOnly. CookieGuard fails the test. Add HttpOnly, run the same login again, and
the same security assertion passes.”

## Isolation and verification

The fixture server binds to an available loopback port and shuts down in fixture
teardown, even when the assertion fails. Browser application requests are
restricted to that origin. Page contents and console output never include cookie
values. HAR, storage-state exports, tracing, and screenshots are not enabled.
Only this headed config enables video and recording pauses.

The original eight integration tests and their config remain unchanged. The
headed config reuses the opt-in `.demo.js` file, outside normal CI discovery.
`npm run test:playwright` still selects those eight tests. The existing
`demo:ci:fail` and `demo:ci:pass` remain quick headless demonstrations without video.

See [the verification report](VERIFICATION.md) for observed results. These are
controlled cookie-policy scenarios, not model accuracy measurements. On a machine
without a graphical desktop, use the headless commands for policy checks; verify
the headed commands on macOS using the exact commands above.
