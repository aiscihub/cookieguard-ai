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

    fig, ax = plt.subplots(figsize=(4, 3))
    wedges, texts, autotexts = ax.pie(
        vals, labels=None, autopct=lambda p: f'{p:.1f}%\n({int(p*total/100):,})',
        colors=colors, startangle=140, pctdistance=0.72,
        wedgeprops={'linewidth':1.5,'edgecolor':'white'},
    )
    for at in autotexts:
        at.set_fontsize(8); at.set_color('white'); at.set_fontweight('bold')

    legend_labels = [f'{l}  ({v:,})' for l,v in zip(labels,vals)]
    ax.legend(wedges, legend_labels, loc='lower center',
              bbox_to_anchor=(0.5,-0.05), ncol=2, fontsize=8, frameon=False)

    ax.set_title('Cookie Type Distribution', fontsize=11, pad=10)
    fig.tight_layout()
    path = CHARTS / 'fig1_cookie_types.png'
    fig.savefig(path, dpi=120, bbox_inches='tight')
    plt.close(fig)
    print(f"  ✓ {path.name}")
    return path

def chart_security_flags(stats):
    categories = ['Secure Flag', 'HttpOnly Flag']
    pcts       = [stats['auth_secure_pct'], stats['auth_httponly_pct']]

    fig, ax = plt.subplots(figsize=(5, 3))
    bars = ax.barh(categories, pcts,
                   color=[C['safe'] if p>=70 else C['warn'] if p>=40 else C['risk'] for p in pcts],
                   height=0.4, zorder=3)

    for bar, pct in zip(bars, pcts):
        ax.text(min(pct+1.5, 97), bar.get_y()+bar.get_height()/2,
                f'{pct:.1f}%', va='center', fontsize=10, fontweight='bold')

    # show the gap
    for bar, pct in zip(bars, pcts):
        ax.text(99, bar.get_y()+bar.get_height()/2,
                f'{100-pct:.1f}% missing',
                va='center', ha='right', fontsize=8, color=C['risk'])

    ax.set_xlim(0, 100)
    ax.set_xlabel('% of Authentication Cookies', fontsize=9)
    ax.set_title('Security Flag Adoption', fontsize=11, pad=8)
    ax.axvline(x=70, color=C['ink2'], linestyle='--', alpha=0.4, linewidth=1)
    ax.tick_params(labelsize=9)
    fig.tight_layout()
    path = CHARTS / 'fig2_security_flags.png'
    fig.savefig(path, dpi=120, bbox_inches='tight')
    plt.close(fig)
    print(f"  ✓ {path.name}")
    return path

def chart_risk_distribution(stats):
    sd = stats['severity_dist']
    order  = ['critical','high','medium','low','info']
    labels = ['Critical','High','Medium','Low','Info']
    vals   = [sd.get(k,0) for k in order]
    colors = [SEVERITY_COLORS[k] for k in order]

    fig, ax = plt.subplots(figsize=(5, 3.5))
    bars = ax.bar(labels, vals, color=colors, width=0.55, zorder=3,
                  edgecolor='white', linewidth=1)

    for bar, val in zip(bars, vals):
        if val:
            ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+max(vals)*0.01,
                    f'{val:,}', ha='center', va='bottom', fontsize=8, fontweight='bold')

    ax.set_ylabel('Number of Cookies', fontsize=9)
    ax.set_title('Risk Level Distribution', fontsize=11, pad=8)
    ax.tick_params(labelsize=8)
    fig.tight_layout()
    path = CHARTS / 'fig3_risk_distribution.png'
    fig.savefig(path, dpi=120, bbox_inches='tight')
    plt.close(fig)
    print(f"  ✓ {path.name}")
    return path

