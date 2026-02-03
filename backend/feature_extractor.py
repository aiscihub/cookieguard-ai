"""
Feature Extractor for Cookie Analysis
Converts raw cookie attributes into ML-ready features
"""

import re
from datetime import datetime
from typing import Dict, List
import math


class CookieFeatureExtractor:
    """Extract security-relevant features from cookie metadata"""
    
    # Common authentication cookie name patterns
    AUTH_PATTERNS = [
        r'session', r'sess', r'auth', r'token', r'login', r'user',
        r'jwt', r'bearer', r'sid', r'ssid', r'jsessionid', r'phpsessid',
        r'aspxauth', r'laravel_session', r'connect\.sid'
    ]
    
    # Tracking/analytics patterns
    TRACKING_PATTERNS = [
        r'^_ga', r'^_gid', r'analytics', r'tracking', r'^utm',
        r'facebook', r'doubleclick', r'adsense', r'amplitude'
    ]
    
    # Preference patterns
    PREFERENCE_PATTERNS = [
        r'lang', r'locale', r'theme', r'timezone', r'currency',
        r'consent', r'preferences', r'settings'
    ]
    
    def extract_features(self, cookie: Dict) -> Dict:
        """
        Extract features from a single cookie
        
        Args:
            cookie: Dict with keys: name, domain, path, secure, httpOnly, 
                    sameSite, expirationDate, value (optional)
        
        Returns:
            Feature dictionary for ML model
        """
        features = {}
        
        # 1. Security Flags (binary)
        features['has_secure'] = int(cookie.get('secure', False))
        features['has_httponly'] = int(cookie.get('httpOnly', False))
        features['has_samesite'] = int(bool(cookie.get('sameSite')))
        
        # 2. SameSite strictness (0=None/missing, 1=Lax, 2=Strict)
        samesite = cookie.get('sameSite', '') or ''
        samesite = samesite.lower() if samesite else ''
        features['samesite_level'] = 2 if samesite == 'strict' else (1 if samesite == 'lax' else 0)
        
        # 3. Expiry characteristics
        expiry = cookie.get('expirationDate')
        if expiry:
            # Convert to days from now
            if isinstance(expiry, (int, float)):
                expiry_dt = datetime.fromtimestamp(expiry)
            else:
                expiry_dt = datetime.fromisoformat(str(expiry))
            
            days_until_expiry = (expiry_dt - datetime.now()).days
            features['is_session_cookie'] = 0
            features['expiry_days'] = min(days_until_expiry, 365)  # Cap at 1 year
        else:
            features['is_session_cookie'] = 1
            features['expiry_days'] = 0
        
        # 4. Domain scope
        domain = cookie.get('domain', '')
        features['domain_is_wildcard'] = int(domain.startswith('.'))
        features['domain_depth'] = domain.count('.')
        
        # 5. Path scope
        path = cookie.get('path', '/')
        features['path_is_root'] = int(path == '/')
        
        # 6. Name pattern analysis
        name = cookie.get('name', '').lower()
        features['name_matches_auth'] = int(self._matches_patterns(name, self.AUTH_PATTERNS))
        features['name_matches_tracking'] = int(self._matches_patterns(name, self.TRACKING_PATTERNS))
        features['name_matches_preference'] = int(self._matches_patterns(name, self.PREFERENCE_PATTERNS))
        
        # 7. Name entropy (randomness indicator)
        features['name_entropy'] = self._calculate_entropy(name)
        features['name_length'] = len(name)
        
        # 8. Value characteristics (if provided, for training)
        value = cookie.get('value', '')
        if value:
            features['value_length'] = len(value)
            features['value_entropy'] = self._calculate_entropy(value)
            features['value_looks_like_jwt'] = int(value.count('.') == 2 and len(value) > 50)
            features['value_looks_like_hex'] = int(bool(re.match(r'^[a-f0-9]+$', value.lower())))
        else:
            features['value_length'] = 0
            features['value_entropy'] = 0
            features['value_looks_like_jwt'] = 0
            features['value_looks_like_hex'] = 0
        
        # Store original cookie for reference
        features['_cookie_name'] = cookie.get('name')
        features['_cookie_domain'] = cookie.get('domain')
        
        return features
    
    def _matches_patterns(self, text: str, patterns: List[str]) -> bool:
        """Check if text matches any pattern in the list"""
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False
    
    def _calculate_entropy(self, text: str) -> float:
        """Calculate Shannon entropy of a string"""
        if not text:
            return 0.0
        
        # Count character frequencies
        char_counts = {}
        for char in text:
            char_counts[char] = char_counts.get(char, 0) + 1
        
        # Calculate entropy
        entropy = 0.0
        text_len = len(text)
        for count in char_counts.values():
            probability = count / text_len
            entropy -= probability * math.log2(probability)
        
        return entropy
    
    def get_feature_names(self) -> List[str]:
        """Return list of feature names for ML model"""
        return [
            'has_secure',
            'has_httponly',
            'has_samesite',
            'samesite_level',
            'is_session_cookie',
            'expiry_days',
            'domain_is_wildcard',
            'domain_depth',
            'path_is_root',
            'name_matches_auth',
            'name_matches_tracking',
            'name_matches_preference',
            'name_entropy',
            'name_length',
            'value_length',
            'value_entropy',
            'value_looks_like_jwt',
            'value_looks_like_hex'
        ]


if __name__ == "__main__":
    # Test with example cookies
    extractor = CookieFeatureExtractor()
    
    test_cookies = [
        {
            "name": "session_token",
            "domain": ".example.com",
            "path": "/",
            "secure": True,
            "httpOnly": False,  # VULNERABLE!
            "sameSite": "Lax",
            "expirationDate": 1748736000,  # 30 days from now
            "value": "abc123def456"
        },
        {
            "name": "_ga",
            "domain": ".example.com",
            "path": "/",
            "secure": False,
            "httpOnly": False,
            "sameSite": None,
            "expirationDate": 1780272000,  # ~1 year
            "value": "GA1.2.123456789.1234567890"
        }
    ]
    
    print("Feature Extraction Test\n" + "="*50)
    for cookie in test_cookies:
        features = extractor.extract_features(cookie)
        print(f"\nCookie: {cookie['name']}")
        print(f"Features: {features}")
