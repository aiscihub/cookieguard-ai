# CookieGuard as an optional Browser Use integration

Investigated November 4, 2026. Selected proposal: **CookieGuard AI: Independent
authentication-cookie security auditing for Browser Use workflows.** Use the
existing insecure-login versus secure-login demo as a small community example,
with an entry in `examples/integrations/README.md`. Maintainers can run and see
the actual policy result. The one-entry listing remains the smallest fallback;
no Browser Use runtime change is needed.

## Compatibility and package provenance

PyPI's latest stable Browser Use release is **0.13.14**, uploaded October 26,
2026. CookieGuard's final-version release is **0.1.0**, uploaded November 4,
2026. It follows **0.1.0b1**, uploaded November 3. The adapter declares `browser-use>=0.13.14,<0.14`,
`cdp-use>=1.4.5,<2`, and Python 3.11+. The wheel bundles the CookieGuard core
and Playwright collector, both version 0.1.0; Node.js 24+ is a separate runtime
requirement. [Browser Use release](https://github.com/browser-use/browser-use/releases/tag/0.13.14),
[CookieGuard package](https://pypi.org/project/cookieguard-browser-use/0.1.0/).

The original validation installed the published **0.1.0b1** wheel into a fresh
environment. Its import locations, wheel URLs and SHA-256 digests are recorded in
[beta provenance](../validation/evidence/provenance.json). That wheel's Python
files match the inspected repository checkout byte for byte. All **89 existing adapter
tests passed in 184.92 seconds**, including the Chromium and scripted Agent
tests, failure paths, multi-tab isolation, collection gaps, and synthetic-secret
checks. Dependency consistency checking passed. These are fresh local results,
not a claim about a newly run hosted CI matrix.

The stable wheel was subsequently downloaded from the [PyPI install index](https://pypi.org/simple/cookieguard-browser-use/)
and its SHA-256 verified against the index. Both wheels contain 31 package files;
the only changed file is `__init__.py`, where the sole change is `__version__`
from `0.1.0b1` to `0.1.0`. All remaining runtime files, including the bundled
engines, are identical. Dependency requirements are unchanged. A second fresh
environment held every other dependency version fixed and passed **6/6 real-browser
example tests** and **71/71 adapter unit tests** with 0.1.0. The full 18-test
adapter browser suite and 100-trial benchmark were not repeated on 0.1.0.
[Stable verification and current patch hashes](../validation/evidence/stable-release.json)
are separate from the preserved beta measurements. The proposed example now
pins 0.1.0. The wheel still declares `Development Status :: 4 - Beta`; this is
a packaging metadata inconsistency despite the final version number.

PR review identified a URL-prefix allowlist in the example and POSIX-only setup
commands without an explicit platform requirement. The example now uses the
exact hostname `127.0.0.1`, and the README specifies a POSIX shell on macOS or
Linux (verified on macOS). A new regression checks the actual demo profile
against lookalike hosts without contacting them. It failed before the fix;
all seven example tests and upstream pre-commit passed afterward. The existing
six browser checks still pass with the stable wheel. [Review verification](../validation/evidence/review-fixes.json)
records the current source and patch hashes; the earlier measurements and
verification records are preserved.

Browser Use `main` was inspected at
[`b49a68e4060acb226da8f784194fef301c53a6d7`](https://github.com/browser-use/browser-use/commit/b49a68e4060acb226da8f784194fef301c53a6d7).
All **171 packaged Python files** matched the released wheel. The upstream
patches were prepared against that snapshot. This bounds compatibility to the
inspected release/source, not future releases.

## What the adapter actually does

The existing Python adapter starts a separate CDP observer on the agent's
browser. It correlates `Network.responseReceivedExtraInfo` with request and
redirect metadata, collects allowed-origin `Set-Cookie` declarations, and reads
the browser cookie store. A local Node subprocess evaluates that evidence with
the existing CookieGuard engine. An independently enforced final result is
`PASS`, `FAIL`, or `INCOMPLETE`.

The developer identifies authentication-cookie names or provides validated
scoped identity evidence. Classifier suggestions are triage; they cannot alone
justify a confirmed authentication-cookie failure. The demo measures cookie
configuration policy, not learned-model accuracy or exploit detection.

| Integration point | Use and boundary |
| --- | --- |
| `BrowserSession` / `BrowserProfile` | Use a fresh profile, `keep_alive=True`, and start the browser before attaching the audit. |
| `session.cdp_client` | Public property exposes the existing connection URL; the adapter opens a separate observer rather than replacing watchdog handlers. |
| `Tools` | `register_tools()` optionally exposes a provisional, sanitized check to the agent. |
| `Agent.run()` | Agent completes the workflow; developer code calls `finish()` before browser cleanup, then `assert_policy()`. |
| Actor `Page` API | Drives identical deterministic browser actions in the benchmark without model latency or cost. |
| `on_step_start` / `on_step_end` | Available lifecycle hooks, but unnecessary for the smallest integration and not a substitute for the final audit. |

The observer is passive. A failing final assertion does not undo a login,
prevent the browser receiving a cookie, or block earlier agent actions.
Source: [BrowserSession](https://github.com/browser-use/browser-use/blob/b49a68e4060acb226da8f784194fef301c53a6d7/browser_use/browser/session.py),
[Actor API](https://github.com/browser-use/browser-use/blob/b49a68e4060acb226da8f784194fef301c53a6d7/browser_use/actor/README.md),
[lifecycle hooks](https://docs.browser-use.com/open-source/customize/hooks).

## Measured comparison

The [validation README](../validation/README.md) specifies the fixtures, policy,
commands, scoring, timing boundaries, and exclusions. The recorded result is
[benchmark.json](../validation/evidence/benchmark.json). The runnable Agent
example and its baseline tests are in [example](example/README.md). The recorded
comparison and direct CLI outcomes below used **0.1.0b1**. Stable demo verification
is recorded separately above; these timing measurements have not been relabeled.

The final example commands were also run directly. Their
[recorded outcomes](../validation/evidence/example-cli.json) show successful
server and agent logins in all three runs: baseline exit 0 with `NOT_AUDITED`,
insecure exit 1 with CG001, and secure exit 0 with `PASS`.

<!-- measured-results-start -->
The final attempt contains **100 measured trials** (50 baseline, 50 guarded),
plus two excluded warmups. **The benchmark exited 1**, because one guarded
trial failed in `BrowserSession.start()` before CookieGuard attached. The root
cause of the Chrome exit remains unresolved. No failed trial was retried.

| Measure | Baseline | CookieGuard |
| --- | --- | --- |
| Cookie-security verdict | NOT_AUDITED | Independent final policy result |
| Insecure cases, 30 attempts | 30 successful logins; no audit | 29 FAIL; 1 browser-start ERROR |
| Expected confirmed rule detections | Not evaluated | 34/34 on executed cases; 34/35 across attempted cases |
| Controls, 15 attempts | Login succeeds; no audit | 15 PASS; 0 confirmed false positives |
| Missing-session cases, 5 attempts | Login fails; no audit | 5 INCOMPLETE; all blocked by final assertion |
| Execution errors | 0/50 | 1/50, before audit start |

All 49 completed audits matched fixture ground truth, including the required
rule IDs and header/browser evidence. No completed insecure audit returned
PASS. The missing-HttpOnly case had four observed FAIL results and one startup
error. The other cases each produced five expected results. Review-only CG009
appeared for the deliberately omitted SameSite declaration; the secure controls
had no review findings.

Timing below is in milliseconds. Baseline distributions contain 50 completed
trials, guarded distributions 49; paired differences use only the 49 complete
pairs. All per-trial measurements and the failed attempt remain in the JSON.

| Timing component | Baseline median / p95 | Guarded median / p95 |
| --- | --- | --- |
| Browser launch | 4852.5 / 9285.5 | 4450.8 / 9352.6 |
| Identical browser actions | 230.3 / 265.6 | 229.8 / 246.6 |
| Audit start | 0.0 / 0.0 | 157.1 / 184.3 |
| Audit finish | 0.0 / 0.0 | 7.9 / 16.7 |
| Workflow including audit | 230.3 / 265.6 | 401.2 / 427.9 |
| Whole session including cleanup | 5205.8 / 9671.0 | 4970.8 / 9881.0 |

The paired added time for the workflow including audit was **166.4 ms
median, 200.9 ms p95**. Median paired overhead was
**72.5%** of this very short synthetic flow; this is not a
percentage estimate for a model-driven agent task. Audit startup is the dominant
measured cost.

Whole-session paired deltas were noisy: median **-3477.8 ms**, p95
**8614.9 ms**, range **-8511.5 to 8842.0 ms**. Browser startup
varied by seconds. The negative median is not evidence that CookieGuard improves
performance; this run does not provide a reliable overall startup-inclusive
percentage. CPU, memory, throughput, Cloud and paid-model overhead were not measured.

Environment: macOS 26.6.2 arm64, Python 3.12.12, Node.js 26.10.0,
Chrome 156.0.8078.81, Browser Use 0.13.14, cdp-use 1.4.5, CookieGuard 0.1.0b1.
<!-- measured-results-end -->

This is a small synthetic test set: six distinct insecure cases, three
controls, and one evidence-gap case, each repeated five times. It does not
estimate deployment-wide precision or recall. `SameSite=None` is a violation of
the selected policy; it is not universally unsafe. The missing-session case is
excluded from the positive/negative detector denominators.

## Existing security examples and documentation placement

The code repository's contribution entry point is
[`.github/CONTRIBUTING.md`](https://github.com/browser-use/browser-use/blob/b49a68e4060acb226da8f784194fef301c53a6d7/.github/CONTRIBUTING.md).
It links the hosted contribution guide and the integration placement rules.
The hosted docs use an `open-source/` section with Customize → Agent, Browser,
Tools and Integrations, Examples → Templates, and Development. Their current
index is [llms.txt](https://docs.browser-use.com/llms.txt); this source snapshot
does not contain a conventional `docs/` tree or Mintlify navigation config.
The smallest contribution therefore has an unambiguous location in the code
repository and needs no new hosted-docs navigation category.

Existing related surfaces serve different purposes:

- [Sensitive data](https://docs.browser-use.com/open-source/examples/templates/sensitive-data)
  demonstrates credential placeholders and domain scope.
- [Secure setup](https://docs.browser-use.com/open-source/examples/templates/secure)
  combines model-provider configuration, restricted domains and sensitive data.
- [Blocked domains](https://github.com/browser-use/browser-use/blob/b49a68e4060acb226da8f784194fef301c53a6d7/examples/features/blocked_domains.py)
  demonstrates navigation restrictions.
- [Saving cookies](https://github.com/browser-use/browser-use/blob/b49a68e4060acb226da8f784194fef301c53a6d7/examples/browser/save_cookies.py)
  demonstrates authenticated-session persistence.
- [`tests/ci/security`](https://github.com/browser-use/browser-use/tree/b49a68e4060acb226da8f784194fef301c53a6d7/tests/ci/security)
  tests sensitive-data handling and browser security flags. No authentication-cookie
  attribute policy check was found in those examples/tests or the security watchdog.

The useful addition is explicit post-login cookie-policy enforcement with
evidence gaps distinguished from success. This complements those examples.
It is not evidence of a Browser Use vulnerability.

## Smallest contribution and acceptance evidence

The merged [integration placement policy](https://github.com/browser-use/browser-use/blob/b49a68e4060acb226da8f784194fef301c53a6d7/examples/integrations/README.md)
directs third-party projects to the community list. Small runnable examples
belong in `examples/integrations/<provider>/`; shipped integrations belong in
`browser_use/integrations/` only when part of the package and tested. Larger
workflows stay external. The example checklist calls for `uv`, explicit runtime
requirements, no secrets, and a repository-root run command.

The prepared patches implement two sizes of the same proposal:

| Candidate | Files | Maintainer burden | Recommendation |
| --- | --- | --- | --- |
| Community list | One entry in the existing integration README | Link review; adapter stays externally maintained | Smallest fallback if maintainers prefer a pointer |
| Runnable example | List entry plus a small script, README and opt-in tests | Review the lifecycle example and pinned optional dependency | Selected proposal: shows the existing insecure/secure login results |
| Built-in adapter or default dependency | Core package, dependency and support surface | Ongoing compatibility/Node ownership | No demonstrated need; do not propose |

The optional script imports the external package's disposable demo app and
scripted model; it does not vendor a scanner, fixture application or classifier.
It shows real `Agent.run()` usage, optional tool registration, final enforcement,
baseline behavior and cleanup. The scripted model is explicitly labelled and
costs nothing to run. A real model workflow would normally use
`ChatBrowserUse()`; no paid-model result is claimed here. The demo-helper imports
are why the example pins the tested release precisely.

Acceptance is a maintainer decision. The observed PR history supports the
placement choice but does not establish a willingness to merge every listing:

- [PR 4856](https://github.com/browser-use/browser-use/pull/4856) introduced the
  policy and was merged May 19, 2026.
- [PR 5221](https://github.com/browser-use/browser-use/pull/5221), a community
  proxy listing, closed unmerged after the stale workflow; no technical rejection
  should be inferred from that closure.
- [PR 6056](https://github.com/browser-use/browser-use/pull/6056), an example plus
  community listing, and [PR 6079](https://github.com/browser-use/browser-use/pull/6079),
  a listing, were still open at inspection.
- A repository issue/PR search for `CookieGuard` returned no matches at inspection.

The [contribution guide](https://docs.browser-use.com/open-source/development/setup/contribution-guide)
asks for a concrete reason, a demo, focused scope and passing CI. Upstream's
`AGENTS.md` requires pre-commit; its CI includes formatting and Pyright over
examples. Optional imports in the prepared example are explicitly marked so a
normal Browser Use install does not acquire CookieGuard as a type-checking
dependency. The tests live next to the optional example and run explicitly.
Existing integration PRs also show the CLA bot; signing is the contributor's
decision and has not been attempted here.

## Limitations and compatibility failures

The adapter's policy path worked with Browser Use 0.13.14 in the tested
macOS/Python 3.12/Node 26/Chrome combination. Two failures found during the work
are recorded explicitly:

- The initial long benchmark aborted after **75 completed trials** when Chrome
  exited before its CDP endpoint became available. This occurred inside
  `BrowserSession.start()`, before `audit.start()`. The original harness did not
  save detailed rows incrementally; that attempt is excluded from timing and
  pooled detection estimates. [Failure record](../validation/evidence/aborted-run.json).
  The revised harness journals every attempt, retains errors, never retries a
  failed trial silently, and returns nonzero for execution failures. No Browser
  Use internals, launch security settings, or CookieGuard runtime were changed.
- Upstream Pyright initially rejected the package's `ScriptedLoginModel` demo
  helper: it lacks the full `BaseChatModel` static/Pydantic protocol, although
  real Agent tests pass. The optional example uses an explicit, commented cast
  at that fixture boundary. This is a typing limitation of the demo helper;
  ordinary model-driven examples should use a typed provider such as
  `ChatBrowserUse`. Import sorting was also corrected to the upstream hook's
  first-party package rules.

The following limits remain material:

- Node is required alongside Python. This investigation does not revalidate
  every supported Python version or Node 24, nor Linux, Windows, Cloud browsers,
  remote CDP gateways, or future Browser Use releases.
- The benchmark uses loopback HTTP where Chromium accepts `Secure` cookies.
  It does not validate HTTPS transport, certificates or deployment settings.
- Header collection can miss activity before attachment, new-target races,
  service workers and other contexts. Missing required declarations prevent an
  otherwise unproven `PASS`; an observed violation can still fail policy.
  Browser-store observations do not reconstruct server declarations.
- Header filtering uses exact origins, but stored cookies are host-scoped, not
  port-scoped. Browser Use domain restrictions also do not distinguish ports.
  Fresh profiles avoid contamination between the local cases.
- Cookie values are transiently accessible in the observer and Node process.
  The tested audit outputs omit them. This is not a universal redaction layer
  for Browser Use, persistent profiles, HAR files, arbitrary page content or
  model-provider logging. Python memory is not securely erased. Node 24's
  permission model does not provide Node 25+'s network denial.
- `PASS` applies only to configured checks and observed identities. The audit
  does not establish XSS/CSRF resistance, session validity, fixation resistance,
  revocation, theft prevention or prompt-injection protection.
- The optional example's tests do not run in default upstream CI unless
  maintainers deliberately add that coverage. The 0.1.0 wheel's retained Beta
  classifier can be corrected in a future CookieGuard metadata release.

The original CookieGuard runtime, extension, models, CLI, MCP, package metadata,
and Browser Use internals were not edited for this proposal.

## Submission sequence

1. Review this evidence and the proposed scope. Make the new validation files
   accessible in CookieGuard before linking them in a public PR.
2. With explicit approval, refresh the target `main` and latest stable version,
   apply only the chosen patch, run pre-commit and required checks, and open a
   focused PR using the prepared description. Include the existing package demo
   and the fresh raw measurements, labelled by what they actually tested.
3. Address maintainer feedback; keep ownership and support with CookieGuard.
   If they prefer an external listing, do not expand the request into core
   hooks or a bundled runtime dependency.

At the time of the initial investigation, no upstream submission, maintainer
contact, CLA signing, or evidence publication had been performed. Local checks
do not constitute upstream CI approval.
