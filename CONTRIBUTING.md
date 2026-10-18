# Contributing

CookieGuard CI extends the original CookieGuard AI work. Preserve its authorship,
award references, model weights, evaluation artifacts, and extension behavior.
The project remains MIT licensed. Read `docs/CI_ARCHITECTURE.md` before changing
normalization, classification, or policy decisions.

## Development

Use Node 24 LTS (`.nvmrc`) and npm. From a clean checkout:

```bash
npm ci
npx --no-install playwright install chromium
npm run check
npm run release:check
```

Linux runners need `playwright install --with-deps chromium`. Tests require
loopback port binding and a permitted Chromium launch. Do not run a separate
demo on port 3000 while running the Playwright example. Native CPU binaries are
included by the pinned ONNX dependency; CUDA is unnecessary. To skip optional
CUDA downloads with npm versions that run its install script, use
`ONNXRUNTIME_NODE_INSTALL=skip npm ci`.

`npm run build` copies the canonical extension engine and MIT license into package
artifacts and verifies exports. Generated vendor files are ignored. Do not edit
or commit a second classifier implementation. Each package has explicit exports
and maintained declaration files; `tests/public-api.ts` checks consumption.

Unit/integration tests cover policy decisions, collection failures, HTTP scan
boundaries, real model inference, extension features/classifications, CLI exit
codes, and the local Action runner. Playwright tests use the entirely local demo.
Expected insecure cases are asserted as failures without making the suite fail.
No public endpoint is part of test coverage.

`npm run release:check` also installs the packaged CLI and Playwright adapter
outside the workspace and checks exit 0/1/2 in each. It runs the dependency
advisory, license, source credential, benchmark, and output leakage gates. The
GitHub workflow additionally exercises all three composite Action outcomes on
Linux. Merge a release PR only after its current commit passes those checks.

## Correctness and privacy

- Keep unknown declarations and effective browser SameSite separate.
- Treat model scores as triage, never validated identity or exploit evidence.
- Require developer evidence for confirmed CI failures.
- Use new allowlisted report objects; never spread raw browser cookies, legacy
  results, request headers, exception objects, or arbitrary context into reports.
- Use synthetic sentinel tokens and check normal, malformed-input, and exception
  paths. Never add real credentials, cookie exports, HAR, or traces to fixtures.
- Test substantive security behavior and false positives. Do not weaken assertions
  to accommodate an implementation bug.

Update architecture, public API declarations, examples, and release notes when
behavior changes. Record measured benchmark results with runtime/platform and
limitations; never describe synthetic accuracy as real-world performance.

## Pull requests and releases

Describe the concrete problem, resulting behavior, and actual checks run. Keep
source changes focused. Use the repository's private reporting process for
security issues (SECURITY.md); public issues must use sanitized reproductions.
See `docs/CI_RELEASE.md` for package verification and the explicit release gates.
Do not publish packages, tags, or announcements as part of routine development.
