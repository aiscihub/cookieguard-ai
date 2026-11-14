# Accuracy-push protocol

Protocol date: November 10, 2026. Report deadline: November 13, 2026. Final-model decision date: November 14, 2026.

This protocol fixes the feature, validation, model-selection, final-test, cloud-comparison, case-gallery, and privacy procedures before any accuracy-push feature, validation split, or model is computed. Work stops after this document until Avelyn approves it.

## 1. Purpose and boundaries

The study asks three separate questions:

1. Does correct website context and a prespecified model comparison improve tracker detection on normalized names absent from training?
2. How does the selected private local model compare with a cloud AI on the same blinded 300-cookie sample?
3. Which measured cases and coverage facts can be used directly in the WAICY presentation?

The following boundaries are fixed:

- Do not change `packages/`, `integrations/`, `extension-standalone/`, `backend/`, `examples/`, the shipped model, or `waicy2026/` submission materials.
- New study artifacts go only under `waicy_2026/accuracy_push/`.
- HEAD remains `1f0ede1`; do not pull, switch branches, commit, push, submit, or publish.
- Reuse the CookieBlock extraction and the Python and Node environments already in the repository. Do not redownload CookieBlock.
- Cookie values may be read only in memory for feature computation and leak checking; no output stores a value.
- The existing test split has already been used by the M1 study. No candidate choice, threshold, hyperparameter, early-stopping decision, tracker-list decision, or prompt design may use it. It is opened only after finalist artifacts are frozen.
- All favorable and unfavorable results are reported.

## 2. Frozen inputs and checksums

Before any new computation, verify and record:

| Input | Required identity |
|---|---|
| CookieBlock dataset archive | MD5 `9aece7e28a54a7cfc2250f5c2861ca20` |
| CookieBlock JSON | SHA-256 `71364f0f8484daa950267aebe774a84cc64e8aecca00b562c48d4607dceb3168` |
| Existing normalized-name split | SHA-256 `d1dc80459727466bfd4c9128395c6c823b6802c4d5a61e94bcca73a92b34b4c5` |
| M1 ONNX | Read and record from `retrain_test/locks.txt`; expected `3d3d46206da96d6cc8f32527a92b408c310aef872f471dc4ee15d064d1fc6cdd` |
| Shipped ONNX | SHA-256 `6820daa4cb8df4e56d96c6fbf92252b4591d73f6edc1645077ff74f1a54191c2` |
| Local-app feature file | SHA-256 `edd56682f1a1b90df163b287b24e91c18ab5a43cc5127111dca6e62761de774b` |

Reuse Python 3.9.6 and the pinned packages in `waicy_2026/retrain_test/.venv`. Record every version and any added package in `locks.txt` and `results.md`. Reuse `tldts` and the other Node packages already installed locally. After approval, add a study-local `.gitignore` for `features/`, `model/`, cloud reply working directories, and downloaded tracker-list data.

## 3. Split discipline

### 3.1 Existing test split

`waicy_2026/retrain_test/split.json` remains authoritative. Every normalized name marked `test` stays test. The implementation verifies its required SHA-256 before reading the assignments.

Test rows may be feature-extracted in a blind, deterministic pass, but no test label distribution, prediction, metric, error, name example, or aggregate is inspected until the finalist model hashes have been written to `locks.txt`. Candidate-training and validation scripts must reject test rows.

### 3.2 Validation split

Create `validation_split.json` only from normalized names marked `train` in the existing split:

1. Sort the training normalized names by Unicode code-point order.
2. Shuffle with Python `random.Random(2026111001)`.
3. Let `n_validation = floor(0.20 × number of existing training names)`.
4. Assign the first `n_validation` names to validation and every remaining name to candidate training.
5. Keep every record with one normalized name on the same side.
6. Write the complete mapping atomically and lock its SHA-256 before fitting a model.

Report name, cookie, and class counts after locking, without changing the assignment.

### 3.3 Inner early-stopping split for C3

For each C3 grid member, sort the candidate-training normalized names, shuffle with `random.Random(2026111002)`, and reserve the first `floor(0.10 × names)` for inner stopping. This split never includes outer validation or test names.

