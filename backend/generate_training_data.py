"""
Generate synthetic training data for cookie classifier
Creates realistic cookie examples with labels
"""

import json
import random
from datetime import datetime, timedelta


class TrainingDataGenerator:
    """Generate labeled cookie data for training"""
    
    # Authentication cookie patterns
    AUTH_NAMES = [
        'session_id', 'JSESSIONID', 'PHPSESSID', 'ASP.NET_SessionId',
        'auth_token', 'authentication', 'login_token', 'access_token',
        'laravel_session', 'connect.sid', 'wordpress_logged_in',
        'sid', 'sessionid', 'user_session', 'jwt_token', 'bearer_token'
    ]
    
    # Tracking cookie patterns
    TRACKING_NAMES = [
        '_ga', '_gid', '_gat', '__utma', '__utmb', '__utmc', '__utmz',
        'fbp', '_fbp', 'fr', 'datr', 'DoubleClickId', 'IDE',
        'amplitude_id', 'mp_mixpanel', 'intercom-session',
        'analytics_token', 'visitor_id', 'tracking_id'
    ]
    
    # Preference cookie patterns
    PREFERENCE_NAMES = [
        'language', 'lang', 'locale', 'timezone', 'tz',
        'theme', 'dark_mode', 'currency', 'region',
        'cookie_consent', 'gdpr_consent', 'preferences',
        'settings', 'layout_preference'
    ]
    
    # Other/functional cookies
    OTHER_NAMES = [
        'csrf_token', 'cache_id', 'ab_test_variant',
        'load_balancer', 'debug_mode', 'feature_flag',
        'temp_id', 'referrer', 'utm_source'
    ]
    
    DOMAINS = [
        'example.com', 'shop.example.com', 'api.example.com',
        'accounts.example.com', 'secure.example.com',
        'analytics.example.com', 'cdn.example.com'
    ]
    
    def generate_auth_cookie(self) -> dict:
        """Generate a realistic authentication cookie"""
        name = random.choice(self.AUTH_NAMES)
        
        # Auth cookies should have good security, but sometimes don't
        secure = random.random() > 0.1  # 90% secure
        http_only = random.random() > 0.3  # 70% httpOnly (VULNERABILITY: should be 100%)
        same_site = random.choice(['Strict', 'Lax', 'Lax', None])  # Often Lax
        
        # Usually session or short-lived
        if random.random() > 0.4:
            expiry = None  # Session cookie
        else:
            days = random.choice([7, 14, 30])
            expiry = int((datetime.now() + timedelta(days=days)).timestamp())
        
        # Authentication cookies often on root domain
        domain = random.choice([
            '.example.com',  # Wildcard
            'accounts.example.com',
            'example.com'
        ])
        
        return {
            'name': name,
            'value': self._generate_token_value(),
            'domain': domain,
            'path': '/',
            'secure': secure,
            'httpOnly': http_only,
            'sameSite': same_site,
            'expirationDate': expiry,
            'label': 'authentication'
        }
    
    def generate_tracking_cookie(self) -> dict:
        """Generate a realistic tracking cookie"""
        name = random.choice(self.TRACKING_NAMES)
        
        # Tracking cookies often have poor security
        secure = random.random() > 0.6  # Only 40% secure
        http_only = random.random() > 0.9  # Only 10% httpOnly
        same_site = random.choice([None, None, 'Lax'])  # Often missing
        
        # Long-lived
        days = random.choice([365, 730, 90, 180])
        expiry = int((datetime.now() + timedelta(days=days)).timestamp())
        
        # Often wildcard domain
        domain = random.choice(['.example.com', '.analytics.example.com'])
        
        return {
            'name': name,
            'value': self._generate_tracking_value(),
            'domain': domain,
            'path': '/',
            'secure': secure,
            'httpOnly': http_only,
            'sameSite': same_site,
            'expirationDate': expiry,
            'label': 'tracking'
        }
    
    def generate_preference_cookie(self) -> dict:
        """Generate a realistic preference cookie"""
        name = random.choice(self.PREFERENCE_NAMES)
        
        # Preferences don't need high security
        secure = random.random() > 0.5
        http_only = random.random() > 0.8  # Usually not httpOnly
        same_site = random.choice(['Lax', None, 'Strict'])
        
        # Medium to long-lived
        days = random.choice([90, 180, 365])
        expiry = int((datetime.now() + timedelta(days=days)).timestamp())
        
        domain = random.choice(self.DOMAINS)
        if random.random() > 0.5:
            domain = '.' + domain
        
        return {
            'name': name,
            'value': self._generate_preference_value(),
            'domain': domain,
            'path': '/',
            'secure': secure,
            'httpOnly': http_only,
            'sameSite': same_site,
            'expirationDate': expiry,
            'label': 'preference'
        }
    
    def generate_other_cookie(self) -> dict:
        """Generate other/functional cookie"""
        name = random.choice(self.OTHER_NAMES)
        
        # Variable security
        secure = random.random() > 0.5
        http_only = random.random() > 0.5
        same_site = random.choice(['Strict', 'Lax', None])
        
        # Variable expiry
        if random.random() > 0.5:
            expiry = None
        else:
            days = random.choice([1, 7, 30, 90])
            expiry = int((datetime.now() + timedelta(days=days)).timestamp())
        
        domain = random.choice(self.DOMAINS)
        
        return {
            'name': name,
            'value': self._generate_random_value(),
            'domain': domain,
            'path': random.choice(['/', '/api', '/admin']),
            'secure': secure,
            'httpOnly': http_only,
            'sameSite': same_site,
            'expirationDate': expiry,
            'label': 'other'
        }
    
    def _generate_token_value(self) -> str:
        """Generate realistic auth token value"""
        if random.random() > 0.5:
            # JWT-like
            parts = [
                self._random_base64(20),
                self._random_base64(40),
                self._random_base64(30)
            ]
            return '.'.join(parts)
        else:
            # Random hex
            return self._random_hex(32)
    
    def _generate_tracking_value(self) -> str:
        """Generate tracking cookie value"""
        formats = [
            f"GA1.2.{random.randint(100000000, 999999999)}.{int(datetime.now().timestamp())}",
            self._random_hex(16),
            f"v1.{random.randint(10000, 99999)}.{self._random_hex(12)}"
        ]
        return random.choice(formats)
    
    def _generate_preference_value(self) -> str:
        """Generate preference cookie value"""
        values = [
            'en-US', 'es-ES', 'fr-FR', 'dark', 'light',
            'UTC', 'America/New_York', 'USD', 'EUR', 'true', 'false'
        ]
        return random.choice(values)
    
    def _generate_random_value(self) -> str:
        """Generate random cookie value"""
        return self._random_hex(random.choice([8, 16, 24]))
    
    def _random_hex(self, length: int) -> str:
        """Generate random hex string"""
        return ''.join(random.choices('0123456789abcdef', k=length))
    
    def _random_base64(self, length: int) -> str:
        """Generate random base64-like string"""
        chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_'
        return ''.join(random.choices(chars, k=length))
    
    def generate_dataset(self, n_samples: int = 400) -> list:
        """
        Generate balanced training dataset
        
        Args:
            n_samples: Total number of samples
        
        Returns:
            List of labeled cookie dictionaries
        """
        samples_per_class = n_samples // 4
        dataset = []
        
        # Generate each class
        for _ in range(samples_per_class):
            dataset.append(self.generate_auth_cookie())
            dataset.append(self.generate_tracking_cookie())
            dataset.append(self.generate_preference_cookie())
            dataset.append(self.generate_other_cookie())
        
        # Shuffle
        random.shuffle(dataset)
        return dataset


if __name__ == "__main__":
    generator = TrainingDataGenerator()
    
    # Generate dataset
    dataset = generator.generate_dataset(n_samples=400)
    
    # Save to file
    output_path = '/home/claude/cookieguard-ai/data/training_cookies.json'
    with open(output_path, 'w') as f:
        json.dump(dataset, f, indent=2)
    
    print(f"Generated {len(dataset)} training samples")
    print(f"Saved to: {output_path}")
    
    # Show examples
    print("\nExample cookies:")
    for label_type in ['authentication', 'tracking', 'preference', 'other']:
        example = next(c for c in dataset if c['label'] == label_type)
        print(f"\n{label_type.upper()}:")
        print(f"  Name: {example['name']}")
        print(f"  Secure: {example['secure']}, HttpOnly: {example['httpOnly']}")
        print(f"  SameSite: {example.get('sameSite', 'None')}")
