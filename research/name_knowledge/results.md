# CookieGuard name knowledge: frozen study results

On the natural-frequency M-A mix, CookieGuard reached 87.0% accuracy and 80.6% balanced accuracy, versus 76.0% for model-only K0. On the 300 identical cookies, cloud AI and CookieGuard were not statistically distinguishable (76.1% vs 71.3% balanced accuracy, difference −1.0 to 10.2); on the fully unseen subset the cloud was clearly better (74.3% vs 54.3%). The cloud result is a separate name-balanced 300-row M-B sample, not an M-A estimate. The deletion test remains the separate proof of the login cookie.

## 1. Outcome

The frozen selected method was **N1**. It improved balanced accuracy over model-only K0 on M-A. The known-name layer hit 10,334/11,160 rows (92.6%); 826 rows were unseen.

## 2. Same-row cloud comparison

On the 300 identical cookies, cloud AI and CookieGuard were not statistically distinguishable (76.1% vs 71.3% balanced accuracy, difference −1.0 to 10.2); on the fully unseen subset the cloud was clearly better (74.3% vs 54.3%). The cloud comparison uses the majority of three runs; individual cloud runs 1–3 were 76.1%, 76.5%, and 75.4%. The fixed fully unseen subset contained 114 rows.

Cloud AI reads cookie names and domains and can use general web knowledge. CookieGuard’s known-name layer uses only its own labeled data and the Apache-2.0 Open Cookie Database; its model sees cookie attributes and a third-party flag but no domain identity. CookieGuard can feed the later run-time deletion test; description-only cloud classification cannot prove the login cookie. Cloud prompts went to OpenAI; local CookieGuard used no network. Saved CLI metadata did not expose cost.

| Slice | Method | Balanced accuracy [95%] | Precision [95%] | Recall [95%] | TN / FP / FN / TP |
|---|---|---:|---:|---:|---|
| Full M-B sample | CookieGuard | 71.3% [66.1%, 76.4%] | 77.0% [71.1%, 83.0%] | 79.1% [72.9%, 84.8%] | 75 / 43 / 38 / 144 |
| Full M-B sample | cloudRun1 | 76.1% [71.0%, 80.6%] | 77.5% [71.9%, 82.7%] | 94.5% [91.2%, 97.4%] | 68 / 50 / 10 / 172 |
| Full M-B sample | cloudRun2 | 76.5% [71.6%, 81.0%] | 77.8% [72.1%, 82.9%] | 94.5% [91.2%, 97.4%] | 69 / 49 / 10 / 172 |
| Full M-B sample | cloudRun3 | 75.4% [70.4%, 80.2%] | 77.0% [71.5%, 82.3%] | 94.0% [90.3%, 97.2%] | 67 / 51 / 11 / 171 |
| Full M-B sample | cloudMajority | 76.1% [71.0%, 80.7%] | 77.5% [71.9%, 82.6%] | 94.5% [91.2%, 97.4%] | 68 / 50 / 10 / 172 |
| Sample M-U | CookieGuard | 54.3% [45.4%, 63.2%] | 52.7% [38.2%, 65.9%] | 52.7% [38.8%, 65.4%] | 33 / 26 / 26 / 29 |
| Sample M-U | cloudRun1 | 74.3% [67.3%, 81.3%] | 66.2% [55.0%, 76.2%] | 92.7% [86.0%, 98.4%] | 33 / 26 / 4 / 51 |
| Sample M-U | cloudRun2 | 75.2% [67.8%, 82.2%] | 67.1% [56.2%, 77.2%] | 92.7% [86.0%, 98.4%] | 34 / 25 / 4 / 51 |
| Sample M-U | cloudRun3 | 73.4% [65.6%, 80.8%] | 65.8% [54.4%, 75.9%] | 90.9% [83.0%, 98.0%] | 33 / 26 / 5 / 50 |
| Sample M-U | cloudMajority | 74.3% [67.0%, 81.1%] | 66.2% [55.3%, 76.2%] | 92.7% [86.0%, 98.4%] | 33 / 26 / 4 / 51 |

Cloud-majority minus CookieGuard balanced accuracy was 4.7% [-1.0%, 10.2%] on the full sample and 20.0% [10.2%, 29.7%] on its M-U subset.

