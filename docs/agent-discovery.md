# Agent discovery

How AI coding agents, MCP clients, and CI systems can find CookieGuard, decide whether it
fits a task, and invoke it. Items marked **main** are in this repository but not in a
published package yet.

## Machine-readable interfaces

| Interface | Where | Status |
| --- | --- | --- |
| Capability document | [`cookieguard.capabilities.json`](../cookieguard.capabilities.json); `cookieguard-ci capabilities --json` | file: main; CLI: main |
| Rule, issue, error, and status explanations | `cookieguard-ci explain ID [--json]`; MCP `cookieguard_explain` | main |
| JSON Schemas for every output | [`schemas/`](../schemas) (generated from the zod schemas the MCP server enforces) | main |
| JSON errors | `cookieguard-ci ... --json` prints `{status: "incomplete", exitCode: 2, error}` on stdout | main |
| MCP tools | `cookieguard_capabilities`, `cookieguard_audit` (`url` or `evidenceFile`), `cookieguard_explain`; 0.1.0 tools kept | main |
| Agent Skill | [`skills/cookieguard`](../skills/cookieguard) (Agent Skills `SKILL.md`) | main |
| Claude Code plugin marketplace | [`.claude-plugin/marketplace.json`](../.claude-plugin/marketplace.json) | main |
| `llms.txt` | [`llms.txt`](../llms.txt), served at `https://aiscihub.github.io/cookieguard-ai/llms.txt` after merge | main |

`npm run build:schemas` regenerates the schemas, the capability document, and the skill's
`rules.md` and `capabilities.json`; tests fail when any of them is stale.

## Does discovery work?

The [discovery benchmark](../benchmarks/discovery/README.md) ran 80 real Claude Code
sessions (`claude-sonnet-5-5`) on 24 tasks that never name the tool:

| Condition | Discovered | Correct integration chosen | CookieGuard audit ran | Session token reached the model |
| --- | --- | --- | --- | --- |
| A: ordinary tools | 0/24 | 0/24 | 0/24 | 4/24 runs |
| B: plus web search | 0/24 | 0/24 | 0/24 | 5/24 runs |
| C: Agent Skill installed | 23/24 | 22/24 | 5/24 | 0/24 |
| D: MCP server configured | 8/8 | 8/8 | 6/8 | 0/8 |

Being public on PyPI, npm, GitHub, and the MCP Registry did not make CookieGuard
discoverable: few agents searched, and their searches returned other tools. Installing the
skill or configuring the server did. Agents also guessed names that do not resolve:
PyPI `cookieguard` does not exist, and npm `cookieguard` is an unrelated package. In C,
install and audit rates were limited by the test machine's sandbox and Python version.

## End-to-end demonstrations

`npm run demo:mcp` connects the official MCP SDK client to the server: it reads the
capabilities, audits PASS, FAIL (CG001), and INCOMPLETE endpoints, explains CG001, and
audits a report written by a separate CLI run.

`integrations/browser-use/scripts/agent_discovery_e2e.py` (run from
`integrations/browser-use` with its virtualenv) adds a real Browser Use agent and
Chromium. It writes sanitized results for an insecure login, a secure login, and a run
that never signs in. It then uses the *Python* MCP SDK to start the Node server, read its
capabilities, select the browser-session integration, and audit each file. Output
observed on macOS arm64 with Python 3.12 and Node.js 26 (abridged). It also passes in
the Browser Use CI job on Linux with Python 3.11, 3.12, and 3.13:

