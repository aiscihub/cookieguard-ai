"""
CookieGuard Web Study — Analysis & Charts
Reads cookies_raw.csv and produces:
  - summary statistics JSON
  - 6 publication-quality charts
  - markdown + HTML report (Cloudflare/Mozilla executive style)
"""

import csv
import json
from collections import defaultdict, Counter
from pathlib import Path
import math

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

BASE    = Path(__file__).parent
CSV     = BASE / "data" / "cookies_raw.csv"
CHARTS  = BASE / "charts"
REPORT  = BASE / "report"
CHARTS.mkdir(exist_ok=True)
REPORT.mkdir(exist_ok=True)

# ── Colour palette ────────────────────────────────────────────
C = {
    'risk':   '#dc2626',
    'warn':   '#ca8a04',
    'safe':   '#16a34a',
    'info':   '#3b82f6',
    'ink':    '#0f172a',
    'ink2':   '#64748b',
    'bg':     '#f8fafc',
    'surf':   '#ffffff',
    'border': '#e2e8f0',
}
SEVERITY_COLORS = {
    'critical': '#dc2626',
    'high':     '#ea580c',
    'medium':   '#ca8a04',
    'low':      '#16a34a',
    'info':     '#94a3b8',
}
TYPE_COLORS = {
    'authentication': '#4f46e5',
    'tracking':       '#dc2626',
    'preference':     '#0891b2',
    'other':          '#94a3b8',
}

plt.rcParams.update({
    'font.family': 'DejaVu Sans',
    'axes.spines.top': False,
    'axes.spines.right': False,
    'axes.facecolor': C['bg'],
    'figure.facecolor': C['surf'],
    'axes.grid': True,
    'grid.alpha': 0.4,
    'grid.color': C['border'],
    'axes.titlesize': 13,
    'axes.titleweight': 'bold',
    'axes.labelsize': 11,
})

# ── Load data ─────────────────────────────────────────────────
TIMEOUT_CSV = BASE / "data" / "timeouts.csv"

def load():
    """Load cookie rows and timeout site list separately."""
    rows = []
    with open(CSV) as f:
        for row in csv.DictReader(f):
            # Skip legacy sentinel rows (old crawler format)
            if not row.get('name') or row.get('type') == 'none':
                continue
            row['secure']     = row['secure'] == 'True'
            row['http_only']  = row['http_only'] == 'True'
            row['risk_score'] = int(row['risk_score'] or 0)
            try:
                row['expires'] = float(row['expires'])
            except Exception:
                row['expires'] = -1
            rows.append(row)

    # Load timeout sites from separate file (new crawler format)
    timeout_sites = set()
    if TIMEOUT_CSV.exists():
        with open(TIMEOUT_CSV) as f:
            for row in csv.DictReader(f):
                if row.get('site'):
                    timeout_sites.add(row['site'])

    return rows, timeout_sites

