"""
Enhanced Feature Extractor - 34 Features (vs original 18)
CookieGuard AI Backend Enhancement
"""

import re, math
from datetime import datetime
from typing import Dict, List

class CookieFeatureExtractor:
    AUTH_PATTERNS = [r'session', r'auth', r'token', r'login', r'jwt', r'bearer', r'sid', r'user']
    TRACKING_PATTERNS = [r'^_ga', r'^_gid', r'analytics', r'tracking', r'^utm', r'^fbp']
    PREFERENCE_PATTERNS = [r'lang', r'theme', r'consent', r'preferences', r'settings']
    
    def extract_features(self, cookie: Dict) -> Dict:
        features = {}
        samesite = (cookie.get('sameSite') or '').lower()
        
        # GROUP 1: Attributes (9 features)
        features['has_secure'] = int(cookie.get('secure', False))
        features['has_httponly'] = int(cookie.get('httpOnly', False))
        features['has_samesite'] = int(bool(cookie.get('sameSite')))
        features['samesite_level'] = 2 if samesite=='strict' else (1 if samesite=='lax' else 0)
        
        expiry = cookie.get('expirationDate')
        if expiry:
            dt = datetime.fromtimestamp(expiry) if isinstance(expiry, (int,float)) else datetime.fromisoformat(str(expiry))
            days = max((dt - datetime.now()).days, 0)
            features['is_session_cookie'], features['expiry_days'] = 0, min(days, 365)
            features['lifetime_category'] = 0 if days<1 else (1 if days<7 else (2 if days<30 else 3))
        else:
            features['is_session_cookie'], features['expiry_days'], features['lifetime_category'] = 1, 0, 0
        
        # GROUP 2: Scope (8 features)
        domain, path = cookie.get('domain',''), cookie.get('path','/')
        features['domain_is_wildcard'] = int(domain.startswith('.'))
        features['domain_depth'] = domain.count('.')
        features['etld_match'] = 1
        features['path_is_root'] = int(path=='/')
        features['path_depth'] = path.count('/')-1
        features['cross_site_sendable'] = int(not samesite or samesite=='none')
        features['exposure_score'] = (2.0 if features['domain_is_wildcard'] else 1.0) * (1 + features['expiry_days']/365.0)
        
        # GROUP 3: Lexical (17 features)
        name, value = cookie.get('name','').lower(), cookie.get('value','')
        features['name_matches_auth'] = int(any(re.search(p,name,re.I) for p in self.AUTH_PATTERNS))
        features['name_matches_tracking'] = int(any(re.search(p,name,re.I) for p in self.TRACKING_PATTERNS))
        features['name_matches_preference'] = int(any(re.search(p,name,re.I) for p in self.PREFERENCE_PATTERNS))
        features['has_host_prefix'] = int(name.startswith('__host-'))
        features['has_secure_prefix'] = int(name.startswith('__secure-'))
        features['name_entropy'] = self._entropy(name)
        features['name_length'] = len(name)
        features['name_has_underscore'] = int('_' in name)
        
        if value:
            ent = self._entropy(value)
            features['value_length'] = len(value)
            features['value_entropy_bucket'] = 0 if ent<2 else (1 if ent<4 else 2)
            features['value_looks_like_jwt'] = int(value.count('.')==2 and len(value)>50)
            features['value_looks_like_hex'] = int(bool(re.match(r'^[a-f0-9]+$', value.lower())))
            features['value_looks_base64'] = int(len(set(value)-set('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/='))<len(set(value))*0.1)
            features['value_has_padding'] = int(value.endswith('='))
            features['value_is_numeric'] = int(value.isdigit())
            features['value_length_bucket'] = 0 if len(value)<20 else (1 if len(value)<50 else (2 if len(value)<100 else 3))
        else:
            for k in ['value_length','value_entropy_bucket','value_looks_like_jwt','value_looks_like_hex','value_looks_base64','value_has_padding','value_is_numeric','value_length_bucket']:
                features[k] = 0
        
        features['_cookie_name'], features['_cookie_domain'] = cookie.get('name'), cookie.get('domain')
        return features
    
    def _entropy(self, text):
        if not text: return 0.0
        counts = {}
        for c in text: counts[c] = counts.get(c,0)+1
        ent = 0.0
        for cnt in counts.values():
            p = cnt/len(text)
            ent -= p*math.log2(p)
        return ent
    
    def get_feature_names(self):
        return ['has_secure','has_httponly','has_samesite','samesite_level','is_session_cookie','expiry_days','lifetime_category',
                'domain_is_wildcard','domain_depth','etld_match','path_is_root','path_depth','cross_site_sendable','exposure_score',
                'name_matches_auth','name_matches_tracking','name_matches_preference','has_host_prefix','has_secure_prefix',
                'name_entropy','name_length','name_has_underscore','value_length','value_entropy_bucket','value_looks_like_jwt',
                'value_looks_like_hex','value_looks_base64','value_has_padding','value_is_numeric','value_length_bucket']