```text
Browser Use insecure-login: login succeeded; local result FAIL; wrote insecure-login.json
Browser Use secure-login: login succeeded; local result PASS; wrote secure-login.json
Browser Use no-session: login not performed; local result INCOMPLETE; wrote no-session.json
ok   discovered tools: cookieguard_audit, cookieguard_capabilities, cookieguard_explain, cookieguard_policy, cookieguard_scan
Selected integration: cookieguard-browser-use 0.1.0 for an authenticated browser workflow
ok   insecure login: CG001 Missing HttpOnly is a confirmed finding on session_id
ok   secure login: PASS (exitCode 0) with no confirmed violations
ok   unavailable session: INCOMPLETE (expected-auth-cookie-not-observed), not a pass
ok   missing evidence file: INCOMPLETE with error EVIDENCE
ok   malformed evidence file: INCOMPLETE with error INPUT
ok   path outside the evidence directory: INCOMPLETE with error EVIDENCE
ok   URL on an unconfigured origin: INCOMPLETE with error TARGET
ok   ambiguous arguments: INCOMPLETE with error CONFIG
Agent discovery end-to-end passed; the session-token canary never appeared in evidence or MCP output.
```

## Installing the skill

- **Claude Code:** `/plugin install cookieguard --marketplace aiscihub/cookieguard-ai`, or
  `claude plugin marketplace add aiscihub/cookieguard-ai` then
  `claude plugin install cookieguard@aiscihub`. Validated with `claude plugin validate .`
  (Claude Code 2.1.318). A copy in a project's `.claude/skills/cookieguard` also works and
  is what the [discovery benchmark](../benchmarks/discovery/README.md) uses.
- **Codex:** copy `skills/cookieguard` to `.agents/skills/` in a repository or to
  `~/.agents/skills/`, or ask `$skill-installer` to install it from
  `https://github.com/aiscihub/cookieguard-ai/tree/main/skills/cookieguard`. Not tested here:
  Codex is not installed on the validation machine.
- **Other agents** that read Agent Skills can use the same folder.
  `node scripts/check-skill.js` checks it against the
  [specification](https://agentskills.io/specification).

Installing a skill does not make it globally discoverable. An agent sees it only where it
is installed, or through a directory that the agent searches.

## Registries and directories

| Channel | State | Needs approval to change |
| --- | --- | --- |
| Official MCP Registry | `io.github.aiscihub/cookieguard` 0.1.0 is active | Publishing a new version |
| npm (`cookieguard-ci`, `@aiscihub/cookieguard-core`, `-playwright`, `-mcp`) | 0.1.0 published; keywords, homepage, and issue links added on main | Next publish |
| PyPI (`cookieguard-browser-use`) | 0.1.0 published; keywords, classifiers, and Documentation/Changelog URLs added on main | Next release |
| Anthropic's Claude Code plugin directory | Not submitted; the marketplace file validates | Submission |
| OpenAI curated skills (`openai/skills`) | Not submitted | External pull request |
| skills.sh / `npx skills` and other skill indexes | Not submitted or tested | Submission |
| GitHub topics such as `agent-skills`, `mcp-server`, `claude-code-plugin` | Not changed | Repository settings |

## Recommended next steps (each needs approval)

1. Release core, CLI, and MCP together so the tools on main are installable, then
   republish the MCP Registry entry.
2. Submit the plugin to Anthropic's directory, the skill to `openai/skills`, and the
   server to MCP directories that agents' searches surfaced, such as Glama.
3. Consider a PyPI `cookieguard` package that installs `cookieguard-browser-use`, since
   agents probe that name. npm `cookieguard` is taken by an unrelated project.
4. Add GitHub topics for Agent Skills, MCP, and Claude Code plugins.
5. Re-run BU1-BU4 and AG1-AG4 in condition C with the fixed harness. The skill now tells
   agents to use Python 3.11+; in the partial re-run all 4 agents did, but pip could not
   reach PyPI from the sandbox.

## Next release

The MCP server on main uses new exports from `@aiscihub/cookieguard-core` and
`cookieguard-ci`, and depends on exact versions. Release them together (core, then CLI,
then MCP), update `packages/mcp/server.json`, set each operation's `availability` to
`released` in `packages/cli/src/capabilities.js`, run `npm run build:schemas`, and
republish the MCP Registry entry. Every step requires maintainer approval.
