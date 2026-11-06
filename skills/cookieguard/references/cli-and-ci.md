# CLI and CI

`cookieguard-ci` 0.1.0 needs only Node.js 24+. It sends one GET (plus same-origin
redirects), with no cookies or authorization headers, and audits `Set-Cookie`.
It cannot log in or run JavaScript.

```bash
npx --yes cookieguard-ci@0.1.0 scan http://127.0.0.1:3000/ --auth-cookie session_id
npx --yes cookieguard-ci@0.1.0 scan http://127.0.0.1:3000/ --auth-cookie session_id --format json --output cookieguard.json
```

| Option | Effect |
| --- | --- |
| `--auth-cookie NAME` | Exact session-cookie name; repeatable. Needed to confirm failures. |
| `--fail-on LEVEL` | `info`, `low`, `medium`, `high` (default), `critical`. |
| `--format json` | Sanitized JSON report on stdout (schema: `report.schema.json`). |
| `--output FILE` | Also write the report with owner-only permissions. |
| `--allow-origin ORIGIN` | Authorize a nonlocal origin you control. Loopback needs none. |
| `--require-explicit-samesite`, `--require-host-only`, `--max-lifetime-days N`, `--allowed-samesite lax,strict` | Stricter policy. |
| `--baseline FILE` | Compare with an earlier JSON report; removed protections become CG007. |
| `--input FILE` | Audit a JSON cookie array instead of scanning. |

Exit codes: `0` PASS, `1` FAIL, `2` INCOMPLETE or error. Treat any nonzero exit
as a failed gate; never retry with a looser policy to get 0.

## Any CI system

Start the application, wait until it answers, then run the CLI and keep its exit code:

```bash
npx --yes cookieguard-ci@0.1.0 scan "$APP_URL" --auth-cookie session_id --format json --output cookieguard.json
```

## GitHub Actions

```yaml
permissions:
  contents: read
steps:
  # ...check out and start the application on the runner...
  - uses: aiscihub/cookieguard-ai/action@12a09fe322b135ac2a5aec45cae1f880b717575f # ci-v0.1.0
    with:
      target: http://127.0.0.1:3000/
      auth-cookies: session_id
      fail-on: high
```

The Action writes a Step Summary and a sanitized JSON artifact, then exits with
the audit's code. Do not pass credentials or tokens as inputs.

## Main branch only (not in 0.1.0 yet)

`cookieguard-ci capabilities --json`, `cookieguard-ci explain CG001 --json`,
`--json` as a shortcut, JSON errors on stdout, and `--input` with a sanitized
CookieGuard or Browser Use JSON report. These need a source checkout until the
next release.