def chart_top_trackers(stats):
    tt = stats['top_trackers']
    if not tt:
        return None
    companies = list(tt.keys())[:10]
    counts    = [tt[c] for c in companies]

    # short names
    short = [c.replace(' Analytics','').replace('/','/')[:18] for c in companies]

    fig, ax = plt.subplots(figsize=(5, 4))
    y = range(len(companies))
    bars = ax.barh(list(y), counts,
                   color=['#dc2626' if i<3 else '#ca8a04' if i<6 else '#64748b'
                          for i in range(len(companies))],
                   height=0.6, zorder=3)

    ax.set_yticks(list(y))
    ax.set_yticklabels(short, fontsize=8)
    ax.invert_yaxis()

    for bar, cnt in zip(bars, counts):
        ax.text(bar.get_width()+max(counts)*0.01, bar.get_y()+bar.get_height()/2,
                f'{cnt:,}', va='center', fontsize=8, fontweight='bold')

    ax.set_xlabel('Cookies Detected', fontsize=9)
    ax.set_title('Top Tracking Companies', fontsize=11, pad=8)
    ax.tick_params(labelsize=8)
    fig.tight_layout()
    path = CHARTS / 'fig4_top_trackers.png'
    fig.savefig(path, dpi=120, bbox_inches='tight')
    plt.close(fig)
    print(f"  ✓ {path.name}")
    return path

def chart_cookies_per_site_histogram(stats):
    data = stats['cookies_per_site_list']
    fig, ax = plt.subplots(figsize=(5, 3.5))
    n, bins, patches = ax.hist(data, bins=25, color=C['info'],
                               edgecolor='white', linewidth=0.6, zorder=3)
    # colour bars by count
    for patch, left in zip(patches, bins[:-1]):
        if left < 10:
            patch.set_facecolor(C['safe'])
        elif left < 30:
            patch.set_facecolor(C['warn'])
        else:
            patch.set_facecolor(C['risk'])

    ax.axvline(np.mean(data), color=C['ink'], linestyle='--', linewidth=1, zorder=4)
    ax.text(np.mean(data)+0.5, ax.get_ylim()[1]*0.92,
            f'Mean: {np.mean(data):.1f}', fontsize=8, color=C['ink'])

    ax.set_xlabel('Cookies per Site', fontsize=9)
    ax.set_ylabel('Number of Sites', fontsize=9)
    ax.set_title('Cookie Count Distribution', fontsize=11, pad=8)
    ax.tick_params(labelsize=8)

    legend = [
        mpatches.Patch(color=C['safe'],  label='< 10'),
        mpatches.Patch(color=C['warn'],  label='10–29'),
        mpatches.Patch(color=C['risk'],  label='≥ 30'),
    ]
    ax.legend(handles=legend, fontsize=7, frameon=False)
    fig.tight_layout()
    path = CHARTS / 'fig5_cookies_histogram.png'
    fig.savefig(path, dpi=120, bbox_inches='tight')
    plt.close(fig)
    print(f"  ✓ {path.name}")
    return path

def chart_samesite(stats):
    ss = stats['samesite_dist']
    label_map = {
        'strict': 'Strict',
        'lax': 'Lax',
        'none': 'None',
        'unset': 'Not Set',
        'no_restriction': 'No Restrict',
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

    fig, ax = plt.subplots(figsize=(5, 3.5))
    bars = ax.bar(labels, vals, color=cols, width=0.5,
                  edgecolor='white', linewidth=1, zorder=3)

    total = sum(vals) or 1
    for bar, val in zip(bars, vals):
        ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+total*0.005,
                f'{val:,}',
                ha='center', va='bottom', fontsize=8, fontweight='bold')

    ax.set_ylabel('Auth Cookies', fontsize=9)
    ax.set_title('SameSite Distribution', fontsize=11, pad=8)
    ax.tick_params(labelsize=8)
    fig.tight_layout()
    path = CHARTS / 'fig6_samesite.png'
    fig.savefig(path, dpi=120, bbox_inches='tight')
    plt.close(fig)
    print(f"  ✓ {path.name}")
    return path

# ── HTML Report (GitHub Pages Ready) ──────────────────────────

