# CookieGuard (AI layer + decision layer) vs cloud AI

**Cloud AI was more accurate than CookieGuard on the frozen 300-name comparison:** CookieGuard balanced accuracy was 64.7% (59.0%–69.5%); the three-run cloud majority was 77.3% (73.0%–81.3%).

CookieGuard ran locally in 0.0283 ms per cookie after warm-up and 33.34 ms per cookie startup-inclusive. Cloud AI averaged 3.83 seconds per cookie and sent the listed cookie metadata to a server. CookieGuard sent nothing, had no per-run service cost, and can feed the run-time deletion test that proves the login cookie; description-only cloud classification cannot prove it.

Cloud cost was not available from the saved CLI metadata. If the cloud result is more accurate, that lead is stated above without qualification.

## 1. Headline comparison

| Method | Balanced accuracy | Precision | Recall |
|---|---:|---:|---:|
| CookieGuard | 64.7% (59.0%–69.5%) | 65.0% (55.2%–74.3%) | 50.8% (41.8%–59.0%) |
| Cloud run 1 | 77.5% (73.1%–81.8%) | 66.9% (59.5%–73.4%) | 90.2% (84.7%–94.9%) |
| Cloud run 2 | 77.9% (73.7%–82.0%) | 67.0% (59.4%–73.7%) | 90.9% (85.1%–95.5%) |
| Cloud run 3 | 75.5% (71.0%–79.9%) | 65.2% (58.0%–72.1%) | 87.9% (81.9%–93.4%) |
| Cloud majority | 77.3% (73.0%–81.3%) | 66.3% (59.0%–72.9%) | 90.9% (85.1%–95.5%) |

| Method | TN | FP | FN | TP |
|---|---:|---:|---:|---:|
| CookieGuard | 132 | 36 | 65 | 67 |
| Cloud run 1 | 109 | 59 | 13 | 119 |
| Cloud run 2 | 109 | 59 | 12 | 120 |
| Cloud run 3 | 106 | 62 | 16 | 116 |
| Cloud majority | 107 | 61 | 12 | 120 |

| Cloud method minus CookieGuard | BA difference | Paired 95% range |
|---|---:|---:|
| Cloud run 1 | 12.9% | 7.5%–18.5% |
| Cloud run 2 | 13.2% | 7.8%–18.9% |
| Cloud run 3 | 10.8% | 5.3%–16.8% |
| Cloud majority | 12.6% | 7.3%–18.3% |

Cloud method: gpt-6-astra, reasoning effort max; 18 fresh ephemeral sessions, three per batch of 50; tools, memory, and web off. 18 of 18 replies passed the exact schema.

**Fairness note.** Cloud AI reads cookie domain names and can use general web knowledge. CookieGuard sees cookie attributes and a third-party flag, but no domain identity.

## 2. What ran

The clean crawl used Tranco 947N2 ranks 3,401–12,560, after excluding ranks 1–3,400 and every name from old training/validation and the 2026 development set. It attempted 9,160 sites, retained 1,368 rows from 262 usable sites, and froze 1,002 normalized names. Stop reason: `name-target`.

Dropped for old training/validation names: 9,706. Dropped for 2026 development names: 7,300. Unmatched declarations: 14,498. The coordinator had 4 disclosed restarts and never revisited an attempted site.

## 3. Cases

**Most common names where K3 corrected at least one component:** `__ps_did` (5), `tmx_guid` (4), `__attentive_session_id` (3), `_bts` (3), `_cc-x` (3), `_hashv` (3), `hdm_privacy_disclosure` (3), `mint` (3), `s_ptc` (3), `tst` (3)

**Most common names K3 still got wrong:** `bvbrandsid` (7), `hdm_cmp` (6), `tfpsi` (6), `_affclk` (5), `_attn_` (5), `_perhip` (5), `mosb` (5), `__attentive_cco` (4), `__attentive_dv` (4), `__attentive_id` (4)

- `cf_clearance`: 0 retained row(s); excluded as prior 2026 development name or absent
- `bm_sv`: 0 retained row(s); excluded as prior 2026 development name or absent
- `hubspotutk`: 0 retained row(s); excluded as prior 2026 development name or absent

## 4. Limits

