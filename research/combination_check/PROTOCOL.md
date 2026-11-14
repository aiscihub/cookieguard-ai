# CookieGuard (AI layer + decision layer) vs cloud AI

Draft for approval — November 11, 2026, America/Los_Angeles.

**Status: NOT APPROVED. Only this protocol may be written now. No crawling, feature preparation, model fitting, scoring, hashing of study inputs, cloud-AI calls, or demo changes are authorized until the user approves this protocol.** Show this draft in the conversation for the user and Avelyn to review; do not send it elsewhere.

Source task: `waicy_2026/codex_task_combination_check.md`. Study results are due November 14; any separately approved demo integration is due November 18. Stop after the study report and await another approval before integration.

## 1. Interpretations requiring approval

1. **K3 is distinct from K2.** The original task duplicated K2 by mistake. This revision uses the corrected two-threshold K3 in section 3: `(r AND p ≥ t_low) OR (NOT r AND p ≥ t_high)`, with `t_low ≤ t_high`. K2 is its `t_low = 0` special case.
2. **The old 2026 test becomes development data.** The detailed validation instructions govern the contradictory sentence that says neither earlier test may choose anything. The privacy-validated push-2 dataset may be used for the specified fit/select procedure. The 2021 test rows remain forbidden for fitting, threshold choice, or selection. Only the new crawl is a confirmatory test.
3. **Some ranks after 3,300 were already touched.** An earlier `accuracy_push2/fresh_test/rows-03301.jsonl.partial` exists. Do not call every rank from 3,301 untouched. Conservatively exclude ranks 3,301–3,400, plus any additional previously attempted chunks identified from operational records after approval. Freeze the remaining frame before the new crawl.
4. **Use the exact vendored rule semantics.** The saved push-2 72.8% score used a Python reproduction. The subsequent audit found 72.6% for the exact JavaScript classifier because normalization changes three near-tie decisions. Neither saved result changes. This study uses the vendored classifier's normalized-score ordering everywhere.
5. **Use validation-stage C2 probabilities for 2021 development rows.** Final C2 was refitted on all training names, including the former validation names, so its probabilities would be optimistic there. Reproduce the validation-stage C2 from candidate-training names only and use its probabilities only for 2021 development measurement, subject to the exact parity gate in section 4.1. The frozen final `main.onnx` remains the only v3 used on 2026 development rows and the new test.
6. **K5 has three explicitly permitted context inputs.** The task's K5 feature list supplements its shorter general input list. No other features, raw names, domain identities, dictionary additions, or embeddings enter K5.

Approving this draft approves these interpretations. Until then, do not execute the study.

## 2. Scope and immutable inputs

Work only in `waicy_2026/combination_check/` during the study. Do not modify any existing model, package, integration, extension, backend, previous study, showcase, or lock file. Do not retrain v1 or v3. The reproduced validation-stage C2 is a measuring tool only; the only new fitted decision estimator is K5. Do not pull, switch branches, commit, submit, or publish. Cloud-AI calls are allowed only for the frozen headline comparison in section 10, after its sample and hash are locked. HEAD must remain `1f0ede14ee9d5e3c990a575f8eeae986a588d346`.

Use these existing sources read-only:

