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

Until a PyPI release exists, install from this repository:

```bash
git clone https://github.com/aiscihub/cookieguard-ai && cd cookieguard-ai
npm ci
node integrations/browser-use/scripts/vendor_engine.mjs --registry  # copies the published npm engine
pip install ./integrations/browser-use
```

The vendor step requires the workspace packages to be byte-identical to the npm
release (`--registry`) and records SHA-256 hashes that are checked before Node starts.