def generate_report(stats):
    s = stats
    from datetime import date
    import shutil

    # Use relative paths for GitHub Pages
    fig1 = 'figures/cookie_types.png'
    fig2 = 'figures/security_flags.png'
    fig3 = 'figures/risk_distribution.png'
    fig4 = 'figures/top_trackers.png'
    fig5 = 'figures/cookies_histogram.png'
    fig6 = 'figures/samesite.png'

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
    font-family: Inter, system-ui, sans-serif;
    background: #f9fafb;
    color: #111827;
    margin: 0;
    line-height: 1.6;
}}
.container{{
    max-width: 1000px;
    margin: auto;
    padding: 0 40px 60px;
}}
.report-header{{
    text-align: center;
    padding: 60px 20px 40px;
}}
.report-header h1{{
    font-size: 42px;
    font-weight: 700;
    margin: 0 0 8px;
}}
.report-subtitle{{
    font-size: 18px;
    color: #4b5563;
    margin: 0;
}}
.report-meta{{
    color: #6b7280;
    margin-top: 8px;
    font-size: 14px;
}}
.section{{
    margin: 50px 0;
}}
.section h2{{
    font-size: 20px;
    font-weight: 600;
    margin: 0 0 12px;
}}
.section p{{
    font-size: 14px;
    color: #4b5563;
    margin: 0 0 16px;
}}
.metrics{{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 20px;
    margin: 40px 0;
}}
.metric{{
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    padding: 24px;
    text-align: center;
}}
.metric-value{{
    font-size: 32px;
    font-weight: 700;
    color: #2563eb;
}}
.metric-label{{
    color: #6b7280;
    font-size: 13px;
    margin-top: 4px;
}}
.executive-summary{{
    background: white;
    border: 1px solid #e5e7eb;
    border-left: 4px solid #2563eb;
    border-radius: 8px;
    padding: 24px 28px;
    margin: 40px 0;
}}
.executive-summary h2{{
    font-size: 16px;
    font-weight: 600;
    color: #1e40af;
    margin: 0 0 12px;
}}
.executive-summary p{{
    font-size: 14px;
    color: #374151;
    margin: 0 0 12px;
    line-height: 1.7;
}}
.executive-summary p:last-child{{
    margin-bottom: 0;
}}
.chart-grid{{
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 20px;
}}
.chart-card{{
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    overflow: hidden;
}}
.chart-card .chart-label{{
    font-size: 12px;
    font-weight: 600;
    color: #374151;
    padding: 12px 16px;
    border-bottom: 1px solid #e5e7eb;
    background: #f9fafb;
}}
.chart-card img{{
    width: 100%;
    display: block;
}}
.insight{{
    background: #eef2ff;
    border-left: 4px solid #6366f1;
    padding: 16px 20px;
    margin-top: 20px;
    font-size: 14px;
    border-radius: 0 8px 8px 0;
}}
table{{
    width: 100%;
    border-collapse: collapse;
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    overflow: hidden;
    font-size: 14px;
}}
th, td{{
    padding: 12px 16px;
    border-bottom: 1px solid #e5e7eb;
    text-align: left;
}}
th{{
    color: #374151;
    background: #f9fafb;
    font-size: 12px;
    font-weight: 600;
}}
tbody tr:last-child td{{
    border-bottom: none;
}}
footer{{
    margin-top: 60px;
    text-align: center;
    color: #6b7280;
    font-size: 13px;
    padding-bottom: 40px;
}}
@media(max-width: 800px){{
    .metrics{{ grid-template-columns: repeat(2, 1fr); }}
    .chart-grid{{ grid-template-columns: 1fr; }}
    .container{{ padding: 0 24px 40px; }}
}}
@media(max-width: 500px){{
    .metrics{{ grid-template-columns: 1fr; }}
    .report-header h1{{ font-size: 32px; }}
    .report-header{{ padding: 40px 16px 30px; }}
}}
</style>
</head>
<body>

<header class="report-header">
<h1>CookieGuard AI</h1>
<p class="report-subtitle">Web Cookie Security Report</p>
<p class="report-meta">Analysis of {s['total_sites']:,} websites and {s['total_cookies']:,} cookies · {today}</p>
</header>

