# Changelog

## Unreleased — CookieGuard for Browser Use 0.1.0b1 (pre-release, not published)

- Add `integrations/browser-use`: the `cookieguard-browser-use` Python package for
  Browser Use 0.13.14 agents.
  - **Collection:** a dedicated CDP observer captures redirect-attributed `Set-Cookie`
    declarations and cookie-store metadata from the agent's browser.
  - **Evaluation:** a sandboxed local Node subprocess runs the unchanged published
    `@aiscihub/cookieguard-core` and `@aiscihub/cookieguard-playwright` 0.1.0 engine,
    vendored with per-file hashes.
  - **Agent tool:** an optional read-only `cookieguard_audit` action returns sanitized,
    provisional, store-only findings.
  - **Enforcement:** `audit.finish()` + `assert_policy()` with PASS/FAIL/INCOMPLETE
    and exit codes 0/1/2, independent of the agent.
- Add a loopback demo app with a real login form, a scripted deterministic agent
  demo (`python -m cookieguard_browser_use.demo`), an LLM example (verified with
  `claude-opus-5-5` plus server-side fallback), 89 tests
  (real Chromium, Agent loop, attribution, privacy canaries), and external wheel
  verification.
- Lint `.mjs` files and the integration; scan Browser Use evidence for its canary prefix;
  add a Browser Use CI job, which passes on `ubuntu-latest` (Python 3.12, Node 24, Chromium
  with its sandbox; the runner allows the user namespaces Ubuntu 24.04 restricts).
- Add a README demo recorded from a real `claude-opus-5-5` run (`scripts/record_demo.py`). It shows the
  agent's Chromium viewport, Browser Use's own log lines, and CookieGuard's verdict, with
  provenance. Also add an animated, theme-aware "how it works" diagram (pure CSS SVG,
  static under reduced motion), and a policy diagram showing which findings each `fail_on`
  setting fails.
- Split the Browser Use README into a short overview (policy diagram, demo, integration code)
  plus tab-style pages under `docs/`. Add `RELEASING.md`, a PyPI release runbook using Trusted Publishing.
- Prepare the Browser Use package description with release-tagged PyPI links and add a
  Trusted Publishing workflow for separately approved TestPyPI and PyPI uploads.
- Pin eslint's `minimatch` to 11.0.4 through an npm override, to clear GHSA-g3hv-75wg-m249 in the
  release gate's dependency audit. This is dev tooling only; published packages are unchanged.

## CookieGuard CI 0.1.0 — public beta — 2026-10-17

One coordinated release in `aiscihub/cookieguard-ai`: npm CLI for the first try,
Playwright for existing tests, and a GitHub Action for CI adoption. All three
integrations use the same core and remain in this repository.

Published npm packages: `cookieguard-ci`, `@aiscihub/cookieguard-core`, and
`@aiscihub/cookieguard-playwright`, all at `0.1.0` with the `beta` dist-tag.
The Action and tested tarballs are available in the
[`ci-v0.1.0` release](https://github.com/aiscihub/cookieguard-ai/releases/tag/ci-v0.1.0).

- Add `@aiscihub/cookieguard-core`, `cookieguard-ci`, and `@aiscihub/cookieguard-playwright` workspaces
  with ESM exports, TypeScript declarations, lockfile, linting, and automated tests.
- Reuse the original JavaScript feature extractor and rule classifier through a
  guarded Node export and generated package copy. Preserve the extension popup,
  original model, Python implementation, research, and archived README.
- Normalize headers, browser metadata, fixtures, and legacy results into value-free
  observations with explicit uncertainty and declaration/acceptance distinctions.
- Add nine stable rule IDs for configuration checks, comparable regressions,
  identity review, and evidence review. Require developer evidence for strict CI.
- Add bounded, loopback-first HTTP CLI scanning, sanitized text/JSON reports,
  optional baselines, and documented 0/1/2 exit codes.
- Add passive Playwright collection and a composite Action with summary, optional
  sanitized artifact, and delayed enforcement after upload.
- Add optional local ONNX Node inference with the existing model and feature order,
  disabled runtime telemetry, labeled triage, and no silent fallback.
- Add local demo, controlled benchmark, sentinel leakage checks, extension
  regressions, contributor docs, and a release procedure.
- Gate the beta on packaged CLI/Playwright consumers outside the workspace,
  exit 0/1/2 scenarios, withheld leaking output, dependency advisories, reviewed
  license expressions, source credential checks, and hosted Chromium/Action tests.

Known limits: no real-world labeled validation; Chromium-only browser verification;
header scans cannot log in or prove cookie acceptance; ambiguous/partitioned scopes
are conservative; no public-suffix inference or server session-expiry checks.
Fresh npm registry installs passed the CLI and Playwright exit 0/1/2 scenarios;
registry integrities match the tested tarballs. See
[validation evidence](docs/CI_VALIDATION.md) for observed results and limitations.
