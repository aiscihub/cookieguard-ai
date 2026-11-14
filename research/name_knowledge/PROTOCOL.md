# CookieGuard name-knowledge layer and natural-mix accuracy

Draft for approval — November 11, 2026, America/Los_Angeles.

**Status: APPROVED on November 11, 2026, with the §5.3 stop-rule amendment recorded in `APPROVAL.md`.**

Source task: `waicy_2026/codex_task_name_knowledge.md`. Results are due November 14, 2026. The WAICY submission deadline is November 29, 2026 at 5 PM Eastern. Stop after the study report; demo or product integration requires separate approval.

## 1. Scope and interpretations requiring approval

1. Work only in `waicy_2026/name_knowledge/`. Do not modify a product package, existing model, prior study, prior lock file, showcase, demo, movie, or submission. Do not retrain v1 or v3. Do not pull, switch branches, commit, submit, or publish. HEAD must remain `1f0ede14ee9d5e3c990a575f8eeae986a588d346`.
2. D1 needs both matching keys named in the task. Build two vote tables from the same permitted labeled rows: a case-sensitive raw-name exact table and an established-normalization table. Each table independently takes the majority binary label and retains tracker/not-tracker vote counts; a tie produces no entry. Raw exact therefore has the requested precedence without pretending that a normalized key is a raw-name record.
3. The original 2021 test names remain forbidden from D1 and from selection. For 2021 D1, admit only the training names identified by `retrain_test/split.json` and the validation names identified by `accuracy_push/validation_split.json`. If those files do not distinguish these partitions unambiguously, stop for clarification rather than infer membership.
4. The N2 title is descriptive; its supplied formula is controlling. On a dictionary hit with label `d`, reject the hit only when model probability is more than 0.30 across the fixed 0.40 boundary on the opposite side: reject tracker `d` when `p < 0.10`, and reject not-tracker `d` when `p > 0.70`. Otherwise use `d`. Do not add a separate rule-agreement gate, because none is specified in the formula.
5. M-U and M-K are row-level slices of M-A and use site-clustered resampling. M-B is the name-balanced view. The cloud is evaluated only on its frozen 300-row sample drawn from M-B, plus the M-U subset of that same sample; it is not evaluated on every M-A row. The report must not call the 300-row cloud result an M-A estimate. The headline will present the M-A operational result and the same-row M-B cloud comparison separately.
6. “Natural mix” has two explicit meanings: M-A is the natural frequency mix of labeled cookies on the crawled sites; the cloud sample is a natural mix of known and unknown names but is name-balanced by construction. Use those exact distinctions in the report.
7. A “known” row is a row for which the final ordered D1/D2 matcher returns a hit. An “unseen” row is a matcher miss. The `seenInTraining` and `seenInDevelopment` flags are source-membership flags on the normalized name, independent of whether its source votes tied and independent of whether D2 also matches.

Approval of this protocol approves these interpretations.

## 2. Immutable inputs and preflight

After approval, verify and record hashes before using any input:

| Input | Location or identity |
|---|---|
| Current v3 / K0 model | `waicy_2026/accuracy_push/model/main.onnx`; expected SHA-256 `a4f3905c7f4ccbd061846e5e3e1c20a51a172daa37f31a8af16e7233e6be2a93`; tracker threshold 0.40 |
| v1 reference | `extension-standalone/model/cookieguard_model.onnx` and its saved class metadata |
| Rules / K1 | `waicy_2026/local_apps_test/node_modules/@aiscihub/cookieguard-core/vendor/engine.cjs`; expected SHA-256 `bcc2718198f0798b77505c27efcfd0bf8a251cfd90dc31b0daf375dc9df7e4bd` |
| 2021 assignments and labels | `waicy_2026/retrain_test/split.json`, `waicy_2026/accuracy_push/validation_split.json`, and the corresponding labeled source rows used by the existing studies |
| 2026 development rows | `waicy_2026/accuracy_push2/finalization_retry/fresh_test/`, with its completed status, privacy receipt, manifest, and locks |
| Frozen 2026 site split and selected rows | `waicy_2026/combination_check/development/splits.json` and locked companion artifacts |
| Name normalization | The existing approved implementation and tests used by `combination_check` |
| Site list | `waicy_2026/accuracy_push2/inputs/tranco-947N2-top20000.csv`, list 947N2 |
| Crawl reference | `waicy_2026/combination_check/crawl.mjs`, its manifest, progress, discard, restart, and receipt records |
| Cloud reference | The Amendment A prompt/reply structural-admission implementation and frozen method in `waicy_2026/combination_check/` |
| Runtime | Existing `waicy_2026/retrain_test/.venv`, local Playwright/Chromium, vendored Node dependencies, and Codex CLI used by the completed comparison |