| Input | Location or expected identity |
|---|---|
| v3 / C2 | `waicy_2026/accuracy_push/model/main.onnx`; expected SHA-256 `a4f3905c7f4ccbd061846e5e3e1c20a51a172daa37f31a8af16e7233e6be2a93`; tracker threshold 0.40 |
| Feature order and 2021 context features | `waicy_2026/accuracy_push/features/` |
| Old validation-name assignments | `waicy_2026/accuracy_push/validation_split.json` |
| Old train/test assignments and normalization | `waicy_2026/retrain_test/split.json` and its approved normalization implementation/tests |
| 2026 development data | `waicy_2026/accuracy_push2/finalization_retry/fresh_test/`; saved manifest reports 4,111 rows, 833 normalized names and 165 usable sites |
| 2026 privacy and integrity evidence | `accuracy_push2/finalization_retry/value_check.json`, `status.json`, and `locks.txt` |
| Rules | `waicy_2026/local_apps_test/node_modules/@aiscihub/cookieguard-core/vendor/engine.cjs`; expected SHA-256 from the saved runtime manifest: `bcc2718198f0798b77505c27efcfd0bf8a251cfd90dc31b0daf375dc9df7e4bd` |
| Rule near-tie audit | `accuracy_push/fairness_correction_2026-11-10/fresh_rule_tie_audit.json` |
| Site list | Existing `accuracy_push2/inputs/tranco-947N2-top20000.csv`, list 947N2; do not substitute a newer list |
| Crawl declaration method | `accuracy_push2/PROTOCOL.md`, sections 3–5; corrected recovery implementation is a reference, not a script to rerun |
| v1 reference | `extension-standalone/model/cookieguard_model.onnx` and its class metadata |
| Runtime | Existing `retrain_test/.venv`, local Playwright/Chromium and vendored Node dependencies |

The expected identities and dataset counts above come from saved evidence, not computations performed for this draft. After approval, verify them, record exact input/script/package hashes and versions in a new manifest, and stop on an unexplained mismatch. Require the prior 2026 status to be complete and its privacy receipt to pass. Do not use the interrupted original crawl or failed recovery as validation rows.

## 3. Common outputs and candidate definitions

Let:

- `p` be class-1 P(tracker) on the same 38 ordered context features used by the rules: reproduced validation-stage C2 for 2021 development rows, and frozen final C2 for 2026 development rows and the new test;
- `r` be whether the exact vendored classifier returns `type === "tracking"`;
- `s` be its four raw scores, ordered authentication, tracking, preference, other;
- `q` be its normalized tracking score: tracking raw score divided by the sum of the four raw scores, with the vendored zero-total behavior;
- `m` be the fixed model reference decision `p ≥ 0.40`.

Copy `classifyRuleBased` into a study script solely to return the four raw scores as well. Keep all arithmetic, normalization, class ordering, sorting and label semantics unchanged. Check its returned label and normalized scores against the unmodified vendored function on every processed row. Do not select the label by the largest raw score: that would repeat the near-tie discrepancy. Expose `name_matches_tracking` for the prescribed input audit, but do not invent a new gate using it.

| ID | Exact tracker decision | Threshold |
|---|---|---|
| K0 | `p ≥ 0.40` | Fixed reference |
| K1 | `r` | Fixed reference; no probability threshold |
| K2 | `r OR p ≥ t2` | Tuned on the fixed grid |
| K3 | `(r AND p ≥ t_low) OR (NOT r AND p ≥ t_high)` | Both tuned on the fixed grid, with `t_low ≤ t_high` |
| K4 | `(p + q) / 2 ≥ t4` | Tuned on the fixed grid |
| K5 | Logistic-regression probability `≥ t5` | Fixed fitting procedure below, then grid threshold |

The grid is the 101 values `i / 100`, for integer `i` from 0 through 100. Do not round probabilities before comparison. No extra candidates, threshold restrictions, calibrators, hand-written exceptions, or post-test repairs are allowed. In particular, do not add special cases for `cf_clearance`, `bm_sv`, or `hubspotutk`.

For ranking metrics, use scores `p`, `q`, `max(p, r)`, K3's frozen branch-specific margin `p - (r ? t_low : t_high)`, `(p+q)/2`, and K5's probability, respectively. Rule and composite scores are not claimed to be calibrated probabilities. These scores do not change the decision formulas above.

### 3.1 Fixed K5 fit

Use these 12 columns, in this order:

1. Model P(tracker).
2. Four raw rule scores: authentication, tracking, preference, other.
3. Four one-hot columns for the vendored rule label, in the same class order.
4. `f_third_party_context`, `has_httponly`, `is_session_cookie`.

