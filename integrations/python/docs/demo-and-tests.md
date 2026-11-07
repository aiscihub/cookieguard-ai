# Demo and tests

[Overview](../README.md) · [Install](install.md) · [Policy](policy.md) · [How it works](how-it-works.md) · [Results](results.md) · [Limits & privacy](limits-and-privacy.md) · **Demo & tests**

## See it run

![A Browser Use agent logs in to two local apps. Both logins succeed. CookieGuard fails the first with CG001 Missing HttpOnly (exit 1) and passes the second (exit 0).](cookieguard-browser-use-demo.gif)

The recording shows the same agent logging in to the same local app twice:
- **Insecure login:** the login succeeds, and CookieGuard returns **FAIL — CG001** (exit 1).
- **Secure login:** with `HttpOnly` set, it returns **PASS** (exit 0).

The left side is the agent's real Chromium viewport. The right side shows Browser
Use's own log lines and the `Set-Cookie` line CookieGuard observed, with its value
withheld. The code strip highlights the line that is running.

It was recorded by [`scripts/record_demo.py`](../scripts/record_demo.py) from a real run,
with Claude (`claude-opus-5-5`) driving the agent. Waits for the model longer than two
seconds are condensed and labelled *fast-forward*; everything else plays in real time.
To re-record, run `scripts/record_demo.py --provider anthropic` with `ANTHROPIC_API_KEY` set,
or omit `--provider` to use the scripted stand-in model, which needs no key. The script
keeps the raw capture under `artifacts/`, so `--recompose` restyles the last run without
running the agent again. Frames use the Geist and Geist Mono fonts (SIL Open Font
License), which the script fetches once with `npm pack geist@1.5.1`.
[MP4](cookieguard-browser-use-demo.mp4) · [provenance](demo-provenance.json).

## Run the demonstration

A loopback-only app with a real login form. The two modes differ only in `HttpOnly`.

```bash
python -m cookieguard.browser_use.demo            # both scenarios, headless; add --headed to watch
```

This runs the real Browser Use `Agent` loop with a scripted stand-in model (no
AI provider or API key). The stand-in reads the browser state and logs in with
`sensitive_data` placeholders. The agent calls `cookieguard_audit`, then CookieGuard enforces:

| Scenario | Login | Agent's provisional check | Final CookieGuard result | Exit |
| --- | --- | --- | --- | --- |
| `insecure` | succeeds (server accepted the cookie) | FAIL | **FAIL — CG001 Missing HttpOnly** | 1 |
| `secure` | succeeds | PASS | **PASS** | 0 |

To try a real model, see [`examples/agent_login.py`](../examples/agent_login.py):

```bash
python examples/agent_login.py --mode insecure                           # scripted
ANTHROPIC_API_KEY=... python examples/agent_login.py --provider anthropic --mode insecure
```

The Anthropic path has been run with `claude-opus-5-5`; see [VALIDATION.md](../VALIDATION.md).
Claude logged in using only `<secret>` placeholders and called `cookieguard_audit`.
- **Insecure app:** CookieGuard returned FAIL CG001 (exit 1).
- **Secure app:** PASS (exit 0).

The example enables Anthropic's server-side fallback, because an unaided diagnostic call
was intermittently declined by a safety classifier. The OpenAI and Browser Use Cloud
paths have not been run.

## Tests

```bash
cd integrations/python
python -m venv .venv && .venv/bin/pip install -e ".[test]" build
.venv/bin/python -m pytest -q          # 89 tests, real Chromium, about 3 minutes, no API key
.venv/bin/python scripts/verify_external.py   # wheel → fresh venv outside the repo → tests + demo
```

Coverage includes:
- **Policy semantics** through the real engine: CG001–CG009, thresholds, lifetime, baseline, unknown identity, missing cookies, and ambiguous or partitioned evidence.
- **Set-Cookie attribution** across redirect orderings and cross-origin redirects.
- **Real-browser flows:** login, store-only mode, origin filtering, new tabs, concurrent sessions, observer disconnection, browser closure, cleanup, and engine death.
- **The real `Agent.run()` loop**, including an agent that skips the tool and one that falsely claims success.
- **Privacy:** synthetic canary tokens are checked across agent-visible text, stdout/stderr at info and debug log levels, saved JSON, and exception chains. See [VALIDATION.md](../VALIDATION.md) for recorded results.