# ── Aggregate stats ───────────────────────────────────────────
def compute_stats(rows, timeout_sites=None):
    """
    rows          — real cookie rows only (no sentinels)
    timeout_sites — set of domains from timeouts.csv (0-cookie / failed)
    """
    timeout_sites = timeout_sites or set()

    # True site count from sites.txt
    sites_txt = BASE / "sites.txt"
    all_sites_listed = len([l for l in sites_txt.read_text().splitlines() if l.strip()]) \
        if sites_txt.exists() else None

    cookie_sites   = set(r['site'] for r in rows)
    all_sites_seen = cookie_sites | timeout_sites

    N              = all_sites_listed or len(all_sites_seen)
    N_with_cookies = len(cookie_sites)
    N_zero         = len(timeout_sites - cookie_sites)   # timed out AND no cookies at all

    by_site = defaultdict(list)
    for r in rows:
        by_site[r['site']].append(r)

    real_rows = rows   # already clean — no sentinels
    sites = list(by_site.keys())

    # per-site metrics (only sites that had cookies)
    cookies_per_site   = [len(v) for v in by_site.values()]
    auth_per_site      = [sum(1 for c in v if c['type']=='authentication') for v in by_site.values()]
    tracking_per_site  = [sum(1 for c in v if c['type']=='tracking') for v in by_site.values()]
    risk_per_site      = [sum(1 for c in v if c['severity'] in ('critical','high')) for v in by_site.values()]

    sites_with_auth     = sum(1 for x in auth_per_site if x > 0)
    sites_with_risk     = sum(1 for x in risk_per_site if x > 0)
    sites_with_tracking = sum(1 for v in by_site.values()
                              if any(c['type']=='tracking' or c['tracker_co'] for c in v))

    tracker_counts = Counter()
    for r in real_rows:
        if r['tracker_co']:
            tracker_counts[r['tracker_co']] += 1

    companies_per_site = []
    for v in by_site.values():
        cos = set(c['tracker_co'] for c in v if c['tracker_co'])
        companies_per_site.append(len(cos))

    auth_cookies = [r for r in real_rows if r['type']=='authentication']
    A = len(auth_cookies) or 1
    pct_secure   = sum(1 for c in auth_cookies if c['secure'])    / A * 100
    pct_httponly = sum(1 for c in auth_cookies if c['http_only']) / A * 100
    ss_vals = Counter(c['same_site'].lower() or 'unset' for c in auth_cookies)

    sev_counts  = Counter(r['severity'] for r in real_rows)
    type_counts = Counter(r['type'] for r in real_rows)

    worst = sorted(
        [(site, sum(1 for c in v if c['severity'] in ('critical','high')),
          sum(1 for c in v if c['type']=='tracking' or c['tracker_co']))
         for site, v in by_site.items()],
        key=lambda x: x[1], reverse=True
    )[:10]

    Nc = N_with_cookies or 1  # denominator for per-site averages

    return {
        'total_sites':             N,
        'sites_with_cookies':      N_with_cookies,
        'sites_zero_cookies':      N_zero,
        'total_cookies':           len(real_rows),
        'avg_cookies_per_site':    round(sum(cookies_per_site)/Nc, 1),
        'avg_auth_per_site':       round(sum(auth_per_site)/Nc, 1),
        'avg_tracking_per_site':   round(sum(tracking_per_site)/Nc, 1),
        'avg_companies_per_site':  round(sum(companies_per_site)/Nc, 1),
        'sites_with_cookies_pct':  round(N_with_cookies/N*100, 1),
        'sites_zero_cookies_pct':  round(N_zero/N*100, 1),
        'sites_with_auth_pct':     round(sites_with_auth/N*100, 1),
        'sites_with_risk_pct':     round(sites_with_risk/N*100, 1),
        'sites_with_tracking_pct': round(sites_with_tracking/N*100, 1),
        'auth_secure_pct':         round(pct_secure, 1),
        'auth_httponly_pct':       round(pct_httponly, 1),
        'samesite_dist':           dict(ss_vals.most_common()),
        'severity_dist':           dict(sev_counts),
        'type_dist':               dict(type_counts),
        'top_trackers':            dict(tracker_counts.most_common(15)),
        'worst_sites':             worst,
        'cookies_per_site_list':   cookies_per_site,
        'companies_per_site_list': companies_per_site,
        'auth_per_site':           auth_per_site,
    }
# ── Charts ────────────────────────────────────────────────────

def chart_cookie_type_dist(stats):
    td = stats['type_dist']
    labels = ['Authentication','Tracking','Preference','Other']
    keys   = ['authentication','tracking','preference','other']
    vals   = [td.get(k,0) for k in keys]
    colors = [TYPE_COLORS[k] for k in keys]
    total  = sum(vals)

    fig, ax = plt.subplots(figsize=(6,5))
    wedges, texts, autotexts = ax.pie(
        vals, labels=None, autopct=lambda p: f'{p:.1f}%\n({int(p*total/100):,})',
        colors=colors, startangle=140, pctdistance=0.72,
        wedgeprops={'linewidth':2,'edgecolor':'white'},
    )
    for at in autotexts:
        at.set_fontsize(9); at.set_color('white'); at.set_fontweight('bold')

    legend_labels = [f'{l}  ({v:,})' for l,v in zip(labels,vals)]
    ax.legend(wedges, legend_labels, loc='lower center',
              bbox_to_anchor=(0.5,-0.08), ncol=2, fontsize=9, frameon=False)

    ax.set_title('Cookie Type Distribution\nAcross All Scanned Sites', pad=16)
    fig.tight_layout()
    path = CHARTS / 'fig1_cookie_types.png'
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"  ✓ {path.name}")
    return path

