"""
CookieGuard Web Study — Cookie Crawler
Visits each site with a headless Chromium browser, collects cookies,
classifies them, scores risk, and writes results to CSV.
"""

import argparse
import csv
import json
import re
import time
import random
import sys
from pathlib import Path
from datetime import datetime, timezone
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

# ── Paths ──────────────────────────────────────────────────────
BASE      = Path(__file__).parent
SITES_TXT = BASE / "sites.txt"
OUT_CSV      = BASE / "data" / "cookies_raw.csv"
TIMEOUT_CSV  = BASE / "data" / "timeouts.csv"   # sites that returned 0 cookies or errored
SUMMARY_JSON = BASE / "data" / "summary.json"
OUT_CSV.parent.mkdir(exist_ok=True)

# ── Tracker company map (mirrors engine.js) ───────────────────
TRACKER_MAP = {
    'google-analytics.com': 'Google Analytics',
    'analytics.google.com': 'Google Analytics',
    'googletagmanager.com': 'Google',
    'googletagservices.com': 'Google',
    'doubleclick.net': 'Google',
    'googlesyndication.com': 'Google',
    'googleadservices.com': 'Google',
    'google.com': 'Google',
    'gstatic.com': 'Google',
    'googleapis.com': 'Google',
    'facebook.com': 'Meta',
    'facebook.net': 'Meta',
    'connect.facebook.net': 'Meta',
    'fbcdn.net': 'Meta',
    'instagram.com': 'Meta',
    'amazon-adsystem.com': 'Amazon',
    'amazon.com': 'Amazon',
    'images-amazon.com': 'Amazon',
    'bing.com': 'Microsoft',
    'bat.bing.com': 'Microsoft',
    'clarity.ms': 'Microsoft Clarity',
    'microsoft.com': 'Microsoft',
    'tiktok.com': 'TikTok',
    'bytedance.com': 'TikTok',
    'twitter.com': 'X/Twitter',
    'twimg.com': 'X/Twitter',
    'linkedin.com': 'LinkedIn',
    'licdn.com': 'LinkedIn',
    'snapchat.com': 'Snap',
    'hotjar.com': 'Hotjar',
    'mixpanel.com': 'Mixpanel',
    'amplitude.com': 'Amplitude',
    'segment.com': 'Segment',
    'segment.io': 'Segment',
    'fullstory.com': 'FullStory',
    'heap.io': 'Heap',
    'logrocket.com': 'LogRocket',
    'intercom.io': 'Intercom',
    'intercom.com': 'Intercom',
    'criteo.com': 'Criteo',
    'outbrain.com': 'Outbrain',
    'taboola.com': 'Taboola',
    'quantserve.com': 'Quantcast',
    'scorecardresearch.com': 'Comscore',
    'chartbeat.com': 'Chartbeat',
    'optimizely.com': 'Optimizely',
    'pubmatic.com': 'PubMatic',
    'rubiconproject.com': 'Rubicon',
    'openx.com': 'OpenX',
    'adnxs.com': 'Xandr',
    'cloudflareinsights.com': 'Cloudflare',
    'hubspot.com': 'HubSpot',
    'hsforms.com': 'HubSpot',
    'pardot.com': 'Salesforce',
    'marketo.net': 'Marketo',
    'pinterest.com': 'Pinterest',
}

NAME_PATTERNS = [
    (re.compile(r'^_ga($|_)', re.I),      'Google Analytics'),
    (re.compile(r'^_gid$', re.I),          'Google Analytics'),
    (re.compile(r'^_gac_', re.I),          'Google Analytics'),
    (re.compile(r'^_gtm', re.I),           'Google Tag Manager'),
    (re.compile(r'^__utm', re.I),          'Google Analytics'),
    (re.compile(r'^_gcl_', re.I),          'Google Ads'),
    (re.compile(r'^_fbp$', re.I),          'Meta'),
    (re.compile(r'^_fbc$', re.I),          'Meta'),
    (re.compile(r'^fr$', re.I),            'Meta'),
    (re.compile(r'^_clck$', re.I),         'Microsoft Clarity'),
    (re.compile(r'^_clsk$', re.I),         'Microsoft Clarity'),
    (re.compile(r'^MUID$'),                'Microsoft'),
    (re.compile(r'^_ttp$', re.I),          'TikTok'),
    (re.compile(r'^tt_', re.I),            'TikTok'),
    (re.compile(r'^amplitude', re.I),      'Amplitude'),
    (re.compile(r'^mp_', re.I),            'Mixpanel'),
    (re.compile(r'^ajs_', re.I),           'Segment'),
    (re.compile(r'^_hjid$', re.I),         'Hotjar'),
    (re.compile(r'^_hjSession', re.I),     'Hotjar'),
    (re.compile(r'^li_', re.I),            'LinkedIn'),
    (re.compile(r'^bcookie$', re.I),       'LinkedIn'),
    (re.compile(r'^cto_', re.I),           'Criteo'),
    (re.compile(r'^_pk_', re.I),           'Matomo Analytics'),
    (re.compile(r'^intercom-', re.I),      'Intercom'),
    (re.compile(r'^__hstc$', re.I),        'HubSpot'),
    (re.compile(r'^hubspotutk$', re.I),    'HubSpot'),
    (re.compile(r'^__hssc$', re.I),        'HubSpot'),
    (re.compile(r'^_pinterest', re.I),     'Pinterest'),
]