Use scikit-learn `LogisticRegression`: `penalty="l2"`, `C=1.0`, `solver="lbfgs"`, `fit_intercept=True`, `class_weight=None`, `tol=1e-8`, `max_iter=10000`, `random_state=2026111105`. No scaling, feature selection, hyperparameter search, or refit on select rows.

Fit once on the two fit subsets defined below, using one row per normalized name within each era. Weight each era/class cell equally: for a fit row of class `y` in era `e`, use weight `N_fit / (4 * n[e,y])`. This gives equal weight to both eras and both classes while keeping total sample weight equal to the fit-row count. Require both classes in each era's fit subset; otherwise stop without choosing a different seed or weighting scheme.

For both the 2021 and 2026 development tables, report the unweighted tracker/not-tracker base rates of the K5 fit rows and the effective weighted base rates produced by this scheme.

Require convergence. Save coefficients, intercept, class order, column order, settings, fit-row identities, versions and hashes. Check that a direct sigmoid calculation reproduces the saved estimator's probabilities within `1e-10` on all select rows. The frozen fitted combiner is used on the new test; there is no final refit.

## 4. Development splits and selection

All row ordering is deterministic: source filenames sorted lexically, then file line order. Name groups are sorted lexically for row sampling. Site IDs are sorted lexically before shuffling. Lock the split and selected row identities before fitting K5 or computing candidate selection metrics.

### 4.1 2021 development part

Use only names assigned `validation` in `accuracy_push/validation_split.json`; reject every original `test` name. Reconstruct the established V-B sample: group those rows by normalized name and choose one per name using `random.Random(2026111004)` in sorted name order.

Reproduce the validation-stage C2 by running the `train_validate.py` C2 procedure on candidate-training names only, with the same 38 features and Random Forest settings, including `random_state=42`. Before using any reproduced probability, require exact reproduction of the saved `validation_results.json`: threshold 0.40, V-B balanced accuracy `0.701548024966506`, and the saved V-A result and confusion counts. Save this parity evidence. If parity fails, stop that reproduction and select combiners on the 2026 era alone; disclose the deviation and fallback. Never save the reproduced estimator as a product model, put it in `models/`, or use it on the new test.

Shuffle the sorted validation names with `random.Random(2026111101)`. The first `floor(n/2)` names form validation-fit; the remainder form validation-select. Use the corresponding V-B rows for both halves. No additional observations of a select name may enter fitting.

Use reproduced validation-stage C2 probabilities for both 2021 halves. K5 therefore fits on validation-stage `p` for 2021 rows and final-v3 `p` for 2026 rows; disclose this explicitly in the validation table and report both fit-row base rates before and after weighting.

### 4.2 2026 development part

Treat the entire saved privacy-validated push-2 dataset as development data, explicitly retiring its status as a clean test for this task.

Shuffle its sorted site IDs with `random.Random(2026111102)`. The first `floor(n/2)` sites form fit; the rest form select. Within each side, group by normalized name and choose one row per name: fit seed `2026111103`, select seed `2026111104`.

Site sets must be disjoint. A normalized name can occur on sites on both sides: report that overlap, but do not silently switch to a name split or drop overlapping names. This is a stated limitation of the requested site split. No select-side row may enter K5 fitting. Report rows, names, sites and class counts for both eras and both sides.

### 4.3 Thresholds and winner

For each K2–K5 grid threshold, compute balanced accuracy separately on the 2021 select V-B rows and the 2026 select one-name-per-row sample. Optimize their unweighted arithmetic mean. Thus each era contributes half of the selection score regardless of sample size.

For exactly tied K2, K4, or K5 threshold scores, prefer the threshold closest to 0.50, then the higher threshold. Use integer grid indices for the distance comparison. K3 searches all 5,151 integer-grid pairs with `i_low ≤ i_high`. For exact K3 ties, prefer, in order: the smallest `|i_low - 50| + |i_high - 50|`; the higher `t_high`; then the higher `t_low`. Derive balanced accuracy from confusion counts; use exact rational comparisons for selection and the 0.005 simplicity boundary, avoiding rounding-based changes to ties.

