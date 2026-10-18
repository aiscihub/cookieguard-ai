# Changelog

## CookieGuard CI 0.1.0 — public beta, unreleased

One coordinated release in `aiscihub/cookieguard-ai`: npm CLI for the first try,
Playwright for existing tests, and a GitHub Action for CI adoption. All three
integrations use the same core and remain in this repository.

- Add `@cookieguard/core`, `cookieguard-ci`, and `@cookieguard/playwright` workspaces
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
  regressions, contributor docs, and a proposed release procedure.
- Gate the beta on packaged CLI/Playwright consumers outside the workspace,
  exit 0/1/2 scenarios, withheld leaking output, dependency advisories, reviewed
  license expressions, source credential checks, and hosted Chromium/Action tests.

Known limits: no real-world labeled validation; Chromium-only browser verification;
header scans cannot log in or prove cookie acceptance; ambiguous/partitioned scopes
are conservative; no public-suffix inference or server session-expiry checks.
Package publication and the immutable release tag remain pending the coordinated
release procedure. See `docs/CI_VALIDATION.md` for observed verification results.
