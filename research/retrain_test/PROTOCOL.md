# Real-cookie retraining protocol

Protocol date: November 10, 2026. Report deadline: November 13, 2026. Decision date: November 14, 2026.

This document fixes the retraining and evaluation design before any new feature is computed, any train/test assignment is made, or either model is trained. Approval of this document is required before work continues.

## 1. Purpose and boundaries

The study asks whether changing only the training data—from 800 synthetic cookies to real CookieBlock cookies—lets the same Random Forest approach beat the shipped rules on normalized cookie names absent from training.

- Do not change product code, the shipped model, or submission materials.
- New study artifacts stay under `waicy_2026/retrain_test/`.
- Reuse the existing CookieBlock extraction; do not download it again.
- Values may be used only in memory to compute features and must never be saved.
- Nothing is submitted, published, pulled, committed, or pushed.
- HEAD must remain `1f0ede1`.

## 2. Fixed data and provenance

- Dataset: `waicy_2026/cookieblock_test/raw/06_Training_Data/tranco_05May_20210510_201615.json`.
- Records: all 304,422 top-level cookie records.
- Dataset archive MD5: `9aece7e28a54a7cfc2250f5c2861ca20`.
- Dataset JSON SHA-256: `71364f0f8484daa950267aebe774a84cc64e8aecca00b562c48d4607dceb3168`.
- License: CC BY 4.0.
- Core package: `@aiscihub/cookieguard-core` 0.3.0.
- Shipped model SHA-256: `6820daa4cb8df4e56d96c6fbf92252b4591d73f6edc1645077ff74f1a54191c2`.

The results cite Bollinger, Kubicek, Cotrini, and Basin, “Automating Cookie Consent and GDPR Violation Detection,” USENIX Security 2022, and Zenodo record 5838646.

## 3. Local environment

After approval, create `waicy_2026/retrain_test/.venv` with Python 3.9.6-compatible pinned versions of:

- NumPy;
- scikit-learn;
- skl2onnx;
- ONNX Runtime.

Record Python and package versions in `locks.txt` and `results.md`. Add a study-local `.gitignore` for `.venv/`, `features/`, and `model/`. No global installation is allowed.

## 4. Cookie mapping and feature extraction

Process the dataset in insertion order and use only `variable_data[0]`, the first observation. The mapping is exactly the approved mapping in `cookieblock_test/score_cookies.mjs`:

| Core field | Dataset source |
|---|---|
| `name` | Record `name`. |
| `value` | First observation `value`, held in memory only. |
| `domain` | Record `domain`. |
| `path` | Record `path`, falling back to `/` only if absent. |
| `secure` | First observation `secure === true`. |
| `httpOnly` | First observation `http_only === true`. |
| `sameSite` | `no_restriction` → `None`, `lax` → `Lax`, `strict` → `Strict`. |
| `hostOnly` | First observation `host_only === true`. |
| `expirationDate` | Omitted for session cookies; otherwise extraction time plus `max(0, expiry)` seconds. |

Call `extractCookieFeatures(cookie)` from `@aiscihub/cookieguard-core` 0.3.0 and serialize the 38 numeric features in `FEATURE_NAMES` order. Before extraction, verify that `FEATURE_NAMES` exactly matches the shipped model metadata.

Feature files are resumable chunks of 10,000 records, written atomically under `features/`. Each row contains only:

- record index;
- the same website ID representation used by `cookieblock_test`;
- lowercase-and-trimmed name;
- normalized name;
- CookieBlock label;
- the 38 numeric feature values.

Each completed chunk receives a SHA-256 entry in `locks.txt`. No cookie value, raw observation, URL containing a value, or derived reversible value representation is saved.

## 5. Name normalization

Normalize a cookie name deterministically:

1. Convert to lowercase and trim surrounding whitespace.
2. Split while preserving `_`, `.`, and `-` separators.
3. Replace a non-separator segment with `#` when it has at least 6 characters and either:
   - contains at least one ASCII letter and at least one digit; or
   - consists only of hexadecimal characters and has at least 8 characters.
4. Rejoin using the original separators.
5. Replace every remaining run of one or more digits with `0`.