- Consent-banner declarations are noisy and sometimes conflicting.
- Only Cookiebot and OneTrust sites are represented.
- Geography, browser behavior, blocking, and crawl attrition limit generalization.
- This all-unseen test is the hardest slice by construction: every name seen in training, the 2021 validation set, or the 2026 development set was excluded, leaving mostly opaque, site-specific names.
- The saved 2026 dataset became development data; names can overlap across its site-based fit/select split.
- K5 used validation-stage C2 probabilities for 2021 and final-v3 probabilities for 2026.
- Component errors are correlated. Tracker classification is not login-cookie identification, and agreement is not a security verdict.

## 5. Inside CookieGuard: how its parts contribute

### 5.1 Frozen development selection

Validation-stage C2 reproduced all five saved metrics and bootstrap ranges exactly. K3 was selected at `t_low=0.31` and `t_high=0.57`.

| Candidate | 2021 BA | 2026 BA | Mean BA |
|---|---:|---:|---:|
| K2 | 68.2% | 73.5% | 70.8% |
| K3 | 68.6% | 74.7% | 71.7% |
| K4 | 67.7% | 73.8% | 70.7% |
| K5 | 67.3% | 74.9% | 71.1% |

K5 fit-row base rates: 2021 tracker 36.7%, 2026 tracker 73.6%; each era/class cell was weighted to an effective 50/50 class rate.

### 5.2 New clean test

| Method | N-B balanced accuracy | N-A balanced accuracy |
|---|---:|---:|
| K0 | 65.6% (62.7%–68.9%) | 63.2% (59.3%–67.1%) |
| K1 | 62.1% (59.6%–64.5%) | 62.3% (58.1%–66.1%) |
| K2 | 65.2% (62.4%–68.0%) | 63.1% (59.0%–67.5%) |
| K3 | 65.3% (62.6%–68.1%) | 63.2% (59.3%–67.7%) |
| K4 | 65.4% (62.6%–68.5%) | 63.9% (59.8%–68.2%) |
| K5 | 65.2% (62.6%–68.0%) | 63.8% (59.3%–68.3%) |
| v1 | 59.9% (56.9%–62.8%) | 57.7% (53.9%–61.4%) |
| everythingTracker | 50.0% (50.0%–50.0%) | 50.0% (50.0%–50.0%) |

On fully unseen cookie names, the AI layer is the strongest single classifier we have (65.6% balanced accuracy, vs 62.1% for the rule signals and 59.9% for model v1). Combining the two did not raise accuracy (K3 65.3%, a tie with the AI layer within the 95% range; +3.3 points over the rules). What the cross-check adds is reliability: when the AI layer and the decision layer agree (64% of cookies), 74% of the labels are right; when they disagree, about half are. CookieGuard uses that as its 'Verify first' signal and proves the login cookie with the run-time test.

K3 − K0 on N-B: -0.3% (-3.1%–2.3%). K3 − K1: 3.3% (1.0%–5.6%). **The combination did not beat both parts on this test.**

### 5.3 Agreement and disagreement

| Group | Share | Component accuracy | K3 accuracy |
|---|---:|---:|---:|
| Agreement | 64.3% | 74.1% | 74.1% |
| Disagreement | 35.7% | 50.6% | 54.7% |

Agreement accuracy N-B 95% range: 70.3%–77.6%. Agreement is a cross-check signal, not proof. Its point accuracy is 74.1%, below the required 0.80 lower-bound rule, so the future chip is **Agree**, never Confident. Disagreements remain **Verify first**.

The future `models/active.json` default remains K2 at its frozen validation threshold, labeled as the protocol specifies. This was locked before the cloud result and was not revisited here.

## 6. Reproducibility and privacy

The original live prompt preflight recorded 11 forbidden text matches and then exited; that failure remains preserved. Under Amendment A1, all six prompts were admitted only after byte-for-byte structural verification against the fixed template and frozen `sample_public.json`. Under Amendment A2, replies were not value-scanned because the cloud received no values; each reply was admitted structurally only if it was exactly one object containing its 50 expected IDs with Boolean values. There were 18 valid replies out of 18.

The Amendment A3 receipt is explicitly hybrid, not a final value-scanned receipt: 2,289 incremental crawl receipts cover crawl artifacts; development and local-analysis artifacts remain locked; A1 covers prompts; A2 covers replies. The 11-match failure and all 4 coordinator restarts are disclosed.

The fixed predictions, N-B selection, 1,000 paired bootstrap resamples per view, cloud replies, and timing records are saved beside this report. `analyze.py` regenerates `results.json` and this report without crawling, fitting, local inference, or cloud calls. HEAD and locked product/model files remain unchanged.