<div class="container">

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
<div class="metric-label">Avg cookies per site</div>
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
<p>Visual breakdown of cookie security practices across all analyzed websites.</p>
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
<div class="insight">
Only <strong>{s['auth_secure_pct']}%</strong> of authentication cookies use the Secure flag, 
leaving <strong>{sec_miss}%</strong> vulnerable to interception on public networks.
<strong>{s['sites_with_risk_pct']}%</strong> of sites have at least one high-risk cookie.
</div>
</div>

<div class="section">
<h2>Worst Offenders</h2>
<p>Sites with the highest concentration of high-risk authentication cookies.</p>
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

    # Create GitHub Pages directory structure
    gh_pages = BASE / 'gh-pages'
    gh_pages.mkdir(exist_ok=True)
    (gh_pages / 'figures').mkdir(exist_ok=True)
    (gh_pages / 'data').mkdir(exist_ok=True)

    # Write index.html
    html_path = gh_pages / 'index.html'
    html_path.write_text(html)
    print(f"  ✓ index.html")

    # Copy figures with clean names
    import shutil
    figure_mapping = {
        'fig1_cookie_types.png': 'cookie_types.png',
        'fig2_security_flags.png': 'security_flags.png',
        'fig3_risk_distribution.png': 'risk_distribution.png',
        'fig4_top_trackers.png': 'top_trackers.png',
        'fig5_cookies_histogram.png': 'cookies_histogram.png',
        'fig6_samesite.png': 'samesite.png',
    }
    for old_name, new_name in figure_mapping.items():
        src = CHARTS / old_name
        if src.exists():
            shutil.copy(src, gh_pages / 'figures' / new_name)
    print(f"  ✓ figures/ (6 PNG charts)")

    # Copy raw data
    if CSV.exists():
        shutil.copy(CSV, gh_pages / 'data' / 'cookies_raw.csv')
    json_src = BASE / 'data' / 'summary.json'
    if json_src.exists():
        shutil.copy(json_src, gh_pages / 'data' / 'summary.json')
    print(f"  ✓ data/ (CSV + JSON)")

    # Generate README.md
    readme = f'''# CookieGuard AI — Web Cookie Security Report

Analysis of **{s["total_sites"]:,} websites** and **{s["total_cookies"]:,} cookies**.

## Key Findings

- **{s["sites_with_risk_pct"]}%** of sites have high-risk authentication cookies
- **{s["auth_secure_pct"]}%** of auth cookies use Secure flag ({sec_miss}% exposed)
- **{s["auth_httponly_pct"]}%** of auth cookies use HttpOnly flag ({http_miss}% exposed)
- **{s["sites_with_tracking_pct"]}%** of sites embed third-party trackers
- Average of **{s["avg_companies_per_site"]}** tracking companies per site

## View Report

📊 **[View the full report](https://YOUR_USERNAME.github.io/cookieguard-report/)**

## Repository Structure

```
├── index.html          # Main report page
├── figures/            # Chart images
│   ├── cookie_types.png
│   ├── security_flags.png
│   ├── risk_distribution.png
│   └── top_trackers.png
├── data/
│   ├── cookies_raw.csv # Raw cookie data
│   └── summary.json    # Aggregated statistics
└── README.md
```

## Methodology

Each website was visited once using headless Chromium via Playwright.
Cookies were collected and classified using CookieGuard AI's on-device classifier.
No user accounts were accessed and no cookie values were stored.

---

Generated by [CookieGuard AI](https://github.com/YOUR_USERNAME/cookieguard-ai) · {today}
'''
    (gh_pages / 'README.md').write_text(readme)
    print(f"  ✓ README.md")

    # Also keep the old report location for backwards compatibility
    (REPORT / 'cookie_security_report.html').write_text(html)

    # Plain markdown (legacy)
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

    print(f"\n  GitHub Pages ready: gh-pages/")
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
    print(f"  charts/    — 6 PNG figures")
    print(f"  report/    — cookie_security_report.md + .html")
    print(f"  gh-pages/  — GitHub Pages ready (index.html + figures/ + data/)")

if __name__ == '__main__':
    main()