Fit up to 400 boosting iterations on the remaining inner-training names with estimator early stopping disabled. Evaluate staged probabilities on the inner-stopping names and select the iteration with minimum binary log loss; exact ties choose the earliest iteration. Refit that C3 grid member on all candidate-training names with the selected iteration count and no internal row-wise validation. The outer validation set is used only afterward for candidate comparison and threshold selection.

## 4. Cookie mapping and website-context features

Use every CookieBlock record and its first observation, with the approved `retrain_test/extract_features.mjs` mapping:

- `lifetime = max(0, expiry)`;
- `expirationDate = extraction time + lifetime` for persistent cookies;
- no expiry for session cookies;
- the same name, value, domain, path, Secure, HttpOnly, SameSite, and host-only normalization;
- the corrected normalized-name algorithm and its 20 unit tests from `retrain_test/PROTOCOL.md`.

Call the vendored engine's `extractFeatures(cookie, { currentDomain })`. Shape the cookie exactly as `normalize.js` does before calling the engine:

- SameSite is lowercase `strict`, `lax`, `none`, or the empty string;
- `expirationDate` is seconds since the epoch or omitted;
- `hostOnly` is Boolean when known;
- domain and path match the approved mapping.

### 4.1 Correct `currentDomain`

`currentDomain` is the visited website's registrable domain—its eTLD+1—computed with `tldts` from `first_party_domain`. It is not the full host. For example, the website host `www.example.com` supplies `example.com`.

The engine removes one leading dot from the cookie domain and marks it third-party when it is neither equal to `currentDomain` nor ends in `.` plus `currentDomain`. Passing `www.example.com` would therefore incorrectly mark a cookie for `example.com` as third-party. A post-WAICY product change would need to pass this same eTLD+1 value; this study does not make that change.

Keep `etld_match` exactly as the current engine computes it, including its current constant value. Do not patch the engine.

### 4.2 Saved feature rows

Write resumable, atomic chunks of 10,000 rows under `features/`. Each row contains only:

- record index;
- CookieBlock website ID in the existing `hash:0` or `hash:1` format;
- lowercase name and normalized name;
- cookie domain;
- truth label;
- the 38 numeric context features in `FEATURE_NAMES` order;
- third-party Boolean;
- Secure, HttpOnly, and normalized SameSite;
- lifetime in days;
- value shape: length and one of `empty`, `digits`, `hex`, `alphanumeric`, `base64/base64url`, or `other`.

No value or reversible value representation is written. Lock each completed chunk hash before proceeding.

### 4.3 Mandatory sanity checks before training

Use only existing training names for these checks:

1. Select 1,000 records without replacement using `random.Random(2026111003)`. For each, compare `extractFeatures(cookie, {})` with `extractCookieFeatures(cookie)` in `FEATURE_NAMES` order. Require exact numeric equality, treating missing features as zero. Any disagreement stops the study.
2. Across all existing training-name records, compare `f_third_party_context` with the inverse of CookieBlock's stored first-party suffix. Require at least 99% agreement. Report the exact agreement and disagreement counts and the share marked third-party by the context extractor. Below 99% stops training and triggers an audit report rather than a model result.

No test aggregate is produced by either sanity check.

## 5. Targets and common evaluation rules

Truth is binary:

- tracker: CookieBlock labels 2 analytics or 3 advertising;
- not tracker: labels 0 necessary or 1 functional.

Exclude and report any other label without changing a split.

For every probabilistic candidate, select a threshold on outer validation from the fixed grid `0.00, 0.01, …, 1.00`, maximizing balanced accuracy on view V-B. Threshold ties choose the value closest to 0.50; a remaining equidistant tie chooses the higher threshold. The selected threshold is frozen with the candidate result.

V-B uses one record per validation normalized name, selected with `random.Random(2026111004)`. All validation metrics and thresholds use this same frozen sample. Also report V-A on all validation records, clustered by website hash with the `:0` or `:1` suffix removed, but V-A cannot select a model or threshold.

Report precision, recall, F1, balanced accuracy, and PR-AUC. Use paired percentile 95% ranges from 1,000 resamples: normalized-name clusters with NumPy seed `2026111005` for V-B and website-hash clusters with seed `2026111006` for V-A.

## 6. Candidate models

Every candidate is trained only on candidate-training names. Record training duration, inference duration, model size, threshold, and both validation views.

### 6.1 C1 — four-class Random Forest

