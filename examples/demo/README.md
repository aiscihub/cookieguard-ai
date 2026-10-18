# Entirely local fixture app

`npm run demo` listens on `127.0.0.1:3000`; `PORT` can select another port.
No credentials, external resources, or real sessions. The artificial token is a
leakage-test sentinel. The server never logs headers or values.

| Path | Case |
| --- | --- |
| `/secure` | A: Secure, HttpOnly, SameSite=Lax |
| `/missing-httponly` | B: missing HttpOnly |
| `/missing-secure` | C: missing Secure |
| `/preference` | D: preference, no confirmed auth role |
| `/unknown` | E: auth hint, review without developer confirmation |
| `/default-samesite` | Absent declaration, browser effective Lax |
| `/rejected-prefix` | Invalid __Host- Path, rejected by Chromium |
| `/rejected-none` | SameSite=None without Secure, rejected by Chromium |
| `/delete` | Deletion header |

Case F creates the session first, then audits the store in Playwright, preserving
unknown declarations. Chromium's loopback exception allows this Secure-cookie
demo over HTTP; production needs HTTPS. No TLS validation is disabled.
