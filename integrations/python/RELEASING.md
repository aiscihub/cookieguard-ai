# Releasing the Python packages to PyPI

Since 0.2.0, one workflow, `.github/workflows/publish-cookieguard.yml`, builds, verifies,
and publishes both distributions from this folder, always at the same version:

| Distribution | Contents |
| --- | --- |
| `cookieguard` | The package: core (`cookieguard`) and integrations (`cookieguard.browser_use`) |
| `cookieguard-browser-use` | Compatibility package in `compat/cookieguard-browser-use`; depends on `cookieguard==<version>` and re-exports it |

## Checklist (used for 0.3.0, published 2026-11-08, and 0.2.0, published 2026-11-06)

1. Merge with CI green, including the upgrade-path step on Python 3.12.
2. On pypi.org, make sure both projects trust the same publisher: owner `aiscihub`,
   repository `cookieguard-ai`, workflow `publish-cookieguard.yml`, environment `pypi`.
   The entries must be identical, environment included. When they differ, PyPI mints a token
   for only one project and the upload fails with `OIDC scoped token is not valid for project`,
   as attempt 1 of the 0.2.0 release did.
3. Tag `main` with an annotated `cookieguard-v<version>` and push the tag. The `pypi`
   environment deploys only `browser-use-v*` and `cookieguard-v*` tags.
4. Run the workflow from the tag with `target: pypi`. The build job runs
   `verify_external.py` (clean consumer, tests, demo, sdist), `twine check`,
   `verify_metadata.py` (links pinned to the tag), the version-lockstep check, and
   `verify_upgrade.py` (fresh install, and upgrades from 0.2.0 and both 0.1.0 releases). Approve
   the `pypi` deployment.
5. Verify the uploads against the workflow artifact, install from PyPI in clean venvs on
   Python 3.11-3.13, and record the publication in [VALIDATION.md](VALIDATION.md).

Browser Use moves to an optional extra (`cookieguard[browser-use]`) only when a second
integration ships; until then it is a default dependency.

# History: cookieguard-browser-use 0.1.x

Runbook for the maintainer and for a coding agent (for example Codex) doing the work.
Steps marked **Maintainer** need a person with access to the `aiscihub` PyPI and GitHub
accounts. An agent must stop and ask at each of them.

## State on 2026-11-04

