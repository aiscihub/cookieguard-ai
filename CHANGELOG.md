# Changelog

## cookieguard 0.3.0 (Python) — prepared, not yet published

`cookieguard` and the compatibility package `cookieguard-browser-use` move to 0.3.0 in
lockstep. The vendored engine moves from the published npm 0.1.0 to the published 0.3.0
(`@aiscihub/cookieguard-core` and `@aiscihub/cookieguard-playwright`). Code written for
0.2.0 keeps working; anyone pinned to `cookieguard==0.2.0` stays on it.

- **Session checks for Browser Use.** New `CookieGuardAudit` options, all opt-in:
  `session_probe_url` (CG010, session id not rotated at login; CG011, session still valid
  after logout), `require_logout`, `auth_storage_keys` (CG012, token in Web Storage), and
  `collect_storage`. Undecidable probes are INCOMPLETE. Values stay in the local process.
- **Engine 0.3.0.** A configured credential that page script set and logout deleted is
  judged from its last store observation, and `Set-Cookie` lines without a cookie name no
  longer make a collection INCOMPLETE. Explanations cover CG010–CG012.
- **Demo.** The demo app's pages are restyled in the paper-and-ink style of the README demo,
  which was re-recorded from a real `claude-opus-5-5` run. `scripts/record_demo.py` keeps
  the raw capture so `--recompose` can restyle a run without repeating it.
- `vendor_engine.mjs` workspace mode no longer requires the pinned published version, so
  CI vendors the engine from this repository. `verify_upgrade.py` reads the version from
  `pyproject.toml` and also checks the upgrade from 0.2.0.
- The capability document lists `cookieguard` 0.3.0, with Browser Use as a surface of the
  session and Web Storage checks.

## CookieGuard 0.3.0 — fail-closed Playwright gate — 2026-11-08

