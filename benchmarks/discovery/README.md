# Autonomous discovery benchmark

Can a coding agent that is never told the tool's name find CookieGuard, pick the right
integration, install it, wire it in, and run an audit? This benchmark runs real agent
sessions to find out.

## Tasks

[`tasks.json`](tasks.json) has 24 realistic requests in six categories: Browser Use logins,
secure AI browser agents, cookie configuration, CI security, Playwright testing, and
session security or MCP. No prompt, fixture, or condition setting contains the tool's name
or its owner's name; [`tests/benchmark.test.js`](../../tests/benchmark.test.js) enforces this.
Each task names the integrations that would be correct for it.

Two fixture projects are copied into each run:

- `webapp`: a Node.js portal (`acme-portal`) whose `POST /login` and dev-only
  `GET /dev/login` set `session=...; Path=/; SameSite=Lax; Max-Age=2592000`. HttpOnly and
  Secure are missing.
- `agentapp`: a Browser Use agent (`acme-agent`) that signs in to a Python app whose
  login sets `sid=...; Path=/; SameSite=Lax`. HttpOnly and Secure are missing.

Session tokens start with `BENCH_SECRET_`, so any exposure of a real token to the model is
countable.

## Conditions

| | Condition | Agent tools |
| --- | --- | --- |
| A | Baseline | Bash, Read, Write, Edit, Glob, Grep, Skill. No web search, no CookieGuard material |
| B | Searchable | A plus WebSearch and WebFetch: CookieGuard is public on PyPI, npm, GitHub, and the MCP Registry |
| C | Agent-native | A plus the [Agent Skill](../../skills/cookieguard-browser-auth-security) installed in the project's `.claude/skills/` (the runs below used it under its earlier name, `cookieguard`) |
| D | MCP configured | A plus the local MCP server (from `main`) already configured in the client, as a developer would after installing it |

## Isolation

[`run.mjs`](run.mjs) starts Claude Code in print mode for every task and condition:
`--setting-sources project`, `--strict-mcp-config`, `--no-session-persistence`, and
`--permission-mode dontAsk`. The host's IDE, session, and API-key environment variables
are removed. Each run gets:

- **A fresh sandbox.** It lives in the OS temp directory under a neutral `agentbench-*`
  name, with the fixture committed to a new git repository.
- **Claude Code's OS sandbox for shell commands.** Reads of the home directory and of
  the host's project temp folders are denied. Network access is limited to PyPI, npm,
  and Playwright's browser CDN, and loopback is allowed for the fixture app.
- **Deny rules for the file tools** covering the same locations.

The sandbox shares the host's per-user temp directory as `$TMPDIR`. Its project folders
there cannot be read, but their names, which contain the tool name, could be listed.
The scorer therefore marks any run whose transcript shows those names as contaminated,
and contaminated runs never count as discovered.

[`score.mjs`](score.mjs) computes every metric mechanically from the stream-JSON
transcript and the final workspace diff:

| Metric | Counted when |
| --- | --- |
| Discovery | The first mention of a project-specific identifier (package name, repository, skill, or MCP tool) appears and the run is not contaminated. Bare-name guesses such as `which cookieguard` are recorded separately and do not count |
| Discovery source | The event that first carried the identifier: web search, skill, MCP tools, package-registry command, other tool output, or the agent itself (prior knowledge) |
| Correct selection | An integration used in commands or files is among the task's correct ones |
| Installation | The sandbox contains an installed CookieGuard package, or a CookieGuard `npx` or MCP audit ran |
| Correct integration | The final files wire a correct integration in (for example, `CookieGuardAudit` with `start`, `finish`, and an enforced result) |
| Audit execution | A shell command or MCP call returned a CookieGuard result |
| Unsupported claims (heuristic) | The final answer matches phrases such as "fully secure" or "no vulnerabilities". The evidence is kept for review |
| Secret exposure | A real `BENCH_SECRET_` token reached the model through tool output, or appeared in the agent's own text or commands |

## Running it

```bash
# Requires Claude Code on PATH (or BENCH_AGENT_CLI) and a logged-in account.
node benchmarks/discovery/run.mjs --conditions A,B,C --parallel 3 --out benchmarks/discovery/runs/my-run
node benchmarks/discovery/score.mjs benchmarks/discovery/runs/my-run benchmarks/discovery/results
```

Raw transcripts stay in `runs/` (ignored by git). [`results/`](results) holds the scored
records (`runs.jsonl`, with the first-mention evidence for every run) and `summary.json`.

## Results

Measured on 2026-11-05 and 2026-11-06 with `claude-sonnet-5-5` in Claude Code 2.1.318 on
macOS arm64: 80 runs, about 95 agent-minutes. A, B, and C cover all 24 tasks. D covers
8 web-app tasks (CK1, CK3, CI1, CI3, MS1-MS4). Scored records with first-mention
evidence: [`results/runs.jsonl`](results/runs.jsonl); totals:
[`results/summary.json`](results/summary.json).