Require the prior 2026 development status and privacy evidence to pass, the `combination_check` locks to verify, and HEAD and pinned model/rules hashes to match. Do not open or rescore the `combination_check` test. A mismatch stops the affected step and is reported; do not silently substitute an input.

Record language and package versions, operating system, CPU architecture, Chromium identity, user agent, Codex interface/model/settings, and the exact study-script hashes. All new scripts and outputs stay under `name_knowledge/`.

## 3. Licensed known-name layer

### 3.1 Permitted sources

Use only:

1. D1, CookieGuard’s own permitted labeled data described below.
2. D2, Open Cookie Database (OCD), under Apache-2.0.

Do not use DuckDuckGo Tracker Radar, EasyList, EasyPrivacy, Disconnect, browser history, search-engine results, cloud knowledge, or any other external name/domain list.

After approval, acquire OCD once into a study-local source directory. Record its canonical repository URL, exact commit hash, retrieval time, data-file hashes, and the complete Apache-2.0 license-file hash. Require the checked-out license to identify Apache-2.0. Do not update the source after development selection or crawl start. If OCD is unavailable, its schema is incompatible with the mappings below, or its license cannot be verified, stop rather than substitute a source.

### 3.2 D1 construction

Use one vote per permitted labeled row. Preserve source-era and binary-label vote counts. Build:

- `d1_raw`: case-sensitive raw cookie name → tracker/not-tracker vote counts and majority label;
- `d1_normalized`: established normalized name → tracker/not-tracker vote counts and majority label.

For each table, tracker majority maps to tracker, not-tracker majority maps to not tracker, and an exact tie yields no entry. Do not use confidence weighting, recency weighting, site weighting, manual corrections, or cloud labels. Save excluded ties and vote counts. If the same row is duplicated across input artifacts, identify it using the saved source row identity and count it once; do not deduplicate legitimate observations merely because their names match.

Build two frozen D1 variants:

1. **Selection D1:** all permitted 2021 training/validation rows plus only rows assigned to the 2026 development fit-side sites in the existing frozen split. Exclude every 2026 select-side row, except that a normalized name legitimately present on both site halves can still be known from its fit-side votes. Record this overlap.
2. **Deployment/test D1:** all permitted 2021 training/validation rows plus every 2026 development row. Freeze it after method selection and before the new crawl.

Never include the old 2021 test rows, the opened `combination_check` test, the new crawl, OCD-derived labels, or cloud answers in D1.

### 3.3 D2 construction

Parse OCD deterministically and retain the source record, platform, category, exact name or wildcard pattern, and mapped binary label:

| OCD category | Binary label |
|---|---|
| Marketing, Analytics | Tracker |
| Functional, Security, Personalization | Not tracker |
| Missing or any other category | No entry |

Category comparison is case-insensitive after trimming surrounding whitespace; preserve the original category in evidence. Cookie-name matching remains case-sensitive. Do not infer a label from platform, description, domain, vendor, or prose.

Create separate exact and wildcard indices. Use only wildcard syntax explicitly represented by OCD; do not invent patterns from exact names. Compile each accepted wildcard to an anchored full-name matcher and record its literal prefix before the first wildcard token. When multiple wildcard entries match, choose the one with the longest literal prefix. If equally preferred exact records or wildcard records map the same key/pattern to conflicting binary labels, exclude that key/pattern as a conflict and report it. If equally preferred matching wildcard patterns with the same longest-prefix length disagree, return no D2 hit for that row. Use lexical source-record identity only to make same-label evidence ordering deterministic, never to resolve a label conflict.

### 3.4 Frozen match order and evidence

For each cookie, apply exactly:

1. Case-sensitive raw-name exact hit in D1.
2. Normalized-name hit in D1.
3. Case-sensitive raw-name exact hit in D2.
4. Case-sensitive D2 wildcard hit, with longest literal prefix winning.
5. Miss.

A hit returns source (`D1` or `D2`), table/match type, binary label, selected entry identifier, and vote counts or OCD evidence. Do not consult later sources after a hit. Save no cookie value.

Unit tests must cover precedence, raw versus normalized D1 behavior, tied D1 votes, all category mappings, unknown categories, exact D2 precedence over wildcard, overlapping wildcard prefixes, conflicting entries, case sensitivity, normalization, and a complete miss.