TRACKING_NAME_RE = re.compile(
    r'^(_ga|_gid|_gac|__utm|_fbp|_fbc|amplitude|mixpanel|ajs_|_hjid|_clck|_ttp|mp_|'
    r'_pk_|intercom|hubspot|pardot|marketo|criteo|outbrain|taboola|quantcast|chartbeat)',
    re.I
)

SESSION_PATTERNS = re.compile(
    r'(session|sess|token|auth|login|logged|jwt|csrf|sid|uid|user_id|account|'
    r'access_token|refresh_token|bearer|identity|principal)',
    re.I
)

PREF_PATTERNS = re.compile(
    r'(lang|language|locale|theme|color|timezone|currency|preferences|settings|consent)',
    re.I
)

def detect_tracker_company(domain: str) -> str | None:
    d = domain.lstrip('.').lower()
    for td, company in TRACKER_MAP.items():
        if d == td or d.endswith('.' + td):
            return company
    return None

def classify_cookie(name: str, domain: str, value: str) -> str:
    # Name-pattern tracker detection
    for pattern, _ in NAME_PATTERNS:
        if pattern.search(name):
            return 'tracking'
    if TRACKING_NAME_RE.search(name):
        return 'tracking'
    if detect_tracker_company(domain):
        return 'tracking'
    if SESSION_PATTERNS.search(name):
        return 'authentication'
    if PREF_PATTERNS.search(name):
        return 'preference'
    # Heuristics: high entropy value → likely session
    if len(value) > 20 and re.search(r'[A-Za-z0-9+/=]{20,}', value):
        return 'authentication'
    return 'other'

def score_risk(cookie_type: str, secure: bool, http_only: bool,
               same_site: str, domain: str, expires: float) -> tuple[int, str]:
    if cookie_type != 'authentication':
        return 0, 'info'
    score = 0
    ss = (same_site or '').lower()
    if not secure:
        score += 30
    if not http_only:
        score += 25
    if not ss or ss in ('none', 'no_restriction'):
        score += 15
    if domain.startswith('.'):
        score += 10
    now = datetime.now(timezone.utc).timestamp()
    if expires and expires > 0:
        days = (expires - now) / 86400
        if days > 365:
            score += 15
        elif days > 30:
            score += 8
    if score >= 40:
        return score, 'critical'
    if score >= 25:
        return score, 'high'
    if score >= 10:
        return score, 'medium'
    if score > 0:
        return score, 'low'
    return 0, 'info'

def crawl_site(page, domain: str) -> list[dict]:
    url = f"https://{domain}"
    try:
        page.goto(url, timeout=15000, wait_until='domcontentloaded')
        page.wait_for_timeout(2000)  # let JS cookies set
    except PWTimeout:
        try:
            page.goto(f"http://{domain}", timeout=10000, wait_until='domcontentloaded')
            page.wait_for_timeout(1500)
        except Exception:
            return []
    except Exception:
        return []

    raw_cookies = page.context.cookies()
    results = []
    for c in raw_cookies:
        name     = c.get('name', '')
        cdomain  = c.get('domain', domain)
        value    = c.get('value', '')
        secure   = bool(c.get('secure', False))
        http_only = bool(c.get('httpOnly', False))
        same_site = c.get('sameSite', '') or ''
        expires  = c.get('expires', -1) or -1
        path     = c.get('path', '/')

        ctype    = classify_cookie(name, cdomain, value)
        tracker  = detect_tracker_company(cdomain)
        # name-pattern tracker company
        if not tracker:
            for pattern, company in NAME_PATTERNS:
                if pattern.search(name):
                    tracker = company
                    break

        risk_score, severity = score_risk(ctype, secure, http_only, same_site, cdomain, expires)

        results.append({
            'site':        domain,
            'name':        name,
            'domain':      cdomain,
            'type':        ctype,
            'secure':      secure,
            'http_only':   http_only,
            'same_site':   same_site,
            'expires':     expires,
            'path':        path,
            'risk_score':  risk_score,
            'severity':    severity,
            'tracker_co':  tracker or '',
            'value_len':   len(value),
        })
    return results

