# Reading results

[Overview](../README.md) · [Install](install.md) · [Policy](policy.md) · [How it works](how-it-works.md) · **Results** · [Limits & privacy](limits-and-privacy.md) · [Demo & tests](demo-and-tests.md)

| Status | Exit | Meaning |
| --- | --- | --- |
| `PASS` | 0 | Evidence complete; no confirmed violation at or above `fail_on`. Review items may remain. |
| `FAIL` | 1 | A confirmed violation at or above `fail_on`. |
| `INCOMPLETE` | 2 | Evidence missing or unreliable: expected cookie absent, observer disconnected, store unreadable, unattributable headers, limits exceeded. Never a pass. |

Each `Finding` has `rule_id`, `severity`, `status`, `cookie_name`/`domain`/`path`/`origin`,
`title`, `explanation`, `recommendation`, `evidence_category`, and sanitized `evidence`.
The `status` is either `confirmed` (a policy violation of a cookie you identified) or `review` (uncertain).
`evidence_category` is either `server-declaration` (an observed `Set-Cookie`) or `browser-observation` (cookie store).
`result.collection` explains how evidence was gathered, including `incompleteReasons`.
`result.to_json()` / `write_json(path)` produce a value-free report (files are `0600`).
`result.report` is the CookieGuard core JSON report (schemaVersion 1).
