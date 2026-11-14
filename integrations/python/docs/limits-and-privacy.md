# Limits and privacy

[Overview](../README.md) · [Install](install.md) · [Policy](policy.md) · [How it works](how-it-works.md) · [Results](results.md) · **Limits & privacy** · [Demo & tests](demo-and-tests.md)

## What it cannot observe

- **Browser state is not a server declaration.** A store cookie's SameSite is the
  effective value. If Chromium reports none, it stays unknown. Declarations come
  only from captured `Set-Cookie` lines.
- **Header capture can miss requests** made before the observer attaches to a
  new tab or iframe, or made by other browser contexts and service workers. Responses served
  by a service worker make the audit INCOMPLETE. Missing headers only remove
  declaration evidence. With the default `require_header_evidence`, they cannot produce a PASS.
- **JavaScript-set cookies** (`document.cookie`) have no header. Their store flags
  are still checked, so a missing HttpOnly still fails.
- Store cookies do not reveal host-only scope, so `CG004` and prefix checks rely on headers.
  Cookies are scoped by host, not port, so another app on the same loopback host
  shares the jar.
- It is a configuration audit. It does not validate server sessions, demonstrate
  XSS/CSRF, or prove an application is secure. Tested only on Chromium with local
  browsers; Browser Use cloud browsers are untested.

## Privacy and authorization

- **Audit only applications you are authorized to test.** Nonlocal origins
  require `allow_nonlocal_origins=True`. Origins limit evidence, not navigation.
  Use `allowed_domains` to keep the agent on the app. CookieGuard never navigates.
- **CookieGuard outputs never contain cookie values.** Values go only to the local
  engine over a stdin pipe; they are never put in argv, files, logs, or exceptions. The engine runs with
  Node's permission model (read-only access to its own files, no writes or child
  processes; Node 25+ also blocks network). As a last check, a result containing
  an observed store cookie value (12+ characters, not purely alphabetic) is refused.
  Python memory is not securely erased.
- **CookieGuard usage reporting defaults on and can be disabled.** The 0.4.0
  [PostHog pilot](https://github.com/aiscihub/cookieguard-ai/blob/main/docs/USAGE_METRICS.md)
  attempts one fixed invocation event after `start()` accepts the session.
  The bundled public token targets CookieGuard's US Cloud project `735326`.
  Existing Python 0.3.0 installations remain unchanged until upgraded.
  Downloads, imports, and construction do not report. `usage_metrics=False`,
  `COOKIEGUARD_USAGE_METRICS=0`, or `DO_NOT_TRACK=1` disables reporting;
  `usage_metrics=None` or omission follows the environment/default. Events contain
  package/version/integration metadata and a fresh invocation UUID, with no
  cookie data, URLs, audit outcomes, or persistent identity. Provider transport
  still receives a source IP; the pilot requires IP discard and disabled GeoIP.
  Delivery is best effort and failures do not affect audits. Provisional checks,
  the compatibility import, and the nested Node engine do not emit additional
  events. This setting is separate from Browser Use.
- **The model is outside CookieGuard's boundary.** Your LLM provider receives the
  task, page content, and the sanitized tool output. Pass credentials through
  Browser Use `sensitive_data` with distinctive values. Browser Use masks every
  occurrence of a secret's value and logs typed text in clear otherwise.
- **Browser Use defaults to check:** anonymized telemetry (task, URLs, actions,
  final answer) is on unless `ANONYMIZED_TELEMETRY=false`. Cloud sync follows it
  (`BROWSER_USE_CLOUD_SYNC`). A configured `storage_state` path, HAR recording
  (`record_har_path`), traces, or a persistent `user_data_dir` can write cookie
  values to disk. These are outside CookieGuard's control.

## Tested environments and dependencies

Version 0.1.0 is tested in these environments only:

| Platform | Python | Node.js | Browser | Browser Use |
| --- | --- | --- | --- | --- |
| Linux, GitHub `ubuntu-latest` (x86_64) | 3.11, 3.12, 3.13 | 24 | Playwright Chromium 156, sandbox on | 0.13.14 |
| macOS 26 (Apple silicon) | 3.12 | 24, 26 | Google Chrome 156 | 0.13.14 |

- **Not tested:** Windows, Browser Use cloud browsers, other Browser Use versions, and
  non-Chromium browsers.
- **Models:** the real-model run used `claude-opus-5-5`. Other providers' paths in
  `examples/agent_login.py` are untested. The demo and tests use a scripted stand-in model.
- **Inherited dependency advisories:** Browser Use 0.13.14 pins exact versions of
  `anyio` (4.12.1), `mcp` (2.1.1), `pillow` (12.3.0), and `pypdf` (6.16.2). On 2026-11-04,
  `pip-audit` listed published advisories against all four.
  - CookieGuard does not import them, and it cannot raise Browser Use's exact pins.
  - Every Browser Use 0.13.14 installation includes them, with or without CookieGuard.
  - Update when Browser Use releases newer pins, and review those advisories for your own
    Browser Use workloads, such as PDF or image handling.