def chart_security_flags(stats):
    categories = ['Secure Flag', 'HttpOnly Flag']
    pcts       = [stats['auth_secure_pct'], stats['auth_httponly_pct']]

    fig, ax = plt.subplots(figsize=(6.5, 4))
    bars = ax.barh(categories, pcts,
                   color=[C['safe'] if p>=70 else C['warn'] if p>=40 else C['risk'] for p in pcts],
                   height=0.4, zorder=3)

    for bar, pct in zip(bars, pcts):
        ax.text(min(pct+1.5, 97), bar.get_y()+bar.get_height()/2,
                f'{pct:.1f}%', va='center', fontsize=12, fontweight='bold')

    # show the gap
    for bar, pct in zip(bars, pcts):
        ax.text(99, bar.get_y()+bar.get_height()/2,
                f'{100-pct:.1f}% missing',
                va='center', ha='right', fontsize=9, color=C['risk'])

    ax.set_xlim(0, 100)
    ax.set_xlabel('% of Authentication Cookies')
    ax.set_title('Security Flag Adoption\non Authentication Cookies', pad=12)
    ax.axvline(x=70, color=C['ink2'], linestyle='--', alpha=0.4, linewidth=1)
    ax.text(70.5, -0.55, '70% threshold', fontsize=8, color=C['ink2'])
    fig.tight_layout()
    path = CHARTS / 'fig2_security_flags.png'
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"  ✓ {path.name}")
    return path

def chart_risk_distribution(stats):
    sd = stats['severity_dist']
    order  = ['critical','high','medium','low','info']
    labels = ['Critical','High','Medium','Low','Info']
    vals   = [sd.get(k,0) for k in order]
    colors = [SEVERITY_COLORS[k] for k in order]

    fig, ax = plt.subplots(figsize=(7,4))
    bars = ax.bar(labels, vals, color=colors, width=0.55, zorder=3,
                  edgecolor='white', linewidth=1.5)

    for bar, val in zip(bars, vals):
        if val:
            ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+max(vals)*0.01,
                    f'{val:,}', ha='center', va='bottom', fontsize=10, fontweight='bold')

    ax.set_ylabel('Number of Cookies')
    ax.set_title('Cookie Risk Level Distribution\n(All Sites)', pad=12)
    fig.tight_layout()
    path = CHARTS / 'fig3_risk_distribution.png'
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"  ✓ {path.name}")
    return path

def chart_top_trackers(stats):
    tt = stats['top_trackers']
    if not tt:
        return None
    companies = list(tt.keys())[:12]
    counts    = [tt[c] for c in companies]

    # short names
    short = [c.replace(' Analytics','').replace('/','/')[:20] for c in companies]

    fig, ax = plt.subplots(figsize=(7,5.5))
    y = range(len(companies))
    bars = ax.barh(list(y), counts,
                   color=['#dc2626' if i<3 else '#ca8a04' if i<6 else '#64748b'
                          for i in range(len(companies))],
                   height=0.6, zorder=3)

    ax.set_yticks(list(y))
    ax.set_yticklabels(short, fontsize=10)
    ax.invert_yaxis()

    for bar, cnt in zip(bars, counts):
        ax.text(bar.get_width()+max(counts)*0.01, bar.get_y()+bar.get_height()/2,
                f'{cnt:,}', va='center', fontsize=9, fontweight='bold')

    ax.set_xlabel('Number of Cookies Detected')
    ax.set_title('Top Tracking Companies Detected\nAcross Scanned Sites', pad=12)
    fig.tight_layout()
    path = CHARTS / 'fig4_top_trackers.png'
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"  ✓ {path.name}")
    return path

