# Security-gate comparison results

## CI decision by app version (correct decisions / runs)

| Version | Expected | A. Native Playwright | B. Minimal fixture | C. CookieGuard | C0. CookieGuard, default policy |
| --- | --- | --- | --- | --- | --- |
| fixed | PASS | 3/3 (PASS) | 3/3 (PASS) | 3/3 (PASS) | 3/3 (PASS) |
| strict-samesite | PASS | 3/3 (PASS) | 3/3 (PASS) | 3/3 (PASS) | 3/3 (PASS) |
| malformed-header | PASS | 3/3 (PASS) | 3/3 (PASS) | 3/3 (PASS) | 3/3 (PASS) |
| no-httponly | FAIL | 3/3 (FAIL) | 3/3 (FAIL) | 3/3 (FAIL) | 3/3 (FAIL) |
| no-secure | FAIL | 3/3 (FAIL) | 3/3 (FAIL) | 3/3 (FAIL) | 3/3 (FAIL) |
| samesite-none | FAIL | 3/3 (FAIL) | 3/3 (FAIL) | 3/3 (FAIL) | 0/3 (PASS) |
| js-token | FAIL | 3/3 (FAIL) | 3/3 (FAIL) | 3/3 (FAIL) | 3/3 (FAIL) |
| logout-kept | FAIL | 3/3 (FAIL) | 3/3 (FAIL) | 3/3 (FAIL) | 3/3 (FAIL) |
| renamed-cookie | INCOMPLETE | 3/3 (FAIL) | 3/3 (INCOMPLETE) | 3/3 (INCOMPLETE) | 3/3 (INCOMPLETE) |
| login-broken | INCOMPLETE | 3/3 (FAIL) | 3/3 (INCOMPLETE) | 3/3 (INCOMPLETE) | 3/3 (INCOMPLETE) |
| replay-error | INCOMPLETE | 3/3 (FAIL) | 3/3 (INCOMPLETE) | 3/3 (INCOMPLETE) | 3/3 (INCOMPLETE) |

## Totals

| Measure | A. Native Playwright | B. Minimal fixture | C. CookieGuard | C0. CookieGuard, default policy |
| --- | --- | --- | --- | --- |
| Flawed versions blocked | 15/15 | 15/15 | 15/15 | 12/15 |
| Secure versions accepted | 9/9 | 9/9 | 9/9 | 9/9 |
| Missing-evidence versions blocked | 9/9 | 9/9 | 9/9 | 9/9 |
| …reported as INCOMPLETE, not as a flaw | 0/9 | 9/9 | 9/9 | 9/9 |
| Runs with a credential value in console output | 3/33 | 0/33 | 0/33 | 0/33 |
| Runs with a credential value in written files | 3/33 | 0/33 | 0/33 | 0/33 |
| Inconsistent cells across repeats | 0/11 | 0/11 | 0/11 | 0/11 |
| Median CI time (s) | 2.2 | 2.3 | 2.3 | 2.3 |

## Neutralized checks on the `no-httponly` app (does CI still block?)

| Workspace edit | A. Native Playwright | B. Minimal fixture | C. CookieGuard |
| --- | --- | --- | --- |
| none: unmodified | blocked (FAIL) | blocked (FAIL) | blocked (FAIL) |
| skip: file-level test.skip() | **accepted** (PASS) | blocked (INCOMPLETE) | blocked (INCOMPLETE) |
| known-failure: file-level test.fail() (the Playwright analogue of a todo test) | **accepted** (PASS) | blocked (FAIL) | blocked (FAIL) |
| swallow: test body wrapped in try/catch | blocked (FAIL) | blocked (FAIL) | blocked (FAIL) |
| filter: npm test runs only the other spec | **accepted** (PASS) | blocked (INCOMPLETE) | blocked (INCOMPLETE) |
| delete: security spec deleted | **accepted** (PASS) | blocked (INCOMPLETE) | blocked (INCOMPLETE) |
| weaken: the HttpOnly requirement removed from workspace test code | **accepted** (PASS) | **accepted** (PASS) | blocked (FAIL) |
| forge: test skipped and a passing verdict file planted (deliberate) | n/a | **accepted** (PASS) | **accepted** (PASS) |

Same edits on the secure app: 6/9 accepted (native/known-failure, fixture/known-failure, cookieguard/known-failure).

## Native assertion idioms: does the failure output contain the credential value?

| Idiom [app version] | Test failed | Value in console | Value in files |
| --- | --- | --- | --- |
| toMatchObject on the cookie object [no-httponly] | yes | no | no |
| toContainEqual on context.cookies() [no-httponly] | yes | **yes** | **yes** |
| toEqual objectContaining on the cookie [no-httponly] | yes | **yes** | **yes** |
| toHaveLength(0) on credentials without HttpOnly [no-httponly] | yes | **yes** | **yes** |
| toBe on the flag [no-httponly] | yes | no | no |
| toBe on the flag with a message [no-httponly] | yes | no | no |
| toContain on the Set-Cookie header [no-httponly] | yes | **yes** | **yes** |
| toMatch on the Set-Cookie header [no-httponly] | yes | **yes** | **yes** |
| node assert.match on the Set-Cookie header [no-httponly] | yes | **yes** | **yes** |
| document.cookie must not contain the token [js-token] | yes | **yes** | **yes** |
| document.cookie names only [js-token] | yes | no | no |
| logout replay, status assertion [logout-kept] | yes | no | no |
| logout replay, not.toBeOK [logout-kept] | yes | **yes** | **yes** |
| logout replay when the request errors [replay-error] | yes | **yes** | **yes** |

## Security-specific code (non-blank, non-comment lines)

| Approach | Test-side code | CI gate | Files |
| --- | --- | --- | --- |
| A. Native Playwright | 22 | none | native/e2e/security.spec.js |
| B. Minimal fixture | 55 | 13 (script) + 1 command | fixture/e2e/security.spec.js, fixture/e2e/session-security.js, fixture/ci/security-gate.mjs |
| C. CookieGuard | 12 | 1 command | cookieguard/e2e/security.spec.js |

Shared login steps used unchanged by all approaches: 14 lines.