The hexadecimal test is case-insensitive and requires the entire segment to match `[0-9a-f]+`. Empty segments created by leading or repeated separators remain empty. Percent signs and other characters do not act as separators.

### 5.1 Twenty real examples

These names already occur in the completed CookieBlock study output; they were inspected only to document this rule. No feature or split was computed.

| Real cookie name | Normalized name |
|---|---|
| `VISITOR_INFO1_LIVE` | `visitor_info0_live` |
| `_gat_UA-131465162-3` | `_gat_ua-0-0` |
| `_gat_UA-377240-26` | `_gat_ua-0-0` |
| `intercom-id-zy5uzrp0` | `intercom-id-#` |
| `intercom-session-zy5uzrp0` | `intercom-session-#` |
| `__csrf_token-1` | `__csrf_token-0` |
| `fsb_total_price_279740` | `fsb_total_price_0` |
| `AMCVS_D7B27FF452128BAA0A490D4C%40AdobeOrg` | `amcvs_#` |
| `AMCV_D7B27FF452128BAA0A490D4C%40AdobeOrg` | `amcv_#` |
| `_gat_gtag_UA_111147133_1` | `_gat_gtag_ua_0_0` |
| `WC_AUTHENTICATION_-1002` | `wc_authentication_-0` |
| `etf4_session` | `etf0_session` |
| `TapAd_3WAY_SYNCS` | `tapad_0way_syncs` |
| `_ga_YKK4GC49SR` | `_ga_#` |
| `_dc_gtm_UA-27781823-16` | `_dc_gtm_ua-0-0` |
| `3060738.3440491` | `0.0` |
| `_sp_id.3d9b` | `_sp_id.0d0b` |
| `tc_tp00` | `tc_tp0` |
| `tk_r3d` | `tk_r0d` |
| `yith_wcwl_session_5c27123ef633899817dff8985f9b8dd1` | `yith_wcwl_session_#` |

Before feature extraction, the implementation will unit-test these exact pairs. A failed example stops the run.

## 6. Train/test split by normalized name

All records sharing a normalized name must be assigned to the same side.

1. Build the sorted list of distinct normalized names.
2. Shuffle that list with Python `random.Random(2026111301)`.
3. Let `n_train = floor(0.8 × number of normalized names)`.
4. Assign the first `n_train` shuffled names to train and the remainder to test.
5. Write the complete normalized-name mapping to `split.json` atomically.
6. Record the split SHA-256 in `locks.txt` before training.

This is not stratified, resampled, or adjusted after inspecting class counts. Report the resulting name, cookie, and class counts without changing the split.

## 7. Test-split embargo

Training code may read `split.json` only to select training rows. It must not calculate test metrics, inspect test-name errors, or select test examples until both models are trained, exported, and hashed in `locks.txt`.

The sequence in `locks.txt` must be:

1. approved protocol hash and environment versions;
2. feature-chunk hashes;
3. split hash;
4. M1 and M2 scikit-learn artifact hashes, ONNX hashes, and metadata hashes;
5. ONNX verification result;
6. analysis and result hashes.

## 8. Models fixed in advance

Both models use `sklearn.ensemble.RandomForestClassifier` with no tuning:

```text
n_estimators=150
max_depth=12
min_samples_split=5
min_samples_leaf=2
class_weight='balanced'
random_state=42
```

CookieBlock classes retain their integer meanings and fixed order:

1. `0`: necessary;
2. `1`: functional;
3. `2`: analytics;
4. `3`: advertising.

### 8.1 M1 — main model

Input: the 38 `FEATURE_NAMES` features only. Target: the four CookieBlock classes. This is the main model because it can use today's feature extractor without adding new feature types.

### 8.2 M2 — secondary model

Input: the same 38 features followed by 256 dense hashed name features generated from the lowercase-and-trimmed, unnormalized cookie name using:

```text
HashingVectorizer(
    analyzer='char_wb',
    ngram_range=(2, 4),
    n_features=256,
    alternate_sign=False
)
```

No IDF fitting, vocabulary fitting, scaling, or tuning is added. M2 asks whether failures come from the data or from the existing feature set. Shipping M2 would require a post-WAICY engine change.

## 9. Model export and verification

