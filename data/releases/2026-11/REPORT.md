# Monthly refresh report: 2026-11

**Candidate artifacts only. Every model release requires human approval.**

Tranco list: Y897G. Attempted sites: 9375; visited sites: 7037; usable sites: 309; labeled cookies: 7542.

## 1. Gates

| Gate | Result | Evidence |
|---|---|---|
| No regression | PASS | paired balanced-accuracy lower 95% bound >= -0.01 against both production baselines; {"lowerBounds": {"production-rules": 0.09969352505260932, "production-v1": 0.17658504811161607}} |
| Unseen names | FAIL | paired balanced-accuracy lower 95% bound >= -0.01 against both production baselines; {"lowerBounds": {"production-rules": -0.016915102892260243, "production-v1": -0.01621892552495028}} |
| Canaries | PASS | npm test with candidate preload; real Browser Use candidate bridge: FAIL CG001 / PASS |
| Parity | PASS | ONNX versus scikit-learn <= 1e-5 on 1000 rows; {"maxAbsoluteDifference": 4.4223958906020044e-07} |
| Privacy | PASS | every included shard passed its own cross-scan and structural check |
| Coverage | PASS | excluded reserved sites / frame <= 25%; at least one included shard; {"evidenceValid": true, "excludedRate": 0.0625, "excludedSites": 625, "includedSites": 9375, "plannedSites": 10000} |
| Health | PASS | usable / visited >= 1.5%; robots response/protocol failures / attempted <= 20%; {"attemptedSites": 9375, "robotsAvailabilityPassed": true, "robotsUnavailableDefinition": "robotsStatus server-error, redirect-limit, too-large, or network-error; each site counted once", "robotsUnavailableRate": 0.030613333333333333, "robotsUnavailableSites": 287, "unreachableOrTlsDefinition": "unreachable plus tls-error; study navigation-failed equivalent; reported only, no gate", "unreachableOrTlsRate": 0.19690666666666667, "unreachableOrTlsSites": 1846, "usableSiteYield": 0.04391075742503908, "usableSites": 309, "visitedSites": 7037, "yieldPassed": true} |

## 2. Evaluation

Tracker is the positive class. Intervals are 95% site-cluster bootstrap intervals from 1,000 seeded draws. Paired differences use the same sampled sites. Unseen comparisons use rows unseen to both methods. An interval is unavailable if fewer than 950 draws define the metric or fewer than two sites are available.

| Method | Subset | Rows | Sites | Balanced accuracy | Precision | Recall |
|---|---|---:|---:|---|---|---|
| candidate | natural | 7542 | 309 | 83.39% [81.92, 84.92] | 91.25% [89.70, 92.67] | 93.82% [92.72, 94.88] |
| candidate | unseenNames | 300 | 116 | 61.64% [55.17, 68.57] | 66.07% [50.00, 81.48] | 33.33% [22.22, 46.73] |
| production-rules | natural | 7542 | 309 | 71.62% [69.24, 73.70] | 92.09% [90.16, 93.65] | 58.26% [53.70, 62.22] |
| production-rules | unseenNames | 7542 | 309 | 71.62% [69.24, 73.70] | 92.09% [90.16, 93.65] | 58.26% [53.70, 62.22] |
| production-v1 | natural | 7542 | 309 | 64.13% [62.90, 65.27] | 84.29% [81.87, 86.21] | 64.27% [63.29, 65.28] |
| production-v1 | unseenNames | 6802 | 307 | 63.08% [61.95, 64.13] | 83.03% [80.42, 85.34] | 61.45% [60.23, 62.61] |
| study-N1-C2 | natural | 7542 | 309 | 81.09% [79.53, 82.61] | 89.98% [88.19, 91.62] | 93.46% [92.44, 94.37] |
| study-N1-C2 | unseenNames | 458 | 150 | 62.45% [56.97, 68.12] | 58.05% [48.57, 67.01] | 58.62% [49.08, 67.43] |

### Paired candidate differences

| Baseline | Subset | Rows | Balanced accuracy difference |
|---|---|---:|---|
| production-rules | natural | 7542 | 11.78% [9.97, 13.92] |
| production-rules | unseenNames | 300 | 2.87% [-1.69, 7.88] |
| production-v1 | natural | 7542 | 19.26% [17.66, 20.82] |
| production-v1 | unseenNames | 300 | 5.11% [-1.62, 12.16] |
| study-N1-C2 | natural | 7542 | 2.30% [1.51, 3.10] |
| study-N1-C2 | unseenNames | 295 | 0.65% [-4.05, 5.12] |

### Lookup and declaration disagreement

| Method | Lookup hits | Hit rate | Hit accuracy | Disagreements |
|---|---:|---|---|---:|
| candidate | 7225 | 95.80% | 89.51% | 758 |
| production-rules | 0 | 0.00% | N/A | 0 |
| production-v1 | 0 | 0.00% | N/A | 0 |
| study-N1-C2 | 7068 | 93.72% | 88.94% | 782 |

Normalized names with conflicting site labels: 145.

## 3. Crawl and privacy

| Status | Sites |
|---|---:|
| blocked | 948 |
| consent-api-missing | 2 |
| declaration-failed | 13 |
| navigation-failed | 58 |
| no-matched-labeled-cookie | 10 |
| no-supported-cmp | 5580 |
| no-usable-declaration | 59 |
| redirect-outside-frame | 51 |
| reload-failed | 4 |
| robots-disallowed | 186 |
| robots-unavailable | 2131 |
| usable | 309 |
| visited-not-recorded | 24 |

### Resume plan: 43627693953

