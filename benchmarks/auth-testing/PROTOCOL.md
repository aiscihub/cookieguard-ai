# Auth-testing benchmark: protocol

Status: **pre-registered** for the pilot. This file is committed before the first paid run,
and any later change is listed under [Changes after registration](#changes-after-registration)
with its date and reason.

## Question

When Claude Code is asked to write tests for an app's login and session handling, does
adding CookieGuard (its Agent Skill and MCP server) make the tests catch more real
authentication-cookie flaws, without making them worse at anything else?

The outcome is measured by **running the tests the agent wrote**, not by grading what the
agent says.

## Task

Every run gets the same prompt, which asks for tests rather than a security review:

> Add automated tests for the login and session handling in this app. They should run as
> part of `npm test`. When you are done, summarize what the tests cover and anything they
> found.

## App

[`fixture/`](fixture) is Acme Notes, a small Express 5 app: form sign-in with a
double-submit CSRF token, notes pages, a JSON API, and sign-out. Its dependencies are
installed, and it already has one `node:test` test and one Playwright test, both run by
`npm test`. Its credentials are the `sid` session cookie and an `api_token` cookie for the
API, which every version issues after sign-in.

| Version | Difference from `fixed` | Checked by CookieGuard 0.2.0 |
| --- | --- | --- |
| `fixed` | none; both credentials are HttpOnly, Secure, SameSite cookies set by the server | n/a |
| `no-httponly` | `sid` is set without HttpOnly (one line, visible in the source) | yes (CG001) |
| `js-token` | the server returns the API token in JSON, and page script stores it with `document.cookie` | yes (CG001, browser store) |
| `open-redirect` | sign-in follows any `next` URL, including other origins (one line) | no |

[`variants.mjs`](variants.mjs) applies each version as exact edits to the fixed app.
Two decoys are present in every version and are correct by design: a readable `theme`
preference cookie, and a readable `csrf_token` cookie that page script sends back in a
header. Credential values have recognizable formats (`sess_` and `tok_` followed by 32 hex
digits), so their exposure is countable.

## Conditions

| | Condition | What the agent has |
| --- | --- | --- |
| A | Default workflow | Bash, Read, Write, Edit, Glob, Grep, Skill. Node 24, the project's Playwright with Chromium installed, and open network access |
| B | A plus CookieGuard | A, plus the Agent Skill in the project's `.claude/skills/` and the published MCP server (`@aiscihub/cookieguard-mcp@0.2.0`) configured in the client by the developer, with `allowedOrigins` for the app and `authCookies: ["sid", "api_token"]` |

The prompt never mentions CookieGuard, the skill, or the MCP server. B agents may install
`@aiscihub/cookieguard-playwright` themselves; it is not preinstalled.

## Environment

[`.github/workflows/auth-testing-benchmark.yml`](../../.github/workflows/auth-testing-benchmark.yml):

- Each run is one GitHub Actions job on a fresh `ubuntu-24.04` VM.
- Claude Code 2.1.319 in print mode, with `--setting-sources project`, `--strict-mcp-config`,
  `--no-session-persistence` and `--permission-mode dontAsk`, plus a spend cap per run.
- The model is `claude-sonnet-5-5`.
- The agent and every test it runs execute as an unprivileged user, who cannot read the
  repository checkout, the runner's home directory, or the run record.
- The agent's environment contains only an allow-listed set of variables plus the agent
  credential.
- Agent sessions are limited to 25 minutes; each replay of `npm test` is limited to 5 minutes.

## Primary outcome

**Caught by an enforceable test.** After the agent finishes, the harness restores the
pristine app files, keeping every test, configuration, and dependency change the agent
made. It then runs the workspace's `npm test` against `fixed`, `no-httponly`, `js-token`,
`open-redirect`, and `fixed` again.

A flaw counts as **caught** when the suite exits non-zero on that version and zero on both
runs of `fixed`. A suite that fails on `fixed` catches nothing. A timeout is not a catch.

The primary outcome for a run shown a flawed version is whether it caught *that* flaw.

## Secondary outcomes

- The suite passes on `fixed`. A failure there means a false alarm or a broken suite.
- Flaws caught on versions the agent was not shown, which measures whether the tests generalize.
- **Credential exposure:** a real `sess_` or `tok_` value appears in tool output the model
  read. Values the agent wrote itself before seeing them do not count.
- Tool use (B): the skill loaded, MCP calls, and a CookieGuard check enforced in the final
  tests or scripts.
- Cost, tokens, turns, and agent time, as reported by the CLI.
- **Heuristic, reviewed by hand:**
  - the final answer names a seeded flaw;
  - the final answer makes an unsupported assurance ("login handling is secure");
  - the agent edited the app source.
- Contamination (A): the transcript shows the tool's name.

## Hypotheses

These are for the full study. The pilot is descriptive.

1. On the cookie flaws (`no-httponly`, `js-token`), B catches the flaw it was shown more
   often than A.
2. On `open-redirect`, which CookieGuard does not check, B does not do worse than A.
3. Fewer B runs than A runs expose a real credential to the model.
4. B suites pass on `fixed` at least as often as A suites.

## Pilot

The pilot is 4 versions × 2 conditions × 2 repeats, which is 16 runs. Its purpose is to check that the
harness and scoring work on real agent output, not to test the hypotheses: two runs per cell
cannot support a claim.

Go/no-go for the full study:

- validation passes;
- at least 14 of 16 runs finish and are scored;
- no harness credential appears in any uploaded run record;
- a manual review of every run finds no scoring error.

If the pilot leads to changes to the prompt, app, or scorer, they are recorded below, and
pilot data is not pooled with the full study.

## Full study (planned, not yet registered)

More frameworks (Flask, FastAPI) and more runtime-only flaws, both prompts (this one and a
security-focused one), and enough repeats per cell for 95% confidence intervals. The design
will be registered here before it runs.

## Analysis

- **Every cell:** report counts with Wilson 95% intervals.
- **Full study:**
  - compare A and B on each flaw with Fisher's exact test, two-sided, with a Holm
    correction across hypotheses 1–4;
  - report effect sizes as differences in proportions;
  - report every run, including null and negative results.

Exclusions:

- **Rerun:** runs that never reached the model because of infrastructure, such as a runner
  failure or rejected authentication. These failures are listed.
- **Kept and scored as they are:** runs that timed out, hit the spend cap, or ended with an
  error.

## Validation before every dispatch

[`validate.mjs`](validate.mjs) replays reference suites through the scoring code, and the
workflow stops if any differs from its design:

| Suite | Built to | Required result |
| --- | --- | --- |
| `strong` | test redirects, HttpOnly on `sid`, and that no script-readable cookie grants API access | passes `fixed`, catches all three |
| `naive` | test sign-in, a wrong password, and that a session is required | passes `fixed`, catches nothing |
| `overstrict` | require every cookie to be HttpOnly, including the decoys | fails `fixed`, credited with nothing |
| `tool` | use `@aiscihub/cookieguard-playwright@0.2.0` with the developer's configuration | informational; measured locally: passes `fixed`, catches `no-httponly` and `js-token`, misses `open-redirect` |

## Known limitations

- **Narrow scope:** one app, one framework, one prompt and one model, and the flaws are
  seeded.
- **The developer's configuration helps B:** the MCP server is configured with the app's
  credential cookie names, which a developer who installed it would do.
- **Agents can read the source:** in both conditions they can see the seeded flaw in the
  code. `no-httponly` and `open-redirect` are one-line differences.
- **Older tool version:** B uses the published CookieGuard 0.2.0. The session rotation,
  logout, and Web Storage checks on `main` are not part of this pilot.

## Changes after registration

- **2026-11-07, before any agent run:** the fixture's `npm test` script changed from
  `node --test test/` to `node --test "test/**/*.test.js"`. On Node 24, the version CI
  uses, a directory argument is treated as a file, so the original script failed before
  running any test. The protocol was validated on Node 26, where it works. Validation
  caught the problem in CI and passes on Node 24 after the change. Metrics, versions and
  conditions are unchanged.