## 4. Fixed development selection before the crawl

### 4.1 Selection rows

Reuse the exact 2026 development **select** half and its one-row-per-normalized-name selection already frozen in `combination_check/development/splits.json` and companion locked artifacts. Preserve its row order and identities. Require both binary classes. Do not resample names, sites, or rows.

Use final v3 probability `p` on those rows and exact vendored-rule decision `r`. Verify saved feature order, model/rule hashes, and row alignment before scoring. Do not use the 2021 development rows for this selection.

Use Selection D1, so no select-side row contributes a D1 vote. D1 can still hit a select row through permitted 2021 data or a same-name occurrence on a 2026 fit-side site. D2 is the frozen licensed source. Report D1 raw, D1 normalized, D2 exact, D2 wildcard, and miss counts on the selection rows.

### 4.2 Candidate definitions

Let `d` be the ordered dictionary hit label when present and `p` be v3 P(tracker):

| ID | Fixed decision |
|---|---|
| K0 | `p ≥ 0.40` |
| N1 | Hit → `d`; miss → K0 |
| N2 | Hit → `d`, except use K0 when `d=tracker AND p<0.10` or `d=not-tracker AND p>0.70`; miss → K0 |
| N3 | Hit and `0.25 ≤ p ≤ 0.55` → `d`; otherwise K0 |

Comparisons are inclusive exactly where shown. Do not round `p`. Do not add thresholds, tune a margin, special-case a name, or use the rule result as an extra N2 gate.

Compute balanced accuracy from confusion counts for N1–N3. Select the highest value; every method within an absolute 0.005 of the best enters the simplicity tie set, preferring N1, then N2, then N3. Use exact integer/rational comparison of confusion-derived balanced accuracy and the 0.005 boundary. K0 is a reference, not eligible. Require both classes; a required candidate failure stops selection.

Before the crawl, lock:

- OCD source, commit, license, parsed records, exclusions, and indices;
- Selection D1 and Deployment/test D1, including source row identities and vote counts;
- dictionary matcher and unit tests;
- frozen selection row identities and input probabilities/rule decisions;
- all N1–N3 decisions, confusion counts, balanced accuracies, tie set, and selected ID;
- model/rules/runtime/script identities.

No new-test result or cloud result may change the dictionary, matching, candidate, or selection.

## 5. Clean-test frame and crawl

### 5.1 Frozen frame

Audit only saved operational metadata from `combination_check` to confirm that rank 12,560 is the last attempted rank. Do not inspect its test labels or predictions. Freeze Tranco 947N2 ranks 12,561–20,000 in ascending order, with rank, source hostname, and a deterministic hashed site ID. Record list and frame hashes.

If operational evidence shows any rank at or above 12,561 was attempted, exclude each bounded attempted rank or whole uncertain batch, disclose it, and continue from the next unattempted rank without replacement or reordering. Stop for clarification if prior-attempt extent cannot be bounded. Never revisit an attempted site.

### 5.2 Crawl conduct and labels

Use a study-local adaptation of the `combination_check` coordinator, preserving its navigation, consent, declaration, privacy, deterministic batching, and restart behavior while removing all prior-name exclusion logic.

- Public home pages only, in clean non-personal Playwright contexts.
- Existing recorded normal desktop Chrome user agent and existing Chromium.
- At most four sites concurrently, dispatched and committed in ascending-rank batches of at most four.
- One attempt per eligible rank and a 30-second whole-site deadline.
- HTTPS first; HTTP fallback only when navigation fails before a document response and not after TLS/certificate failure.
- Stop immediately on blocks, CAPTCHAs, rate limits, access-denied responses, or consent-region restrictions; record only a categorical reason.
- No login, form submission other than the supported CMP consent API, link following, proxy change, TLS bypass, challenge workaround, screenshot, trace, HAR, page body, console dump, or network transcript.
- Support only the pinned Cookiebot and OneTrust declaration/consent methods and English category mappings used by the approved prior crawl.
- Match observed cookies to declarations exactly as in the approved prior crawl. Tracker wins conflicting matching declarations.
- Accept all only through the detected CMP API, reload the final home page, wait exactly five seconds after `domcontentloaded` within the site deadline, and read browser-context cookies.
- Keep the first observation per `(raw name, normalized cookie domain, path)`.

Use the same declaration labels:

