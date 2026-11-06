# cookieguard-browser-use

CookieGuard's Python package is now [`cookieguard`](https://pypi.org/project/cookieguard/),
and the Browser Use integration lives in `cookieguard.browser_use`.

This package installs `cookieguard` and keeps existing code working:
`from cookieguard_browser_use import CookieGuardAudit` returns the same objects as
`from cookieguard import CookieGuardAudit`, and `python -m cookieguard_browser_use.demo`
still runs the demo.

For new projects:

```bash
pip install cookieguard
```

```python
from cookieguard import CookieGuardAudit
```

Documentation: https://github.com/aiscihub/cookieguard-ai/tree/main/integrations/python