Select among K2–K5 only. Every candidate within 0.005 of the best mean select balanced accuracy enters the simplicity tie set; prefer K2, then K3, then K4, then K5. K0 and K1 are reported references, not eligible winners. Confirm that K3 with `t_low = 0` reproduces K2 at the same `t_high`; a discrepancy is an implementation error.

Require both classes in each select era. Do not reshuffle or tune around a failed split. Report every candidate's two-era metrics, mean score, threshold, and any failed fit. A required failed candidate stops the planned comparison rather than silently shrinking the candidate set.

**Lock all K2–K5 thresholds, the selected ID, K5 weights, validation results and decision code before starting the new crawl.** No new-test result may change any of them.

## 5. Agreement and disagreement

Agreement means `m == r`, using model threshold 0.40 and the exact vendored rule label. It does not use the selected combiner's tuned threshold to redefine the component labels.

For each select era separately, and later for both new-test views, report:

- total rows and agreement/disagreement counts and shares;
- component accuracy among agreements;
- selected-combiner accuracy among agreements and among disagreements;
- counts, class balance and false-positive/false-negative counts in both groups;
- the rate and accuracy of cases where the combiner overrides an agreed component label;
- conditional balanced accuracy when both classes are present; otherwise mark it undefined.

Accuracy here means the ordinary fraction correct, distinguished from balanced accuracy. Agreement is a potentially useful verification signal, **not proof of correctness or a calibrated confidence guarantee**. Report unfavorable conditional results too. The proposed interface chip says “agree” or “disagree”; any confidence wording must be supported by the measured table.

## 6. Freeze the clean-test site frame

After approval, inspect only saved operational attempt/checkpoint metadata to identify previous push-2 crawl attempts. Do not inspect excluded partial-cookie labels or predictions to choose sites.

Start from the existing Tranco 947N2 ranks 3,301–20,000 in ascending order. Exclude the whole 3,301–3,400 partial batch. Exclude any other previously attempted batch/rank range shown by saved operational evidence, conservatively excluding a whole 100-rank chunk when its attempted extent is uncertain. Do not claim an uncertain chunk is untouched. Stop for clarification if the prior-attempt extent cannot be bounded from existing operational evidence.

Freeze the ordered eligible ranks and site identifiers, the excluded ranges and reasons, and the site-list hash before crawling. Do not add replacement sites, switch lists, or reorder the frame according to labels, yields, or model outcomes. With the currently known partial batch, the earliest eligible rank is 3,401, subject to that operational audit.

The original 2021 test set is never scored or used for choices in this study. A name that belonged only to that old test is not automatically excluded from newly observed data: apply precisely the exclusion unions in section 8 and disclose that the new test is fresh collection, not a claim that every name has never appeared in any earlier research.

## 7. Crawl conduct and declaration labels

Use public home pages, clean non-personal Playwright browser contexts, the existing Chromium installation and a recorded normal desktop Chrome user-agent. Run at most four sites concurrently, each with a 30-second whole-site deadline. Use one attempt per eligible rank. The sole fallback is HTTPS to HTTP when navigation fails before a document response, never after a certificate/TLS error. No other retries or replacement domains.

Stop immediately on blocks, CAPTCHAs, rate limits, access-denied responses or consent-region restrictions; record only a categorical reason. No logins, other forms, link-following, proxy changes, TLS bypasses, challenge workarounds, screenshots, traces, HARs, page bodies, console dumps or network transcripts.

Use the Cookiebot and OneTrust declaration endpoints, domain matching, and fixed English category mapping in sections 4–5 of the approved push-2 protocol. Do not expand supported CMP families or discover unrelated endpoints. In particular:

| Declaration | Binary label |
|---|---|
| Cookiebot Statistics / Advertising | Tracker |
| Cookiebot Necessary / Preference | Not tracker |
| Cookiebot Unclassified | Exclude |
| Standard OneTrust C0001 / C0003 | Not tracker |
| Standard OneTrust C0002 / C0004 / C0005 | Tracker |
| Renamed/custom OneTrust group | Only the pinned English mapping; otherwise exclude |

