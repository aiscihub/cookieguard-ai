#!/usr/bin/env python3
"""Build the published CookieGuard cookie database from the frozen November 2026 studies.

Reads only frozen study artifacts under waicy_2026/ and writes the public files in data/.
No cookie value is read or written: the study rows carry value *shape* only.

Outputs
  known-cookie-names.json / .csv   the known-name lookup table CookieGuard uses before the model
  cookies-2026.jsonl / .csv        16,571 consent-declared cookies from 788 real websites, 2026
  stats.json                       counts shown on the website
"""
import csv, json, glob, os, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = os.path.join(ROOT, 'waicy_2026')
OUT = os.path.dirname(os.path.abspath(__file__))
NK = os.path.join(W, 'name_knowledge')

def load(p):
    with open(p) as f:
        return json.load(f)

def rows(pattern):
    out = []
    for p in sorted(glob.glob(pattern)):
        with open(p) as f:
            out += [json.loads(l) for l in f if l.strip()]
    return out

# ---------------------------------------------------------------- known names
d1 = load(os.path.join(NK, 'dictionary', 'd1_deployment.json'))
d2 = load(os.path.join(NK, 'dictionary', 'd2.json'))
LABEL = {0: 'not-tracker', 1: 'tracker'}

def d1_entries(table):
    out = []
    for name, v in sorted(table.items()):
        era = v.get('eraRows', {})
        out.append({
            'name': name,
            'label': LABEL[v['label']],
            'trackerVotes': v['trackerVotes'],
            'notTrackerVotes': v['notTrackerVotes'],
            'rows2021': era.get('2021', 0),
            'rows2026': era.get('2026', 0),
        })
    return out

def d2_entries(table, kind):
    out = []
    for name, v in sorted(table.items()):
        recs = v.get('records', [])
        out.append({
            'name': name,
            'match': kind,
            'label': LABEL[v['label']],
            'platform': sorted({r.get('platform', '') for r in recs if r.get('platform')}),
            'category': sorted({r.get('category', '') for r in recs if r.get('category')}),
            'ocdIds': [r['id'] for r in recs if r.get('id')],
        })
    return out

raw = d1_entries(d1['raw'])
norm = d1_entries(d1['normalized'])
ocd = d2_entries(d2['exact'], 'exact') + d2_entries(d2['wildcard'], 'prefix')

known = {
    'schemaVersion': 1,
    'title': 'CookieGuard known cookie names',
    'generated': datetime.date.today().isoformat(),
    'license': {
        'cookieguard': 'CC BY 4.0',
        'openCookieDatabase': 'Apache-2.0 (redistributed with attribution; see README.md)',
    },
    'lookupOrder': ['cookieguard.raw (exact, case-sensitive)', 'cookieguard.normalized (after name normalization)', 'ocd (exact)', 'ocd (prefix)'],
    'labels': {'tracker': 'declared Analytics/Statistics/Advertising by the site', 'not-tracker': 'declared Necessary/Functional/Preference'},
    'normalization': 'lowercase; split on _ . -; a piece with 6+ chars mixing letters and digits, or 8+ hex chars, becomes #; every digit run becomes 0',
    'counts': {
        'cookieguardRaw': len(raw), 'cookieguardNormalized': len(norm),
        'cookieguardSourceRows': d1['sourceRows'],
        'ocdExact': len(d2['exact']), 'ocdPrefix': len(d2['wildcard']),
    },
    'cookieguard': {'raw': raw, 'normalized': norm},
    'ocd': ocd,
}
with open(os.path.join(OUT, 'known-cookie-names.json'), 'w') as f:
    json.dump(known, f, separators=(',', ':'), ensure_ascii=False)

with open(os.path.join(OUT, 'known-cookie-names.csv'), 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['table', 'name', 'label', 'trackerVotes', 'notTrackerVotes', 'rows2021', 'rows2026', 'ocdMatch', 'ocdPlatform', 'ocdCategory'])
    for e in raw:
        w.writerow(['cookieguard-raw', e['name'], e['label'], e['trackerVotes'], e['notTrackerVotes'], e['rows2021'], e['rows2026'], '', '', ''])
    for e in norm:
        w.writerow(['cookieguard-normalized', e['name'], e['label'], e['trackerVotes'], e['notTrackerVotes'], e['rows2021'], e['rows2026'], '', '', ''])
    for e in ocd:
        w.writerow(['open-cookie-database', e['name'], e['label'], '', '', '', '', e['match'], '|'.join(e['platform']), '|'.join(e['category'])])

