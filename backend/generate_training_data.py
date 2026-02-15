"""
CookieGuard AI 2.0 - Training Data Generator
Now includes behavior features (login-diff signals) with realistic correlations.
"""

import json
import random
import hashlib
from datetime import datetime, timedelta


class TrainingDataGenerator:
    """Generate labeled cookie data with behavior features for training"""

    # Authentication cookie patterns
    AUTH_NAMES = [
        'session_id', 'JSESSIONID', 'PHPSESSID', 'ASP.NET_SessionId',
        'auth_token', 'authentication', 'login_token', 'access_token',
        'laravel_session', 'connect.sid', 'wordpress_logged_in',
        'sid', 'sessionid', 'user_session', 'jwt_token', 'bearer_token',
        '__Host-session', '__Secure-auth', 'id', 'token', 'sess',
        'remember_me', 'persistent_login', 'sso_token', 'refresh_token',
        'csrf_session', 'xsrf_token_session'
    ]

    TRACKING_NAMES = [
        '_ga', '_gid', '_gat', '__utma', '__utmb', '__utmc', '__utmz',
        'fbp', '_fbp', 'fr', 'datr', 'DoubleClickId', 'IDE',
        'amplitude_id', 'mp_mixpanel', 'intercom-session',
        'analytics_token', 'visitor_id', 'tracking_id',
        '_clck', '_clsk', 'hubspotutk', 'ajs_anonymous_id',
        '__gads', 'NID', '1P_JAR', 'APISID'
    ]

    PREFERENCE_NAMES = [
        'language', 'lang', 'locale', 'timezone', 'tz',
        'theme', 'dark_mode', 'currency', 'region',
        'cookie_consent', 'gdpr_consent', 'preferences',
        'settings', 'layout_preference', 'font_size',
        'accessibility', 'country', 'ui_mode', 'compact_view'
    ]

    OTHER_NAMES = [
        'csrf_token', 'cache_id', 'ab_test_variant',
        'load_balancer', 'debug_mode', 'feature_flag',
        'temp_id', 'referrer', 'utm_source', 'nonce',
        'request_id', 'trace_id', 'build_hash', 'cdn_pop',
        'rate_limit_bucket', 'geo_resolved'
    ]

    SITES = [
        {'site_id': 'site_banking', 'domains': ['secure.bank.com', 'api.bank.com', '.bank.com']},
        {'site_id': 'site_ecommerce', 'domains': ['shop.example.com', '.example.com', 'checkout.example.com']},
        {'site_id': 'site_social', 'domains': ['www.social.net', '.social.net', 'api.social.net']},
        {'site_id': 'site_news', 'domains': ['news.media.org', '.media.org', 'cdn.media.org']},
        {'site_id': 'site_saas', 'domains': ['app.saas.io', '.saas.io', 'auth.saas.io']},
        {'site_id': 'site_healthcare', 'domains': ['portal.health.com', '.health.com', 'api.health.com']},
        {'site_id': 'site_edu', 'domains': ['learn.edu.org', '.edu.org', 'sso.edu.org']},
        {'site_id': 'site_gaming', 'domains': ['play.game.gg', '.game.gg', 'api.game.gg']},
    ]

    def _pick_site(self):
        return random.choice(self.SITES)

    def generate_auth_cookie(self) -> dict:
        """Generate a realistic authentication cookie with behavior signals"""
        site = self._pick_site()
        name = random.choice(self.AUTH_NAMES)

        secure = random.random() > 0.1
        http_only = random.random() > 0.3
        same_site = random.choice(['Strict', 'Lax', 'Lax', None])

        if random.random() > 0.4:
            expiry = None
        else:
            days = random.choice([7, 14, 30])
            expiry = int((datetime.now() + timedelta(days=days)).timestamp())

        domain = random.choice(site['domains'])

        # --- BEHAVIOR FEATURES (auth cookies strongly correlate with login) ---
        changed_during_login = 1 if random.random() < 0.85 else 0
        new_after_login = 1 if random.random() < 0.80 else 0
        rotated_after_login = 1 if random.random() < 0.75 else 0

        # Third-party: auth cookies are almost always first-party
        third_party = 1 if random.random() < 0.05 else 0

        return {
            'name': name,
            'value': self._generate_token_value(),
            'domain': domain,
            'path': '/',
            'secure': secure,
            'httpOnly': http_only,
            'sameSite': same_site,
            'expirationDate': expiry,
            'hostOnly': not domain.startswith('.'),
            'site_id': site['site_id'],
            # Behavior features
            'changed_during_login': changed_during_login,
            'new_after_login': new_after_login,
            'rotated_after_login': rotated_after_login,
            'third_party': third_party,
            'label': 'authentication'
        }

    def generate_tracking_cookie(self) -> dict:
        """Generate a realistic tracking cookie with behavior signals"""
        site = self._pick_site()
        name = random.choice(self.TRACKING_NAMES)

        secure = random.random() > 0.6
        http_only = random.random() > 0.9
        same_site = random.choice([None, None, 'Lax'])

        days = random.choice([365, 730, 90, 180])
        expiry = int((datetime.now() + timedelta(days=days)).timestamp())

        domain = random.choice([site['domains'][-1], '.analytics.tracker.com'])

        # Tracking cookies rarely change at login
        changed_during_login = 1 if random.random() < 0.10 else 0
        new_after_login = 1 if random.random() < 0.08 else 0
        rotated_after_login = 1 if random.random() < 0.05 else 0

        # Tracking cookies are often third-party
        third_party = 1 if random.random() < 0.65 else 0

        return {
            'name': name,
            'value': self._generate_tracking_value(),
            'domain': domain,
            'path': '/',
            'secure': secure,
            'httpOnly': http_only,
            'sameSite': same_site,
            'expirationDate': expiry,
            'hostOnly': not domain.startswith('.'),
            'site_id': site['site_id'],
            'changed_during_login': changed_during_login,
            'new_after_login': new_after_login,
            'rotated_after_login': rotated_after_login,
            'third_party': third_party,
            'label': 'tracking'
        }

    def generate_preference_cookie(self) -> dict:
        """Generate a realistic preference cookie with behavior signals"""
        site = self._pick_site()
        name = random.choice(self.PREFERENCE_NAMES)

        secure = random.random() > 0.5
        http_only = random.random() > 0.8
        same_site = random.choice(['Lax', None, 'Strict'])

        days = random.choice([90, 180, 365])
        expiry = int((datetime.now() + timedelta(days=days)).timestamp())

        domain = random.choice(site['domains'])
        if random.random() > 0.5:
            domain = site['domains'][-1]  # wildcard

        # Preferences rarely change at login
        changed_during_login = 1 if random.random() < 0.15 else 0
        new_after_login = 1 if random.random() < 0.10 else 0
        rotated_after_login = 1 if random.random() < 0.05 else 0
        third_party = 1 if random.random() < 0.10 else 0

        return {
            'name': name,
            'value': self._generate_preference_value(),
            'domain': domain,
            'path': '/',
            'secure': secure,
            'httpOnly': http_only,
            'sameSite': same_site,
            'expirationDate': expiry,
            'hostOnly': not domain.startswith('.'),
            'site_id': site['site_id'],
            'changed_during_login': changed_during_login,
            'new_after_login': new_after_login,
            'rotated_after_login': rotated_after_login,
            'third_party': third_party,
            'label': 'preference'
        }

    def generate_other_cookie(self) -> dict:
        """Generate other/functional cookie with behavior signals"""
        site = self._pick_site()
        name = random.choice(self.OTHER_NAMES)

        secure = random.random() > 0.5
        http_only = random.random() > 0.5
        same_site = random.choice(['Strict', 'Lax', None])

        if random.random() > 0.5:
            expiry = None
        else:
            days = random.choice([1, 7, 30, 90])
            expiry = int((datetime.now() + timedelta(days=days)).timestamp())

        domain = random.choice(site['domains'][:2])

        # Some functional cookies (like CSRF) do change at login
        changed_during_login = 1 if random.random() < 0.30 else 0
        new_after_login = 1 if random.random() < 0.20 else 0
        rotated_after_login = 1 if random.random() < 0.25 else 0
        third_party = 1 if random.random() < 0.15 else 0

        return {
            'name': name,
            'value': self._generate_random_value(),
            'domain': domain,
            'path': random.choice(['/', '/api', '/admin']),
            'secure': secure,
            'httpOnly': http_only,
            'sameSite': same_site,
            'expirationDate': expiry,
            'hostOnly': not domain.startswith('.'),
            'site_id': site['site_id'],
            'changed_during_login': changed_during_login,
            'new_after_login': new_after_login,
            'rotated_after_login': rotated_after_login,
            'third_party': third_party,
            'label': 'other'
        }

    def _generate_token_value(self) -> str:
        if random.random() > 0.5:
            parts = [self._random_base64(20), self._random_base64(40), self._random_base64(30)]
            return '.'.join(parts)
        else:
            return self._random_hex(32)

    def _generate_tracking_value(self) -> str:
        formats = [
            f"GA1.2.{random.randint(100000000, 999999999)}.{int(datetime.now().timestamp())}",
            self._random_hex(16),
            f"v1.{random.randint(10000, 99999)}.{self._random_hex(12)}"
        ]
        return random.choice(formats)

    def _generate_preference_value(self) -> str:
        values = ['en-US', 'es-ES', 'fr-FR', 'dark', 'light',
                  'UTC', 'America/New_York', 'USD', 'EUR', 'true', 'false']
        return random.choice(values)

    def _generate_random_value(self) -> str:
        return self._random_hex(random.choice([8, 16, 24]))

    def _random_hex(self, length: int) -> str:
        return ''.join(random.choices('0123456789abcdef', k=length))

    def _random_base64(self, length: int) -> str:
        chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_'
        return ''.join(random.choices(chars, k=length))

    def generate_dataset(self, n_samples: int = 800) -> list:
        samples_per_class = n_samples // 4
        dataset = []
        for _ in range(samples_per_class):
            dataset.append(self.generate_auth_cookie())
            dataset.append(self.generate_tracking_cookie())
            dataset.append(self.generate_preference_cookie())
            dataset.append(self.generate_other_cookie())
        random.shuffle(dataset)
        return dataset


if __name__ == "__main__":
    generator = TrainingDataGenerator()
    dataset = generator.generate_dataset(n_samples=800)

    output_path = '/Users/zhenl/Projects/git/cookieguard-ai/data/training_cookies.json'
    with open(output_path, 'w') as f:
        json.dump(dataset, f, indent=2)

    print(f"Generated {len(dataset)} training samples")
    print(f"Saved to: {output_path}")

    # Show distribution of behavior features by label
    for label in ['authentication', 'tracking', 'preference', 'other']:
        subset = [c for c in dataset if c['label'] == label]
        avg_changed = sum(c['changed_during_login'] for c in subset) / len(subset)
        avg_new = sum(c['new_after_login'] for c in subset) / len(subset)
        avg_rotated = sum(c['rotated_after_login'] for c in subset) / len(subset)
        avg_3p = sum(c['third_party'] for c in subset) / len(subset)
        print(f"\n{label.upper()} (n={len(subset)}):")
        print(f"  changed_during_login: {avg_changed:.0%}")
        print(f"  new_after_login:      {avg_new:.0%}")
        print(f"  rotated_after_login:  {avg_rotated:.0%}")
        print(f"  third_party:          {avg_3p:.0%}")
