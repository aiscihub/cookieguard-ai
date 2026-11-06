# MCP server

`@aiscihub/cookieguard-mcp` 0.1.0 is a local stdio server (registry name
`io.github.aiscihub/cookieguard`). It needs Node.js 24+ and a startup JSON file
that fixes the allowed origins and policy; tool calls cannot change them.

Save the configuration outside directories the agent can edit, for example
`/absolute/path/cookieguard.json`:

```json
{
  "allowedOrigins": ["http://127.0.0.1:3000"],
  "policy": { "authCookies": ["session_id"], "failOn": "high" },
  "timeoutMs": 10000
}
```

Claude Code: `claude mcp add cookieguard -- npx --yes @aiscihub/cookieguard-mcp@0.1.0 --config /absolute/path/cookieguard.json`

Clients using an `mcpServers` object:

```json
{ "mcpServers": { "cookieguard": { "command": "npx",
  "args": ["--yes", "@aiscihub/cookieguard-mcp@0.1.0", "--config", "/absolute/path/cookieguard.json"] } } }
```

Codex (`~/.codex/config.toml`):

```toml
[mcp_servers.cookieguard]
command = "npx"
args = ["--yes", "@aiscihub/cookieguard-mcp@0.1.0", "--config", "/absolute/path/cookieguard.json"]
```

Tools in 0.1.0: `cookieguard_policy` (read the fixed configuration) and
`cookieguard_scan` (`{"url": ...}` on a configured origin). Results contain
`status`, `exitCode`, `findings` (rule ID, severity, `confirmed`/`review`, fix),
`issues`, and `error`. Check both `isError` and `status`. Cookie values and
unconfigured cookie names are never returned.

The scan is an HTTP header audit; it cannot log in. For sign-in flows, run the
Browser Use or Playwright integration in your test code.

## Main branch only (not in 0.1.0 yet)

`cookieguard_capabilities`, `cookieguard_explain`, and `cookieguard_audit`
(`{"url"}` or `{"evidenceFile"}`). With `"evidenceDir": "/absolute/dir"` in the
configuration, `cookieguard_audit {"evidenceFile": "login.json"}` re-evaluates a
sanitized report that your own Browser Use (`result.write_json`), Playwright, or
CLI (`--output`) run wrote there.