def chart_cookies_per_site_histogram(stats):
    data = stats['cookies_per_site_list']
    fig, ax = plt.subplots(figsize=(7,4))
    n, bins, patches = ax.hist(data, bins=30, color=C['info'],
                               edgecolor='white', linewidth=0.8, zorder=3)
    # colour bars by count
    for patch, left in zip(patches, bins[:-1]):
        if left < 10:
            patch.set_facecolor(C['safe'])
        elif left < 30:
            patch.set_facecolor(C['warn'])
        else:
            patch.set_facecolor(C['risk'])

    ax.axvline(np.mean(data), color=C['ink'], linestyle='--', linewidth=1.5, zorder=4)
    ax.text(np.mean(data)+0.5, ax.get_ylim()[1]*0.92,
            f'Mean: {np.mean(data):.1f}', fontsize=9, color=C['ink'])

    ax.set_xlabel('Cookies per Site')
    ax.set_ylabel('Number of Sites')
    ax.set_title('Distribution of Cookie Count per Site', pad=12)

    legend = [
        mpatches.Patch(color=C['safe'],  label='< 10 cookies'),
        mpatches.Patch(color=C['warn'],  label='10–29 cookies'),
        mpatches.Patch(color=C['risk'],  label='≥ 30 cookies'),
    ]
    ax.legend(handles=legend, fontsize=9, frameon=False)
    fig.tight_layout()
    path = CHARTS / 'fig5_cookies_histogram.png'
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"  ✓ {path.name}")
    return path

def chart_samesite(stats):
    ss = stats['samesite_dist']
    label_map = {
        'strict': 'Strict\n(most secure)',
        'lax': 'Lax\n(moderate)',
        'none': 'None\n(risky)',
        'unset': 'Not Set\n(risky)',
        'no_restriction': 'No Restriction\n(risky)',
    }
    order  = ['strict','lax','none','no_restriction','unset']
    colors = [C['safe'], '#0891b2', C['risk'], C['risk'], C['warn']]

    labels = []
    vals   = []
    cols   = []
    for k, col in zip(order, colors):
        v = ss.get(k, 0)
        if v:
            labels.append(label_map.get(k, k))
            vals.append(v)
            cols.append(col)

    fig, ax = plt.subplots(figsize=(6.5,4.5))
    bars = ax.bar(labels, vals, color=cols, width=0.5,
                  edgecolor='white', linewidth=1.5, zorder=3)

    total = sum(vals) or 1
    for bar, val in zip(bars, vals):
        ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+total*0.005,
                f'{val:,}\n({val/total*100:.1f}%)',
                ha='center', va='bottom', fontsize=9, fontweight='bold')

    ax.set_ylabel('Number of Authentication Cookies')
    ax.set_title('SameSite Attribute Distribution\non Authentication Cookies', pad=12)
    fig.tight_layout()
    path = CHARTS / 'fig6_samesite.png'
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"  ✓ {path.name}")
    return path

# ── HTML Report (Cloudflare/Mozilla Executive Style) ──────────