Before export, inspect the shipped ONNX graph's input and output names and types without scoring a test row. Export M1 and M2 with skl2onnx so that:

- the numeric input is named `features`;
- class probabilities are available from an output named `probabilities`;
- probability columns follow class order `[0, 1, 2, 3]`;
- ZipMap is disabled so probabilities are a dense numeric tensor.

Write `model/m1_meta.json` and `model/m2_meta.json` with feature names, class order, training-name count, training-row count, split SHA-256, library versions, and model SHA-256.

After both exported models and metadata are hashed, select 1,000 test rows using `random.Random(2026111302)`. For each model, compare every ONNX probability with scikit-learn `predict_proba`; the maximum absolute difference must be at most `1e-5`. Failure stops analysis and is reported.

## 10. Baselines

### 10.1 Shipped model and shipped rules

Reuse `waicy_2026/cookieblock_test/predictions/chunk-NNN.jsonl`, keyed by record index. Before reading predictions, verify every chunk against its corresponding SHA-256 in `cookieblock_test/locks.txt`. The shipped model uses the saved full probability vector; its prediction is the highest-probability class, with metadata class order breaking exact ties. The shipped rules use the saved label and score.

### 10.2 Fixed rules

Create a study-only copy of the shipped rule-classification path. It must be identical except for these two regular expressions:

- replace `/^fbp/i` with `/^_?fbp/i`;
- replace `/^utm/i` with `/^_*utm/i`.

No product or vendored engine file is edited. Before evaluation, verify on nonmatching names that the study copy produces the same result as the shipped implementation, and separately unit-test `_fbp`, `fbp`, `_utm`, `__utm`, and `utm` as matching the corrected patterns. This is a prespecified comparison, not tuning.

## 11. Measurement 1 — tracker detection on test names

Truth is tracking for labels 2 analytics and 3 advertising; labels 0 necessary and 1 functional are not tracking. Report and exclude any other label.

- M1 and M2 say tracking when `P(analytics) + P(advertising) ≥ 0.5`.
- The shipped model says tracking when its highest-probability class is `tracking`.
- Shipped and fixed rules say tracking when their label is `tracking`.

### 11.1 Views

**T-B — main view:** group test records by normalized name and choose one record uniformly from each group with `random.Random(2026111303)`. Bootstrap normalized names with replacement 1,000 times using NumPy seed `2026111304`.

**T-A — all test cookies:** include all cookies assigned to test names. Bootstrap exact website-ID clusters with replacement 1,000 times using NumPy seed `2026111305`.

All bootstrap comparisons are paired: each replicate applies the same sampled names or websites to every method.

### 11.2 Metrics and verdict

Report tracking precision, recall, F1, and balanced accuracy with percentile 95% bootstrap ranges for M1, M2, shipped model, shipped rules, and fixed rules.

The main result is M1 F1 versus shipped-rules F1 in T-B:

- **Win:** M1's point F1 is at least 0.05 higher and the paired bootstrap 95% range of `M1 F1 − shipped-rules F1` is entirely above zero.
- **Loss:** M1's point F1 is below shipped-rules F1.
- **Tie/no win:** every other result.

Also report, without additional win rules, paired differences for M1 versus fixed rules and the shipped model, and M2 versus every other method.

## 12. Measurement 2 — semi-synthetic tests saved

This measurement combines real website cookies with the five real local-app cookie sets and is labeled semi-synthetic.

### 12.1 Website cookies and sampling

- Keep CookieBlock website cookies only when their normalized name is assigned to test.
- Keep only first-party cookies, using the same first-party determination recorded by `cookieblock_test`.
- Eligible websites have 10–60 remaining first-party test-name cookies.
- For each app, choose 50 eligible websites without replacement using seed `2026111310 + app index`, with app order Grafana, Jupyter, Datasette, code-server, Django admin.
- Drop website cookies whose lowercase name equals an app cookie's lowercase name.
- Report if fewer than 50 websites are eligible.

### 12.2 App cookies

Verify SHA-256 `edd56682f1a1b90df163b287b24e91c18ab5a43cc5127111dca6e62761de774b` for `waicy_2026/local_apps_test/v2/data/app_features.json` before reading it. Join its keys to each `<app>.labels.json`; a login cookie is one with `loginCookie: true` from the existing deletion test.