Features: 38 context features. Target classes: necessary, functional, analytics, advertising. Tracker probability is `P(analytics) + P(advertising)`.

```text
n_estimators=150
max_depth=12
min_samples_split=5
min_samples_leaf=2
class_weight='balanced'
random_state=42
n_jobs=-1
```

### 6.2 C2 — binary Random Forest

Features: 38 context features. Binary tracker target. Use exactly the same Random Forest settings as C1.

### 6.3 C3 — binary histogram gradient boosting

Features: 38 context features. Binary target. Use `class_weight='balanced'`, `random_state=42`, and the inner-name stopping procedure in section 3.3. Evaluate exactly these four configurations and no others:

| Variant | Learning rate | Maximum depth | Maximum iterations |
|---|---:|---:|---:|
| C3a | 0.05 | 6 | 400 |
| C3b | 0.05 | None | 400 |
| C3c | 0.10 | 6 | 400 |
| C3d | 0.10 | None | 400 |

Within C3, choose by V-B balanced accuracy. If variants are within 0.005, prefer depth 6 over unlimited depth, then learning rate 0.10 over 0.05 for the faster fixed model. Report all four variants and their selected iteration counts.

### 6.4 Main-finalist selection

For each of C1, C2, and the selected C3 variant, use its frozen V-B threshold. Find the highest V-B balanced accuracy. Any candidate within 0.005 of that maximum enters the simplicity tie set. Choose in order C2, then C1, then C3. Lock every validation result, the selected threshold, and the main-finalist ID before final retraining.

## 7. C4 — separately labeled tracker-list lookup

C4 will be attempted because the source license is clear. Use DuckDuckGo Tracker Radar release `2026.10.20`, tag `2026.10.20`, from `https://github.com/duckduckgo/tracker-radar`. The official repository licenses the data CC BY-NC-SA 4.0, which permits this attributed, non-commercial student comparison. Preserve the license and attribution and label every C4 result **with a tracker-list lookup**.

After approval, download the release archive once into the ignored study data directory. Record release tag, release date, resolved commit, archive SHA-256, the relevant list-file SHA-256, source URL, and license. If the pinned release or license cannot be verified, skip C4 and record the exact reason.

Use `build-data/static/categorized_trackers.csv`. Parse its documented domain column, normalize domains with IDNA and lowercase, and build the union across categories. The added feature is 1 when the cookie's registrable domain is exactly in that set, otherwise 0. Do not use CookieBlock labels or validation/test errors to add or remove a domain.

C4 uses the selected main candidate's algorithm and fixed settings, with the tracker-list Boolean appended as feature 39. Refit on candidate-training names and select only its threshold on V-B using the common threshold rule. C4 never changes which C1–C3 model is the main finalist. Report it separately even if it wins.

## 8. Final retraining, ONNX export, and test embargo

Retrain the main finalist, and C4 if available, on every normalized name marked `train` in the existing split—candidate training plus outer validation. Preserve the chosen algorithm, hyperparameters, C3 iteration count if applicable, and validation threshold. Do not retune.

Export each finalist with skl2onnx:

- input named `features`;
- dense output named `probabilities`;
- no ZipMap;
- class order recorded in metadata;
- input width 38 for the main finalist and 39 for C4.

Write metadata with feature names, target/class order, algorithm settings, threshold, validation-split hash, training counts, environment versions, tracker-list provenance when applicable, and model hashes.

Verify ONNX against scikit-learn on 1,000 outer-validation rows selected with `random.Random(2026111007)`. Require maximum absolute probability difference at most `1e-5`. Lock scikit-learn, ONNX, and metadata hashes plus verification results. Only after that lock may evaluation code read a test assignment, test label, or test prediction.

## 9. Single final test

Open the unchanged test split exactly once after finalist locking.

### 9.1 Test views and resampling

- **T-B, main:** one record per test normalized name using the retrain study's seed `random.Random(2026111303)`. Bootstrap normalized names 1,000 times with NumPy seed `2026111304`.
- **T-A:** all test records. The paired bootstrap cluster is the website hash after removing the trailing `:0` or `:1` first-party suffix. Bootstrap 1,000 times with NumPy seed `2026111305`.

Every method receives the same sampled rows in every replicate.

### 9.2 Final methods