For custom group names, use the pinned order: advertising/targeting/marketing/tracking patterns, necessary patterns, analytics/performance patterns, functional/preference/security patterns, then unknown. Do not infer a renamed group's meaning from its numeric ID alone. For conflicting matching declarations, tracker takes precedence, as in push 2.

Accept all only through the detected CMP's own API. For OneTrust, register the consent-update listener before invoking `AllowAll` and wait for `OneTrustGroupsUpdated`; retain the documented Optanon fallback. For Cookiebot, use `submitCustomConsent(true, true, true)` and wait for its consent update. Missing API or failed consent update means an unusable site. Reload the final home page and wait exactly five seconds after `domcontentloaded`, within the whole-site deadline.

Read browser-context cookies and keep the first observation per `(name, normalized cookie domain, path)`. Match observed names exactly to declarations; apply the pinned normalized-domain equality/subdomain rule. Use the established normalization tests and the existing 38-feature order, including explicit `hostOnly`, lifetime at collection time, and the visited input site's registrable-domain context.

During collection, call feature extraction only. **Do not run v1, v3, rules classification, or any combiner on clean-test rows before the test freeze.** Label mapping and structural/count checks are permitted; prediction or performance inspection is not.

## 8. Exclusions, stop rule and test freeze

Exclude every observed cookie whose normalized name is in either:

1. the old CookieBlock training-name set, including all `accuracy_push` validation names;
2. the complete saved 2026 development-name set, including both its fit and select sides.

Report each exclusion count and their overlap, plus unmatched/unknown declaration and duplicate-observation counts. Preserve all eligible labeled rows in N-A, including repeated names on different sites. Do not filter suspected bot-protection cookies or disagreeing labels to improve a result.

Save only the privacy-safe metadata and features allowed by push 2: rank and hashed site ID, CMP/category/match information, cookie name/normalized name/domain/path, binary label, cookie attributes, lifetime, value-shape summary and numeric features. Save no input-site URL/domain, final URL, raw value, value hash or value prefix.

Dispatch and commit sites in deterministic batches of at most four, retaining completed results in rank order. Stop scheduling after the first complete batch reaches at least 1,000 eligible normalized names. Keep that batch intact and report any overshoot rather than trimming favorable rows or names.

The hard collection cutoff is **November 13, 2026, 18:00 America/Los_Angeles (UTC−08:00)**. Schedule nothing at or after it; abort unfinished site work at the cutoff, record the categorical cutoff outcome, and discard incomplete site buffers. Also stop if the frozen frame is exhausted. If approval arrives after the cutoff, do not start crawling.

Use atomic nonempty row shards; an empty site has an attempt record but no empty row file. Require at least 300 eligible normalized names and both truth classes to score. Otherwise report the achieved size and failure to meet the test minimum; do not extend the deadline or change exclusions.

Verify source hashes, ordered row hashes, schema, finite features, deduplication, all exclusions, and counts. Freeze the final row manifest and an integrity lock **before any test prediction**. A mutable heartbeat is not a frozen artifact. Keep original prior-run files untouched.

## 9. One clean-test evaluation

Score all six frozen K0–K5 methods, frozen v1, and everything-is-a-tracker on identical rows. For v1, use the same context-feature vectors, map its frozen class metadata, and predict tracker only when its top class is tracking. Do not repeat the old no-context comparison error.

Write an evaluation-opening marker before prediction and immutable prediction shards during that single opening. Final results must be reproducible from saved predictions; do not rerun predictions to search for a better result. A scoring interruption does not authorize changing settings or reopening the test as a new opportunity.

| View | Rows | Bootstrap unit | Seed |
|---|---|---|---|
| N-B, primary | One row per sorted normalized name, chosen with `random.Random(2026111106)` | Normalized-name rows | NumPy `2026111107` |
| N-A | Every kept test row in frozen order | Entire hashed-site clusters, in first-appearance order | NumPy `2026111108` |