- Score app features with M1.
- Append the 256 hashed lowercase-name features and score with M2.
- Score the 38 features with the shipped model.
- Score rules using the vendored engine's `classifyRuleBased(features)`.

The app files are inputs only and are never rewritten.

### 12.3 Orderings

- M1: descending `P(necessary)`.
- M2: descending `P(necessary)`.
- Shipped model: descending `P(authentication)`.
- Rules: authentication-labeled cookies first by descending rule score, then all remaining cookies in deterministic seeded-random order.
- Random: exact expected first-login position `(n + 1) / (k + 1)` for `n` cookies and `k` login cookies.

Break model-score and authentication-rule-score ties with SHA-256 of `2026111320|method|app|website ID|cookie key`. Use the same namespace to order the non-authentication rules tail.

For each app and overall, report mean tests, median tests, share within the first 3 tests, and median mix size for all five orderings.

## 13. Analysis reporting

`results.md` must report every result, favorable or unfavorable:

- dates, exact package versions, checksums, split counts, class counts, and elapsed times;
- Table 1 for both tracker-detection views and all five methods;
- the fixed main verdict and paired F1-difference range;
- Table 2 per app and overall;
- M1 versus shipped-model changes: 15 most common test names flipped wrong-to-right and 15 flipped right-to-wrong;
- the split location and outcome for `_gid`, `_gat`, and `optanonalertboxclosed`;
- M1's top 10 impurity-based feature importances compared with the shipped model's recorded feature importances, labeled as descriptive rather than causal;
- limitations and the required CookieBlock citation;
- review-only slide and spoken-answer drafts for both win and no-win outcomes.

`analyze.py` must recreate `results.json` and `results.md` using only locked features, split, model artifacts, saved CookieBlock predictions, and frozen app inputs. It must not load raw cookie values.

## 14. Leak check

During feature extraction, hold every CookieBlock value of at least 8 characters in memory. After all outputs exist, search the raw bytes of every non-ignored output file for every complete held value using an exact multi-pattern search. Report:

- number of values searched;
- number and names of files containing at least one complete value of length 8 or more;
- count of matching values per affected file, without printing the values;
- separately, short overlaps under 8 characters that are expected from names, domains, labels, or numeric fields, with the reason for classifying them as incidental.

The required long-value file count is zero. Any complete value match of length 8 or more fails the privacy check; it is not automatically dismissed as incidental. The check itself must not write the value set to disk.

## 15. Known limitations

- Consent-banner labels are noisy.
- The data is from 2021.
- Necessary does not mean login; M1 cannot identify which necessary cookie maintains a signed-in session. The run-time deletion test remains necessary.
- M1 has no authentication class and cannot replace the shipped model inside `createOnnxClassifier`.
- M2 requires a new name-hashing feature path and therefore is not shippable without an engine change.
- Normalized-name grouping reduces obvious name memorization but cannot eliminate semantic similarity between training and test names.
- Random Forest impurity importances can favor continuous or high-cardinality features and are descriptive only.

## 16. Approval gate

Stop after writing this protocol. Before approval, do not:

- create a feature file or feature chunk;
- enumerate normalized names to create a split;
- write `split.json` or `locks.txt`;
- install the training environment;
- fit, export, inspect predictions from, or evaluate a model;
- inspect test membership or compute any metric.

After approval, the first recorded artifact is the SHA-256 of this exact protocol, followed by environment versions and then the ordered feature, split, model, verification, and result locks.

## 17. Approved corrections — November 10, 2026

These corrections were approved with the protocol and take precedence over the corresponding earlier wording:

1. **Normalization:** a segment made only of digits never becomes `#`. The all-hexadecimal rule applies only to a segment that contains at least one letter from `a` through `f`. Digit-only segments remain unchanged until step 5, when every digit run becomes `0`. The 20 examples in section 5.1 remain unchanged and are the required normalization unit tests.
2. **Measurement 2:** for every app cookie, report whether its normalized name belongs to M1's training split, and include that status in Table 2.
3. **View T-A:** website bootstrap clusters use the CookieBlock website hash after removing its trailing `:0` or `:1` first-party suffix.
