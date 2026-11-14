# cookieguard-browser-use

CookieGuard's Python package is now [`cookieguard`](https://pypi.org/project/cookieguard/),
and the Browser Use integration lives in `cookieguard.browser_use`.

This package installs `cookieguard` and keeps existing code working:
`from cookieguard_browser_use import CookieGuardAudit` returns the same objects as
`from cookieguard import CookieGuardAudit`, and `python -m cookieguard_browser_use.demo`
still runs the demo.

Version 0.4.0 depends on exactly `cookieguard==0.4.0`. Existing 0.3.0
installations remain unchanged until upgraded.

The 0.4.0 [usage-reporting pilot](https://github.com/aiscihub/cookieguard-ai/blob/main/docs/USAGE_METRICS.md)
defaults on. Both imports share `CookieGuardAudit` and `flush_usage_metrics`;
one accepted audit attempts one event as package `cookieguard`, integration
`browser-use`. The import spelling is not measured. `usage_metrics=False`,
`COOKIEGUARD_USAGE_METRICS=0`, or `DO_NOT_TRACK=1` disables reporting. Events contain
fixed package/version/integration fields, a fresh invocation ID, and privacy
controls, without cookie data or audit results. The bundled public token targets
CookieGuard's PostHog US Cloud project `735326`. Delivery is best effort and never
changes audit results. Downloads, imports, and construction do not report.

For new projects:

```bash
pip install cookieguard==0.4.0
```

```python
from cookieguard import CookieGuardAudit
```

Documentation: https://github.com/aiscihub/cookieguard-ai/tree/main/integrations/python
