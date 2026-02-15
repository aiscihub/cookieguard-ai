"""
CookieGuard AI 2.0 - Explainability Engine
Generates human-readable explanations for why the AI flagged each cookie.
Two paths: rule-based top signals + LR coefficient-based contributions.
"""

from typing import Dict, List, Tuple


# ─────────────────────────────────────────────────────────────
# Feature → human-readable explanation mapping
# ─────────────────────────────────────────────────────────────

AUTH_SIGNAL_MAP = {
    'name_matches_auth':        ('Identity keyword in name', 'Cookie name matches authentication patterns (session, auth, token, etc.)'),
    'f_changed_during_login':   ('Changed during login', 'Cookie value changed when user logged in — strong authentication signal'),
    'f_new_after_login':        ('Appeared after login', 'Cookie was created during the login process'),
    'f_rotated_after_login':    ('Rotated after login', 'Cookie value was rotated at login — typical of session tokens'),
    'has_httponly':              ('HttpOnly flag set', 'Server restricted JavaScript access — common for auth cookies'),
    'has_secure':               ('Secure flag set', 'Cookie requires HTTPS — standard for sensitive tokens'),
    'is_session_cookie':        ('Session-scoped', 'Cookie expires when browser closes — typical for session tokens'),
    'value_looks_like_jwt':     ('JWT token pattern', 'Value matches JSON Web Token structure (header.payload.signature)'),
    'value_entropy_bucket':     ('High-entropy token', 'Cookie value has high randomness — characteristic of cryptographic tokens'),
    'value_looks_like_hex':     ('Hex token value', 'Value is hexadecimal — common for session identifiers'),
    'value_length_bucket':      ('Long token value', 'Cookie value length suggests a security token'),
    'has_host_prefix':          ('__Host- prefix', 'Uses secure __Host- prefix — locked to specific origin'),
    'has_secure_prefix':        ('__Secure- prefix', 'Uses __Secure- prefix — requires HTTPS'),
    'f_login_behavior_score':   ('Strong login correlation', 'Multiple login-related behavior signals detected'),
}

RISK_SIGNAL_MAP = {
    'cross_site_sendable':      ('Sent cross-site (SameSite=None)', 'Cookie is sent with cross-origin requests, enabling CSRF attacks'),
    'domain_is_wildcard':       ('Shared across subdomains', 'Wildcard domain scope — any subdomain can access this cookie'),
    'f_subdomain_shared':       ('Subdomain-shared scope', 'Cookie accessible to multiple subdomains — broader attack surface'),
    'f_third_party_context':    ('Third-party context', 'Cookie set by or shared with a different domain'),
    'exposure_score':           ('High exposure score', 'Combined domain scope and lifetime create elevated exposure'),
    'f_persistent_days_bucket': ('Long-lived cookie', 'Extended lifetime increases window for replay attacks'),
}

TRACKING_SIGNAL_MAP = {
    'name_matches_tracking':    ('Tracking keyword in name', 'Name matches known analytics/tracking patterns (_ga, fbp, etc.)'),
    'f_third_party_context':    ('Third-party tracker', 'Cookie is set by an external domain — typical of ad/analytics trackers'),
}


