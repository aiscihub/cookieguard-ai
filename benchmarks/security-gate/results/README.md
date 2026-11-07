# Security-gate study: results

The protocol is [`../PROTOCOL.md`](../PROTOCOL.md), registered before any measured run. All
credential values in these files are synthetic, and are replaced with `sess_<redacted>` /
`tok_<redacted>`.

| Part | Where | Provenance |
| --- | --- | --- |
| 1. Comparison | [`comparison-ci/`](comparison-ci) | GitHub Actions run 42420263420, ubuntu-24.04, commit `600b69a` |
| 1. Replication | [`comparison-macos/`](comparison-macos) | macOS arm64, same code; identical decision and idiom tables. `recheck-after-dedupe.jsonl`: C and C0 after the post-registration change |
| 2. Fix and retest | [`fix-retest/`](fix-retest) | Smoke: run 42420306123 (`600b69a`). Study: run 42421329635 (`01894b6`). Claude Code 2.1.319, `claude-sonnet-5-5` |

## Part 1: the same requirements, three ways (33 runs per approach)

| | A. Native Playwright | B. Minimal fixture + gate script | C. CookieGuard fixture + gate | C0. CookieGuard defaults |
| --- | --- | --- | --- | --- |
| Flawed versions blocked | 15/15 | 15/15 | 15/15 | **12/15**: accepts SameSite=None |
| Secure versions accepted | 9/9 | 9/9 | 9/9 | 9/9 |
| Missing evidence blocked, and labeled INCOMPLETE | 9/9, labeled as plain failures | 9/9, 9/9 | 9/9, 9/9 | 9/9, 9/9 |
| Runs exposing a credential | **3/33** | 0/33 | 0/33 | 0/33 |
| Lazy neutralizations that pass CI (of 6) | **5** | **1** (weakened check) | 0 | — |
| Deliberate forgery passes CI | n/a | yes | yes | — |
| Security-specific lines | 22 | 55 | 12 + 1 CI command | 12 + 1 |
| Flaky cells | 0/11 | 0/11 | 0/11 | 0/11 |

- **A's exposures:** all 3 were the `replay-error` version. A deliberately value-safe spec
  still printed both credentials, because Playwright's call log for a failed API request lists
  the `Cookie` header.
- **The six lazy neutralizations:** `skip`, `known-failure` (`test.fail()`), `swallow`,
  `filter`, `delete`, and `weaken`.
  - A blocked only `swallow`, because its assertions are `expect.soft`.
  - B failed only `weaken`: its gate trusts the workspace's verdict.
  - C's gate re-evaluates the evidence under its own policy.
- **Native idioms:** 9 of the 14 common cookie assertions print the credential when they
  fail. Examples are `toContainEqual` on `context.cookies()`, `toContain` on the `Set-Cookie`
  header, `not.toContain` on `document.cookie`, and `not.toBeOK()` on a replay. The safe ones
  assert on single flags, status codes, or cookie names.

## Part 2: an agent fixes a flawed app that has a security test (6 runs per condition)

| | N. Native test | C. CookieGuard fixture + gate |
| --- | --- | --- |
| Final app fixed, per the protected runner (both pristine suites) | 6/6 | 6/6 |
| Agent's CI still blocks the original flaw | 6/6 | 6/6 |
| Agent edited a test, config, or script file | 0/6 | 0/6 |
| Credential value reached the model | 0/6 | 0/6 |
| Cost / median time | $0.16 / 0.3 min | $0.17 / 0.3 min |

Every run made the minimal, correct fix: HttpOnly on `sid`, server-side session deletion at
logout, or a server-set HttpOnly `api_token` with the page script no longer handling the
token. Total paid spend this cycle, including the smoke run: **$0.35**.

## Answers

1. **Does CookieGuard catch problems the reference setup misses?** No. A, B, and C detected
   the same 15/15 flaws. With its default policy, CookieGuard caught fewer (12/15).
2. **Safer diagnostics?** Somewhat. CookieGuard exposed nothing in 66 runs, including
   malformed headers, exceptions, and failed replays. A careful native spec leaked on one
   exception path, and most common idioms leak. A careful hand-written fixture (B) also
   leaked nothing.
3. **Less setup and maintenance?** Less code: 12 lines against 22 (native, not fail-closed)
   and 55 (fail-closed fixture). No human was timed, and the checks CookieGuard has but this
   app did not exercise (Domain, lifetime, prefixes, rotation, Web Storage) were not measured.
4. **Enforcement without the agent choosing the tool?** Yes, as a developer-installed fixture
   and gate, and only against lazy neutralization; a forged evidence file still passes. The
   agents in Part 2 never tried to neutralize a test, so this protection went unexercised.
   In the pilot, agents writing their own tests did record flaws as `todo` tests.
5. **Worth a dependency?** Only as a small Playwright fixture plus a CI gate. The MCP server
   and Agent Skill were unused in the pilot, and nothing here depends on them.
6. **Would a small native fixture do the same?** Essentially yes. B matched every outcome
   except the weakened-policy case, with about 40 more lines. Its author also needed to know
   the pitfalls that CookieGuard encodes: a fail-closed design, the call-log leak, store
   timing for script-set cookies, and nameless `Set-Cookie` lines.

## Decision: PIVOT

The checks are correct and the fail-closed gate is useful, but the measured advantage over a
50-line fixture is convenience and pitfall avoidance, not capability. Keep the policy engine,
the Playwright fixture, and the CLI gate. Stop developing the MCP server, the Agent Skill, the
classifier, and agent-discovery work. Keep the Browser Use integration in maintenance only:
this study has no evidence for or against it.

Defects found in CookieGuard during this work, all fixed on this branch:
- a script-set credential deleted at logout was missed;
- nameless `Set-Cookie` lines aborted collection;
- INCOMPLETE masked a confirmed violation;
- review items misled agents;
- duplicate findings;
- a Browser Use bridge regression from the first fix.