# ── Main ───────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description='CookieGuard Web Study Crawler')
    parser.add_argument('--recrawl',          action='store_true',
                        help='Re-crawl ALL sites (ignore existing cookies_raw.csv)')
    parser.add_argument('--recrawl-timeouts', action='store_true',
                        help='Re-crawl only sites that previously timed out or returned 0 cookies')
    args = parser.parse_args()

    all_sites = [s.strip() for s in SITES_TXT.read_text().splitlines() if s.strip()]
    print(f"[CookieGuard Study] {len(all_sites)} sites in list")

    fieldnames = ['site','name','domain','type','secure','http_only','same_site',
                  'expires','path','risk_score','severity','tracker_co','value_len']

    # ── Load already-crawled state ──────────────────────────────
    crawled_ok      = set()   # sites with real cookies
    crawled_timeout = set()   # sites that previously timed out / returned 0 cookies

    if OUT_CSV.exists() and not args.recrawl:
        with open(OUT_CSV) as f:
            for row in csv.DictReader(f):
                if row.get('type') == 'none' or not row.get('name'):
                    crawled_timeout.add(row['site'])
                else:
                    crawled_ok.add(row['site'])

    if TIMEOUT_CSV.exists() and not args.recrawl:
        with open(TIMEOUT_CSV) as f:
            for row in csv.DictReader(f):
                crawled_timeout.add(row['site'])

    # ── Decide which sites to crawl ─────────────────────────────
    skip = set()
    if args.recrawl:
        print("  --recrawl: starting fresh, re-crawling all sites")
        # Wipe both files
        OUT_CSV.unlink(missing_ok=True)
        TIMEOUT_CSV.unlink(missing_ok=True)
    elif args.recrawl_timeouts:
        print(f"  --recrawl-timeouts: re-crawling {len(crawled_timeout)} previously failed sites")
        skip = crawled_ok          # skip only the ones that already have cookies
        # Remove timeout entries from main CSV (will be re-attempted)
        if OUT_CSV.exists():
            rows = []
            with open(OUT_CSV) as f:
                for row in csv.DictReader(f):
                    if row['site'] not in crawled_timeout:
                        rows.append(row)
            with open(OUT_CSV, 'w', newline='') as f:
                w = csv.DictWriter(f, fieldnames=fieldnames)
                w.writeheader(); w.writerows(rows)
        # Wipe timeout file — will be rebuilt
        TIMEOUT_CSV.unlink(missing_ok=True)
    else:
        skip = crawled_ok | crawled_timeout   # default: skip everything already done
        already = len(crawled_ok) + len(crawled_timeout)
        if already:
            print(f"  Resuming — {len(crawled_ok)} with cookies, "
                  f"{len(crawled_timeout)} timeouts already recorded (use --recrawl-timeouts to retry those)")

    sites_to_crawl = [s for s in all_sites if s not in skip]
    print(f"  Crawling {len(sites_to_crawl)} sites now\n")

    if not sites_to_crawl:
        print("Nothing to do. Use --recrawl or --recrawl-timeouts to re-run.")
        return

    visited, timeouts = 0, 0

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=['--no-sandbox','--disable-dev-shm-usage','--disable-gpu']
        )
        ctx = browser.new_context(
            user_agent='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
                       '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 1280, 'height': 800},
            ignore_https_errors=True,
        )
        page = ctx.new_page()

        # Open both output files
        cookie_mode  = 'w' if args.recrawl else 'a'
        timeout_mode = 'w' if (args.recrawl or args.recrawl_timeouts) else 'a'

        with open(OUT_CSV, cookie_mode, newline='') as cookie_f,              open(TIMEOUT_CSV, timeout_mode, newline='') as timeout_f:

            cookie_writer  = csv.DictWriter(cookie_f, fieldnames=fieldnames)
            timeout_writer = csv.DictWriter(timeout_f,
                                            fieldnames=['site','reason','timestamp'])

            if cookie_mode == 'w':
                cookie_writer.writeheader()
            if timeout_mode == 'w':
                timeout_writer.writeheader()

            for i, site in enumerate(sites_to_crawl):
                sys.stdout.write(
                    f"\r[{i+1:4d}/{len(sites_to_crawl)}] {site:<45} "
                    f"ok={visited} timeout={timeouts}"
                )
                sys.stdout.flush()

                cookies = crawl_site(page, site)

                if cookies:
                    cookie_writer.writerows(cookies)
                    cookie_f.flush()
                    visited += 1
                else:
                    # Write to separate timeouts file — NOT mixed into cookies CSV
                    timeout_writer.writerow({
                        'site':      site,
                        'reason':    'no_cookies_or_timeout',
                        'timestamp': datetime.now(timezone.utc).isoformat(),
                    })
                    timeout_f.flush()
                    timeouts += 1

                ctx.clear_cookies()
                time.sleep(random.uniform(0.3, 0.8))

        browser.close()

    total_ok      = len(crawled_ok) + visited
    total_timeout = len(crawled_timeout - (crawled_ok)) + timeouts
    print(f"\n\n── Run complete ──────────────────────────────────────────")
    print(f"  This run:   {visited} with cookies, {timeouts} timeouts")
    print(f"  All-time:   {total_ok} with cookies, {total_timeout} timeouts")
    print(f"  cookies_raw.csv  → {OUT_CSV}")
    print(f"  timeouts.csv     → {TIMEOUT_CSV}")

if __name__ == '__main__':
    main()