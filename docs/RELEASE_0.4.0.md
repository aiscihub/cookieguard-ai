# CookieGuard 0.4.0 release — November 13, 2026

This release adds default-on, best-effort package invocation reporting to
CookieGuard's PostHog US Cloud project `735326`. Events contain fixed package,
version, integration, and privacy fields with a fresh invocation ID. They exclude
cookie data, URLs, audit results, and persistent identity. Set
`COOKIEGUARD_USAGE_METRICS=0`, `DO_NOT_TRACK=1`, or an explicit API opt-out to
disable reporting. Existing 0.3.0 installations remain unchanged until upgraded.
See the [usage guide](USAGE_METRICS.md) for the contract and delivery limits.

## Source and release checks

[PR #52](https://github.com/aiscihub/cookieguard-ai/pull/52) automatically
squash-merged after all required checks passed. Release tag
[`cookieguard-v0.4.0`](https://github.com/aiscihub/cookieguard-ai/tree/cookieguard-v0.4.0)
identifies commit `f9027658cd55a687ed455f3aa389eeab3d51fd73`.

- [Hosted CI](https://github.com/aiscihub/cookieguard-ai/actions/runs/43561282237)
  passed the Node 24 packaged-consumer job and Browser Use jobs on Python
  3.11, 3.12, and 3.13. Python 3.12 also checked fresh installation and upgrades
  from the published 0.1.0, 0.2.0, and 0.3.0 packages.
- The local Node release gate passed lint, types, 132 Node tests, eight Chromium
  tests, isolated tarball consumers, the controlled benchmark, dependency/license
  review, source-credential checks, and output-leakage checks.
- Local Python installed-wheel validation passed 134 tests with two
  compatibility-only tests skipped in the canonical-only consumer. Clean wheel
  and source-distribution demos returned the expected insecure FAIL and secure
  PASS. All four distribution files passed strict `twine` checks, and canonical
  description links were pinned to the release tag.

The Python compatibility package requires exactly `cookieguard==0.4.0` and
re-exports its audit and flush helpers. The canonical Python package retains
the published npm engine 0.3.0, with child-process reporting disabled.

## Package publication

All four npm packages and both Python distributions are published at **0.4.0**.
The timestamps below are UTC on November 14, 2026; the release date in Los Angeles
was November 13. npm uses the `latest` dist-tag. The Python distributions were
uploaded by the existing
[Trusted Publishing workflow](https://github.com/aiscihub/cookieguard-ai/actions/runs/43562040077).

| npm package | Published at (UTC) | Registry integrity |
| --- | --- | --- |
| `@aiscihub/cookieguard-core@0.4.0` | `2026-11-14T05:34:41.138Z` | Matches tested tarball |
| `cookieguard-ci@0.4.0` | `2026-11-14T05:37:27.706Z` | Matches tested tarball |
| `@aiscihub/cookieguard-playwright@0.4.0` | `2026-11-14T05:37:34.181Z` | Matches tested tarball |
| `@aiscihub/cookieguard-mcp@0.4.0` | `2026-11-14T05:40:01.692Z` | Matches tested tarball |

The npm uploads used normal browser 2FA and the exact tarballs that passed
isolated-consumer checks. They were published locally; no npm provenance is
claimed. Registry metadata became visible before every tarball reached the CDN.
The first fresh CLI consumer attempt returned HTTP 404 for its tarball; it was
retained as a propagation failure, not treated as a passed install or retried
upload. After that cached response expired, normal fresh-registry installation
with an empty npm cache passed:

- CLI text and JSON scans returned the expected exit codes 0, 1, and 2; files,
  stdout, and stderr matched the required results without sentinel leakage.
- The npm-installed Playwright adapter passed the Chromium scenarios for exit
  codes 0, 1, and 2.
- A separate clean MCP registry consumer passed tool discovery, rule explanation,
  audits returning exit codes 0, 1, and 2, and the evidence-file audit returning
  exit code 1. No synthetic cookie-value sentinel appeared in output.

All four actual npm downloads also match the tested files by SHA-256. Reporting
was explicitly disabled in these final consumers, including MCP SDK children.

| PyPI distribution file | Uploaded at (UTC) | SHA-256 |
| --- | --- | --- |
| `cookieguard-0.4.0-py3-none-any.whl` | `2026-11-14T05:38:51.000666Z` | `ac81246f0bd0571d9b13a957f1bb05706eb0cdce33f98f6fedf2d9736a192cf8` |
| `cookieguard-0.4.0.tar.gz` | `2026-11-14T05:38:53.550739Z` | `0c3b81be1ad97ce28dd06b1d09bb4045aa12b871de89ccda175f6153913185e8` |
| `cookieguard_browser_use-0.4.0-py3-none-any.whl` | `2026-11-14T05:38:52.484389Z` | `17c4a884bd928673c67900e1b589ff6c2e9d8e8aa852affd713bf429bb705de9` |
| `cookieguard_browser_use-0.4.0.tar.gz` | `2026-11-14T05:38:54.506260Z` | `cc2af875a84cff05465c115261910a551e3d3f8048e7c1f9acb2790bc9c0af3e` |

The PyPI JSON metadata and actual downloads of all four files match the workflow
artifacts by size and SHA-256; none is yanked. A fresh official-PyPI install in an
external Python 3.12.16 virtualenv passed `pip check`, verified shared canonical
and compatibility audit/flush objects, and verified the pinned engine 0.3.0 hashes.
With reporting disabled, the installed Chromium demo returned insecure FAIL
(exit 1) and secure PASS (exit 0), with no sentinel leakage. It used browser-use
0.13.14 and cdp-use 1.4.5. Hosted CI supplies the separate Python 3.11 and 3.13
coverage; a fresh registry install on those versions was not repeated locally.

## MCP Registry

The [official registry entry](https://registry.modelcontextprotocol.io/v0.1/servers/io.github.aiscihub%2Fcookieguard/versions/0.4.0)
for `io.github.aiscihub/cookieguard` 0.4.0 is active and latest, published at
`2026-11-14T05:41:17.591521Z`. It points to npm
`@aiscihub/cookieguard-mcp@0.4.0`, with stdio transport and the required `--config`
argument. Publisher v1.8.9 was verified against official checksums and its GitHub
asset digest before use. An initial submission returned HTTP 401 because its
registry login had expired; refreshing through the existing GitHub authentication
and retrying succeeded. No registry change occurred on the failed attempt.

## Metrics cutoff

For initial 0.4.0 adoption charts, filter to `package_version = 0.4.0` and events
**after `2026-11-14T05:44:21Z`** (November 13, 2026, at 9:44:21 p.m. PST).
This cutoff was recorded after publication, all fresh-registry consumer checks,
and the [release-tag CI run](https://github.com/aiscihub/cookieguard-ai/actions/runs/43562024319)
finished. It conservatively excludes any legitimate consumer invocations that
arrived during the same release-validation interval.

MCP SDK subprocess launchers originally dropped the parent's
`COOKIEGUARD_USAGE_METRICS=0` and `DO_NOT_TRACK=1` environment settings. Some
synthetic 0.4.0 MCP invocations from local or hosted validation may therefore
have reached PostHog. The invocation IDs were not logged and receipt was not
verified, so the affected events cannot be removed by an exact ID list. The
follow-up validation launchers pass both opt-outs explicitly to the child
process. This correction changes validation code, not the published package
runtime.

Also exclude the two known 0.2.0 CLI pilot invocation IDs in
[USAGE_METRICS_VERIFICATION.json](USAGE_METRICS_VERIFICATION.json). That historical
record is unchanged. The owner verified those two events in PostHog; project-level
privacy settings and saved-dashboard creation remain unverified. Report totals
as **reported audit invocations**, not unique users, installations, or successful
audits.
