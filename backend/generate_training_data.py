"""
CookieGuard AI 2.0 - Training Data Generator (Hardened)
Generates 5000+ samples with:
  - 22 simulated sites across diverse verticals
  - Ambiguous/borderline cookies that challenge the classifier
  - Vendor-specific naming that doesn't follow obvious patterns
  - Noise in behavior features (auth cookies that DON'T change at login, etc.)
  - Realistic security misconfigurations
"""

import json
import random
import hashlib
from datetime import datetime, timedelta


class TrainingDataGenerator:
    """Generate labeled cookie data with behavior features for training"""

    # ─── Authentication cookie patterns ──────────────────────
    AUTH_NAMES_OBVIOUS = [
        'session_id', 'JSESSIONID', 'PHPSESSID', 'ASP.NET_SessionId',
        'auth_token', 'login_token', 'access_token', 'jwt_token',
        'laravel_session', 'connect.sid', 'wordpress_logged_in',
        'sid', 'sessionid', 'user_session', 'bearer_token',
        '__Host-session', '__Secure-auth', 'sso_token', 'refresh_token',
    ]

    # Auth cookies with non-obvious names
    AUTH_NAMES_AMBIGUOUS = [
        'id', 'token', 'sess', 'remember_me', 'persistent_login',
        '_t', 'li_at', 'c_user', 'xs',
        'SID', 'HSID', 'SSID', 'APISID', 'SAPISID',
        '_gh_sess', 'dotcom_user',
        '_twitter_sess', 'twid',
        'AWSALB', 'AWSALBCORS',
        'rack.session', '_myapp_session', 'express:sess',
        'ci_session', 'PLAY_SESSION', '_session_id',
        'sc_anonymous_id', 'mp_userid', 'device_id',
    ]

    # ─── Tracking cookie patterns ────────────────────────────
    TRACKING_NAMES_OBVIOUS = [
        '_ga', '_gid', '_gat', '__utma', '__utmb', '__utmc', '__utmz',
        '_fbp', 'fr', 'DoubleClickId', 'IDE',
        'amplitude_id', 'mp_mixpanel', 'analytics_token',
        'tracking_id', '_clck', '_clsk', 'hubspotutk',
        'ajs_anonymous_id', '__gads', 'NID', '1P_JAR',
    ]

    TRACKING_NAMES_AMBIGUOUS = [
        'visitor_id', '_vis', 'uid', '_uuid', 'cid',
        'client_id', '_gcl_au', '_dc_gtm_UA', '_hjid',
        'intercom-id', 'intercom-session',
        'optimizelyEndUserId', '_mkto_trk',
        'ki_t', 'ki_r',
        '__cf_bm',
        '_derived_epik',
        'guest_id', 'guest_id_ads',
        'YSC', 'VISITOR_INFO1_LIVE',
        '_uetsid', '_uetvid',
        'personalization_id',
    ]

    # ─── Preference cookie patterns ──────────────────────────
    PREFERENCE_NAMES = [
        'language', 'lang', 'locale', 'timezone', 'tz',
        'theme', 'dark_mode', 'currency', 'region',
        'cookie_consent', 'gdpr_consent', 'preferences',
        'settings', 'layout_preference', 'font_size',
        'accessibility', 'country', 'ui_mode', 'compact_view',
        'cookieyes-consent', 'CookieConsent', 'euconsent-v2',
        'OptanonConsent', 'OptanonAlertBoxClosed',
        'nf_lang', 'wp_lang', 'PREF', 'i18n_lang',
    ]

    # ─── Other/functional cookies ────────────────────────────
    OTHER_NAMES = [
        'csrf_token', 'cache_id', 'ab_test_variant',
        'load_balancer', 'debug_mode', 'feature_flag',
        'temp_id', 'referrer', 'utm_source', 'nonce',
        'request_id', 'trace_id', 'build_hash', 'cdn_pop',
        'rate_limit_bucket', 'geo_resolved',
        'cf_clearance',
        'XSRF-TOKEN', '_csrf', '__RequestVerificationToken',
        'ARRAffinity', 'ARRAffinitySameSite',
        'BIGipServer', 'TS01',
        'incap_ses', 'visid_incap',
        'bm_sv', 'bm_sz',
        '_dd_s', 'newrelic', 'akamai_generated',
    ]

    # ─── 22 sites across diverse verticals ───────────────────
    SITES = [
        {'site_id': 'bank_chase', 'domains': ['secure.chase.com', '.chase.com', 'auth.chase.com']},
        {'site_id': 'bank_bofa', 'domains': ['www.bankofamerica.com', '.bankofamerica.com', 'secure.bankofamerica.com']},
        {'site_id': 'ecom_amazon', 'domains': ['www.amazon.com', '.amazon.com', 'api.amazon.com']},
        {'site_id': 'ecom_shopify', 'domains': ['mystore.myshopify.com', '.myshopify.com', 'checkout.shopify.com']},
        {'site_id': 'social_facebook', 'domains': ['www.facebook.com', '.facebook.com', 'api.facebook.com']},
        {'site_id': 'social_twitter', 'domains': ['twitter.com', '.twitter.com', 'api.twitter.com']},
        {'site_id': 'social_reddit', 'domains': ['www.reddit.com', '.reddit.com', 'oauth.reddit.com']},
        {'site_id': 'news_nyt', 'domains': ['www.nytimes.com', '.nytimes.com', 'myaccount.nytimes.com']},
        {'site_id': 'news_bbc', 'domains': ['www.bbc.com', '.bbc.com', 'account.bbc.com']},
        {'site_id': 'saas_github', 'domains': ['github.com', '.github.com', 'api.github.com']},
        {'site_id': 'saas_slack', 'domains': ['app.slack.com', '.slack.com', 'api.slack.com']},
        {'site_id': 'saas_notion', 'domains': ['www.notion.so', '.notion.so', 'api.notion.so']},
        {'site_id': 'health_portal', 'domains': ['portal.myhealth.org', '.myhealth.org', 'api.myhealth.org']},
        {'site_id': 'health_epic', 'domains': ['mychart.epic.com', '.epic.com', 'auth.epic.com']},
        {'site_id': 'edu_canvas', 'domains': ['school.instructure.com', '.instructure.com', 'api.instructure.com']},
        {'site_id': 'edu_coursera', 'domains': ['www.coursera.org', '.coursera.org', 'api.coursera.org']},
        {'site_id': 'gaming_steam', 'domains': ['store.steampowered.com', '.steampowered.com', 'login.steampowered.com']},
        {'site_id': 'gaming_epic', 'domains': ['www.epicgames.com', '.epicgames.com', 'account.epicgames.com']},
        {'site_id': 'gov_portal', 'domains': ['login.gov', '.login.gov', 'secure.login.gov']},
        {'site_id': 'travel_airline', 'domains': ['www.united.com', '.united.com', 'booking.united.com']},
        {'site_id': 'media_spotify', 'domains': ['open.spotify.com', '.spotify.com', 'accounts.spotify.com']},
        {'site_id': 'media_netflix', 'domains': ['www.netflix.com', '.netflix.com', 'api.netflix.com']},
    ]

    def _pick_site(self):
        return random.choice(self.SITES)

    def generate_auth_cookie(self, difficulty='normal') -> dict:
        site = self._pick_site()
        if difficulty == 'hard':
            name = random.choice(self.AUTH_NAMES_AMBIGUOUS)
        else:
            pool = self.AUTH_NAMES_OBVIOUS + self.AUTH_NAMES_AMBIGUOUS
            weights = [3] * len(self.AUTH_NAMES_OBVIOUS) + [1] * len(self.AUTH_NAMES_AMBIGUOUS)
            name = random.choices(pool, weights=weights, k=1)[0]

        if difficulty == 'hard':
            secure = random.random() > 0.4
            http_only = random.random() > 0.5
            same_site = random.choice([None, None, 'Lax', None])
        else:
            secure = random.random() > 0.1
            http_only = random.random() > 0.3
            same_site = random.choice(['Strict', 'Lax', 'Lax', None])

        if random.random() > 0.4:
            expiry = None
        else:
            days = random.choice([1, 7, 14, 30, 60, 90, 180, 365])
            expiry = int((datetime.now() + timedelta(days=days)).timestamp())

        domain = random.choice(site['domains'])

        if difficulty == 'hard':
            changed_during_login = 1 if random.random() < 0.55 else 0
            new_after_login = 1 if random.random() < 0.50 else 0
            rotated_after_login = 1 if random.random() < 0.45 else 0
        else:
            changed_during_login = 1 if random.random() < 0.82 else 0
            new_after_login = 1 if random.random() < 0.75 else 0
            rotated_after_login = 1 if random.random() < 0.70 else 0

        third_party = 1 if random.random() < 0.05 else 0

        if name in ('remember_me', 'persistent_login', 'device_id'):
            value = random.choice(['true', '1', self._random_hex(8)])
        else:
            value = self._generate_token_value()

        return {
            'name': name, 'value': value, 'domain': domain, 'path': '/',
            'secure': secure, 'httpOnly': http_only, 'sameSite': same_site,
            'expirationDate': expiry, 'hostOnly': not domain.startswith('.'),
            'site_id': site['site_id'],
            'changed_during_login': changed_during_login,
            'new_after_login': new_after_login,
            'rotated_after_login': rotated_after_login,
            'third_party': third_party, 'label': 'authentication'
        }

    def generate_tracking_cookie(self, difficulty='normal') -> dict:
        site = self._pick_site()
        if difficulty == 'hard':
            name = random.choice(self.TRACKING_NAMES_AMBIGUOUS)
        else:
            pool = self.TRACKING_NAMES_OBVIOUS + self.TRACKING_NAMES_AMBIGUOUS
            weights = [3] * len(self.TRACKING_NAMES_OBVIOUS) + [1] * len(self.TRACKING_NAMES_AMBIGUOUS)
            name = random.choices(pool, weights=weights, k=1)[0]

        secure = random.random() > 0.6
        http_only = random.random() > 0.9
        same_site = random.choice([None, None, 'Lax', None, 'None'])

        days = random.choice([30, 90, 180, 365, 730])
        expiry = int((datetime.now() + timedelta(days=days)).timestamp())

        if random.random() < 0.5:
            domain = random.choice(site['domains'])
        else:
            domain = random.choice([
                '.analytics.tracker.com', '.doubleclick.net', '.facebook.com',
                '.google-analytics.com', '.hotjar.com', '.clarity.ms', '.segment.io',
            ])

        if difficulty == 'hard':
            changed_during_login = 1 if random.random() < 0.25 else 0
            new_after_login = 1 if random.random() < 0.20 else 0
            rotated_after_login = 1 if random.random() < 0.15 else 0
        else:
            changed_during_login = 1 if random.random() < 0.10 else 0
            new_after_login = 1 if random.random() < 0.08 else 0
            rotated_after_login = 1 if random.random() < 0.05 else 0

        third_party = 1 if random.random() < 0.65 else 0

        if difficulty == 'hard' and random.random() < 0.3:
            value = self._generate_token_value()
        else:
            value = self._generate_tracking_value()

        return {
            'name': name, 'value': value, 'domain': domain, 'path': '/',
            'secure': secure, 'httpOnly': http_only, 'sameSite': same_site,
            'expirationDate': expiry, 'hostOnly': not domain.startswith('.'),
            'site_id': site['site_id'],
            'changed_during_login': changed_during_login,
            'new_after_login': new_after_login,
            'rotated_after_login': rotated_after_login,
            'third_party': third_party, 'label': 'tracking'
        }

    def generate_preference_cookie(self, difficulty='normal') -> dict:
        site = self._pick_site()
        name = random.choice(self.PREFERENCE_NAMES)
        secure = random.random() > 0.5
        http_only = random.random() > 0.8
        same_site = random.choice(['Lax', None, 'Strict'])
        days = random.choice([30, 90, 180, 365])
        expiry = int((datetime.now() + timedelta(days=days)).timestamp())
        domain = random.choice(site['domains'])

        changed_during_login = 1 if random.random() < 0.15 else 0
        new_after_login = 1 if random.random() < 0.10 else 0
        rotated_after_login = 1 if random.random() < 0.05 else 0
        third_party = 1 if random.random() < 0.10 else 0

        if 'consent' in name.lower() or 'optanon' in name.lower():
            value = self._random_base64(random.randint(40, 120))
        else:
            value = self._generate_preference_value()

        return {
            'name': name, 'value': value, 'domain': domain, 'path': '/',
            'secure': secure, 'httpOnly': http_only, 'sameSite': same_site,
            'expirationDate': expiry, 'hostOnly': not domain.startswith('.'),
            'site_id': site['site_id'],
            'changed_during_login': changed_during_login,
            'new_after_login': new_after_login,
            'rotated_after_login': rotated_after_login,
            'third_party': third_party, 'label': 'preference'
        }

    def generate_other_cookie(self, difficulty='normal') -> dict:
        site = self._pick_site()
        name = random.choice(self.OTHER_NAMES)
        secure = random.random() > 0.5
        http_only = random.random() > 0.5
        same_site = random.choice(['Strict', 'Lax', None])

        if random.random() > 0.5:
            expiry = None
        else:
            days = random.choice([0, 1, 7, 30, 90])
            expiry = int((datetime.now() + timedelta(days=days)).timestamp())

        domain = random.choice(site['domains'][:2])

        is_csrf_like = 'csrf' in name.lower() or 'xsrf' in name.lower()
        if is_csrf_like:
            changed_during_login = 1 if random.random() < 0.70 else 0
            new_after_login = 1 if random.random() < 0.50 else 0
            rotated_after_login = 1 if random.random() < 0.60 else 0
        else:
            changed_during_login = 1 if random.random() < 0.20 else 0
            new_after_login = 1 if random.random() < 0.15 else 0
            rotated_after_login = 1 if random.random() < 0.15 else 0

        third_party = 1 if random.random() < 0.15 else 0

        if is_csrf_like or name in ('nonce', 'request_id'):
            value = self._generate_token_value()
        else:
            value = self._generate_random_value()

        return {
            'name': name, 'value': value, 'domain': domain,
            'path': random.choice(['/', '/api', '/admin', '/app']),
            'secure': secure, 'httpOnly': http_only, 'sameSite': same_site,
            'expirationDate': expiry, 'hostOnly': not domain.startswith('.'),
            'site_id': site['site_id'],
            'changed_during_login': changed_during_login,
            'new_after_login': new_after_login,
            'rotated_after_login': rotated_after_login,
            'third_party': third_party, 'label': 'other'
        }

    # ─── Value generators ────────────────────────────────────

    def _generate_token_value(self) -> str:
        r = random.random()
        if r < 0.35:
            parts = [self._random_base64(20), self._random_base64(40), self._random_base64(30)]
            return '.'.join(parts)
        elif r < 0.65:
            return self._random_hex(random.choice([16, 24, 32, 40, 64]))
        elif r < 0.85:
            return self._random_base64(random.choice([20, 32, 44, 64]))
        else:
            h = self._random_hex(32)
            return f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:]}"

    def _generate_tracking_value(self) -> str:
        formats = [
            f"GA1.2.{random.randint(100000000, 999999999)}.{int(datetime.now().timestamp())}",
            f"GA1.3.{random.randint(100000000, 999999999)}.{int(datetime.now().timestamp())}",
            self._random_hex(16),
            f"v1.{random.randint(10000, 99999)}.{self._random_hex(12)}",
            f"amp-{self._random_base64(22)}",
            f"{random.randint(1000000, 9999999)}.{random.randint(1000000, 9999999)}",
            f"fb.1.{int(datetime.now().timestamp())}.{random.randint(100000000, 999999999)}",
        ]
        return random.choice(formats)

    def _generate_preference_value(self) -> str:
        values = [
            'en-US', 'es-ES', 'fr-FR', 'de-DE', 'ja-JP', 'zh-CN', 'ko-KR',
            'dark', 'light', 'auto', 'system',
            'UTC', 'America/New_York', 'Europe/London', 'Asia/Tokyo',
            'USD', 'EUR', 'GBP', 'JPY',
            'true', 'false', '1', '0',
            'compact', 'comfortable', 'default',
        ]
        return random.choice(values)

    def _generate_random_value(self) -> str:
        return self._random_hex(random.choice([4, 8, 12, 16, 24]))

    def _random_hex(self, length: int) -> str:
        return ''.join(random.choices('0123456789abcdef', k=length))

    def _random_base64(self, length: int) -> str:
        chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_'
        return ''.join(random.choices(chars, k=length))

    def generate_dataset(self, n_samples: int = 5000) -> list:
        """
        Generate dataset with mixed difficulty.
        ~60% normal (clean signals), ~40% hard (ambiguous/noisy).
        """
        samples_per_class = n_samples // 4
        dataset = []
        for _ in range(samples_per_class):
            diff = 'hard' if random.random() < 0.40 else 'normal'
            dataset.append(self.generate_auth_cookie(difficulty=diff))
            diff = 'hard' if random.random() < 0.40 else 'normal'
            dataset.append(self.generate_tracking_cookie(difficulty=diff))
            dataset.append(self.generate_preference_cookie())
            diff = 'hard' if random.random() < 0.40 else 'normal'
            dataset.append(self.generate_other_cookie(difficulty=diff))
        random.shuffle(dataset)
        return dataset


if __name__ == "__main__":
    random.seed(42)
    generator = TrainingDataGenerator()
    dataset = generator.generate_dataset(n_samples=5000)

    output_path = '/home/claude/cookieguard-ai/data/training_cookies.json'
    import os; os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(dataset, f, indent=2)

    print(f"Generated {len(dataset)} training samples")
    print(f"Sites: {len(set(c['site_id'] for c in dataset))}")

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