Compare:

1. main finalist at its frozen threshold;
2. C4 at its frozen threshold, if available, labeled with tracker-list lookup;
3. M1 from `retrain_test/model/`, using its prespecified tracker rule `P(analytics) + P(advertising) ≥ 0.5`;
4. shipped model, top class `tracking`;
5. shipped rules, label `tracking`;
6. fixed rules with only the approved `_fbp` and leading-underscore UTM pattern corrections;
7. everything-is-a-tracker, a constant positive prediction.

For probabilistic models, report PR-AUC along with balanced accuracy, precision, recall, and F1. For deterministic rules, report the four threshold metrics and mark PR-AUC not applicable. Show the trivial baseline beside the models; its balanced accuracy should be 0.5 when both truth classes are present.

### 9.3 Fixed win rule

The main finalist wins only when its T-B balanced accuracy is higher than M1, the shipped model, shipped rules, fixed rules, and everything-is-a-tracker, and every paired 95% range for `main finalist − baseline` balanced accuracy is entirely above zero. C4 is reported beside the result but is not treated as a baseline for this main-model win rule. If C4 beats the main finalist, state that plainly.

Lock the complete test-result file immediately. No later result may change the finalist, threshold, feature set, model, prompt, or sample.

## 10. Semi-synthetic tests saved

Repeat the retrain study's Measurement 2 exactly:

- website cookies must have normalized names in the test split;
- use only first-party cookies;
- eligible websites have 10–60 such cookies;
- choose 50 websites per app with seeds `2026111310 + app index` in order Grafana, Jupyter, Datasette, code-server, Django admin;
- remove website cookies sharing a lowercase name with an app cookie;
- preserve tie namespace `2026111320` and the same random expected-position formula.

Add the main finalist and C4 if available, ordering by descending `P(not tracker)`. Preserve M1, M2, shipped model, rules, and random as comparison orderings.

For website cookies, use the saved website-context features. For app cookies, verify `app_features.json`, copy its 38 feature numbers, and recompute only context-dependent fields from the app cookie key and app host—principally `f_third_party_context`. Use the app's registrable host as `currentDomain`; keep `etld_match` exactly as the engine currently computes it. For C4, derive the extra Boolean from the app cookie's domain; do not infer it from the app name.

Report per app and overall mean tests, median tests, within-first-3 share, median mix size, login-cookie names, and whether each app normalized name was train, test, or absent.

## 11. Cloud AI sample

### 11.1 Frozen sample

After the finalist and final-test result are locked, start from the already frozen T-B test rows. Select 300 normalized names without replacement using `random.Random(2026111010)`, then use T-B's previously selected record for each name. Assign shuffled opaque IDs `C001` through `C300` with `random.Random(2026111011)`. Divide the ordered IDs into six prompt files of 50.

The prompt and sample are frozen and hashed before any cloud call. The truth key is stored separately and is not accessible to a cloud session. No model choice or local threshold changes after viewing a reply.

### 11.2 Information shown

For each ID, show only:

- cookie name;
- cookie domain;
- third-party yes/no;
- Secure yes/no;
- HttpOnly yes/no;
- SameSite category;
- lifetime in days or session;
- value length and character-set category.

Do not show values, website names, truth labels, local predictions, other cases' results, or evidence paths.

The prompt defines tracking as analytics or advertising and requests exactly one JSON object mapping every ID to Boolean `tracking`, with no prose. Invalid or missing IDs are counted wrong; do not repair a reply after scoring.

### 11.3 Cloud execution

Use the established LLM-baseline method:

- Codex CLI ephemeral execution in an empty temporary directory;
- model `gpt-6-astra` and reasoning effort `max`, unless unavailable—in which case stop and request approval rather than silently substitute;
- project instructions, tools, shell, browser, web search, apps, plugins, memories, skills, and user configuration disabled;
- identical prompt bytes sent through standard input;
- model, CLI version, exact flags, timestamps, token usage, prompt/reply hashes, and warnings recorded;
- replies saved verbatim before scoring.

For each of the six 50-cookie prompt files, run three independent fresh sessions, giving 18 isolated sessions total. This applies the earlier “three fresh sessions” method separately to every batch and prevents one batch from influencing another. Failed infrastructure calls may be retried, but every attempt and reason is recorded; completed model replies are never discarded.