For each view, use paired percentile bootstrap 95% ranges from 1,000 valid resamples. Every method and paired difference receives the same resampled indices/clusters. Draw clusters uniformly with replacement. Redraw a whole resample if it lacks a truth class; record rejected draws, with a maximum of 10,000 total attempts to obtain 1,000 valid resamples. Failure to obtain them prevents a confirmed win. Do not reject draws based on a method's performance.

Report balanced accuracy, precision, recall, F1, PR-AUC for the fixed ranking scores, and confusion counts. Zero predicted positives gives precision/F1 zero. An empty agreement subgroup has undefined accuracy, not zero; conditional intervals report their number of finite bootstrap values. No interval excludes unsuccessful methods.

For the selected combiner, compute paired balanced-accuracy differences against K0 and K1 in both views. The win rule uses N-B only: **both point differences must be strictly positive, and both paired 95% lower bounds must be strictly above zero.** Otherwise report “no demonstrated win.” These are the two prespecified component comparisons; do not promote another candidate because it happens to lead on the test.

Report the section 5 agreement tables on the test, including uncertainty from the same resamples. No new threshold, weighting, exceptional-cookie list, or classifier change follows the test.

## 10. Headline comparison: CookieGuard vs cloud AI

After the clean test and N-B row selection are frozen, select 300 N-B names with a fixed, recorded seed, one cookie per normalized name. If N-B has fewer than 300 names, use all of it. Freeze and hash the ordered sample before any cloud call. The local CookieGuard side is the already selected combiner on exactly those rows; no prompt result may change its selection, threshold, weights, or inputs.

Run the established `llm_baseline` and `accuracy_push` cloud method:

- use three fresh Codex sessions per batch of 50, each session in a separate empty folder;
- turn tools, memory, and web search off;
- record the exact cloud model and settings;
- provide only the fields used previously: ID, cookie name, cookie domain, third-party, Secure, HttpOnly, SameSite, lifetime, value length, and value character set; provide no cookie values or website names;
- require: “Reply with one JSON object whose keys are the IDs and whose values are `true` or `false`, e.g. `{"C001": true, "C002": false}`.” Missing, extra, malformed, or invalid answers count as wrong under a prespecified parser;
- save each raw reply before scoring it and record elapsed time per batch.

Within each batch, the three fresh sessions occupy fixed run positions 1, 2, and 3. Concatenate the same position across batches to form cloud runs 1, 2, and 3, then define the majority result per cookie from those three Boolean answers. Do not retry, repair, or reinterpret a saved answer after looking at truth labels.

Time CookieGuard locally on the benchmark's same 11 cases and with the same method as `llm_baseline/benchmark_local.mjs`: warm-batch timing and startup-inclusive runs. Separately record end-to-end local scoring time on the frozen 300-name comparison sample. Record runtime, versions, hardware context, number of repetitions, and both aggregate and per-cookie results.

Report CookieGuard beside cloud runs 1, 2, 3, and their majority: balanced accuracy, precision, recall, confusion counts, and paired-bootstrap 95% ranges and paired differences against CookieGuard using the fixed N-B resamples. Also report time per cookie, where data goes, cost per run if known, and whether the method can prove the login cookie. CookieGuard can use the later run-time deletion test; a cloud classifier that only reads descriptions cannot. If cloud AI is more accurate, say so plainly in the comparison's first sentence.

State the fairness note: **cloud AI reads domain names and can use general web knowledge; CookieGuard sees cookie attributes and a third-party flag but no domain identity.**

Cloud prompts, replies, parsings, timing records, and derived tables are new study artifacts. Admit them only through the incremental privacy scan in section 11. A prompt may contain only strings already present in accepted frozen rows plus fixed template text. Do not make cloud calls for any other purpose under this approval.

## 11. Privacy, interruption handling and locks