| Declaration | Binary label |
|---|---|
| Cookiebot Statistics or Advertising | Tracker |
| Cookiebot Necessary or Preference | Not tracker |
| Cookiebot Unclassified | Exclude |
| Standard OneTrust C0001 or C0003 | Not tracker |
| Standard OneTrust C0002, C0004, or C0005 | Tracker |
| Renamed/custom OneTrust group | Pinned English mapping; otherwise exclude |

During collection, extract only the existing feature vector, structural attributes, dictionary-source membership flags, and privacy-safe metadata. Do not run v1, v3, rules, selected N, or cloud AI before the freeze. Dictionary matching during collection is limited to writing the two required source-membership flags; do not write hit labels or inspect yields by prediction.

### 5.3 Rows, flags, stop rule, and minimum

Keep every declaration-labeled cookie. Apply no name exclusion. Each saved row includes:

- rank and hashed site ID, but no input-site URL/domain or final URL;
- CMP, declaration category/group/match evidence, raw name, normalized name, cookie domain/path;
- binary declaration label and cookie attributes;
- lifetime at collection, value length and character-set shape, and numeric features;
- `seenInTraining`: normalized-name membership in permitted 2021 D1 source names;
- `seenInDevelopment`: normalized-name membership in 2026 D1 source names.

Save no raw cookie value, value hash, value prefix, browser storage, or personalized identifier.

A usable site is an attempted site contributing at least one retained declaration-labeled row. Stop scheduling after the first complete batch for which any condition holds:

1. At least 500 usable sites.
2. November 13, 2026 at 18:00:00 America/Los_Angeles has been reached.
3. The frozen rank frame is exhausted.

Keep the complete final batch and report overshoot. Minimum to score is at least 150 usable sites and at least 300 rows whose final Deployment/test D1/D2 matcher is a miss. If the crawl stops without both minima, freeze and report an incomplete study; do not extend the frame, change sources, loosen labeling, or call cloud AI.

## 6. Privacy and interruption handling

Retain every distinct newly observed cookie value of at least eight characters in coordinator memory only. Disable browser/session recording and logs that can serialize values. No value or value hash may be checkpointed.

Use the approved incremental cross-scan. Before accepting batch `k`, scan its artifacts against all values held in memory so far and rescan every earlier accepted artifact against batch `k`’s newly observed values. Scan structured strings and keys, and binaries bytewise. Permit matches only in name/domain/numeric fields; fail matches in other fields, prose, hashes, or binaries. Store a privacy receipt for each accepted batch with counts, artifact paths/types, and frontier identity, never matched values or their hashes.

If the coordinator dies, preserve accepted batches with valid receipts, discard the in-flight batch, and resume at the next unattempted rank. Never revisit a site. Rebuild the accepted frontier, begin a new in-memory value set, disclose the restart and discarded ranks, and scan every later artifact against values held since that restart. A missing or inconsistent receipt invalidates the affected batch; it does not authorize a revisit.

Cloud prompts use Amendment A structural admission:

1. Freeze the public sample rows and prompt manifest before calls.
2. Verify each prompt byte-for-byte as a fixed intro followed by the exact rendering of its frozen structured rows, in the frozen order and with nothing else.
3. Preserve prompt hashes and write a structural A1-style admission receipt.
4. Save each raw cloud reply before parsing.
5. Admit a reply structurally only if it is one JSON object with exactly that batch’s 50 IDs and Boolean values. An invalid reply makes all 50 answers in that reply wrong; do not retry, repair, or reinterpret it.
6. Replies are not value-scanned because the cloud receives no values. State this explicitly.

The final privacy receipt is hybrid, not described as a final value scan: incremental receipts cover crawl/local artifacts within their restart scope; structural verification covers prompts; exact-schema admission covers replies. Preserve and disclose all restart and rejection evidence.

## 7. Test freeze and single opening

After a stop condition, finish the last batch, close the browser, complete privacy receipts, and write immutable schema and manifest files containing frame identity, attempts, statuses, exclusions, usable sites, rows, normalized names, source-membership counts, stop reason, overshoot, restarts, row-shard hashes, and privacy scope.

Before inference, verify the manifest, shard hashes, both minima, dictionary/selection locks, model/rules hashes, and feature schema. Write a single-opening marker before loading a model or rules engine. Never inspect partial performance, cases, hit accuracy, or cloud labels before all local predictions are saved. Score the frozen test once. A scoring crash may resume only from saved immutable inputs with the same code and must not alter selection.

## 8. Frozen evaluation definitions

### 8.1 Deterministic row views

Use source shard filenames in lexical order and line order within each shard.

