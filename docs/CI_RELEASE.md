# CookieGuard CI release procedure

Published on **2026-10-17**:
[CookieGuard CI v0.1.0 — public beta](https://github.com/aiscihub/cookieguard-ai/releases/tag/ci-v0.1.0).
The npm CLI, Playwright adapter, and GitHub Action ship from `aiscihub/cookieguard-ai` as one
coordinated release of the same security engine. Keep code, issues, contributors,
and documentation in this repository.

The published packages are `cookieguard-ci`, `@aiscihub/cookieguard-core`, and
`@aiscihub/cookieguard-playwright`, each at `0.1.0` with the `beta` dist-tag.
Tag `ci-v0.1.0` identifies source commit
`12a09fe322b135ac2a5aec45cae1f880b717575f`. The GitHub prerelease includes the
three tested tarballs, `SHA256SUMS`, and a release manifest. Registry integrities
match the tested packages, and fresh registry installs passed the CLI and
Playwright scenarios below. See [the validation record](CI_VALIDATION.md).

## Merge and release gates

Push the implementation to a feature branch and open a pull request into `main`.
The checked-in workflow must pass on the PR's current commit before merge. It
installs Node 24 and Chromium on a GitHub-hosted Linux runner, runs the release
checks, and exercises the actual composite Action and artifact service.

| Scenario | Required result |
| --- | --- |
| Secure, explicitly identified authentication cookie | Exit 0 |
| Confirmed authentication cookie missing HttpOnly | Exit 1 |
| Expected authentication cookie not observed | Exit 2 |
| Synthetic sentinel token in a cookie | Absent from reports and logs |

These outcomes are checked in the CLI, Playwright adapter, and Action. CLI and
Playwright are also installed from packed tarballs in a temporary project outside
the monorepo, with an empty npm cache and registry access disabled. Browser tests
then use a separately packed Playwright runtime and the installed Chromium.
`tests/extension.test.js` explicitly checks the original extension's browser
globals, feature ordering, and classification against the Node adapter.

Review the dependency advisory result, locked license inventory, source credential
check, sanitized logs, and generated reports before merging. The source check
detects selected high-confidence credential formats; it is not a guarantee that
every possible secret format is absent. Sentinel-bearing test output is withheld
before it can enter the release log. New dependency license expressions fail the
gate until reviewed. Reports and reviewed evidence have seven-day artifact
retention in the hosted workflow.

## Reproducible source and packages

Use Node 24 LTS. A full source build:

```bash
npm ci
npx --no-install playwright install chromium
npm run release:check
```

Create local distribution tarballs after the build:

```bash
mkdir -p artifacts/packages
npm pack --workspace @aiscihub/cookieguard-core --pack-destination artifacts/packages
npm pack --workspace cookieguard-ci --pack-destination artifacts/packages
npm pack --workspace @aiscihub/cookieguard-playwright --pack-destination artifacts/packages
```

Install all three tarballs together in an empty temporary project (paths relative
to that project must point to this checkout's artifacts). For example, from the
repository root:

```bash
node scripts/verify-packages.js
```

The verification script builds and packs the workspaces, checks required exports,
license and engine files, rejects model/native artifacts in the lightweight
packages, and verifies all three exit codes through the installed executable and
browser adapter. CLI text/JSON and browser JSON reports are checked for sentinel
leakage. Tarballs and evidence under `artifacts/` are ignored by Git.

`npm run release:check` includes build, lint, declaration checking, Node tests,
Chromium tests, packaged-consumer checks, the benchmark, dependency advisories,
license inventory, source credential checks, and output leakage checks. It writes
reviewable evidence to `artifacts/release/`, `artifacts/packaged/`, and
`artifacts/dependency-licenses.json`.

Core has no runtime dependencies. CLI and Playwright depend only on the core.
Playwright and ONNX runtimes are optional peers; no native model or browser binary
is included in the lightweight tarballs. npm package licenses in the lockfile are
MIT, Apache-2.0, ISC, BSD-2-Clause, BSD-3-Clause, BlueOak-1.0.0, or MIT/CC0-1.0 dual
license. Preserve upstream notices when distributing dependencies; the generated
engine is covered by the project's MIT license. The model remains an existing
repository artifact, not a newly trained or bundled dependency.

## Before a public release

1. Review the source and privacy boundaries. Publishing uses npm account
   `aiscihub`, with `@aiscihub/cookieguard-core`, `cookieguard-ci`, and
   `@aiscihub/cookieguard-playwright`. Verify ownership and name/version
   availability again immediately before publication. Require a verified email
   and two-factor authentication; both were enabled for this release.
2. Run the checked-in workflow on the feature branch and pull request. Inspect
   summaries and artifacts, verify all required outcomes, and merge only after
   the current commit passes. Test any other claimed platforms separately.
3. Verify clean source installation, package tarballs, Node 24 support, original
   extension compatibility tests, and the validation report. Re-run dependency
   security and license review for the locked versions. Resolve audit findings
   before release.
4. Confirm npm publishing access. In one release window, publish core first, then
   CLI and Playwright at `0.1.0`, using the `beta` npm dist-tag and provenance
   where supported. Create an immutable reviewed `ci-v0.1.0` tag for the Action
   at the same source commit and record its SHA. Announce the public beta only
   after all three integrations are available and their installed use is checked.
5. Update installation examples to the actually published names/tag and announce
   the measured scope and limitations. Do not claim real-world detection accuracy.

Publish the exact tarballs that passed external-consumer checks, with explicit
`--access public --tag beta --registry=https://registry.npmjs.org`. Scoped
packages also declare those defaults in `publishConfig`. The root workspace is
private and must not be published. `artifacts/packages/manifest.json` records
the tested tarballs and their integrity digests. Keep browser-based npm 2FA
approval in the maintainer's browser; never put passwords or OTPs into scripts.

This beta uses an npm `beta` dist-tag and a GitHub prerelease, preserving the
existing extension releases. Local publication does not generate npm provenance;
do not claim provenance unless the registry reports a verified statement.

After all packages are published, run `node scripts/verify-packages.js --registry`
to repeat the CLI and Chromium outcomes from a fresh npm registry installation.
Evidence is written to `artifacts/published/`. Compare the registry's package
integrities with the tested manifest before creating the coordinated GitHub
prerelease and attaching the three tested tarballs.

## Highest-value follow-ups

1. Validate on consenting applications with independently labeled session roles.
2. Add Firefox/WebKit and Windows evidence tests.
3. Improve partitioned-cookie and repeated-header association without weakening
   uncertainty handling.
4. Add tested framework examples for common session middleware and HTTPS fixtures.
5. Consider scoped configuration files and richer baseline review only after the
   initial evidence model has production feedback.
