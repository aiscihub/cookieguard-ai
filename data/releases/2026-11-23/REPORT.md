# Dataset refresh report: 2026-11-23

**Candidate artifacts only. Every model release requires human approval.**

Tranco list: 8PW6V. Attempted sites: 7500; visited sites: 5554; usable sites: 248; labeled cookies: 5875.

## 1. Gates

| Gate | Result | Evidence |
|---|---|---|
| No regression | PASS | paired balanced-accuracy lower 95% bound >= -0.01 against both production baselines; {"lowerBounds": {"production-rules": 0.10877105967492098, "production-v1": 0.17204455817426398}} |
| Unseen names | FAIL | paired balanced-accuracy lower 95% bound >= -0.01 against both production baselines; {"lowerBounds": {"production-rules": -0.03697138047138038, "production-v1": -0.10554227494461484}} |
| Canaries | PASS | npm test with candidate preload; real Browser Use candidate bridge: FAIL CG001 / PASS |
| Parity | PASS | ONNX versus scikit-learn <= 1e-5 on 1000 rows; {"maxAbsoluteDifference": 4.4223958906020044e-07} |
| Privacy | PASS | every included shard passed its own cross-scan and structural check |
| Coverage | PASS | excluded reserved sites / frame <= 25%; at least one included shard; {"evidenceValid": true, "excludedRate": 0.25, "excludedSites": 2500, "includedSites": 7500, "plannedSites": 10000} |
| Health | PASS | usable / visited >= 1.5%; robots response/protocol failures / attempted <= 20%; {"attemptedSites": 7500, "robotsAvailabilityPassed": true, "robotsUnavailableDefinition": "robotsStatus server-error, redirect-limit, too-large, or network-error; each site counted once", "robotsUnavailableRate": 0.03253333333333333, "robotsUnavailableSites": 244, "unreachableOrTlsDefinition": "unreachable plus tls-error; study navigation-failed equivalent; reported only, no gate", "unreachableOrTlsRate": 0.2092, "unreachableOrTlsSites": 1569, "usableSiteYield": 0.044652502700756214, "usableSites": 248, "visitedSites": 5554, "yieldPassed": true} |

## 2. Evaluation

Tracker is the positive class. Intervals are 95% site-cluster bootstrap intervals from 1,000 seeded draws. Paired differences use the same sampled sites. Unseen comparisons use rows unseen to both methods. An interval is unavailable if fewer than 950 draws define the metric or fewer than two sites are available.

| Method | Subset | Rows | Sites | Balanced accuracy | Precision | Recall |
|---|---|---:|---:|---|---|---|
| candidate | natural | 5875 | 248 | 84.42% [82.62, 86.13] | 90.85% [88.83, 92.70] | 93.71% [92.34, 94.82] |
| candidate | unseenNames | 284 | 100 | 60.23% [54.62, 65.64] | 58.54% [41.93, 73.34] | 28.92% [18.05, 40.00] |
| production-rules | natural | 5875 | 248 | 71.16% [68.07, 73.94] | 91.87% [89.29, 94.01] | 55.19% [49.40, 60.05] |
| production-rules | unseenNames | 5875 | 248 | 71.16% [68.07, 73.94] | 91.87% [89.29, 94.01] | 55.19% [49.40, 60.05] |
| production-v1 | natural | 5875 | 248 | 65.56% [64.17, 66.87] | 83.66% [80.72, 86.27] | 64.09% [62.54, 65.47] |
| production-v1 | unseenNames | 5280 | 244 | 64.24% [62.87, 65.58] | 81.98% [78.39, 84.83] | 61.16% [59.26, 62.85] |
| study-N1-C2 | natural | 5875 | 248 | 81.34% [79.52, 83.08] | 88.89% [86.63, 91.08] | 93.42% [92.12, 94.50] |
| study-N1-C2 | unseenNames | 448 | 132 | 62.43% [56.96, 67.88] | 54.46% [44.84, 63.82] | 62.03% [54.02, 69.67] |

### Paired candidate differences

| Baseline | Subset | Rows | Balanced accuracy difference |
|---|---|---:|---|
| production-rules | natural | 5875 | 13.26% [10.88, 15.92] |
| production-rules | unseenNames | 284 | 2.54% [-3.70, 8.03] |
| production-v1 | natural | 5875 | 18.86% [17.20, 20.54] |
| production-v1 | unseenNames | 284 | -3.64% [-10.55, 3.03] |
| study-N1-C2 | natural | 5875 | 3.08% [2.19, 4.09] |
| study-N1-C2 | unseenNames | 284 | 1.95% [-4.23, 7.53] |

### Lookup and declaration disagreement