def explain_prediction(
        features: Dict,
        classification_type: str,
        classification_probs: Dict,
        risk_severity: str,
        risk_issues: List[Dict],
        model_contributions: Dict = None,
) -> Dict:
    """
    Generate per-cookie explainability payload.
    
    Args:
        features: Extracted feature dict
        classification_type: 'authentication', 'tracking', 'preference', 'other'
        classification_probs: Dict of class probabilities
        risk_severity: 'critical', 'high', 'medium', 'low', 'info'
        risk_issues: List of issue dicts from risk scorer
        model_contributions: Optional output from classifier.get_feature_contributions()
    
    Returns:
        Dict with 'auth_signals', 'risk_signals', 'tracking_signals', 'risk_formula'
    """

    auth_signals = []
    risk_signals = []
    tracking_signals = []

    # ── Auth classification signals ──────────────────────────
    if classification_type == 'authentication' or classification_probs.get('authentication', 0) > 0.3:
        for feat_name, (short, detail) in AUTH_SIGNAL_MAP.items():
            val = features.get(feat_name, 0)
            if _is_active(feat_name, val):
                auth_signals.append({
                    'signal': short,
                    'detail': detail,
                    'feature': feat_name,
                    'value': val,
                    'direction': 'positive',  # increases P(auth)
                })

        # Add model-based contributions if available
        if model_contributions and model_contributions.get('auth_drivers'):
            for fname, contrib, fval in model_contributions['auth_drivers']:
                # Avoid duplicating signals already captured
                if not any(s['feature'] == fname for s in auth_signals):
                    human = AUTH_SIGNAL_MAP.get(fname, (fname.replace('_', ' ').title(), ''))
                    if isinstance(human, tuple):
                        short, detail = human
                    else:
                        short, detail = human, ''
                    if fval > 0:
                        auth_signals.append({
                            'signal': short,
                            'detail': detail or f'Model contribution: {contrib:.3f}',
                            'feature': fname,
                            'value': fval,
                            'direction': 'positive',
                            'coefficient_contribution': contrib,
                        })

    # ── Risk / exposure signals ──────────────────────────────
    for feat_name, (short, detail) in RISK_SIGNAL_MAP.items():
        val = features.get(feat_name, 0)
        if _is_active(feat_name, val):
            risk_signals.append({
                'signal': short,
                'detail': detail,
                'feature': feat_name,
                'value': val,
            })

    # ── Tracking signals ─────────────────────────────────────
    if classification_type == 'tracking' or classification_probs.get('tracking', 0) > 0.3:
        for feat_name, (short, detail) in TRACKING_SIGNAL_MAP.items():
            val = features.get(feat_name, 0)
            if _is_active(feat_name, val):
                tracking_signals.append({
                    'signal': short,
                    'detail': detail,
                    'feature': feat_name,
                    'value': val,
                })

    # ── Risk formula breakdown ───────────────────────────────
    auth_prob = classification_probs.get('authentication', 0)
    exposure = features.get('exposure_score', 1.0)

    # Reconstruct severity points from issue list (mirrors risk_scorer.py)
    severity_point_map = {
        'httponly': 40,
        'secure flag': 25,
        'samesite': 20,
        'wildcard domain': 15,
        'long-lived': 10,
        'moderate session': 5,
        'multi-day': 3,
        'broad path': 5,
        'non-host-only': 6,
        'shared cookie': 4,
    }
    severity_points = 0
    for issue in risk_issues:
        title_lower = (issue.get('title', '') or '').lower()
        for pattern, pts in severity_point_map.items():
            if pattern in title_lower:
                severity_points += pts
                break

    # Breadth factor (from domain scope)
    domain_wildcard = features.get('domain_is_wildcard', 0)
    breadth = 1.5 if domain_wildcard else 1.0

    # Lifetime factor
    expiry_days = features.get('expiry_days', 0)
    is_session = features.get('is_session_cookie', 0)
    lifetime = 1.0 if is_session else (1.0 + min(expiry_days / 365.0, 1.0))

    risk_formula = {
        'components': {
            'auth_gate': round(auth_prob, 3),
            'severity_points': severity_points,
            'breadth_factor': round(breadth, 2),
            'lifetime_factor': round(lifetime, 2),
            'estimated_score': int(severity_points * breadth * lifetime) if auth_prob > 0.3 else 0,
        },
        'formula': 'RiskScore = Σ(Severity Points) × Breadth × Lifetime  [gated on P(auth) > 0.3]',
        'interpretation': _interpret_risk(auth_prob, severity_points, breadth * lifetime),
    }

    return {
        'auth_signals': auth_signals[:5],    # Top 5
        'risk_signals': risk_signals[:3],     # Top 3
        'tracking_signals': tracking_signals[:3],
        'risk_formula': risk_formula,
    }


def _is_active(feat_name: str, value) -> bool:
    """Determine if a feature value is 'active' (contributes to the explanation)."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        # Special thresholds for certain features
        if feat_name in ('value_entropy_bucket',):
            return value >= 2  # high entropy
        if feat_name in ('value_length_bucket',):
            return value >= 2  # long value
        if feat_name in ('exposure_score',):
            return value > 1.5
        if feat_name in ('f_persistent_days_bucket',):
            return value >= 3  # >30 days
        if feat_name in ('f_login_behavior_score',):
            return value >= 2  # at least 2 of 3 login signals
        return value > 0
    return False



def _interpret_risk(auth_prob: float, severity_points: int, exposure_multiplier: float) -> str:
    estimated = int(severity_points * exposure_multiplier) if auth_prob > 0.3 else 0
    if auth_prob > 0.7 and estimated >= 50:
        return "High-confidence auth cookie with critical security gaps — account takeover possible"
    if auth_prob > 0.7 and estimated >= 30:
        return "High-confidence auth cookie with significant security gaps"
    if auth_prob > 0.7 and estimated < 15:
        return "Auth cookie with good security posture — low risk"
    if auth_prob > 0.3 and estimated >= 30:
        return "Possible auth cookie with elevated risk from missing protections"
    if auth_prob > 0.3 and estimated > 0:
        return "Possible auth cookie with moderate risk"
    if auth_prob <= 0.3:
        return "Low authentication probability — severity checks not applied"
    return "Minimal security concerns detected"