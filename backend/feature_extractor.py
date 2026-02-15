"""
CookieGuard AI 2.0 - Enhanced Feature Extractor
38 features across 4 groups: Attributes, Scope, Lexical, Behavior
"""

import re
import math
from datetime import datetime
from typing import Dict, List


class CookieFeatureExtractor:
    AUTH_PATTERNS = [r'session', r'auth', r'token', r'login', r'jwt', r'bearer', r'sid', r'user', r'sso', r'refresh']
    TRACKING_PATTERNS = [r'^_ga', r'^_gid', r'analytics', r'tracking', r'^utm', r'^fbp', r'amplitude', r'mixpanel', r'^_cl']
    PREFERENCE_PATTERNS = [r'lang', r'theme', r'consent', r'preferences', r'settings', r'locale', r'timezone', r'currency']

    # Feature groups for explainability
    FEATURE_GROUPS = {
        'attributes': [
            'has_secure', 'has_httponly', 'has_samesite', 'samesite_level',
            'is_session_cookie', 'expiry_days', 'lifetime_category'
        ],
        'scope': [
            'domain_is_wildcard', 'domain_depth', 'etld_match',
            'path_is_root', 'path_depth', 'cross_site_sendable', 'exposure_score'
        ],
        'lexical': [
            'name_matches_auth', 'name_matches_tracking', 'name_matches_preference',
            'has_host_prefix', 'has_secure_prefix', 'name_entropy', 'name_length',
            'name_has_underscore', 'value_length', 'value_entropy_bucket',
            'value_looks_like_jwt', 'value_looks_like_hex', 'value_looks_base64',
            'value_has_padding', 'value_is_numeric', 'value_length_bucket'
        ],
        'behavior': [
            'f_changed_during_login', 'f_new_after_login', 'f_rotated_after_login',
            'f_persistent_days_bucket', 'f_subdomain_shared', 'f_third_party_context',
            'f_login_behavior_score', 'f_security_posture_score'
        ]
    }

    def extract_features(self, cookie: Dict, context: Dict = None) -> Dict:
        """
        Extract all 38 features from a cookie.
        
        Args:
            cookie: Cookie dict with standard fields
            context: Optional dict with loginEvent, changedCookies, beforeCookieIndex, currentDomain
        
        Returns:
            Feature dict (38 numeric features + 2 metadata fields)
        """
        context = context or {}
        features = {}
        samesite = (cookie.get('sameSite') or '').lower()

        # ═══════════════════════════════════════════════════════════
        # GROUP 1: ATTRIBUTES (7 features)
        # ═══════════════════════════════════════════════════════════
        features['has_secure'] = int(bool(cookie.get('secure', False)))
        features['has_httponly'] = int(bool(cookie.get('httpOnly', False)))
        features['has_samesite'] = int(bool(cookie.get('sameSite')))
        features['samesite_level'] = 2 if samesite == 'strict' else (1 if samesite == 'lax' else 0)

        expiry = cookie.get('expirationDate')
        if expiry:
            dt = datetime.fromtimestamp(expiry) if isinstance(expiry, (int, float)) else datetime.fromisoformat(str(expiry))
            days = max((dt - datetime.now()).days, 0)
            features['is_session_cookie'] = 0
            features['expiry_days'] = min(days, 365)
            features['lifetime_category'] = 0 if days < 1 else (1 if days < 7 else (2 if days < 30 else 3))
        else:
            features['is_session_cookie'] = 1
            features['expiry_days'] = 0
            features['lifetime_category'] = 0

        # ═══════════════════════════════════════════════════════════
        # GROUP 2: SCOPE (7 features)
        # ═══════════════════════════════════════════════════════════
        domain = cookie.get('domain', '')
        path = cookie.get('path', '/')
        features['domain_is_wildcard'] = int(domain.startswith('.'))
        features['domain_depth'] = domain.count('.')
        features['etld_match'] = 1
        features['path_is_root'] = int(path == '/')
        features['path_depth'] = max(path.count('/') - 1, 0)
        features['cross_site_sendable'] = int(not samesite or samesite in ('none', 'no_restriction'))
        features['exposure_score'] = (
            (2.0 if features['domain_is_wildcard'] else 1.0)
            * (1 + features['expiry_days'] / 365.0)
        )

        # ═══════════════════════════════════════════════════════════
        # GROUP 3: LEXICAL (16 features)
        # ═══════════════════════════════════════════════════════════
        name = cookie.get('name', '').lower()
        value = cookie.get('value', '')

        features['name_matches_auth'] = int(any(re.search(p, name, re.I) for p in self.AUTH_PATTERNS))
        features['name_matches_tracking'] = int(any(re.search(p, name, re.I) for p in self.TRACKING_PATTERNS))
        features['name_matches_preference'] = int(any(re.search(p, name, re.I) for p in self.PREFERENCE_PATTERNS))
        features['has_host_prefix'] = int(name.startswith('__host-'))
        features['has_secure_prefix'] = int(name.startswith('__secure-'))
        features['name_entropy'] = self._entropy(name)
        features['name_length'] = len(name)
        features['name_has_underscore'] = int('_' in name)

        if value:
            ent = self._entropy(value)
            features['value_length'] = len(value)
            features['value_entropy_bucket'] = 0 if ent < 2 else (1 if ent < 4 else 2)
            features['value_looks_like_jwt'] = int(value.count('.') == 2 and len(value) > 50)
            features['value_looks_like_hex'] = int(bool(re.match(r'^[a-f0-9]+$', value.lower())))
            features['value_looks_base64'] = int(
                len(set(value) - set('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=-_')) < max(len(set(value)) * 0.1, 1)
            )
            features['value_has_padding'] = int(value.endswith('='))
            features['value_is_numeric'] = int(value.isdigit())
            features['value_length_bucket'] = 0 if len(value) < 20 else (1 if len(value) < 50 else (2 if len(value) < 100 else 3))
        else:
            for k in ['value_length', 'value_entropy_bucket', 'value_looks_like_jwt',
                       'value_looks_like_hex', 'value_looks_base64', 'value_has_padding',
                       'value_is_numeric', 'value_length_bucket']:
                features[k] = 0

        # ═══════════════════════════════════════════════════════════
        # GROUP 4: BEHAVIOR (8 features) - NEW IN 2.0
        # ═══════════════════════════════════════════════════════════
        cookie_name = cookie.get('name', '')
        changed_cookies = context.get('changedCookies', [])
        login_event = context.get('loginEvent', False)
        before_index = context.get('beforeCookieIndex', {})
        current_domain = context.get('currentDomain', '')

        # Direct behavior signals (from training data or runtime context)
        if 'changed_during_login' in cookie:
            # Training data path: behavior fields are embedded in cookie dict
            features['f_changed_during_login'] = int(cookie.get('changed_during_login', 0))
            features['f_new_after_login'] = int(cookie.get('new_after_login', 0))
            features['f_rotated_after_login'] = int(cookie.get('rotated_after_login', 0))
        elif login_event and changed_cookies:
            # Runtime path: derive from context
            features['f_changed_during_login'] = int(cookie_name in changed_cookies)
            if before_index:
                was_present = cookie_name in before_index
                features['f_new_after_login'] = int(not was_present)
                features['f_rotated_after_login'] = int(
                    was_present and before_index.get(cookie_name, {}).get('present', False)
                )
            else:
                features['f_new_after_login'] = int(cookie_name in changed_cookies)
                features['f_rotated_after_login'] = 0
        else:
            # No login context: default to 0 (unknown)
            features['f_changed_during_login'] = 0
            features['f_new_after_login'] = 0
            features['f_rotated_after_login'] = 0

        # Persistent days bucket: 0=session, 1=1-7d, 2=8-30d, 3=>30d
        days = features['expiry_days']
        if features['is_session_cookie']:
            features['f_persistent_days_bucket'] = 0
        elif days <= 7:
            features['f_persistent_days_bucket'] = 1
        elif days <= 30:
            features['f_persistent_days_bucket'] = 2
        else:
            features['f_persistent_days_bucket'] = 3

        # Subdomain shared: domain starts with "." or hostOnly is False
        host_only = cookie.get('hostOnly')
        features['f_subdomain_shared'] = int(
            domain.startswith('.') or (host_only is not None and not host_only)
        )

        # Third-party context
        if 'third_party' in cookie:
            features['f_third_party_context'] = int(cookie.get('third_party', 0))
        elif current_domain:
            clean_domain = domain.lstrip('.')
            features['f_third_party_context'] = int(
                clean_domain != current_domain and not clean_domain.endswith('.' + current_domain)
            )
        else:
            features['f_third_party_context'] = 0

        # Composite: login behavior score (0-3)
        features['f_login_behavior_score'] = (
            features['f_changed_during_login']
            + features['f_new_after_login']
            + features['f_rotated_after_login']
        )

        # Composite: security posture score (0-3, higher = more secure)
        features['f_security_posture_score'] = (
            features['has_secure']
            + features['has_httponly']
            + min(features['samesite_level'], 1)  # 1 if lax or strict
        )

        # Metadata (not used as model features, but useful for explainability)
        features['_cookie_name'] = cookie.get('name')
        features['_cookie_domain'] = cookie.get('domain')

        return features

    def _entropy(self, text):
        if not text:
            return 0.0
        counts = {}
        for c in text:
            counts[c] = counts.get(c, 0) + 1
        ent = 0.0
        for cnt in counts.values():
            p = cnt / len(text)
            ent -= p * math.log2(p)
        return ent

    def get_feature_names(self):
        """Return ordered list of all numeric feature names (no metadata)."""
        names = []
        for group_features in self.FEATURE_GROUPS.values():
            names.extend(group_features)
        return names

    def get_feature_groups(self):
        """Return feature group mapping for explainability."""
        return self.FEATURE_GROUPS.copy()