- **M-A:** every retained labeled row.
- **M-B:** group M-A by normalized name, sort names lexically, and choose one row per name with `random.Random(2026111201)`.
- **M-U:** every M-A row for which the frozen ordered Deployment/test D1/D2 matcher misses.
- **M-K:** every M-A row for which that matcher hits.

M-U and M-K partition M-A exactly. Report rows, normalized names, sites, tracker/not-tracker counts, and dictionary source/match-type counts in every view/slice. Require both classes for balanced accuracy; if a slice has one class, mark balanced accuracy and its interval undefined without changing the slice.

### 8.2 Methods

Score:

| Method | Decision |
|---|---|
| Selected N / CookieGuard | Frozen selected N1, N2, or N3 using Deployment/test D1/D2 and final v3 `p` |
| K0 | Final v3 `p ≥ 0.40` |
| K1 | Exact vendored rule classifier returns tracker |
| v1 | Existing v1 tracker class decision |
| Everything tracker | Always tracker |

Dictionary lookup returns label/evidence only; it does not change v3 probability. No threshold, exception, mapping, or dictionary entry changes after opening.

### 8.3 Bootstrap and metrics

Use 1,000 valid resamples and percentile 95% ranges:

| Estimate | Seed | Resampling unit |
|---|---:|---|
| M-A | 2026111204 | Site clusters, sampling the observed number of sites with replacement and including all rows in each selected site |
| M-B | 2026111205 | Normalized-name rows |
| M-U | 2026111206 | Site clusters within the fixed unseen slice |
| M-K | 2026111207 | Site clusters within the fixed known slice |
| Cloud comparison | 2026111208 | The frozen M-B sample rows, paired across methods |

Reject and redraw a resample lacking either class for a metric that requires both. Cap attempts at 10,000 per view; report valid and rejected counts. Do not silently replace an undefined interval.

For every local method and view/slice, report balanced accuracy, precision, recall, and confusion counts. Precision is zero when there are no predicted positives. On M-A also report plain accuracy. Use paired resamples to report selected-N differences against K0 and K1 in each view/slice; these comparisons are descriptive and do not change selection.

Report dictionary hit rate overall and separately for D1 raw, D1 normalized, D2 exact, D2 wildcard, and miss. A row is attributed only to its first ordered hit. Report hit accuracy and confusion counts without relabeling a source entry.

### 8.4 Cases

On M-A, report the ten most common normalized names where selected N is correct and K0 is wrong, and the ten most common normalized names where selected N is wrong, sorting by descending row count then lexical normalized name. Also report component-specific correction counts and dictionary source/evidence so claims are not double-counted. Do not remove unfavorable or bot-protection cases.

## 9. Cloud comparison

After the test, M-B, local predictions, and all locks are frozen, select 300 M-B rows with `random.Random(2026111202)`; use all if fewer than 300. Assign opaque IDs, shuffled with `random.Random(2026111203)`. Freeze and hash ordered public rows, hidden truth/local decisions, prompt files, and a sample manifest before any call.

Use exactly the established fields: opaque ID, raw cookie name, cookie domain, third-party, Secure, HttpOnly, SameSite, lifetime, value length, and character set. Do not send cookie values, website names, truth, dictionary evidence, source-membership flags, local predictions, scores, or labels.

Run six batches of 50, three fresh sessions per batch, in separate empty folders. Use the same Codex model/interface/reasoning settings as the completed `combination_check` cloud comparison unless the exact model is unavailable; if unavailable, stop rather than substitute. Disable tools, memory, web, apps, plugins, hooks, multi-agent, shell, browser/computer use, image generation, and repository context. Require exactly one JSON object with all and only the batch IDs mapped to Boolean values. Save every raw reply before parsing and record process exit, model/settings, prompt/reply hashes, elapsed batch time, schema validity, and empty-session evidence. No retry.

Concatenate fixed run position 1, 2, or 3 across batches. Majority is at least two true answers; if a reply is invalid, every row in that reply is scored wrong under the frozen invalid-answer policy.

On the full 300-row sample, report CookieGuard, cloud runs 1–3, and cloud majority: balanced accuracy, precision, recall, confusion counts, percentile paired ranges, and paired cloud-minus-CookieGuard differences. Report the same metrics on the fixed M-U subset of those 300 rows; report its size and class counts, and mark metrics undefined if it lacks both classes. Do not draw a replacement sample to enlarge M-U.

Report time per batch and cookie, destination/privacy, cost if known from saved metadata, and whether the method can prove the login cookie. CookieGuard can feed the later run-time deletion test; description-only cloud classification cannot. State plainly if cloud AI is more accurate.

