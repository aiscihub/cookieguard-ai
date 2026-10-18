# Community demo verification

Verified from a clean Git clone on **2026-10-18**, using macOS, Node 24.22.0,
Playwright 1.64.1, and Chromium 156.0.8078.4. `npm ci` installed and built fresh
workspace packages; Chromium was downloaded into a separate browser cache.
These are observed local results, separate from hosted workflow results.

| Command | Observed result | Process exit |
| --- | --- | --- |
| `npm run demo:ci:fail` | Login succeeds; `CG001 — Missing HttpOnly`; `CookiePolicyError`; **1 failed** | **1** |
| `npm run demo:ci:pass` | Login succeeds; cookie policy passes; **1 passed** | **0** |
| `npm run demo:browser:fail` | Server accepts the session cookie; `CG001`; real policy exception; **1 failed** | **1** |
| `npm run demo:browser:pass` | Server accepts the session cookie; policy passes; **1 passed** | **0** |
| `npm run test:playwright` | Original **8 passed** | **0** |
| `npm test` | **29 passed**, including extension compatibility | **0** |
| `npm run lint` | Passed | **0** |

Both demonstration modes use the real collector and call `assertCookiePolicy()`
directly. The insecure exception reaches Playwright; it is not caught or marked
as an expected failure. The browser command launcher forwards that actual exit
status. Each command starts and stops its own server through fixture teardown.

The original eight integration tests, their config, security engine, extension,
package versions, lockfile, and research documentation remain unchanged. The
`.demo.js` tests use separate opt-in configs, outside normal test discovery.
The clean checkout remained unchanged after the runs. The artifact leakage check
inspected **19 generated files** and found no fixture sentinel values; captured
command output was also checked before saving.

## Included launch recording

The [combined MP4](cookieguard-ci-demo-25s.mp4) was recorded locally using these
same demo sources before the clean-checkout verification above. Its output panel
contains verbatim excerpts from each original recording's Playwright log, labeled
**Captured Playwright output**. It is an edited composition of browser recordings
and saved results. Runtime durations shown in the video belong to those runs.

- **0–11 seconds:** insecure login, CG001, real policy exception, **1 failed**, exit 1.
- **11–22 seconds:** secure login, policy success, **1 passed**, exit 0.
- **22–25 seconds:** repository closing card.
- FFprobe verified **25 seconds**, **625 frames**, **1920 × 1080**, H.264; the full
  video decoded without FFmpeg errors.
- Inspected frames show both real browser workflows and no cookie values.
  Headings and embedded browser steps use **1, 2, 3** without leading zeros.
  The rule identifier **CG001** is preserved.

The reviewed file is 676502 bytes; SHA-256:
`912ca4a879fe9134f9d1e8bf6c8c1605fbb63fb9fc6713fb8dc560c5b0af535c`.

See the [recording and composition guide](README.md#create-the-25-second-launch-video)
to reproduce it. Generated logs, source recordings, and composition manifests
stay in the ignored `artifacts/` directory. These controlled cookie-policy
scenarios do not measure model research accuracy or prove exploitability.