| Method | Lookup hits | Hit rate | Hit accuracy | Disagreements |
|---|---:|---|---|---:|
| candidate | 5575 | 94.89% | 89.51% | 585 |
| production-rules | 0 | 0.00% | N/A | 0 |
| production-v1 | 0 | 0.00% | N/A | 0 |
| study-N1-C2 | 5405 | 92.00% | 88.86% | 602 |

Normalized names with conflicting site labels: 149.

## 3. Crawl and privacy

| Status | Sites |
|---|---:|
| blocked | 747 |
| consent-api-missing | 1 |
| declaration-failed | 11 |
| navigation-failed | 57 |
| no-matched-labeled-cookie | 10 |
| no-supported-cmp | 4400 |
| no-usable-declaration | 35 |
| redirect-outside-frame | 40 |
| reload-failed | 1 |
| robots-disallowed | 137 |
| robots-unavailable | 1813 |
| usable | 248 |

### Shard exclusions

Included sites: 7500; excluded reserved sites: 2500 / 10000.

Publication requires at most 25% excluded sites. Health uses included shards only. Excluded payloads are removed before the deliverable audit and upload.

| Excluded shard | Reserved sites | Reason code |
|---|---:|---|
| 3 | 625 | privacy-rejected |
| 5 | 625 | privacy-rejected |
| 6 | 625 | missing-shard |
| 7 | 625 | missing-shard |


### Coverage and Health

| Measure | Count | Rate | Rule |
|---|---:|---:|---|
| Usable / visited | 248 / 5554 | 4.47% | At least 1.5% |
| Robots response/protocol failures / attempted | 244 / 7500 | 3.25% | At most 20% |
| Unreachable + TLS / attempted | 1569 / 7500 | 20.92% | Report only; no gate |

Visited means robots permitted an origin and document navigation started. The 20% cap counts only server-error, redirect-limit, too-large, and network-error, once per site. Unreachable plus tls-error is the study navigation-failed equivalent and has no gate. Counts use the final robots outcome after any HTTP fallback.

| CMP family | Attempted sites |
|---|---:|
| Cookiebot | 102 |
| OneTrust | 235 |
| None | 7163 |

| Robots status | Sites |
|---|---:|
| absent-4xx | 1059 |
| allowed | 4490 |
| disallowed | 138 |
| network-error | 132 |
| not-checked | 0 |
| redirect-limit | 16 |
| server-error | 49 |
| tls-error | 161 |
| too-large | 47 |
| unreachable | 1408 |

Visited but not recorded: 0. These count as attempted; their document/robots outcomes are unknown and they are never revisited.

Monthly releases are not directly comparable with the November 2026 study crawl: this crawler identifies itself as CookieGuardResearch/1.0, while the study used a Chrome user agent. Hosted Actions runs also originate from datacenter addresses. Consent managers may treat these requests differently; the hosted pilot measures their effect on yield.


No site is revisited. A site with an unverifiable robots policy is skipped conservatively. All shards run at concurrency 4 with a 30-second site cap. Cookies remain in memory; no browser traces, screenshots, storage-state files, page text, or raw exceptions are exported.

Privacy receipts record the frozen crawler's incremental cross-scan: strings of at least 8 characters, with independently observed cookie names, domains, and numeric coincidences accounted for. Short strings are protected by fixed schemas and exclusion of contents fields. Grep is an additional check, not proof that arbitrary unknown secrets are impossible.

## 4. Training and provenance

Training rows: 320993; normalized names: 10993; threshold: 0.56. No current-period refresh rows enter training or lookup construction.

C2: 150 trees, depth 12, minimum split 5, minimum leaf 2, balanced weights, random state 42. Threshold selection holds out normalized names using the release-period seed, then refits on historical rows only.

The v1 unseen-name membership conservatively includes all names in the supplied production training source (including validation); its exact historical fit membership was not recorded. Website declarations are proxy labels, and Cookiebot/OneTrust coverage is not representative of all websites.

Model SHA-256: 3c73ff1db5938899c5b6d0de3884460d725a28279441fb4f3ad1a9823401cef0

Lookup SHA-256: 54af011b28a6b291f36d8236c3156e50ebf151bb9fa79847d547ed3b58224149

Dataset SHA-256: 3c958ee2f699986c7a4e2b214cc3bca3a8a9b6a12bd21a48ed44cbfbe23cb6f8

## 5. Validation evidence

npm test: 133 tests; passed=True. Both real Browser Use scenarios invoke the candidate model. The test adapter is isolated from the shipped bridge.

The included crawl data uses 12 shards. A separate browser fixture exercises a usable Cookiebot declaration, consent, reload, 38-feature extraction, and content exclusion without any public requests. Fixture results are not added to the dataset or its yield.

See privacy-audit.json for the SHA-256 output inventory and grep-proof.txt for actual zero-match checks. The privacy audit is run after this report is written.

## 6. Decision

No model PR is eligible.
Package defaults are unchanged. No package publication is performed.