Use a live coordinator for each uninterrupted collection segment. Retain every distinct newly observed cookie value of at least eight characters in memory only. Disable browser/session recording and logs that could serialize values. No values or value hashes may be checkpointed.

Use an incremental cross-scan. Before accepting batch `k`, scan batch `k`'s artifacts against every distinct value held in memory so far, and rescan every previously accepted artifact against batch `k`'s newly observed values. Thus every accepted artifact–value pair is checked while that value is still in memory. Scan structured string content and keys; scan binary artifacts bytewise. Count permitted matches in name/domain/numeric fields; fail matches in other fields, prose, hashes or binary artifacts. Do not waive schema-word or incidental-hash matches. Store a receipt for every accepted batch with counts, paths, field types, and the accepted-artifact frontier, but never values or their hashes.

Pre-crawl validation/selection locks establish integrity before future cookie values exist; they do not claim a privacy check against values not yet collected. Their data-derived outputs enter the final scan too. Existing pinned inputs and pre-collection source/protocol text are separately hash-verified; do not relabel historical values as newly audited.

For a collision in nonessential, still-unlocked report wording, keep the coordinator alive, replace that wording with the fixed marker `[redacted by privacy gate]`, and rescan. Do not change locked artifacts, required evidence, numerical results or data to evade a collision. A required collision blocks completion. Receipts contain only counts, paths and field types, never matched values or their hashes.

If the coordinator dies, preserve accepted batches and their cross-scan receipts, discard the in-flight batch, and restart from the next unattempted rank. Never revisit an attempted site. On restart, rebuild the accepted-artifact frontier from the immutable receipts and accepted shards, disclose the restart and discarded rank range, and begin a new in-memory value set. Every artifact written after the restart—including predictions, reports, cloud prompts, and derived tables—may contain only strings already present in accepted rows plus fixed template text. Scan every later artifact against all values held since the restart, and perform a final scan against those values. Earlier accepted batches remain valid because their artifact–value pairs were checked incrementally before loss of memory. Report every restart; a missing or inconsistent receipt invalidates the affected accepted batch rather than authorizing a revisit.

After approval, append new study-local locks in this order:

1. Approved protocol, inputs, runtime, implementation and test-frame definition.
2. Development splits and fixed row selections.
3. K5 fit and parity check, validation results, every threshold and selected ID.
4. Collection batches and privacy receipts, then the frozen clean-test manifest.
5. Single-opening marker and saved predictions.
6. Frozen cloud sample, prompts, replies, parsing, local/cloud timings and comparison results.
7. Test results, case tables, final report and final privacy receipt covering values held since the last restart.

Keep mutable progress separate. Verify all existing study locks before continuing a live process. Never overwrite prior locked results. Preserve original model and product files and verify their hashes again at completion.

## 12. Report and stopping point

After approval, implement `analyze.py` so it reproduces `results.json` and `results.md` from frozen manifests, predictions, and saved cloud replies without a crawl, fit, new local inference, or cloud call.

Put the **CookieGuard vs cloud AI headline first**: accuracy and paired ranges for cloud runs 1, 2, 3, majority, and CookieGuard; speed, privacy/data destination, cost if known, and ability to prove the login cookie. State a cloud accuracy lead plainly if one occurs.

Then report the crawl and study facts:

- actual frame, attempted ranks, exclusions, usable sites, CMP coverage, rows, names, deadline/threshold stop reason and any overshoot;
- all development splits, name overlaps, class counts, both-era K5 fit-row base rates before and after weighting, thresholds and selection;
- validation-stage C2 parity, its limited 2021 measuring role, and the mixed probability sources used to fit K5;
- the distinct K2/K3 definitions and canonical rule near-tie semantics;
- the ten most common normalized names where the selected combiner is correct and at least one of K0/K1 is wrong, and ten most common names where it is wrong, counted on N-A and tied lexically; show component-specific correction counts to avoid double-counting claims;
- explicit rows for `cf_clearance`, `bm_sv`, and `hubspotutk`: retained counts and performance, or the exact exclusion/absence reason. Never exempt these names from clean-test exclusions;
- runtime and source identities, checks, privacy scope, deviations, and preserved-file verification.