## 3. Crawl and populations

The crawl attempted 7,440 ranks (7,436 accepted attempts), found 359 usable Cookiebot/OneTrust sites, retained 11,160 rows and 1,620 normalized names, and stopped because `frame-exhausted`. Restarts: 1. Discarded sites: 4.

| View | Rows | Names | Sites | Tracker | Not tracker |
|---|---:|---:|---:|---:|---:|
| M-A | 11,160 | 1,620 | 359 | 8,423 | 2,737 |
| M-B | 1,620 | 1,620 | 286 | 983 | 637 |
| M-U | 826 | 580 | 218 | 410 | 416 |
| M-K | 10,334 | 1,040 | 359 | 8,013 | 2,321 |

## 4. Local accuracy

| View | Method | Accuracy | Balanced accuracy | Precision | Recall | TN / FP / FN / TP |
|---|---|---:|---:|---:|---:|---|
| M-A | selectedN | 87.0% | 80.6% [78.6%, 82.5%] | 89.9% [87.5%, 91.8%] | 93.2% [92.3%, 94.0%] | 1859 / 878 / 572 / 7851 |
| M-A | K0 | 84.3% | 76.0% [74.1%, 77.8%] | 87.6% [84.9%, 89.6%] | 92.2% [90.9%, 93.4%] | 1634 / 1103 / 653 / 7770 |
| M-A | K1 | 67.4% | 71.7% [68.9%, 73.9%] | 90.7% [87.8%, 92.6%] | 63.3% [58.5%, 67.3%] | 2191 / 546 / 3094 / 5329 |
| M-A | v1 | 63.5% | 63.3% [62.1%, 64.5%] | 84.1% [81.4%, 86.2%] | 63.7% [62.6%, 64.7%] | 1724 / 1013 / 3058 / 5365 |
| M-A | everythingTracker | 75.5% | 50.0% [50.0%, 50.0%] | 75.5% [72.1%, 78.3%] | 100.0% [100.0%, 100.0%] | 0 / 2737 / 0 / 8423 |
| M-B | selectedN | 77.0% | 75.0% [72.8%, 77.2%] | 79.1% [76.5%, 81.4%] | 84.5% [82.3%, 86.7%] | 417 / 220 / 152 / 831 |
| M-B | K0 | 71.6% | 68.9% [66.7%, 71.3%] | 74.2% [71.7%, 76.8%] | 81.6% [79.3%, 84.0%] | 358 / 279 / 181 / 802 |
| M-B | K1 | 65.3% | 69.1% [67.2%, 71.2%] | 85.6% [82.9%, 88.6%] | 51.5% [48.6%, 54.6%] | 552 / 85 / 477 / 506 |
| M-B | v1 | 58.7% | 60.8% [58.3%, 63.2%] | 72.8% [69.3%, 76.0%] | 51.1% [48.1%, 54.3%] | 449 / 188 / 481 / 502 |
| M-B | everythingTracker | 60.7% | 50.0% [50.0%, 50.0%] | 60.7% [58.3%, 63.0%] | 100.0% [100.0%, 100.0%] | 0 / 637 / 0 / 983 |
| M-U | selectedN | 61.4% | 61.4% [56.8%, 65.7%] | 59.4% [51.8%, 66.2%] | 70.0% [64.2%, 75.4%] | 220 / 196 / 123 / 287 |
| M-U | K0 | 61.4% | 61.4% [56.8%, 65.7%] | 59.4% [51.8%, 66.2%] | 70.0% [64.2%, 75.4%] | 220 / 196 / 123 / 287 |
| M-U | K1 | 60.0% | 59.8% [55.0%, 64.8%] | 72.5% [59.4%, 85.0%] | 31.5% [22.3%, 40.1%] | 367 / 49 / 281 / 129 |
| M-U | v1 | 58.2% | 58.1% [53.4%, 62.7%] | 60.6% [51.6%, 68.6%] | 45.4% [38.4%, 52.5%] | 295 / 121 / 224 / 186 |
| M-U | everythingTracker | 49.6% | 50.0% [50.0%, 50.0%] | 49.6% [43.9%, 55.0%] | 100.0% [100.0%, 100.0%] | 0 / 416 / 0 / 410 |
| M-K | selectedN | 89.1% | 82.5% [80.4%, 84.6%] | 91.7% [89.5%, 93.5%] | 94.4% [93.7%, 95.0%] | 1639 / 682 / 449 / 7564 |
| M-K | K0 | 86.1% | 77.2% [75.2%, 79.2%] | 89.2% [86.8%, 91.1%] | 93.4% [92.2%, 94.4%] | 1414 / 907 / 530 / 7483 |
| M-K | K1 | 68.0% | 71.7% [69.1%, 73.9%] | 91.3% [88.7%, 93.1%] | 64.9% [60.4%, 68.5%] | 1824 / 497 / 2813 / 5200 |
| M-K | v1 | 63.9% | 63.1% [61.9%, 64.3%] | 85.3% [82.8%, 87.4%] | 64.6% [63.6%, 65.7%] | 1429 / 892 / 2834 / 5179 |
| M-K | everythingTracker | 77.5% | 50.0% [50.0%, 50.0%] | 77.5% [74.3%, 80.0%] | 100.0% [100.0%, 100.0%] | 0 / 2321 / 0 / 8013 |