def generate_report(stats):
    s = stats
    from datetime import date
    import base64

    def img_b64(path):
        if Path(path).exists():
            return 'data:image/png;base64,' + base64.b64encode(Path(path).read_bytes()).decode()
        return ''

    fig1 = img_b64(CHARTS / 'fig1_cookie_types.png')
    fig2 = img_b64(CHARTS / 'fig2_security_flags.png')
    fig3 = img_b64(CHARTS / 'fig3_risk_distribution.png')
    fig4 = img_b64(CHARTS / 'fig4_top_trackers.png')
    fig5 = img_b64(CHARTS / 'fig5_cookies_histogram.png')
    fig6 = img_b64(CHARTS / 'fig6_samesite.png')

    today = date.today().strftime('%B %d, %Y')
    total_cookies = s['total_cookies'] or 1
    sev = s['severity_dist']
    sec_miss  = round(100 - s['auth_secure_pct'], 1)
    http_miss = round(100 - s['auth_httponly_pct'], 1)

    # Build tracker table rows
    tracker_rows = ''
    for i, (co, cnt) in enumerate(list(s['top_trackers'].items())[:10]):
        tracker_rows += f'<tr><td>{i+1}</td><td>{co}</td><td>{cnt:,}</td></tr>\n'

    # Build worst offenders table rows
    worst_rows = ''
    for i, (site, risk, track) in enumerate(s['worst_sites']):
        worst_rows += f'<tr><td>{i+1}</td><td>{site}</td><td>{risk}</td><td>{track}</td></tr>\n'

    # ── HTML ─────────────────────────────────────────────────────
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CookieGuard AI – Web Cookie Security Report</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
body{{
    font-family: "Inter", system-ui, sans-serif;
    background:#f8fafc;
    color:#111827;
    margin:0;
    line-height:1.6;
}}
.container{{
    max-width:820px;
    margin:auto;
    padding:40px 28px;
}}
h1{{
    font-size:28px;
    font-weight:700;
    margin-bottom:4px;
}}
h2{{
    margin-top:40px;
    font-size:18px;
    font-weight:600;
}}
.subtitle{{
    color:#6b7280;
    font-size:14px;
}}
.metrics{{
    display:grid;
    grid-template-columns:repeat(4,1fr);
    gap:12px;
    margin:28px 0;
}}
.metric{{
    background:white;
    border-radius:6px;
    padding:14px 16px;
    border:1px solid #e5e7eb;
}}
.metric-value{{
    font-size:20px;
    font-weight:700;
    color:#2563eb;
}}
.metric-label{{
    color:#6b7280;
    font-size:11px;
    margin-top:2px;
}}
.section{{
    margin-top:36px;
}}
.section p{{
    font-size:13px;
    color:#4b5563;
    margin:6px 0 0;
}}
.executive-summary{{
    margin-top:28px;
    background:white;
    border:1px solid #e5e7eb;
    border-left:3px solid #2563eb;
    border-radius:6px;
    padding:16px 20px;
}}
.executive-summary h2{{
    margin:0 0 10px;
    font-size:14px;
    font-weight:600;
    color:#1e40af;
}}
.executive-summary p{{
    font-size:13px;
    color:#374151;
    margin:0 0 10px;
    line-height:1.6;
}}
.executive-summary p:last-child{{
    margin-bottom:0;
}}
.chart{{
    margin-top:14px;
    background:white;
    padding:12px;
    border-radius:6px;
    border:1px solid #e5e7eb;
}}
.chart img{{
    width:100%;
    max-width:420px;
    display:block;
    margin:0 auto;
}}
.insight{{
    background:#eef2ff;
    border-left:3px solid #6366f1;
    padding:12px 14px;
    margin-top:14px;
    font-size:13px;
}}
table{{
    width:100%;
    border-collapse:collapse;
    margin-top:16px;
    background:white;
    border-radius:6px;
    overflow:hidden;
    border:1px solid #e5e7eb;
    font-size:13px;
}}
th,td{{
    padding:8px 12px;
    border-bottom:1px solid #e5e7eb;
    text-align:left;
}}
th{{
    color:#374151;
    background:#f9fafb;
    font-size:11px;
    font-weight:600;
}}
tbody tr:last-child td{{
    border-bottom:none;
}}
footer{{
    margin-top:50px;
    color:#6b7280;
    font-size:12px;
}}
.chart-grid{{
    display:grid;
    grid-template-columns:repeat(2,1fr);
    gap:12px;
    margin-top:14px;
}}
.chart-card{{
    background:white;
    border:1px solid #e5e7eb;
    border-radius:6px;
    overflow:hidden;
}}
.chart-card .chart-label{{
    font-size:11px;
    font-weight:600;
    color:#374151;
    padding:8px 12px;
    border-bottom:1px solid #e5e7eb;
    background:#f9fafb;
}}
.chart-card img{{
    width:100%;
    display:block;
}}
@media(max-width:600px){{
    .metrics{{grid-template-columns:repeat(2,1fr);}}
    .chart-grid{{grid-template-columns:1fr;}}
}}
@media(max-width:400px){{
    .metrics{{grid-template-columns:1fr;}}
    .container{{padding:24px 16px;}}
    h1{{font-size:24px;}}
}}
}}
</style>
</head>
<body>
<div class="container">