Add an evidence appendix titled **“Inside CookieGuard: how its parts contribute”** containing both-era K0–K5 validation tables, every N-B/N-A component result, the selected combiner's paired differences and win-rule verdict against K0 and K1, and the agreement/disagreement coverage, accuracy, errors, and overrides. Phrase a no-win as **“the combination did not beat both parts on this test”**, not as a failure of CookieGuard.

State the limits: noisy or conflicting consent declarations, only Cookiebot/OneTrust sites, geographic/browser and crawl attrition, old 2026 data reused as validation, possible same-name overlap across its site split, validation-stage probabilities used for 2021 development while final-v3 probabilities were used for 2026, and correlated component errors. Disclose every coordinator restart. A tracker decision is not a login-cookie identification, and agreement is not a security verdict.

Draft both outcome statements, with actual counts and intervals filled only after the study:

- Win: “On the new unseen-name test, the frozen combination beat both component references under our prespecified paired-bootstrap rule. The deletion test still verifies the login cookie.”
- No win/incomplete: “The combination did not beat both parts on this test. Agreement and disagreement remain signals to evaluate; they do not prove a cookie's role.”

Avelyn writes the final presentation wording. **Stop after the report and privacy/integrity checks. Do not update the demo, active model, showcase, movie or submission at this stage.**

## 13. Separately approved demo integration

This section describes the later task; approval to run the study alone does not authorize it.

- Use `examples/campus-market/` together with `codex_task_demo_update.md`; do not port to product packages before WAICY.
- Show one CookieGuard result per cookie. Do not show separate rules, model, and combined decisions. The AI layer's score and the decision layer's rule signals appear only inside a **“How CookieGuard decided”** expander. Do not label “not tracker” as “proven login.”
- Lock the chip rule now: a component disagreement says **“Verify first”**. An agreement says **“Confident”** only when ordinary agreement accuracy on the new-test N-B view has a paired-bootstrap 95% lower bound at least 0.80; otherwise it says **“Agree”**.
- `models/active.json` selects the frozen chosen combiner only if its test win rule passed. Otherwise use K2 with its already frozen validation threshold, clearly labeled a default not proven better. No new-test tuning or replacement with a different test-leading candidate.
- Use the two-layer framing throughout: the **AI layer**, followed by the **decision layer's cross-check, prove, and decide steps**. Cross-check supplies the chip. Prove puts component disagreements first within the demo's approved likely-login candidate pool, then orders by the frozen non-tracker ranking score with a deterministic name/key tie-break. The candidate-pool implementation is reviewed with the demo task before integration. Removal, signed-out evidence and restoration establish the login cookie; ranking alone does not.
- The decision layer's decide step checks CG001, CG003, CG004, CG010 and CG011 on that verified cookie. High-severity findings produce FAIL. Medium findings remain visible as Needs review with rule IDs, never a silent PASS.
- Add the SameSite=None cross-site shopping scenario and parent-Domain sharing scenario using a hostname such as `campus.localhost`. Do not silently turn medium findings into blocking failures.
- Campus Market keeps its current dark November 10 redesign as specified in the Design section of `codex_task_demo_update.md`. The showcase uses its own design tokens. Show the two-layer architecture and link each measured evidence source. Use display numbering 1, 2, 3 without leading zeros; preserve identifiers such as CG001.
- Run the existing `npm test` and `npm run verify:ui` commands and the requested disagreement-first, medium-finding, new-scenario and no-values-output checks. Report screenshots and test output after that separate approval. Do not publish.

## 14. Approval gates

1. **Now:** write this file only, show it in the conversation, and stop.
2. **After explicit protocol approval:** perform the fixed study through section 12, including only the section 10 cloud calls, report by November 14, and stop.
3. **After explicit integration approval:** carry out section 13, target November 18, and report without publishing.