Fairness wording: **Cloud AI reads cookie names and domains and can use general web knowledge. CookieGuard’s known-name layer uses only its own labeled data and the Apache-2.0 Open Cookie Database; its model sees cookie attributes and a third-party flag but no domain identity.**

## 10. Timing

Benchmark the complete selected-N path, including normalization, ordered D1/D2 lookup, feature extraction, v3 inference on misses or when the selected rule requires K0, and final decision. Use the same fixed 11 cases and method as `llm_baseline/benchmark_local.mjs`:

- three startup-inclusive fresh-process runs;
- three warm processes;
- 20 warm-up batches per warm process;
- 100 measured 11-cookie batches per warm process.

Record aggregate and per-cookie mean, median, minimum, maximum, and p95, plus runtime, model/dictionary hashes, hardware, and whether networking occurred. Separately time end-to-end local scoring on the frozen 300-row cloud sample. Timing never changes the selected method.

## 11. Locks and reproducibility

Append study-local locks in this order:

1. Approved protocol, immutable inputs, runtimes, scripts, OCD commit/data/license, and test frame.
2. Selection/deployment D1, D2 indices, parser/matcher tests, selection rows and decisions, selected method, and all selection results.
3. Accepted crawl batches and privacy receipts, then frozen manifest/schema.
4. Single-opening marker, saved local predictions, M-B indices, and analysis seeds.
5. Timing outputs, frozen cloud sample/prompts, structural prompt admission, raw replies, run metadata, structural reply admission, and cloud results.
6. Results, report, reproduction checks, and hybrid final privacy receipt.

Keep mutable progress outside locks. Never overwrite a locked artifact; use a new labeled correction artifact if necessary. Verify every prior lock before continuing. At completion, verify HEAD and the original model/rules/product hashes again.

Implement `analyze.py` so it regenerates `results.json` and `results.md` from frozen manifests, saved predictions, lookup evidence, timing, and saved cloud replies without crawling, dictionary rebuilding, selection, new local inference, or cloud calls. Run it twice and require byte-identical outputs.

## 12. Report and stopping point

Put the outcome first, while keeping the two populations distinct:

1. M-A CookieGuard accuracy and balanced accuracy on the natural frequency mix of labeled cookies.
2. CookieGuard versus cloud runs and majority on the identical frozen 300-row M-B sample, including the paired difference, speed, privacy/data destination, cost if known, and ability to prove the login cookie.
3. The corresponding comparison on the sample’s M-U subset.

If cloud AI is more accurate on either same-row comparison, say so in the first paragraph. Do not imply the cloud was run on all M-A rows.

Then report:

- crawl frame, attempts, statuses, exclusions, usable sites, rows, names, stop condition/overshoot, restarts, and privacy scope;
- M-A, M-B, M-U, and M-K counts, class balance, every local method’s metrics/ranges, and selected-N paired differences against K0/K1;
- overall and per-source dictionary hit rates, hit accuracy, conflicts/ties, and the known/unseen contribution;
- development selection rows, D1-ablation rule, D2 commit/license, N1–N3 results, tie set, and selected method;
- the ten most common names the dictionary fixed and the ten it still got wrong, with source evidence;
- timing and reproduction/integrity checks.

State these limitations plainly:

- consent-banner declarations can be noisy or conflicting;
- only Cookiebot and OneTrust sites are represented;
- D1 includes 2026 development labels in deployment/test condition;
- OCD categories are a third party’s judgment;
- the cloud comparison is a name-balanced 300-row sample, not the all-row M-A population;
- tracker classification is not login-cookie identification.

Draft both outcome statements with actual values only after scoring:

- Improvement: “On the natural mix, the frozen known-name layer improved CookieGuard over the model-only reference. The deletion test still proves the login cookie.”
- No improvement/incomplete: “The frozen known-name layer did not improve CookieGuard on this test, or the minimum clean-test evidence was not reached. The deletion test remains the separate proof of the login cookie.”

Avelyn writes the final presentation wording. **Stop after `results.md`, its reproduction/privacy/integrity checks, and the report to the user. Do not modify a product package, `models/active.json`, demo, showcase, movie, or submission without separate approval.**

## 13. Approval gate

Current authorization ends with this protocol. After explicit approval, execute sections 2–12 exactly. Without approval, do not fetch OCD, build either dictionary, inspect development rows for this study, freeze or crawl sites, score, benchmark, call cloud AI, or write results.