<h1>CookieGuard AI</h1>
<div class="subtitle">Web Cookie Security Report · {today}</div>

<div class="metrics">
<div class="metric">
<div class="metric-value">{s['total_sites']:,}</div>
<div class="metric-label">Websites analyzed</div>
</div>
<div class="metric">
<div class="metric-value">{s['total_cookies']:,}</div>
<div class="metric-label">Cookies collected</div>
</div>
<div class="metric">
<div class="metric-value">{s['avg_cookies_per_site']}</div>
<div class="metric-label">Average cookies per site</div>
</div>
<div class="metric">
<div class="metric-value">{s['sites_with_tracking_pct']}%</div>
<div class="metric-label">Sites with trackers</div>
</div>
</div>

<div class="executive-summary">
<h2>Executive Summary</h2>
<p>
This study analyzed <strong>{s['total_sites']:,} popular websites</strong> to assess cookie security practices
and tracking prevalence. CookieGuard AI collected <strong>{s['total_cookies']:,} cookies</strong> and classified
them using on-device machine learning.
</p>
<p>
<strong>Key findings:</strong> {s['sites_with_risk_pct']}% of sites deploy at least one high-risk authentication
cookie vulnerable to session hijacking. Only {s['auth_secure_pct']}% of authentication cookies use the
Secure flag, and {s['auth_httponly_pct']}% use HttpOnly — leaving {sec_miss}% and {http_miss}% exposed
to interception and XSS attacks respectively.
</p>
<p>
Third-party tracking remains pervasive: <strong>{s['sites_with_tracking_pct']}% of sites</strong> embed trackers,
connecting to an average of <strong>{s['avg_companies_per_site']} tracking companies</strong> per site.
Users browsing without protection are profiled across nearly every website they visit.
</p>
</div>

<div class="section">
<h2>Analysis</h2>
<div class="chart-grid">
<div class="chart-card">
<div class="chart-label">Security Flag Adoption</div>
<img src="{fig2}" alt="Security Flags">
</div>
<div class="chart-card">
<div class="chart-label">Risk Level Distribution</div>
<img src="{fig3}" alt="Risk Levels">
</div>
<div class="chart-card">
<div class="chart-label">Cookie Type Distribution</div>
<img src="{fig1}" alt="Cookie Types">
</div>
<div class="chart-card">
<div class="chart-label">Top Tracking Companies</div>
<img src="{fig4}" alt="Trackers">
</div>
</div>
</div>

<div class="section">
<h2>Worst Offenders</h2>
<p>Sites with the highest number of high-risk cookies.</p>
<table>
<thead>
<tr>
<th>Rank</th>
<th>Website</th>
<th>High-Risk Cookies</th>
<th>Tracker Companies</th>
</tr>
</thead>
<tbody>
{worst_rows}
</tbody>
</table>
</div>

<div class="section">
<h2>Top Tracking Companies</h2>
<p>Companies with the largest tracking footprint ({s['sites_with_tracking_pct']}% of sites have trackers, averaging {s['avg_companies_per_site']} companies per site).</p>
<table>
<thead>
<tr>
<th>Rank</th>
<th>Company</th>
<th>Cookie Count</th>
</tr>
</thead>
<tbody>
{tracker_rows}
</tbody>
</table>
</div>

<div class="section">
<h2>Methodology</h2>
<p>
Each website was visited once using headless Chromium via Playwright.
Cookies were collected and classified using CookieGuard AI's
on-device classifier. No user accounts were accessed and
no cookie values were stored during the analysis.
</p>
</div>

<footer>
Generated by CookieGuard AI · {today}
</footer>