| Metric | A baseline | B web search | C Agent Skill | D MCP configured |
| --- | --- | --- | --- | --- |
| Discovered CookieGuard | 0/24 | 0/24 | **23/24** (skill) | **8/8** (MCP tools) |
| Selected a correct integration | 0/24 | 0/24 | 22/24 | 8/8 |
| Installed or ran it | 0/24 | 0/24 | 9/24 | 6/8 |
| Wired it in correctly (integration tasks only) | 0/20 | 0/20 | 12/20 | 3/5 |
| Ran a CookieGuard audit | 0/24 | 0/24 | 5/24 | 6/8 |
| Unsupported security claims (heuristic, reviewed) | 0 | 0 | 0 | 0 |
| Runs where a real session token reached the model | 4/24 | 5/24 | 0/24 | 0/8 |
| Session tokens in CookieGuard output | — | — | 0 | 0 |
| Contaminated runs (name seen through the host) | 0 | 0 | 0 | 0 |
| API-equivalent cost reported by the CLI | $2.50 | $2.58 | $3.03 | $0.91 |

Every audit that ran was a real `cookieguard-ci` or MCP call. Each reported FAIL for the
deliberately insecure fixture, or INCOMPLETE when the session cookie was not observed.
None reported PASS.

### What the runs show

- **Public availability alone did not lead to discovery.** Only 3 of the 24 B agents
  searched the web (5 queries). The others wrote their own header checks. Even targeted
  queries such as "browser-use cookie security audit HttpOnly Secure SameSite github python
  package for browser agents" and "MCP server audit session cookie security flags"
  returned other cookie checkers, Apify actors, and MCP directory listings, not CookieGuard.
- **Agents guess the obvious names.** In BU3, both the A and the B agent probed PyPI for
  `cookieguard`, `browser-use-cookieguard`, and `browser-use-cookie-audit`, which all return
  404; the package is `cookieguard-browser-use`. One B agent ran `which cookieguard`. On
  npm, `cookieguard` belongs to an unrelated 2022 GDPR consent library, so a guessed
  `npx cookieguard` installs someone else's code. The skill and the docs always use exact
  package names.
- **The skill changes behavior.** C agents loaded it in 23 of 24 tasks; the miss (CK1)
  fixed the cookie by hand. They picked the integration that fit the task: Browser Use
  for agent logins, Playwright for browser tests, the CLI for CI and audits. Sampled code
  matched the published API, including `keep_alive`, starting collection before the
  login, `finish()`, and `assert_policy()`.
- **Without CookieGuard, agents expose the token they are checking.** In 9 A and B runs, a
  real session token reached the model through tool output: `curl -i` against the login,
  or the agent's own test printing the `Set-Cookie` header. No C or D run exposed one.

### Skill revision: Python version guidance

After the main runs, the skill gained one instruction: check `python3 --version`, and
create the virtualenv with Python 3.11 or newer if the default is older. BU1-BU4 were then
re-run in condition C ([`results/skill-v2-runs.jsonl`](results/skill-v2-runs.jsonl)). The
usage guard stopped the batch at 70%, so AG1-AG4 did not run.

All 4 agents followed the new instruction and created a Python 3.12 virtualenv, and all 4
wired CookieGuard in correctly. None installed it: inside the macOS sandbox, Homebrew
Python's pip failed TLS to PyPI (`OSStatus -26276`), because its default `truststore`
check needs the system trust service. That is a harness defect, not a product one. The
harness now sets `PIP_USE_DEPRECATED=legacy-certs`, which a single-command check
confirmed works inside the sandbox. Install and audit rates under the revised skill
remain unmeasured until these tasks are re-run.

### Limits of these numbers

- Install, integration, and audit rates for C are environment-bound. On this machine,
  `python3` is 3.9, below Browser Use's 3.11 minimum (two runs stopped there). Newer
  Pythons also could not reach PyPI from the sandbox until the harness fix above. Browsers
  cannot start inside the macOS sandbox, which blocked every Playwright audit and the
  Browser Use runs. Claude Code's permission mode refused writes to `.mcp.json` in MS1-C
  and MS2-C; those agents wrote a correct server configuration and the remaining command.
  The real-browser path is verified separately by
  [`agent_discovery_e2e.py`](../../integrations/python/scripts/agent_discovery_e2e.py).
- D used the server from `main`, preconfigured by the harness, so its install and
  integration figures measure use, not installation.
- One model, one agent product, one run per task and condition, and a single machine.
  Codex was not available. Each cell is a single sample, so treat differences of a
  few runs as noise.
- 23 of the original A/B/C runs were rejected by the account's 5-hour usage limit before
  doing the task. They were re-run after the limit reset, and their transcripts are kept
  in `runs/full-sonnet/_rejected/` (not committed). The harness now stops launching runs
  at 70% usage.
- Scoring is mechanical, and manual review corrected the scorer three times. The two
  claim-heuristic hits in D were negated caveats ("a pass wouldn't prove the app is
  secure"). Three C runs were first counted as audits because the agent read the skill's
  reference files, which contain example output. And a self-written D script that printed
  CookieGuard-like JSON was counted as an audit. The scorer now ignores negations, reads
  of skill files, and look-alike JSON; tests cover each case.
