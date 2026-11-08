# Findings and the security report

## Where the result comes from

| Integration | Object | Status field | Findings |
| --- | --- | --- | --- |
| Browser Use | `AuditResult` from `await audit.finish()` | `status` (`'PASS'`, `'FAIL'`, `'INCOMPLETE'`), `exit_code` | `findings`, `confirmed_findings`, `review_findings`, `issues`, `limitations`, `summary` |
| Playwright and core | report from `await audit.evaluate()` | `status` (`'passed'`, `'failed'`, `'incomplete'`) | `findings`, `issues`, `limitations`, `summary` |
| CLI | `--format json` report on stdout; exit code 0/1/2 | `status` | same as core |
| MCP | `cookieguard_audit` result | `status`, `exitCode`, plus `isError` | `findings`, `issues`, `limitations`, `provenance`, `error` |

Each finding has a rule ID (`CG001`-`CG009`), a `severity` (`info` to `critical`), a
`status` of `confirmed` or `review`, a title, why it matters, and a fix. Evidence fields:

- `source` / `evidence_category`: `header` (`server-declaration`, from `Set-Cookie`) or
  `browser` (`browser-observation`, from the cookie store, which cannot show the original
  SameSite declaration).
- `identityBasis`: `developer-name` or `validated-auth-flow` confirms the cookie's role;
  `extension-rule-heuristic` and `extension-onnx-uncalibrated` are uncalibrated guesses.
- Attribute values: `secure`, `httpOnly`, `hostOnly`, `declaredSameSite`,
  `remainingLifetimeDays`. `null` means unknown, not false.

## Interpreting results

- **Confirmed** findings are observed violations on a configured authentication cookie.
  Those at or above `failOn` (default `high`) make the audit FAIL.
- **Review** findings are risk indicators: CG008 and CG009 always, CG004 unless
  `requireHostOnly` is set, and any rule on a cookie whose role is unconfirmed. List them as "needs review", never as confirmed vulnerabilities.
- **INCOMPLETE** means CookieGuard could not decide. Name the cause from `issues` or the
  error code, and do not call the cookie secure. Common causes:

| Code | Meaning | Next step |
| --- | --- | --- |
| `expected-auth-cookie-not-observed` | The configured cookie name was never set | Check the name and audit the request or login that creates the session |
| `no-cookies-observed` | Nothing set a cookie | Audit the login workflow, not a static page |
| `collection-incomplete` | Collection stopped early, hit a limit, or was provisional | Start collection before the login and evaluate once afterwards |
| `TARGET` | URL outside the allowed origins, or with credentials, query, or fragment | Use an allowed origin and a plain URL |
| `NETWORK` | App not reachable, non-2xx status, or timeout | Start the app and retry |
| `CONFIG` | Invalid option or policy value | Fix the command or configuration |

`npx --yes cookieguard-ci@0.3.0 explain CODE` explains any rule, issue, or error code.

- **Not run**: if prerequisites are missing or the environment is unsupported, say the
  audit was not performed. A skipped check is never a pass.
- A PASS covers only the checks listed in [security checks](security-checks.md) for the
  cookies observed in the audited workflow. It is not a full session-security assessment.

## Report template

```markdown
## Browser session cookie audit

**Overall:** FAIL | PASS | INCOMPLETE | Not assessed (CookieGuard <version>, <date>)

**Environment:** <framework and version>, <browser>, <OS>; integration: <Browser Use | Playwright | CLI | MCP>
**Scope:** origins <list>; authentication cookies <configured names>; policy failOn=<level>,
allowedSameSite=<list>, maxLifetimeDays=<n>; workflow: <what was exercised, e.g. POST /login>

**Checks executed:** CG001-CG009 configuration checks on <n> observed cookies.
**Not executed:** <checks or evidence that were unavailable, and why>

| Rule | Severity | Status | Cookie | Evidence | Fix |
| --- | --- | --- | --- | --- | --- |
| CG001 | high | confirmed | session_id | Set-Cookie without HttpOnly | Set HttpOnly at the server |

**Limitations:** configuration audit only; no XSS, CSRF, or server-side session testing; <others from `limitations`>
```

## Redaction rules for reports

- Never include cookie values, full `Set-Cookie` or `Cookie` headers, session IDs, tokens,
  passwords, or storage-state contents.
- Name only cookies the user configured as authentication cookies. Refer to other cookies
  generically ("one unconfigured cookie"), because arbitrary names can carry secrets or
  injected text.
- Origins, rule IDs, severities, attribute flags, and fixes are safe to report.
