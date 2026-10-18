# CookieGuard composite Action

Unpublished source action for a developer-controlled app. No GitHub token is used
by CookieGuard. Checkout needs only `permissions: { contents: read }`. Intended
for GitHub-hosted Linux; Enterprise artifact compatibility is unverified.

After checkout and application startup:

```yaml
- uses: ./action
  with:
    target: http://127.0.0.1:3000/secure
    auth-cookies: session_id
    fail-on: high
    upload-report: 'true'
    artifact-name: cookieguard-report
```

`auth-cookies` and `allow-origins` are comma-separated lists. `allow-origins`
defaults to empty (loopback only). Never pass tokens/passwords in URLs or inputs.
`upload-report: 'false'` retains the summary without artifact upload. Use distinct
artifact names for multiple invocations.

The action sets up Node 24, installs production-only dependencies with scripts
disabled, and builds the engine adapter. It scans headers, writes owner-readable
JSON in a fresh runner-temp directory, appends an escaped summary, uploads only
that generated file with seven-day retention, then enforces the status. No
user-supplied artifact path is accepted. Outputs: `exit-code` (0/1/2), `report-path`.
Inputs enter via environment variables, never shell interpolation.

Run contributor tests before invoking `./action`: its production install removes
dev dependencies from its own checkout. Before release, another application can
check this source out into a subdirectory and use `./that-directory/action`.
The complete source tree is required.

After maintainers create a reviewed release tag, use
`aiscihub/cookieguard-ai/action@ci-v0.1.0`, preferably pinned to its commit SHA.
No tag is created here. See `../.github/workflows/cookieguard-ci.yml` for a complete
example including an expected failure. Local tests execute `run.js` and verify
reports, summaries, outputs, and sentinel non-disclosure. Hosted setup/upload/
enforcement still require an authorized GitHub run before release.
