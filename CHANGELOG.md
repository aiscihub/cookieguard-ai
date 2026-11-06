# Changelog

## Unreleased — agent discovery

Not published. The packages below keep version 0.1.0 until a release is approved.

- **Capability interface.** `cookieguard-ci capabilities --json` and the generated
  `cookieguard.capabilities.json` describe every check, operation, input, permission,
  privacy property, output schema, exit code, and limitation. `cookieguard-ci explain ID`
  explains rule IDs, incomplete reasons, error codes, and statuses. `--json` is a shortcut
  for `--format json`, and JSON mode now prints a machine-readable error on stdout.
- **JSON Schemas** for the core report, MCP audit and explain results, CLI errors, and
  capabilities are published under `schemas/`, generated from the zod schemas the MCP
  server enforces.
- **Evidence files.** `@aiscihub/cookieguard-core` adds `readEvidence()`: a sanitized
  CookieGuard report or Browser Use result can be re-evaluated under a new policy. Values
  and unknown fields are dropped; provisional or incomplete collections stay incomplete.
  `cookieguard-ci scan --input` accepts these reports.
- **MCP server.** New tools `cookieguard_capabilities`, `cookieguard_audit` (`url`, or
  `evidenceFile` inside an optional startup `evidenceDir`), and `cookieguard_explain`.
  Findings add `evidenceSource` and `identityBasis`; results add `provenance`. The 0.1.0
  tools are unchanged apart from these added fields.
- **Agent Skill** `skills/cookieguard` (Agent Skills format) and a Claude Code plugin
  marketplace file. `scripts/check-skill.js` checks the skill against the specification.
- **Discovery benchmark** under `benchmarks/discovery`: 24 tasks that never name the
  tool, run as 80 real Claude Code sessions. Agents found CookieGuard in 0/24 runs with
  ordinary tools, 0/24 with web search, 23/24 with the Agent Skill installed, and 8/8 with
  the MCP server configured. See its README for method and limits.
- **End-to-end check:** `integrations/browser-use/scripts/agent_discovery_e2e.py` runs a
  real Browser Use login, then audits the evidence through the MCP server with the
  Python MCP SDK. It passes in CI on Linux with Python 3.11-3.13.
- Package metadata: npm keywords, homepage, and issue links; PyPI keywords, classifiers,
  and Documentation/Changelog URLs. They take effect on the next publish.
- `llms.txt`, a minimal GitHub Actions example, and `docs/agent-discovery.md`.

## CookieGuard MCP 0.1.0 — first stable release — 2026-11-05

The code is the same as 0.1.0-beta.1; only the version changed.

- Publish under the default `latest` npm dist-tag. Run it with
  `npx --yes @aiscihub/cookieguard-mcp@0.1.0 --config <path>` on Node.js 24+.
- Listed in the official MCP Registry as `io.github.aiscihub/cookieguard`, version 0.1.0.
- Tested with the official MCP SDK client on Linux (Node.js 24) and macOS
  (Node.js 26). Desktop MCP clients have not been tested yet.

## CookieGuard MCP 0.1.0-beta.1 — preview — 2026-11-05

- Add `@aiscihub/cookieguard-mcp`, a local stdio MCP server with two tools:
  - `cookieguard_policy` shows the allowed origins and the policy in force.
  - `cookieguard_scan` audits one allowed URL's `Set-Cookie` headers and returns
    PASS / FAIL / INCOMPLETE with rule IDs, explanations, and fixes.
- The allowed origins, policy, and timeout are fixed at startup from a local
  configuration file; the client can choose only which URL to scan.
- The server uses the published `cookieguard-ci` scanner and
  `@aiscihub/cookieguard-core` policy engine at 0.1.0. Results never contain cookie
  values or arbitrary observed cookie names.
- Add MCP Registry metadata (`server.json`, name `io.github.aiscihub/cookieguard`).
- Run it with `npx --yes @aiscihub/cookieguard-mcp@0.1.0-beta.1 --config <path>`
  on Node.js 24+. The core, CLI, Playwright, and Browser Use packages are unchanged.

## CookieGuard for Browser Use 0.1.0 — first stable release — 2026-11-04

The code and behavior are the same as 0.1.0b1. Since the `browser-use-v0.1.0b1` tag, only
the version string changed in `src/cookieguard_browser_use`, and the vendored engine is
still the published `@aiscihub/cookieguard-core` and `@aiscihub/cookieguard-playwright` 0.1.0.

- Release 0.1.0 as a final version: `pip install cookieguard-browser-use` no longer needs
  `--pre`. Package description links are pinned to `browser-use-v0.1.0`.
- `scripts/verify_external.py` now also installs the sdist into a second clean venv,
  where pip builds it from source. It checks the engine hashes and runs the end-to-end demo.
- Document the tested environments:
  - Linux with Python 3.11–3.13 and macOS with Python 3.12;
  - Browser Use 0.13.14 and Chromium-family browsers 156.
- Document the dependency advisories inherited from Browser Use 0.13.14's exact pins:
  `anyio`, `mcp`, `pillow`, and `pypdf`. CookieGuard does not import them and cannot
  change those pins.
- Known limits are unchanged. Windows, Browser Use cloud browsers, other Browser Use
  versions, and model providers other than `claude-opus-5-5` remain untested.

## CookieGuard for Browser Use 0.1.0b1 — pre-release — 2026-11-03

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
- Lead the main README with Browser Use, followed by the Chrome extension and CI tools;
  keep the detailed CLI, Playwright, and Action instructions in `docs/CI_GUIDE.md`.
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