All intervals and paired selected-N differences are saved in `results.json`; M-A/M-U/M-K resample sites and M-B resamples name rows, with 1,000 valid draws.

## 5. Dictionary and selection

D1 used 246,505 permitted CookieGuard rows. D2 is the Apache-2.0 Open Cookie Database at commit `7786335566460016f07a50705a92fc781c976f6f`. Selection used 549 frozen 2026 development rows: N1 75.9%, N2 75.8%, N3 74.2%; tie set: N1, N2. The select-side rows were excluded from Selection D1.

| First hit | Rows | Hit rate | Label accuracy |
|---|---:|---:|---:|
| D1_raw | 9,774 | 87.6% | 89.6% |
| D1_normalized | 408 | 3.7% | 81.9% |
| D2_exact | 87 | 0.8% | 78.2% |
| D2_wildcard | 65 | 0.6% | 73.8% |

## 6. Timing and privacy

The complete N1 path averaged 0.037 ms/cookie in warm 11-cookie batches. Startup-inclusive mean was 262.8 ms/process. End-to-end scoring of the frozen cloud sample averaged 0.012 ms/cookie. Cloud averaged 5.49 seconds/cookie. Local timing made no network requests.

Incremental value scans covered crawl and local artifacts within the active restart scope. Prompts were admitted by exact structural rendering (A1); replies were admitted as exact Boolean objects (A2). Replies were not value-scanned because the cloud received no values.

## 7. Cases

Most common normalized names where N1 corrected a K0 error:
- `bm_sv` — 31 rows; D1 raw
- `__eoi` — 30 rows; D1 raw
- `sa-user-id-v0` — 23 rows; D1 raw
- `fpid` — 22 rows; D1 raw
- `fplc` — 21 rows; D1 raw
- `bm_sz` — 14 rows; D1 raw
- `cf_clearance` — 14 rows; D1 raw
- `fpgsid` — 13 rows; D1 raw
- `_lr_retry_request` — 12 rows; D1 raw
- `sailthru_visitor` — 12 rows; D1 raw

Most common normalized names N1 still got wrong:
- `__cf_bm` — 128 rows; D1 raw
- `muid` — 28 rows; D1 raw
- `mr` — 25 rows; D1 raw
- `xid` — 24 rows; D1 normalized
- `sm` — 23 rows; D1 raw
- `rt` — 22 rows; D1 raw
- `akloc` — 21 rows; miss
- `anonchk` — 21 rows; D1 raw
- `clid` — 20 rows; D1 raw
- `awsalbcors` — 19 rows; D1 raw

## 8. Limitations

- Consent-banner declarations can be noisy or conflicting.
- Only Cookiebot and OneTrust sites are represented.
- D1 includes 2026 development labels in the deployment/test condition.
- OCD categories are a third party’s judgment.
- The cloud comparison is a name-balanced 300-row sample, not the all-row M-A population.
- Tracker classification is not login-cookie identification.

Stopped before §13: no product, model, demo, showcase, movie, or submission files were changed.
