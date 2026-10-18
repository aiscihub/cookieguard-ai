# Privacy Policy

CookieGuard AI is designed with a privacy-first architecture.  
All analysis is performed locally on the user's device.

## CookieGuard CI (0.1.0 public beta)

CI reads cookie values only transiently to compute the original engine's numeric
features. Values, raw Set-Cookie headers, credentials, arbitrary error messages,
and legacy nested analysis contexts never enter CI reports. Output uses an
allowlist of metadata and fixed evidence explanations. Files written by the CLI
are owner-readable. CI creates no storage-state exports, traces, HAR, screenshots,
or telemetry. Default CLI scanning sends no cookies or authorization headers.

Playwright continues making the application's normal authenticated requests;
CookieGuard is a passive local observer and adds no transmission of values. The
optional Node ONNX adapter sets `ORT_DISABLE_TELEMETRY=1` before loading the
runtime. Applications loading ONNX independently must set this at process startup.
JavaScript memory is garbage-collected, not securely erased. Cookie names, domains,
and paths can themselves identify an application: review metadata before sharing
reports or uploading artifacts. The example Action retains sanitized reports for
seven days, and upload can be disabled.

## Legacy extension boundary

The original extension is preserved. Its manual **Export Cookies as JSON** path
in `popup.js` includes raw cookie values, and `analyzeAllCookies()` returns values
in memory. Do not treat that legacy export as a sanitized CI report or commit it
as a fixture. CI does not call those export functions and strips legacy fields
when importing observations. Caller-enabled Playwright traces and application
logs are outside CookieGuard CI's control. The commitments below describe local
analysis; the legacy export is an explicit exception to metadata-only storage.

## What Data Is Accessed

CookieGuard reads cookie metadata available through the browser, including:

- Cookie name
- Domain
- Path
- Expiration
- Secure flag
- HttpOnly flag
- SameSite attribute

## What Data Is NOT Collected

- CI does not store or transmit raw cookie values; see the legacy export exception above.
- Authentication tokens are never exfiltrated.
- No browsing history is logged.
- No personal data is sent to external servers.

## Local Processing

- All classification and risk scoring occurs on-device.
- The Python backend runs locally at `localhost`.
- No remote API calls are required for analysis.

## Data Storage

- CI persists only requested, sanitized metadata reports. The legacy manual export is described above.
- Analysis results are displayed in-session only.
- No analytics tracking is included.

## User Control

Users can:
- Disable the extension at any time.
- Inspect the open-source code.
- Modify or remove local backend components.

## Security Philosophy

CookieGuard is built to reduce identity theft risk while minimizing data exposure.  
The system follows the principle of least privilege and metadata-only inspection.

If you discover any privacy-related issue, please report it responsibly (see SECURITY.md).
