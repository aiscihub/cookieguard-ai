# MCP implementation verification

Verified locally on November 3, 2026, using Node.js `v26.10.0` and npm `11.19.1`.
This is implementation evidence for `0.1.0-beta.1`, not evidence of publication.
The existing CI toolkit job uses Node.js 24; its hosted result is recorded on the PR.

## Commands and observed results

`npm run build` — exit 0:

```text
Build: canonical engine, package licenses, and exports verified.
```

`npm run test:mcp` — exit 0 after correcting the fixture described below:

```text
ℹ tests 9
ℹ suites 0
ℹ pass 9
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
```

The nine tests cover real stdio discovery/calls in legacy and 2026-07-28 modes,
output schema validation, pass/fail/incomplete outcomes, exact-origin boundaries,
policy override rejection, config snapshots, remote metadata/value privacy,
explicit output truncation, redirects, HTTP failures, timeout/concurrency limits,
unknown-identity review, and safe startup errors.

`npm run verify:mcp` — exit 0:

```text
MCP package: aiscihub-cookieguard-mcp-0.1.0-beta.1.tgz; required files and registry metadata match.
Offline MCP install passed with an empty npm cache and packed locked runtime dependencies.
MCP tools: cookieguard_policy, cookieguard_scan
secure: PASSED (exitCode 0)
missing-httponly: FAILED (exitCode 1) — CG001 Missing HttpOnly
preference: INCOMPLETE (exitCode 2)
MCP demo passed; cookie-value canary absent from results and diagnostics.
Isolated MCP tarball consumer passed; no client SDK, browser, or native runtime installed.
```

This installs local core, CLI, and MCP tarballs plus the installed, locked MCP SDK
and Zod dependencies into a temporary consumer with an empty npm cache. It
validates offline packaging and dependency resolution without workspace links or
cached registry metadata. A published-npm consumer check remains a release-stage task.

`npm run lint` and `npm run typecheck` — both exit 0, with no diagnostics after
their command banners.

`node scripts/check-source-secrets.js` — exit 0 at the time of the check:

```text
Source credential check: 230 files checked; no supported credential patterns found.
```

`node scripts/check-licenses.js` — exit 0:

```text
License gate: 131 locked package entries use reviewed license expressions.
```

`npm audit --audit-level=low` — exit 0:

```text
found 0 vulnerabilities
```

`mcp-publisher validate packages/mcp/server.json` using official publisher
`v1.8.7` — exit 0, without login or publication:

```text
Validating against https://registry.modelcontextprotocol.io...
✅ server.json is valid
```

The publisher archive's SHA256 matched the checksum in the official release:
`b63dc083beb27e1a44c07c252ac147ff2c34af2f7822f705a17f8d0e1b44d592`.
Registry validation checks metadata; it does not establish that the npm package
has been uploaded or that namespace ownership has been authenticated.

## Failed attempts and corrections

- The first `node --test --test-timeout=30000 tests/mcp.test.js` attempt exited 1:
  the sandbox rejected fixture binding with `listen EPERM: operation not permitted
  127.0.0.1`, causing all nine tests to fail their setup. The permitted local-network
  run exercised the tests.
- That run reported eight passes and one failure. The test expected a finding for
  an unconfigured cookie whose synthetic name the engine classified as preference.
  The fixture now uses a `session_` prefix to exercise authentication-candidate
  findings. No classifier or policy behavior was changed. All nine then passed.
- Publisher extraction initially failed because the system Python did not support
  `tarfile.extractall(filter=...)`. The verified archive's single executable was
  extracted explicitly instead.
- The first registry validation attempt exited 1 because sandbox DNS access was
  blocked (`no such host`). Validation with permitted network access succeeded.
- The initial [Node 24 CI job](https://github.com/aiscihub/cookieguard-ai/actions/runs/41758744428/job/126341070026)
  failed at `installed-mcp-tarball` with `ENOTCACHED` for
  `@modelcontextprotocol/server`. The original verifier incorrectly assumed that
  `npm ci` cached the registry metadata required by a fresh offline install.
  It now packs the installed runtime dependencies, checks their versions against
  the lockfile, and installs with an explicitly empty temporary cache. The
  corrected `npm run verify:mcp` exited 0 with the output above. Targeted ESLint
  on `scripts/verify-mcp-package.js` and `git diff --check` also exited 0.
  Before this packaging failure, CI passed all 38 Node tests and 8 Playwright
  tests; all three Browser Use Python jobs passed as well.

No full Browser Use or Playwright suite was rerun locally for this adapter. Their
runtime code, vendored engine, and published package versions were not changed.
Nothing was merged, tagged, uploaded to npm, or registered in the MCP Registry.
