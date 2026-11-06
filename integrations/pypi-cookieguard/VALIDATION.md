# cookieguard (PyPI alias) validation

## 0.1.0 publication — 2026-11-06

Published by `publish-cookieguard.yml` with PyPI Trusted Publishing from tag
`cookieguard-v0.1.0` (`3b6a858`, #31), run
[42261140999](https://github.com/aiscihub/cookieguard-ai/actions/runs/42261140999).

- Build job: `twine check --strict` passed for the wheel and sdist, and a clean venv
  installed the wheel against the published `cookieguard-browser-use` 0.1.0:
  `cookieguard 0.1.0 -> cookieguard-browser-use 0.1.0`.
- Two earlier deployment attempts failed without uploading anything:
  - from `main`: the `pypi` environment only deployed `browser-use-v*` tags. The
    maintainer approved adding a `cookieguard-v*` tag rule; required reviewers are unchanged.
  - from the tag, attempt 1: `invalid-publisher`, because the pending publisher did not
    exist yet. After the maintainer added it, attempt 2 succeeded.
- Uploaded files are byte-identical to the verified workflow artifact:

| File | SHA-256 |
| --- | --- |
| `cookieguard-0.1.0-py3-none-any.whl` | `5fe59bf96bbb4e979aff18f03da1b590bfa26110216e47d331548294e632f838` |
| `cookieguard-0.1.0.tar.gz` | `32edd77322d7e20c714d6584fd98f0a1f92a8894e2beeb4d2f4ed786433e0ddf` |

- `pip install cookieguard==0.1.0` from PyPI in a clean Python 3.12 venv on macOS arm64
  installed `cookieguard-browser-use` 0.1.0, and `cookieguard.CookieGuardAudit is
  cookieguard_browser_use.CookieGuardAudit` was `True`.