Resume crawls only remainingSiteIds; recorded and visitedNotRecorded sites are never revisited.

Recorded: 7204; visited but not recorded: 60; never visited: 2736. Kept usable sites: 235; kept cookie rows: 5826.

Explicit visited-prefix inputs: 2=36.

| Shard | State | Recorded | Visited, not recorded | Remaining | Kept rows |
|---|---|---:|---:|---:|---:|
| 1 | complete | 625 | 0 | 0 | 463 |
| 2 | failed-closed | 0 | 36 | 589 | 0 |
| 3 | complete | 625 | 0 | 0 | 528 |
| 4 | complete | 625 | 0 | 0 | 328 |
| 5 | complete | 625 | 0 | 0 | 499 |
| 6 | complete | 625 | 0 | 0 | 380 |
| 7 | complete | 625 | 0 | 0 | 628 |
| 8 | complete | 625 | 0 | 0 | 223 |
| 9 | complete | 625 | 0 | 0 | 812 |
| 10 | interrupted | 420 | 4 | 201 | 317 |
| 11 | interrupted | 388 | 4 | 233 | 369 |
| 12 | interrupted | 384 | 4 | 237 | 706 |
| 13 | interrupted | 372 | 4 | 249 | 152 |
| 14 | never-started | 0 | 0 | 625 | 0 |
| 15 | interrupted | 400 | 4 | 221 | 298 |
| 16 | interrupted | 240 | 4 | 381 | 123 |

Recorded prefixes are preserved by digest. Their original batch scans are source evidence; old cookie contents are unavailable for a new scan. New visits retain a separate privacy receipt. Visited-not-recorded attempts have unknown document/robots outcomes and no cookie rows.


### Shard exclusions

Included sites: 9375; excluded reserved sites: 625 / 10000.

Publication requires at most 25% excluded sites. Health uses included shards only. Excluded payloads are removed before the deliverable audit and upload.

| Excluded shard | Reserved sites | Reason code |
|---|---:|---|
| 2 | 625 | privacy-rejected |


### Coverage and Health

| Measure | Count | Rate | Rule |
|---|---:|---:|---|
| Usable / visited | 309 / 7037 | 4.39% | At least 1.5% |
| Robots response/protocol failures / attempted | 287 / 9375 | 3.06% | At most 20% |
| Unreachable + TLS / attempted | 1846 / 9375 | 19.69% | Report only; no gate |

Visited means robots permitted an origin and document navigation started. The 20% cap counts only server-error, redirect-limit, too-large, and network-error, once per site. Unreachable plus tls-error is the study navigation-failed equivalent and has no gate. Counts use the final robots outcome after any HTTP fallback.

| CMP family | Attempted sites |
|---|---:|
| Cookiebot | 117 |
| OneTrust | 320 |
| None | 8938 |

| Robots status | Sites |
|---|---:|
| absent-4xx | 1349 |
| allowed | 5682 |
| disallowed | 187 |
| network-error | 163 |
| not-checked | 24 |
| redirect-limit | 16 |
| server-error | 62 |
| tls-error | 205 |
| too-large | 46 |
| unreachable | 1641 |

Visited but not recorded: 24. These count as attempted; their document/robots outcomes are unknown and they are never revisited.

Monthly releases are not directly comparable with the November 2026 study crawl: this crawler identifies itself as CookieGuardResearch/1.0, while the study used a Chrome user agent. Hosted Actions runs also originate from datacenter addresses. Consent managers may treat these requests differently; the hosted pilot measures their effect on yield.


No site is revisited. A site with an unverifiable robots policy is skipped conservatively. All shards run at concurrency 4 with a 30-second site cap. Cookies remain in memory; no browser traces, screenshots, storage-state files, page text, or raw exceptions are exported.

Privacy receipts record the frozen crawler's incremental cross-scan: strings of at least 8 characters, with independently observed cookie names, domains, and numeric coincidences accounted for. Short strings are protected by fixed schemas and exclusion of contents fields. Grep is an additional check, not proof that arbitrary unknown secrets are impossible.

## 4. Training and provenance

Training rows: 320993; normalized names: 10993; threshold: 0.53. No current-month refresh rows enter training or lookup construction.

C2: 150 trees, depth 12, minimum split 5, minimum leaf 2, balanced weights, random state 42. Threshold selection holds out normalized names using the month seed, then refits on historical rows only.

The v1 unseen-name membership conservatively includes all names in the supplied production training source (including validation); its exact historical fit membership was not recorded. Website declarations are proxy labels, and Cookiebot/OneTrust coverage is not representative of all websites.

Model SHA-256: b33d9aa44f00401f4722dbac7d0208a55dff3e6ec5c4a192598c280b179d20c0

Lookup SHA-256: 54af011b28a6b291f36d8236c3156e50ebf151bb9fa79847d547ed3b58224149

Dataset SHA-256: e4795ca22b93fefc7bbef03164796d825533db4626fc03987c3cf79b718bec09

## 5. Validation evidence

npm test: 133 tests; passed=True. Both real Browser Use scenarios invoke the candidate model. The test adapter is isolated from the shipped bridge.

The included crawl data uses 15 shards. A separate browser fixture exercises a usable Cookiebot declaration, consent, reload, 38-feature extraction, and content exclusion without any public requests. Fixture results are not added to the dataset or its yield.

See privacy-audit.json for the SHA-256 output inventory and grep-proof.txt for actual zero-match checks. The privacy audit is run after this report is written.

## 6. Decision

No model PR is eligible.
Package defaults are unchanged. No package publication is performed.
