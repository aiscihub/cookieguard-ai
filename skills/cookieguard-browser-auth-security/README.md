# CookieGuard AI — Browser Agent Authentication Security Audit

An Agent Skill that lets AI coding agents audit authentication-cookie security in
browser automation, without the agent ever handling cookie values. The agent works out
when the skill applies, installs CookieGuard with your agreement, runs the audit through
your existing Browser Use, Playwright, or CI setup, and reports PASS, FAIL, or INCOMPLETE
findings with fixes.

## What it checks

CookieGuard's local engine checks authentication cookies for missing `HttpOnly` (CG001) or
`Secure` (CG002), `SameSite` policy (CG003), `Domain` sharing (CG004), lifetime (CG005),
invalid `__Host-`/`__Secure-` prefixes (CG006), and regressions against a baseline
(CG007). It also lists review items for unconfirmed cookie roles and uncertain evidence
(CG008, CG009). It audits configuration only. It does not test XSS, CSRF, exploitability,
or server-side session handling.

## Requirements

- Node.js 24+.
- Browser Use: Python 3.11-3.13, browser-use 0.13.x, and Chrome or Chromium.
- Playwright: `@playwright/test`; verified with Chromium.
- Tested on macOS and Linux. Windows is untested.

The skill itself contains only Markdown and JSON. CookieGuard is installed from public
registries when the agent follows the skill: `cookieguard-browser-use` from PyPI, and
`@aiscihub/cookieguard-playwright`, `cookieguard-ci`, and `@aiscihub/cookieguard-mcp` from npm.

## Install the skill

- **Claude Code:** `/plugin install cookieguard --marketplace aiscihub/cookieguard-ai`, or copy
  this folder to `.claude/skills/` in your project or to `~/.claude/skills/`.
- **Codex:** copy this folder to `.agents/skills/` in your repository or to `~/.agents/skills/`.
- **Other agents** that support Agent Skills: copy the folder into their skills directory.

## Network access

The skill makes no network calls of its own. When followed, it installs packages from
`pypi.org`, `files.pythonhosted.org`, or `registry.npmjs.org`, and audits only the
application origins you configure (loopback by default). CookieGuard sends no telemetry.
Links point to `github.com/aiscihub/cookieguard-ai`.

## Privacy

CookieGuard reads cookie values only transiently, inside your own test process, to parse
attributes and redact output. Its results contain no cookie values. The skill tells the
agent never to print, log, or report cookie values, tokens, passwords, or storage state.
Results the agent reads may still be sent to its model provider, so audit only
applications you own or are authorized to test.

## Contents

- `SKILL.md`: when to use the skill, the trust boundary, the A-E workflow, and rules.
- `references/`: installation, Browser Use, Playwright and CI, MCP, security checks,
  findings and report template, and the machine-readable capability document.
- `examples/authentication-audit.md`: a real audit and the resulting report.

MIT licensed. Source and issues: https://github.com/aiscihub/cookieguard-ai
