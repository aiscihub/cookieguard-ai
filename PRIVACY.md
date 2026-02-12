# Privacy Policy

CookieGuard AI is designed with a privacy-first architecture.  
All analysis is performed locally on the user's device.

## What Data Is Accessed

CookieGuard reads cookie metadata available through the browser, including:

- Cookie name
- Domain
- Path
- Expiration
- Secure flag
- HttpOnly flag
- SameSite attribute

## What Data Is NOT Collected

- Raw cookie values are not stored or transmitted.
- Authentication tokens are never exfiltrated.
- No browsing history is logged.
- No personal data is sent to external servers.

## Local Processing

- All classification and risk scoring occurs on-device.
- The Python backend runs locally at `localhost`.
- No remote API calls are required for analysis.

## Data Storage

- CookieGuard does not persist cookie data.
- Analysis results are displayed in-session only.
- No analytics tracking is included.

## User Control

Users can:
- Disable the extension at any time.
- Inspect the open-source code.
- Modify or remove local backend components.

## Security Philosophy

CookieGuard is built to reduce identity theft risk while minimizing data exposure.  
The system follows the principle of least privilege and metadata-only inspection.

If you discover any privacy-related issue, please report it responsibly (see SECURITY.md).
