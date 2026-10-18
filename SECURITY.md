# Security Policy

CookieGuard AI is a research and educational tool focused on authentication cookie risk analysis.

CookieGuard CI `0.1.0` is available as a public beta for developer policy checks.
A clean report is limited to the observed cookies and configured policy; it is
not a security certification. Strict failures require
developer-identified authentication names or scoped server-session validation.
Classifier scores, Domain sharing, and SameSite=None do not prove attacks.

CI accepts only loopback targets by default. Nonlocal scans require explicit
exact-origin authorization for an application the developer controls. Redirects
stay on the initial origin; credentials, URL queries, private remote destinations,
and unbounded crawling are unsupported. The Playwright adapter does not navigate
or impose a network sandbox on the caller's browser.

Never attach real tokens, headers, storage exports, or traces to a vulnerability
report. Use synthetic reproduction values. CI errors deliberately omit original
exception text. See [the architecture](docs/CI_ARCHITECTURE.md) and
[validation limits](docs/CI_VALIDATION.md). The legacy extension's manual JSON
export includes values; handle it as sensitive data, as explained in PRIVACY.md.

## Supported Versions

The latest tagged release is actively maintained.  
Older versions may not receive updates.

## Reporting a Vulnerability

If you discover a security issue:

1. Do NOT open a public GitHub issue.
2. Email the maintainer directly.
3. Provide:
    - Description of the vulnerability
    - Steps to reproduce
    - Potential impact

We will:
- Acknowledge receipt within 72 hours.
- Investigate and validate the issue.
- Provide a patch or mitigation if applicable.

## Scope

CookieGuard:
- Performs metadata-based risk analysis.
- Does NOT modify cookies.
- Does NOT bypass browser security mechanisms.

This tool is intended for defensive security research and awareness.

## Disclaimer

CookieGuard AI is not a replacement for professional security audits.  
False positives and false negatives may occur.
