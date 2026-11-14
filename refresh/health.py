"""Coverage counts, health rules, and the shared report text."""
from collections import Counter

ROBOTS_STATUSES = {'allowed', 'disallowed', 'absent-4xx', 'server-error', 'network-error', 'redirect-limit', 'too-large', 'unreachable', 'tls-error'}
ROBOTS_FAILURE_STATUSES = {'server-error', 'redirect-limit', 'too-large', 'network-error'}
UNANSWERED_STATUSES = {'unreachable', 'tls-error'}
CMP_FAMILIES = ('cookiebot', 'onetrust', 'none')
COMPARABILITY_NOTICE = (
    'Monthly releases are not directly comparable with the November 2026 study crawl: '
    'this crawler identifies itself as CookieGuardResearch/1.0, while the study used a Chrome user agent. '
    'Hosted Actions runs also originate from datacenter addresses. Consent managers may treat these '
    'requests differently; the hosted pilot measures their effect on yield.'
)

def attempt_metrics(attempts):
    for item in attempts:
        if (type(item.get('visited')) is not bool or item.get('robotsStatus') not in ROBOTS_STATUSES
            or item.get('cmp') not in CMP_FAMILIES):
            raise ValueError('missing-or-invalid-coverage-evidence')
        if item['status'] == 'usable' and (not item['visited'] or item['cmp'] == 'none'):
            raise ValueError('usable-without-visit-or-cmp')
    unavailable = sum(item['robotsStatus'] in ROBOTS_FAILURE_STATUSES for item in attempts)
    unanswered = sum(item['robotsStatus'] in UNANSWERED_STATUSES for item in attempts)
    families = Counter(item['cmp'] for item in attempts)
    return {
        'visitedSites': sum(item['visited'] for item in attempts),
        'robotsUnavailableSites': unavailable,
        'unreachableOrTlsSites': unanswered,
        'robotsStatusCounts': dict(sorted(Counter(item['robotsStatus'] for item in attempts).items())),
        'cmpFamilyCounts': {family: families[family] for family in CMP_FAMILIES},
    }

def assess_health(manifest):
    attempted, visited = manifest['attempted'], manifest.get('visitedSites')
    unavailable = manifest.get('robotsUnavailableSites')
    usable = manifest['usableSites']
    counts_valid = (type(visited) is int and type(unavailable) is int and
                    0 <= usable <= visited <= attempted and 0 <= unavailable <= attempted)
    site_yield = usable / visited if counts_valid and visited else None
    unavailable_rate = unavailable / attempted if counts_valid and attempted else None
    # Reachability is diagnostic only: it never participates in either health rule.
    unanswered = manifest.get('unreachableOrTlsSites')
    unanswered_rate = (unanswered / attempted if type(unanswered) is int and attempted > 0
                       and 0 <= unanswered <= attempted else None)
    # 1.5%: the November 2026 pilot measured 11 usable of 330 visited (3.3%; 95% interval about
    # 1.7-5.9%). A broken parser yields about 0%. The floor catches that without failing a healthy month.
    yield_passed = site_yield is not None and site_yield >= .015
    availability_passed = unavailable_rate is not None and unavailable_rate <= .20
    return {
        'passed': yield_passed and availability_passed,
        'rule': 'usable / visited >= 1.5%; robots response/protocol failures / attempted <= 20%',
        'attemptedSites': attempted, 'visitedSites': visited, 'usableSites': usable,
        'usableSiteYield': site_yield, 'yieldPassed': yield_passed,
        'robotsUnavailableSites': unavailable, 'robotsUnavailableRate': unavailable_rate,
        'robotsAvailabilityPassed': availability_passed,
        'unreachableOrTlsSites': unanswered, 'unreachableOrTlsRate': unanswered_rate,
        'robotsUnavailableDefinition': 'robotsStatus server-error, redirect-limit, too-large, or network-error; each site counted once',
        'unreachableOrTlsDefinition': 'unreachable plus tls-error; study navigation-failed equivalent; reported only, no gate',
    }

def health_report(manifest):
    health = assess_health(manifest)
    fmt = lambda x: 'N/A' if x is None else format(100 * x, '.2f') + '%'
    lines = ['', '### Coverage and Health', '', '| Measure | Count | Rate | Rule |', '|---|---:|---:|---|',
             '| Usable / visited | ' + str(health['usableSites']) + ' / ' + str(health['visitedSites']) +
             ' | ' + fmt(health['usableSiteYield']) + ' | At least 1.5% |',
             '| Robots response/protocol failures / attempted | ' + str(health['robotsUnavailableSites']) + ' / ' + str(health['attemptedSites']) +
             ' | ' + fmt(health['robotsUnavailableRate']) + ' | At most 20% |',
             '| Unreachable + TLS / attempted | ' + str(health['unreachableOrTlsSites']) + ' / ' + str(health['attemptedSites']) +
             ' | ' + fmt(health['unreachableOrTlsRate']) + ' | Report only; no gate |', '',
             'Visited means robots permitted an origin and document navigation started. The 20% cap counts only '
             'server-error, redirect-limit, too-large, and network-error, once per site. Unreachable plus tls-error '
             'is the study navigation-failed equivalent and has no gate. Counts use the final robots outcome after any HTTP fallback.', '',
             '| CMP family | Attempted sites |', '|---|---:|']
    for family, label in [('cookiebot', 'Cookiebot'), ('onetrust', 'OneTrust'), ('none', 'None')]:
        lines.append('| ' + label + ' | ' + str(manifest.get('cmpFamilyCounts', {}).get(family, 'unavailable')) + ' |')
    lines += ['', '| Robots status | Sites |', '|---|---:|']
    for status in sorted(ROBOTS_STATUSES):
        count = manifest.get('robotsStatusCounts', {}).get(status, 0)
        lines.append('| ' + status + ' | ' + str(count) + ' |')
    lines += ['', COMPARABILITY_NOTICE, '']
    return lines