# ---------------------------------------------------------------- 2026 cookies
feature_names = load(os.path.join(NK, 'test', 'schema.json'))['featureNames']
crawls = [
    ('tune', os.path.join(W, 'accuracy_push2', 'finalization', 'fresh_test', 'rows-*.jsonl'), 'ranks 1-3,300; used to tune thresholds'),
    ('unseen-test', os.path.join(W, 'combination_check', 'test', 'batches', 'rows-*.jsonl'), 'ranks 3,401-12,560; only names never seen in training or tuning'),
    ('mix-test', os.path.join(NK, 'test', 'batches', 'rows-*.jsonl'), 'ranks 12,561-20,000; every matched cookie kept'),
]
FORBIDDEN = {'value', 'siteId', 'features'}
records = []
for crawl, pattern, _ in crawls:
    for r in rows(pattern):
        assert 'value' not in r
        rec = {'crawl': crawl, 'rank': r['rank'], 'cmp': r['cmp'], 'declaredCategory': r['category'], 'declaredGroup': r['groupId'],
               'name': r['name'], 'normalizedName': r['normalizedName'], 'domain': r['domain'], 'path': r['path'],
               'label': LABEL[r['label']], 'secure': r['secure'], 'httpOnly': r['httpOnly'], 'sameSite': r['sameSite'],
               'hostOnly': r['hostOnly'], 'session': r['session'], 'lifetimeSeconds': r['lifetimeSeconds'],
               'valueLength': r['valueShape']['length'], 'valueCharacterSet': r['valueShape']['characterSet'],
               'declarationMatch': r['declarationMatch']}
        if 'seenInTraining' in r:
            rec['seenInTraining'] = r['seenInTraining']
            rec['seenInTuning'] = r['seenInDevelopment']
        rec['features'] = r['features']
        records.append(rec)

with open(os.path.join(OUT, 'cookies-2026.jsonl'), 'w') as f:
    for rec in records:
        f.write(json.dumps(rec, separators=(',', ':'), ensure_ascii=False) + '\n')

base_cols = ['crawl', 'rank', 'cmp', 'declaredCategory', 'declaredGroup', 'name', 'normalizedName', 'domain', 'path', 'label',
             'secure', 'httpOnly', 'sameSite', 'hostOnly', 'session', 'lifetimeSeconds', 'valueLength', 'valueCharacterSet',
             'declarationMatch', 'seenInTraining', 'seenInTuning']
with open(os.path.join(OUT, 'cookies-2026.csv'), 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(base_cols + feature_names)
    for rec in records:
        w.writerow([rec.get(c, '') for c in base_cols] + rec['features'])

sites = len({(r['crawl'], r['rank']) for r in records})
names = len({r['normalizedName'] for r in records})
stats = {
    'generated': known['generated'],
    'knownNames': {'raw': len(raw), 'normalized': len(norm), 'ocd': len(ocd), 'sourceRows': d1['sourceRows']},
    'cookies2026': {'rows': len(records), 'sites': sites, 'normalizedNames': names,
                    'byCrawl': {c: sum(1 for r in records if r['crawl'] == c) for c, _, _ in crawls},
                    'trackers': sum(1 for r in records if r['label'] == 'tracker')},
    'crawls': [{'id': c, 'note': n} for c, _, n in crawls],
    'featureNames': feature_names,
    'files': {n: os.path.getsize(os.path.join(OUT, n)) for n in ['known-cookie-names.json', 'known-cookie-names.csv', 'cookies-2026.jsonl', 'cookies-2026.csv']},
}
with open(os.path.join(OUT, 'stats.json'), 'w') as f:
    json.dump(stats, f, indent=1)
print(json.dumps(stats, indent=1))