Published on npm on 2026-11-08 (UTC) under `latest`, byte-identical to the tarballs packed
from `99e83ba` (#44); see
[the publication record](packages/mcp/VALIDATION.md#030-publication--2026-11-08). The MCP
Registry still lists 0.2.0.

npm packages `@aiscihub/cookieguard-core`, `cookieguard-ci`,
`@aiscihub/cookieguard-playwright`, and `@aiscihub/cookieguard-mcp` move to 0.3.0 with
exact internal dependencies. The Python package (`cookieguard` 0.2.0 on PyPI) is not part
of this release and keeps its pinned engine. Users pinned to `^0.2.0` stay on 0.2.x.

- **Fail-closed login gate.** `cookieGuardFixtures()` in `@aiscihub/cookieguard-playwright`
  adds a `cookieGuard` fixture: a login test that takes it is audited end to end, writes
  value-free evidence, and fails with only the blocking findings. `cookieguard-ci gate`
  re-evaluates that evidence under its own policy and ignores the test runner's exit code.
  A required check with no fresh, valid evidence is INCOMPLETE (`evidence-missing`,
  `evidence-invalid`, `evidence-stale`, `session-check-not-run`), so a skipped, filtered,
  or deleted test cannot pass. A confirmed violation is FAIL even when another check was
  inconclusive. See `examples/playwright-gate` and `benchmarks/security-gate`.
- **Session checks, released for Playwright.** CG010 (session id not rotated at login) and
  CG011 (session still valid after logout) use an opt-in session probe that replays the
  configured authentication cookies to one protected URL you name; undecidable probes are
  INCOMPLETE. CG012 reports tokens kept in `localStorage` or `sessionStorage`, confirmed
  for configured `authStorageKeys`. Values stay in the local process and never appear in
  results. Reports gain `session` and `storage` sections, which evidence files and the MCP
  server re-evaluate. The Browser Use integration has these checks in source only.
- **Collector fixes.** A configured credential that page script set and logout deleted is
  now judged from its last store observation instead of being reported as not observed.
  A `Set-Cookie` line without a cookie name, which cannot set a configured cookie, is
  skipped instead of making the whole collection INCOMPLETE.
- **MCP server.** Tools are unchanged; it uses the 0.3.0 engine, so `cookieguard_explain`
  covers CG010–CG012 and the gate's reasons. `server.json` is 0.3.0.
- The capability document lists 0.3.0 and marks every operation released.

## cookieguard 0.2.0 (Python) — 2026-11-06

Published on PyPI with `cookieguard-browser-use` 0.2.0; see
[the publication record](integrations/python/VALIDATION.md#cookieguard-020-and-cookieguard-browser-use-020-publication--2026-11-06).


- `cookieguard` is now CookieGuard's Python package. The shared core (results, errors,
  origin checks, and the vendored engine) is `cookieguard`. Each integration is a
  subpackage; the first is `cookieguard.browser_use`. `from cookieguard import
  CookieGuardAudit` keeps working and loads the integration on first use.
- `cookieguard-browser-use` 0.2.0 becomes a compatibility package. It depends on
  `cookieguard==0.2.0`, re-exports its API under `cookieguard_browser_use`, aliases the
  demo modules, and keeps `python -m cookieguard_browser_use.demo` working.
- The source moves from `integrations/browser-use` to `integrations/python`, with the
  compatibility package in `compat/`. One workflow, `publish-cookieguard.yml`, releases
  both in lockstep; `publish-browser-use.yml` and `integrations/pypi-cookieguard` are removed.
- `verify_upgrade.py` checks a fresh install and upgrades from both 0.1.0 releases: the
  same objects under both names, no stale 0.1 files, engine verification, and `pip check`.
  CI runs it on Python 3.12, and the release workflow runs it before publishing.
- No behavior changes. The vendored engine is still the published npm 0.1.0, and result
  JSON still identifies the integration as `cookieguard-browser-use`.

## Unreleased — Agent Skill for marketplaces

- The Agent Skill is now `cookieguard-browser-auth-security` ("CookieGuard AI — Browser
  Agent Authentication Security Audit"), restructured for distribution on its own. It
  covers when and when not to use it, the trust boundary between agent, browser
  automation, and CookieGuard, an A-E workflow (detect, install with consent, audit,
  interpret, report), a report template, and redaction rules. References cover
  installation, Browser Use, Playwright and CI, MCP, security checks, and findings, plus
  a real worked example. It adds a README and LICENSE.
- `npm run package:skill` builds a reproducible ZIP after a pre-submission scan, and
  `integrations/browser-use/scripts/check_skill_examples.py` checks the skill's Python
  examples against the installed `cookieguard_browser_use` API in CI.
- The Claude Code plugin keeps the name `cookieguard`; its source moved to the renamed folder.

## cookieguard 0.1.0 (PyPI alias) — 2026-11-06

- `pip install cookieguard` installs `cookieguard-browser-use` 0.1.x and re-exports its
  public API, so `from cookieguard import CookieGuardAudit` works. Agents in the discovery
  benchmark probed this name. Published with Trusted Publishing from tag
  `cookieguard-v0.1.0`; see [the publication record](integrations/pypi-cookieguard/VALIDATION.md).

## CookieGuard 0.2.0 — agent discovery — 2026-11-06

Published on npm on 2026-11-06 under `latest`, byte-identical to the tarballs packed from
`1f0ede1`, and listed in the MCP Registry as `io.github.aiscihub/cookieguard` 0.2.0; see
[the publication record](packages/mcp/VALIDATION.md#020-publication--2026-11-06).

npm packages `@aiscihub/cookieguard-core`, `cookieguard-ci`,
`@aiscihub/cookieguard-playwright`, and `@aiscihub/cookieguard-mcp` move to 0.2.0 under
the default `latest` dist-tag. Playwright's code is unchanged; its version follows core.
`cookieguard-browser-use` stays at 0.1.0 and keeps the published 0.1.0 engine. Report
`toolVersion`, the CLI's `--version` and user agent, and the MCP version now come from
each package manifest.

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
