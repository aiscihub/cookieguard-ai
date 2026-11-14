# Install

[Overview](../README.md) · **Install** · [Policy](policy.md) · [How it works](how-it-works.md) · [Results](results.md) · [Limits & privacy](limits-and-privacy.md) · [Demo & tests](demo-and-tests.md)

- Python 3.11+ (CI tests 3.11, 3.12, and 3.13), browser-use `>=0.13.14,<0.14`.
- Node.js 24+ on `PATH` (or set `COOKIEGUARD_NODE`) for the local engine. Tested on Node 24 and 26.
- Chrome or Chromium. Browser Use finds an installed browser or `uvx playwright install chromium`.
  On Ubuntu 23.10+ (including GitHub's `ubuntu-latest`), AppArmor blocks the user
  namespaces Chromium's sandbox needs, and Chrome exits at launch. Fix it in one of two ways:
  - Allow the namespaces, as this repo's CI does: `sudo sysctl -w kernel.apparmor_restrict_unprivileged_userns=0`.
  - Use Google Chrome, which has a setuid sandbox: `BrowserProfile(channel='chrome')`.

  Avoid `--no-sandbox`.

## From PyPI

Version 0.4.0 is being prepared for [PyPI](https://pypi.org/project/cookieguard/).
After publication, install it with:

```bash
pip install cookieguard
# Or pin this release:
pip install cookieguard==0.4.0
```

Code that uses `cookieguard-browser-use` or `import cookieguard_browser_use` keeps working:
that package now installs `cookieguard` and re-exports it.

Version 0.4.0 enables minimal invocation reporting by default. Disable it with
`COOKIEGUARD_USAGE_METRICS=0`, `DO_NOT_TRACK=1`, or `usage_metrics=False`; see
[limits and privacy](limits-and-privacy.md). Installing or importing does not report.

Node.js 24+ and Chrome or Chromium are still required; pip does not install them.
See [tested environments and dependencies](limits-and-privacy.md#tested-environments-and-dependencies).

## From source

To work from a checkout:

```bash
git clone https://github.com/aiscihub/cookieguard-ai && cd cookieguard-ai
npm ci
node integrations/python/scripts/vendor_engine.mjs --published  # copies the published npm engine
pip install ./integrations/python
```

The `--published` vendor step downloads the pinned npm engine 0.3.0 and records
SHA-256 hashes that are checked before Node starts. It does not replace that engine
with the newer workspace packages. The separate `--registry` verification mode
compares workspace packages with the pinned published engine.