Record wall-clock time per prompt and divide each successful prompt time by 50 for cloud seconds per cookie. For the local comparison, quote both shipped-model timings from `llm_baseline/local_timing.json`:

- warm mean per cookie = warm mean batch time divided by 11;
- cold-process mean per cookie = cold-process mean divided by 11.

Label these practical execution-path timings, not matched inference-only timings. Optionally measure the finalist locally with the same 300 rows, but do not replace the required saved local baseline.

### 11.4 Cloud scoring

Only after all 18 replies are saved, score each of the three 300-cookie runs and compare with the main finalist, M1, shipped model, and shipped rules on the identical sample. Report balanced accuracy with paired name-bootstrap 95% ranges using seed `2026111012`, plus precision, recall, F1, and PR-AUC where applicable.

Agreement reporting includes:

- three-way unanimous share across the 300 IDs;
- each pairwise agreement share;
- Fleiss' kappa for the three binary runs;
- count of cookies on which the cloud majority differs from the main finalist.

Frame the local claim only as “highest among methods that run privately on your own computer.” If any cloud run or the cloud majority scores higher, say so plainly.

## 12. Case gallery

Write `case_gallery.json` as the source of truth and render `case_gallery.md` from it. Include 6–8 cases. Each case contains:

- title;
- exactly two explanatory sentences;
- structured numbers with units and denominators;
- evidence file path and, when practical, JSON key or Markdown heading;
- one-line lesson;
- split status for any claim of model improvement.

Every number must be read from a locked result or evidence file. The required cases are:

1. **Version 1's lifetime shortcut:** `_gid` as a version-1 failure only because it is in training for later models. The task text says 18,349 misses, while the current `cookieblock_test/results.md` reports 17,745 under “model wrong and rules right.” Use the evidence-file number and flag this discrepancy; never copy 18,349 without supporting evidence.
2. **A test-split fix:** `_gat`, including M1's documented 5,404 wrong-to-right flips and its final-model status.
3. **Rules' brittle prefix:** shipped `^fbp` versus fixed `^_?fbp`, with measured `_fbp` results from the locked test evaluation.
4. **Jupyter login cookie:** shipped ranking selected `_xsrf`; deletion testing identified `username-jupyter-localhost-8443`.
5. **Datasette login cookie:** rules selected `ds_csrftoken`; compare the locked semi-synthetic rankings for `ds_actor`.
6. **A real final-model miss:** use the most common locked test-split wrong name, without cherry-picking a training name.
7. **Campus Market logout:** FAIL-to-PASS only if evidence exists; otherwise label the case “pending the demo task” and make no numeric PASS claim.

An eighth case may cover website context or the cloud comparison only if it adds a distinct, locked result.

## 13. Coverage report

Write `coverage.md` as one evidence-linked table with no unsupported totals. Include:

- CookieBlock cookies, website IDs, normalized training/validation/test names, and final test rows;
- the five local apps and their verified login cookies;
- every attempted and excluded app with the reason from `local_apps_test/v2/audit_summary.md` and `RUN_NOTE_2026-11-10.md`;
- Campus Market status and evidence;
- all 11 trap cookies and their existing local/cloud coverage;
- the 300-cookie cloud sample, six batches, three runs per batch, and valid/invalid reply counts.

If two evidence files disagree, display both values with a discrepancy note rather than choosing silently.

## 14. Analysis reproducibility and report

`analyze.py` must regenerate `results.json` and `results.md` from locked feature chunks, validation split, validation results, model artifacts, final test result, tests-saved inputs, and cloud reply files. It must not load raw values.

`results.md` includes:

- dates, versions, hashes, counts, sanity checks, tracker-list provenance, and elapsed time;
- every C1–C3 validation result, all four C3 variants, C4 if run, and every selected threshold;
- both final test views, all baselines, PR-AUC for probabilistic methods, paired differences, and fixed verdict;
- semi-synthetic tests saved;
- cloud results, run agreement, timing, and private-local framing;
- limitations;
- review-only draft wording for “version 1 → real data → website context,” “why not a simple rule?”, and “why not ChatGPT?” for favorable and unfavorable outcomes.

Limitations explicitly state:

- consent-banner labels are noisy;
- the dataset is from 2021;
- the test split has been used twice;
- tracker is not login, so run-time deletion still proves the login cookie;
- the shipped extension and npm package do not pass website context until a post-WAICY fix;
- C4 depends on an external tracker list and its license;
- cloud results cover only 300 sampled names and one recorded model configuration.

## 15. Field-aware leak check

During feature extraction, retain every distinct cookie value of at least 8 characters in memory. After all artifacts are created, perform an exact multi-pattern search over every generated data, metadata, model, prompt, reply, result, gallery, coverage, and lock file. The approved protocol and executable source files are code/design inputs, not generated cookie-data outputs, and are listed as out of scope in `value_check.json`; `.venv` and the raw input dataset are also out of scope.

Classify every exact match by parsing its enclosing artifact:

- **Allowed but reported:** the same byte string appears in a cookie-name field, normalized-name field, domain field, or numeric field. Report file, field type, and match count without printing the value.
- **Fail:** the string appears anywhere else, including free prose, a prompt field other than allowed cookie name/domain/numbers, a reply, model metadata string, or an unclassified binary location.

Binary model files are scanned byte-for-byte; any match is failing because they have no allowed textual field. Do not hard-code counts or infer safety solely from the absence of a `value` key. Write `value_check.json` from the measured scan, including all in-scope and excluded files and reasons. A failing match blocks completion.

## 16. Lock order and interruption recovery

After approval, the first write is the SHA-256 of this protocol. `locks.txt` then records, in order:

1. protocol and environment;
2. feature schema, feature chunks, and sanity-check result;
3. validation-split hash;
4. every validation candidate and threshold;
5. main-finalist and C4 selection;
6. final scikit-learn, ONNX, metadata, and verification hashes;
7. single test result and tests-saved result;
8. cloud sample, prompt, reply, scoring, and timing hashes;
9. case-gallery and coverage hashes;
10. leak-check and final report hashes.

Long operations use atomic temporary files and resumable chunks. On resume, verify every existing artifact against its lock before skipping it. Never overwrite a locked split, candidate result, selection, model, test result, or cloud reply.

## 17. Approval gate

Stop after writing this protocol. Before approval, do not:

- add `.gitignore`, `locks.txt`, scripts, features, tracker-list files, validation splits, prompts, cloud samples, replies, models, galleries, or coverage files;
- compute or inspect context features or sanity-check aggregates;
- create validation or inner-stopping assignments;
- train, export, time, or evaluate any candidate;
- inspect a test prediction or test aggregate;
- call a cloud model.

After approval, hash this exact document before any other accuracy-push artifact is written.

## 18. Approved amendment — November 10, 2026

Avelyn approved this protocol on November 10, 2026, with the following additions. This amendment is part of the protocol and is hashed before any later study artifact.

### 18.1 Ablation A1 — without website context

After the main finalist is selected from C1–C3, train A1 using that finalist's algorithm, hyperparameters, iteration count if applicable, and threshold-selection method, but use the no-context features already frozen under `waicy_2026/retrain_test/features/`. Use exactly the same candidate-training and outer-validation normalized names as the context candidates. Select A1's threshold on V-B using the common grid and tie rule in section 5.

Lock A1 with the finalists and report it in both validation views and in the single final test as **without website context**. A1 is an ablation only: it is excluded from the finalist-selection rule and the fixed win rule, and it cannot change the main finalist or C4.

### 18.2 `_gid` evidence

Use the evidence-file count of 17,745 cases in which version 1 was wrong and the rules were right. Do not use the unsupported task-text count of 18,349. An optional supporting calculation may use only the already locked `cookieblock_test` predictions to count version-1 `_gid` not-a-tracker predictions by truth label; if performed, save and hash that evidence before citing it.

### 18.3 Cloud-table information note

The cloud-comparison table must state that the cloud AI sees the cookie's domain name. The main finalist does not see a domain name or domain identity; it sees only the derived third-party-context flag among its features. C4 additionally sees the derived tracker-list-membership flag. This information asymmetry must be visible next to the comparison, not only in the limitations.

### 18.4 C4 licensing language

`results.md` must state that C4 uses DuckDuckGo Tracker Radar data licensed CC BY-NC-SA 4.0, is shown for comparison only, and is not proposed for the CookieGuard product without a separate license review.
