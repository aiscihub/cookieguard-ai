# Installation

Install CookieGuard only as a test or development dependency of the project being
audited, after telling the user what you will add. Every command below installs a
published release.

| Package | Registry | Version | Install | Requires |
| --- | --- | --- | --- | --- |
| `cookieguard` | PyPI | 0.2.0 | `.venv/bin/pip install cookieguard==0.2.0` | Python 3.11-3.13, browser-use >=0.13.14,<0.14, Node.js 24+, Chrome or Chromium |
| `cookieguard-browser-use` | PyPI | 0.2.0 | Only for existing projects | Compatibility package: installs `cookieguard` and keeps `import cookieguard_browser_use` working |
| `@aiscihub/cookieguard-playwright` | npm | 0.2.0 | `npm install --save-dev @aiscihub/cookieguard-playwright@0.2.0` | Node.js 24+, `@playwright/test` |
| `@aiscihub/cookieguard-core` | npm | 0.2.0 | `npm install --save-dev @aiscihub/cookieguard-core@0.2.0` | Node.js 24+; only needed to write JSON reports from Playwright |
| `cookieguard-ci` | npm | 0.2.0 | `npx --yes cookieguard-ci@0.2.0 ...` (no install) | Node.js 24+ |
| `@aiscihub/cookieguard-mcp` | npm | 0.2.0 | `npx --yes @aiscihub/cookieguard-mcp@0.2.0 --config /absolute/path/cookieguard.json` | Node.js 24+ |

On npm, the package named `cookieguard` is an unrelated project. Use the names above.

## Python environment for Browser Use

```bash
python3 --version                      # must be 3.11, 3.12, or 3.13
python3.12 -m venv .venv               # if the default python3 is older
.venv/bin/pip install cookieguard==0.2.0
node --version                         # must be 24 or newer
```

`pip` does not install Node.js or a browser. Browser Use finds an installed Chrome or
Chromium. On Ubuntu 23.10 and later, Chromium's sandbox needs unprivileged user namespaces;
do not work around that with `--no-sandbox`.

## Verify the installation

```bash
.venv/bin/python -m cookieguard.browser_use.demo   # real browser, no LLM key; exit 0 = expected FAIL and PASS
npx --yes cookieguard-ci@0.2.0 --version           # prints 0.2.0
npx --yes cookieguard-ci@0.2.0 explain CG001       # rule explanation, no network audit
```

## Network access

Installation contacts `pypi.org` and `files.pythonhosted.org`, or `registry.npmjs.org`.
Audits contact only the application origins you configure. CookieGuard sends no telemetry.
