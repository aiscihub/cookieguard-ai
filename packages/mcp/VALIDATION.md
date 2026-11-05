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

## npm publication — 2026-11-05

The maintainer published the reviewed tarball from their own npm session as `aiscihub`:

```bash
npm publish aiscihub-cookieguard-mcp-0.1.0-beta.1.tgz --access public --tag beta --registry=https://registry.npmjs.org
```

Before the upload, `npm run verify:mcp` re-packed the tarball from `main` at `83fc76d`
(PR #27) and exited 0. The tarball was byte-identical to the one tested on the PR branch:

```text
sha256     bc048a2f6ab1b1030d27de33a5353f4bcaa5890f547133ad27899ffc62f1a63e
integrity  sha512-PJ0kg69A7bthOufaqX2gRpqHolxDXIHqf2tpdoOejHRRMhkS3Ly+jkk3YMaNZvSFQeFNewiZW6qcM1ynQ5KewA==
```

npm's staged publishing created the public `0.0.0-stage` placeholder at 20:48:21 UTC.
`0.1.0-beta.1` was released at 20:49:38 UTC, during the maintainer's publish session;
`npm stage list` afterwards reported no staged versions. Registry metadata after release:

| Field | Value |
| --- | --- |
| Versions | `0.0.0-stage`, `0.1.0-beta.1` |
| Dist-tags | `latest` and `beta` both point to `0.1.0-beta.1` |
| `mcpName` | `io.github.aiscihub/cookieguard` |
| Integrity | Matches the tested tarball; the downloaded registry tarball is byte-identical |
| Files | 8 |
| Dependencies | `@aiscihub/cookieguard-core` 0.1.0, `cookieguard-ci` 0.1.0, `@modelcontextprotocol/server` 2.4.0, `zod` 4.6.7 |
| Provenance | None (published locally) |

Installed from npm in a new directory with an empty npm cache, on macOS (arm64) with
Node.js v26.10.0 and npm 11.19.1:

- `npm install @aiscihub/cookieguard-mcp@0.1.0-beta.1` added 6 packages, all resolved
  from `registry.npmjs.org`. `npm audit signatures` reported verified registry signatures
  for all 6.
- The repository's MCP SDK client (`examples/mcp/run.js`) against the installed binary,
  exit 0:

  ```text
  MCP tools: cookieguard_policy, cookieguard_scan
  secure: PASSED (exitCode 0)
  missing-httponly: FAILED (exitCode 1) — CG001 Missing HttpOnly
  preference: INCOMPLETE (exitCode 2)
  MCP demo passed; cookie-value canary absent from results and diagnostics.
  ```

- `npx --yes @aiscihub/cookieguard-mcp@0.1.0-beta.1 --version` and
  `npx --yes @aiscihub/cookieguard-mcp --version` (which resolves `latest`), each with an
  empty cache, both printed `0.1.0-beta.1`.

Not yet done: registration in the MCP Registry, and testing in named desktop MCP
clients. Only the official MCP SDK client has been used.

## 0.1.0 publication — 2026-11-05

### npm

The maintainer published the tarball re-packed from `main` at `ce705d9` (PR #28) from
their own npm session:

```bash
npm publish aiscihub-cookieguard-mcp-0.1.0.tgz --access public --registry=https://registry.npmjs.org
```

Before the upload, `npm run verify:mcp` on `main` exited 0, and the tarball was
byte-identical to the one tested on the PR branch:

```text
sha256     9cef3be1fc773711a7c67f5ca1f06abd8a8db050d1bc5856d684dda61c917815
integrity  sha512-c8sGonAUGpmZ9csH/NDfhZFUVP+OZVaWCQzfDH+g+bIg3QBA26kJS7VMfQtS571QL594WnhDRdehQIPoYDWwyQ==
```

`0.1.0` was published at 21:42:13 UTC. Compared with the published beta tarball, only
`README.md`, `package.json`, and `server.json` differ; `bin/` and `src/` are identical.
Registry metadata after release:

| Field | Value |
| --- | --- |
| Versions | `0.0.0-stage`, `0.1.0-beta.1`, `0.1.0` |
| Dist-tags | `latest` points to `0.1.0`; `beta` still points to `0.1.0-beta.1` |
| `mcpName` | `io.github.aiscihub/cookieguard` |
| Integrity | Matches the tested tarball; the downloaded registry tarball is byte-identical |
| Files | 8 |
| Dependencies | `@aiscihub/cookieguard-core` 0.1.0, `cookieguard-ci` 0.1.0, `@modelcontextprotocol/server` 2.4.0, `zod` 4.6.7 |
| Provenance | None (published locally) |

Installed from npm in a new directory with an empty npm cache, on macOS (arm64) with
Node.js v26.10.0 and npm 11.19.1:

- `npm install @aiscihub/cookieguard-mcp@0.1.0` added 6 packages, all resolved from
  `registry.npmjs.org`. `npm audit signatures` reported verified registry signatures
  for all 6.
- The repository's MCP SDK client (`examples/mcp/run.js`) against the installed binary,
  exit 0:

  ```text
  MCP tools: cookieguard_policy, cookieguard_scan
  secure: PASSED (exitCode 0)
  missing-httponly: FAILED (exitCode 1) — CG001 Missing HttpOnly
  preference: INCOMPLETE (exitCode 2)
  MCP demo passed; cookie-value canary absent from results and diagnostics.
  ```

- `npx --yes @aiscihub/cookieguard-mcp@0.1.0 --version` and
  `npx --yes @aiscihub/cookieguard-mcp --version`, each with an empty cache, both
  printed `0.1.0`.

### MCP Registry

- The publisher was `mcp-publisher` v1.8.7 from the official `modelcontextprotocol/registry`
  GitHub release. The SHA-256 of `mcp-publisher_darwin_arm64.tar.gz`
  (`b63dc083beb27e1a44c07c252ac147ff2c34af2f7822f705a17f8d0e1b44d592`) matched the
  release's checksum file. Its Sigstore bundle was not checked.
- `server.json` was taken from the published npm 0.1.0 tarball and is identical to
  `main`. `mcp-publisher validate` against the live registry printed
  `✅ server.json is valid`.
- The maintainer authenticated with `mcp-publisher login github` and ran
  `mcp-publisher publish`:

  ```text
  Publishing io.github.aiscihub/cookieguard@0.1.0 to https://registry.modelcontextprotocol.io...
  ✓ Successfully published
  ✓ Server io.github.aiscihub/cookieguard version 0.1.0
  ```

- `GET https://registry.modelcontextprotocol.io/v0.1/servers?search=io.github.aiscihub/cookieguard`
  returned one entry: version 0.1.0, status `active`, marked latest, published
  2026-11-05T22:18:23Z. It names npm package `@aiscihub/cookieguard-mcp` 0.1.0 with
  stdio transport and a required `--config` file-path argument. Apart from `$schema`,
  the listing matches the published `server.json`.

Not yet done: testing in named desktop MCP clients. Only the official MCP SDK client
has been used.