- **0.1.0 (first stable release) is [published on PyPI](https://pypi.org/project/cookieguard-browser-use/0.1.0/).**
  It was merged in [PR #22](https://github.com/aiscihub/cookieguard-ai/pull/22) and published on
  2026-11-04 from tag `browser-use-v0.1.0` at commit `d1b5de0`, through Trusted Publishing in
  [release run 41882052045](https://github.com/aiscihub/cookieguard-ai/actions/runs/41882052045)
  after maintainer approval. The [GitHub release](https://github.com/aiscihub/cookieguard-ai/releases/tag/browser-use-v0.1.0)
  includes the verified wheel, source archive, and `SHA256SUMS`.
- Release gates are in [VALIDATION.md](VALIDATION.md#010-release-candidate--2026-11-04), and the
  published result in [VALIDATION.md](VALIDATION.md#010-publication--2026-11-04).
  One item remains: a person's visual check of the rendered PyPI page (see "Done when (0.1.0)").

0.1.0b1 history:


- The integration was merged to `main` in [PR #13](https://github.com/aiscihub/cookieguard-ai/pull/13)
  on 2026-11-03 (`1ed1b82`). Its CI passed: the toolkit job, plus the Browser Use job on
  Python 3.11, 3.12, and 3.13. Step 0 is complete.
- Version is `0.1.0b1`, set in `pyproject.toml` and `src/cookieguard_browser_use/__init__.py`.
  It was [published to PyPI](https://pypi.org/project/cookieguard-browser-use/0.1.0b1/) on
  2026-11-03 from tag `browser-use-v0.1.0b1` at commit `ff3e27b`.
- The maintainer approved direct PyPI publication without the TestPyPI rehearsal because
  TestPyPI setup was unavailable. [Release run 41725841083](https://github.com/aiscihub/cookieguard-ai/actions/runs/41725841083)
  passed its build and package checks, then published through the approved `pypi` environment.
- The [GitHub pre-release](https://github.com/aiscihub/cookieguard-ai/releases/tag/browser-use-v0.1.0b1)
  includes the verified wheel, source archive, and `SHA256SUMS`.
- The remaining release checks passed on 2026-11-03: fresh PyPI installs on Python
  3.11, 3.12, and 3.13, plus the live PyPI page's images, metadata, and documentation
  links. See [the final validation record](VALIDATION.md#final-release-checks--2026-11-03).
- `scripts/verify_external.py` builds the wheel and sdist, installs the wheel into a fresh venv
  outside the repo, and runs the copied suite and the demo. Results are in [VALIDATION.md](VALIDATION.md).

## Rules for the agent

1. **Never publish without the maintainer's explicit approval** for that specific upload,
   to TestPyPI or PyPI. Version numbers can never be reused, even after a deletion.
2. **Never create, request, store, or print PyPI tokens.** Publishing uses
   [Trusted Publishing](https://docs.pypi.org/trusted-publishers/) (GitHub OIDC). No secret exists.
3. **Do not change the CookieGuard engine.** The wheel must contain the published
   `@aiscihub/cookieguard-core` and `@aiscihub/cookieguard-playwright` 0.1.0, vendored with
   `node scripts/vendor_engine.mjs --published` (it vendors the published npm engine; `--registry`
   instead checks that the workspace still matches it). Do not edit `src/cookieguard_browser_use/_node/`.
4. **Work on a branch and open a PR.** Do not push to `main` or create tags without approval.
5. **Commit messages carry no AI attribution trailers** (for example no `Co-Authored-By: Claude`).
6. **Pin every GitHub Action to a full commit SHA** with a version comment, as the existing workflow does.
7. **Report failures as failures**, with the command and output. Do not weaken a check to make it pass.

## 0. Merge the integration — Maintainer

Review and merge `feat/browser-use-integration` into `main`. All later steps start from `main`.

## 1. One-time PyPI setup — Maintainer

1. Sign in to <https://pypi.org> and <https://test.pypi.org> as the `aiscihub` owner, with 2FA enabled.
2. On each site, add a **pending publisher** under *Your projects → Publishing*:
   - Project name: `cookieguard-browser-use`
   - Owner: `aiscihub`; repository: `cookieguard-ai`
   - Workflow filename: `publish-browser-use.yml`
   - Environment: `testpypi` on TestPyPI, `pypi` on PyPI
3. In GitHub → *Settings → Environments*, create `testpypi` and `pypi`. Give `pypi` a required
   reviewer (the maintainer) and restrict it to tags matching `browser-use-v*`.

## 2. Make the README render on PyPI — Agent

PyPI shows `README.md` as the project description, but relative links and images break there.
PyPI also strips `<picture>` and `<source>`, so only the fallback `<img>` (light diagram) remains.

- Add `hatch-fancy-pypi-readme==25.1.0` to `[build-system].requires`. Replace `readme = "README.md"`
  with `dynamic = ["readme"]` and a `[tool.hatch.metadata.hooks.fancy-pypi-readme]` config.
  Its substitutions should rewrite, in the PyPI copy only:
  - relative image paths (`docs/*.svg`, `docs/*.gif`) to
    `https://raw.githubusercontent.com/aiscihub/cookieguard-ai/<tag>/integrations/browser-use/…`;
  - relative page links (`docs/*.md`, `../../README.md`) to
    `https://github.com/aiscihub/cookieguard-ai/blob/<tag>/…`.
  Keep the repository README relative, so GitHub still renders local files.
- Pin `<tag>` to the release tag (`browser-use-v<version>`, currently `browser-use-v0.1.0`), not `main`, so the page matches the release.
- In `docs/install.md`, add the PyPI install command. It is a pre-release, so plain `pip install`
  will not select it:
  `pip install --pre cookieguard-browser-use` (or `pip install cookieguard-browser-use==0.1.0b1`).
  Keep the from-source steps, and state that Node.js 24+ and Chrome/Chromium are still required.
- Verify:
  1. `python -m build`, then `twine check --strict dist/*`, using twine 7.0.0.
  2. `python scripts/verify_metadata.py` extracts the wheel's `METADATA` and the sdist's
     `PKG-INFO`; confirm there are no relative links and all repository links use the release tag.
  3. Run the link checker below on the repo copy.

```bash
python3 - <<'EOF'
import re, pathlib
for f in [pathlib.Path('README.md'), *pathlib.Path('docs').glob('*.md')]:
    for t in re.findall(r'\]\(([^)\s]+)\)', f.read_text()) + re.findall(r'(?:src|srcset)="([^"]+)"', f.read_text()):
        if not t.startswith(('http', '#')) and not (f.parent / t.split('#')[0]).exists(): print('BROKEN', f, t)
EOF
```

## 3. Add the publish workflow — Agent

Create `.github/workflows/publish-browser-use.yml`:

- Triggers: `push` of tags `browser-use-v*`, plus `workflow_dispatch` with an input
  `target: testpypi | pypi`, default `testpypi`.
- Top-level `permissions: contents: read`.
- Job `build` on `ubuntu-latest`:
  1. `actions/checkout` with `persist-credentials: false`.
  2. Node 24 and Python 3.12, using the same pinned SHAs as `cookieguard-ci.yml`.
  3. `npm ci`, then `node integrations/browser-use/scripts/vendor_engine.mjs --published`.
  4. `python -m build` in `integrations/browser-use`, then `twine check --strict dist/*`.
  5. The `sudo sysctl -w kernel.apparmor_restrict_unprivileged_userns=0` step, then
     `npx --no-install playwright install --with-deps chromium`, then `python scripts/verify_external.py`.
  6. Upload `dist/` with `actions/upload-artifact@b7c566a772e6b6bfb58ed0dc250532a479d7789f # v6`.
- Job `publish-testpypi`:
  - `needs: build`; `environment: testpypi`; `permissions: id-token: write`.
  - Download with `actions/download-artifact@018cc2cf5baa6db3ef3c5f8a56943fffe632ef53 # v6.0.0`.
  - Publish with `pypa/gh-action-pypi-publish@7245906fb61fa33a13554f9d5fb856fe61758086 # v1.14.3`,
    with `repository-url: https://test.pypi.org/legacy/`.
- Job `publish-pypi`: the same, but `environment: pypi`, and it runs only for a tag push or `target == pypi`.
- Do not add API tokens or `password:` inputs. The action publishes through OIDC and creates attestations.

Open a PR with steps 2–3. CI must pass, and the maintainer reviews and merges it.

## 4. TestPyPI rehearsal — Maintainer approves, agent runs

1. With approval, run the workflow manually with `target: testpypi`.
2. In a new empty directory outside the repo, install without letting TestPyPI supply
   dependencies, since anyone can upload look-alike packages there:
   ```bash
   python3.12 -m venv venv && . venv/bin/activate
   pip install --no-deps --index-url https://test.pypi.org/simple/ cookieguard-browser-use==0.1.0b1
   pip install "browser-use>=0.13.14,<0.14" "cdp-use>=1.4.5,<2" "pydantic>=2.10,<3"
   ANONYMIZED_TELEMETRY=false python -m cookieguard_browser_use.demo; echo "exit=$?"   # expect 0
   ```
3. Check the TestPyPI project page:
   - the diagrams and GIF display;
   - the links open the tagged GitHub files;
   - Python ≥3.11 and the MIT license are shown.
4. Any problem means fix, bump to `0.1.0b2`, and repeat. TestPyPI versions can't be reused either.

## 5. Publish to PyPI — Maintainer approves

1. Update `CHANGELOG.md` with the release date. Open a PR, get it merged, then create and push the tag
   `browser-use-v<version>` (for this release, `browser-use-v0.1.0`) on that `main` commit (with approval).
   `scripts/verify_metadata.py` fails the workflow if the tag and package version differ.
2. The tag triggers the workflow. The maintainer approves the `pypi` environment when prompted.
3. Verify from PyPI in a fresh directory: `pip install cookieguard-browser-use==<version>`, then run the demo
   (expect exit 0). Also run the copied test suite, as `verify_external.py` does.
4. Create a GitHub release for the tag. Attach the wheel and sdist, plus their SHA-256 sums,
   and link the PyPI page and `VALIDATION.md`.
5. Record the PyPI install result in `VALIDATION.md`. In the READMEs, change "not yet on PyPI" to the
   install command.

**If something is wrong after publishing:** do not delete. The maintainer can *yank* the version on
PyPI, and the fix ships as the next patch version (after 0.1.0, `0.1.1`).

## Done when (0.1.0)

- [x] Hosted CI passes on the release PR: toolkit, plus Browser Use on Python 3.11, 3.12, and 3.13.
- [x] The changelog entry is dated, and the PR is merged to `main`.
- [x] Tag `browser-use-v0.1.0` is pushed with approval; the release workflow passes and publishes through `pypi`.
- [x] `pip install cookieguard-browser-use` (no `--pre`) installs 0.1.0 in clean venvs on Python 3.11–3.13.
- [x] The demo installed from PyPI returns insecure FAIL (exit 1) and secure PASS (exit 0).
- [ ] The PyPI page renders, with links pinned to `browser-use-v0.1.0`. The links are verified through
  PyPI's JSON API. The rendered page still needs a person's look: PyPI served its bot check to
  every automated browser.
- [x] The GitHub release has the wheel, sdist, and `SHA256SUMS`; VALIDATION.md records the published result.

## Done when (0.1.0b1, completed)

- [x] `pip install --pre cookieguard-browser-use` works in a clean venv on Python 3.11–3.13.
- [x] The demo installed from PyPI returns insecure FAIL (exit 1), secure PASS (exit 0), and overall exit 0.
- [x] The PyPI page renders, with absolute links pinned to the tag.
- [x] The release workflow uses Trusted Publishing, and the repo and logs contain no tokens.
- [x] The vendored engine equals the npm 0.1.0 packages (`--registry` passed in the build log).
- [x] The GitHub release has the artifacts and SHA-256 sums; VALIDATION.md and CHANGELOG are updated.

## After the release

1. Announce in Browser Use's Discord and GitHub Discussions (*Show and tell*) as a community
   integration, with the GIF and the "Add it to your agent" snippet.
2. Add a copy-paste Quickstart script and a pytest example to the docs, each verified by a run.
3. Add Python 3.14 to the CI matrix and the classifiers once it passes.
4. Run the OpenAI and Browser Use Cloud model paths of `examples/agent_login.py`.
5. Test on Windows and with Browser Use cloud browsers.