</div>
</body>
</html>
'''

    html_path = REPORT / 'cookie_security_report.html'
    html_path.write_text(html)
    print(f"  ✓ {html_path.name}  ({len(html)//1024} KB, self-contained)")

    # Plain markdown
    md_lines = [
                   '# CookieGuard AI — Web Cookie Security Study',
                   f'**Date:** {today}  **Sites:** {s["total_sites"]:,}  **Cookies:** {s["total_cookies"]:,}',
                   '',
                   '## Summary',
                   '| Metric | Value |',
                   '|--------|-------|',
                   f'| Sites attempted | {s["total_sites"]:,} |',
                   f'| Sites with cookies | {s["sites_with_cookies"]:,} ({s["sites_with_cookies_pct"]}%) |',
                   f'| Sites timed out | {s["sites_zero_cookies"]:,} ({s["sites_zero_cookies_pct"]}%) |',
                   f'| Total cookies | {s["total_cookies"]:,} |',
                   f'| Avg cookies/site | {s["avg_cookies_per_site"]} |',
                   f'| Sites with risk | {s["sites_with_risk_pct"]}% |',
                   f'| Sites with tracking | {s["sites_with_tracking_pct"]}% |',
                   f'| Auth cookies Secure | {s["auth_secure_pct"]}% |',
                   f'| Auth cookies HttpOnly | {s["auth_httponly_pct"]}% |',
                   f'| Avg tracker companies | {s["avg_companies_per_site"]} |',
                   '',
                   '## Top Trackers',
               ] + [f'- **{co}**: {cnt:,} cookies' for co, cnt in list(s['top_trackers'].items())[:10]] + [
                   '',
                   '## Worst Offenders',
               ] + [f'{i+1}. `{site}` — {risk} high-risk cookies, {track} tracker companies'
                    for i, (site, risk, track) in enumerate(s['worst_sites'])]

    md_path = REPORT / 'cookie_security_report.md'
    md_path.write_text('\n'.join(md_lines))
    print(f"  ✓ {md_path.name}")
    return html_path, md_path


# ── Main ──────────────────────────────────────────────────────
def main():
    if not CSV.exists():
        print(f"ERROR: {CSV} not found. Run crawler.py first.")
        return

    print(f"Loading {CSV}...")
    rows, timeout_sites = load()
    print(f"  {len(rows):,} cookie records from {len(set(r['site'] for r in rows))} sites")
    if timeout_sites:
        print(f"  {len(timeout_sites)} timeout/zero-cookie sites (from timeouts.csv)")

    print("Computing statistics...")
    stats = compute_stats(rows, timeout_sites)

    # Save JSON
    json_path = BASE / "data" / "summary.json"
    with open(json_path, 'w') as f:
        json.dump({k:v for k,v in stats.items() if 'list' not in k}, f, indent=2)
    print(f"  ✓ summary.json")

    print("Generating charts...")
    chart_cookie_type_dist(stats)
    chart_security_flags(stats)
    chart_risk_distribution(stats)
    chart_top_trackers(stats)
    chart_cookies_per_site_histogram(stats)
    chart_samesite(stats)

    print("Writing report...")
    generate_report(stats)

    print("\n── Summary ──────────────────────────────────────")
    print(f"  Sites attempted:         {stats['total_sites']}")
    print(f"  Sites with cookies:      {stats['sites_with_cookies']} ({stats['sites_with_cookies_pct']}%)")
    print(f"  Sites zero/timeout:      {stats['sites_zero_cookies']} ({stats['sites_zero_cookies_pct']}%)")
    print(f"  Total cookies:           {stats['total_cookies']:,}")
    print(f"  Avg cookies/site:        {stats['avg_cookies_per_site']}")
    print(f"  Sites with risk:         {stats['sites_with_risk_pct']}%")
    print(f"  Sites with tracking:     {stats['sites_with_tracking_pct']}%")
    print(f"  Auth cookies Secure:     {stats['auth_secure_pct']}%")
    print(f"  Auth cookies HttpOnly:   {stats['auth_httponly_pct']}%")
    print(f"  Avg tracker companies:   {stats['avg_companies_per_site']}")
    print("─────────────────────────────────────────────────")
    print(f"\nOutputs:")
    print(f"  charts/   — 6 PNG figures")
    print(f"  report/   — cookie_security_report.md + .html")

if __name__ == '__main__':
    main()