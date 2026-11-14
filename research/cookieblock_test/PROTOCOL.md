# CookieBlock comparison protocol

Protocol date: November 10, 2026. Decision date: November 14, 2026. This protocol is written before any CookieBlock cookie is scored.

## 1. Scope and fixed inputs

This study compares the shipped CookieGuard model with the shipped simple rules on held-out real cookies. It makes no product or model changes and performs no retraining.

- Dataset: CookieBlock `06_Training_Data/tranco_05May_20210510_201615.json`, MD5 `9aece7e28a54a7cfc2250f5c2861ca20`, SHA-256 `71364f0f8484daa950267aebe774a84cc64e8aecca00b562c48d4607dceb3168`.
- Core package: `@aiscihub/cookieguard-core` 0.3.0 from `waicy_2026/local_apps_test/node_modules`.
- Model: `extension-standalone/model/cookieguard_model.onnx`, SHA-256 `6820daa4cb8df4e56d96c6fbf92252b4591d73f6edc1645077ff74f1a54191c2`.
- Runtime: `onnxruntime-node` from `waicy_2026/local_apps_test/node_modules` with CPU execution.
- Rules: `classifyCookie` from the same core package.
- App inputs: the five frozen v2 apps: Grafana, Jupyter, Datasette, code-server, and Django admin. Their existing prediction and label files are read without rerunning the apps.

No output may contain a cookie value. Raw files remain under git-ignored `raw/`. Nothing is submitted or published.

## 2. Cookie mapping

For each top-level CookieBlock record, use only `variable_data[0]`, the first observation. Map it to the core package input as follows:

| Package field | CookieBlock source and normalization |
|---|---|
| `name` | Record `name`. |
| `value` | First observation `value`; held in memory only. |
| `domain` | Record `domain`. |
| `path` | Record `path`, with `/` only if missing. |
| `secure` | First observation `secure === true`. |
| `httpOnly` | First observation `http_only === true`. |
| `sameSite` | `no_restriction` → `None`; `lax` → `Lax`; `strict` → `Strict`. |
| `hostOnly` | First observation `host_only === true`. |
| `expirationDate` | Omitted when `session` is true; otherwise scoring time plus nonnegative lifetime seconds. |

### 2.1 Expiry amendment required by inspection

The requested generic rule was to subtract observation time from an absolute expiry, falling back to May 10, 2021. `INSPECT.md` found that this JSON has no observation-time field and its integer `expiry` is already duration-like: the median positive value is about one year and session observations use zero. Therefore this protocol uses `lifetime = max(0, expiry)` seconds directly. Subtracting the crawl timestamp would turn ordinary persistent cookies into expired cookies. Approval of this protocol explicitly approves this dataset-specific interpretation.

## 3. Model and rules

Copy, rather than import, the `probabilities()` helper and cookie mapping pattern from `waicy_2026/local_apps_test/v2/run_v2.mjs`, so no server starts as a side effect.

1. Confirm `model_meta.json.feature_names` exactly equals `FEATURE_NAMES`.
2. Run `extractCookieFeatures(cookie)`.
3. Build the float vector in `FEATURE_NAMES` order.
4. Run the ONNX model and retain the whole probability vector for every class.
5. The model's predicted class is the class with greatest probability. Ties use model metadata class order.
6. Run `classifyCookie(cookie)` once and retain its label and score.

The model says tracking only when its highest-probability class is `tracking`. The rules say tracking only when `classifyCookie` returns label `tracking`.

## 4. Measurement 1: tracker detection

### 4.1 Truth and exclusions

- Tracking: labels 2 analytics and 3 advertising.
- Not tracking: labels 0 necessary and 1 functional.
- Exclude and report every record with another or missing label. Inspection found zero such records, but scoring rechecks this.

### 4.2 Views

**View A — all cookies.** Use every eligible cookie. Compute 95% percentile bootstrap ranges from 1,000 resamples of websites, sampling website clusters with replacement. A website cluster is the exact `first_party_domain` string. Fixed bootstrap seed: `2026111401`.

**View B — one cookie per name.** Group by lowercase cookie name. Select one record uniformly from each group with `random.Random(2026111402)`. Use that selected record and label. Compute 95% percentile bootstrap ranges from 1,000 resamples of lowercase names with seed `2026111403`.

**View C — unseen names.** Start with View B and exclude names appearing case-insensitively in either `data/training_cookies.json` or any quoted string literal in `backend/generate_training_data.py`. Decode ordinary Python string literals using the Python AST; do not infer dynamically constructed strings. Compute 95% ranges from 1,000 bootstrap resamples of names with seed `2026111404`.

### 4.3 Metrics and main result

For model and rules, report tracking-class precision, recall, F1, and balanced accuracy. If a metric denominator is zero, report it as undefined rather than substituting zero.

For every bootstrap replicate, also compute `model F1 - rules F1`. The main result is View C F1:

- **Win:** point difference is at least 0.05 and the percentile 95% interval of the difference excludes zero on the positive side.
- **Loss:** the model's point F1 is below the rules' point F1.
- **Tie/no win:** every other outcome.

## 5. Measurement 2: tests saved

This measurement is labeled **semi-synthetic** because it combines real cookies from real apps with real cookies from real websites.

### 5.1 App cookies and truth

Read, without modifying, each `<app>.predictions.json` and `<app>.labels.json` under `waicy_2026/local_apps_test/v2/data/`. Match labels by `name|domain|path`. A login cookie is a key marked as a login cookie by the existing deletion test. Read model `P(authentication)`, rules label, and rules score from the prediction file.

### 5.2 Website selection and mixes

For each app independently:

1. Use the first observation for each CookieBlock record.
2. Parse `first_party_domain` and obtain its registrable domain using the public-suffix implementation already available in the local Node dependencies; do not approximate by taking the last two labels.
3. A cookie is first-party when its normalized cookie domain equals that registrable domain or is its subdomain.
4. Keep websites with 10–60 first-party cookies.
5. Select 50 websites uniformly without replacement using seed `2026111405 + app index`, where app order is Grafana, Jupyter, Datasette, code-server, Django admin.
6. Mix that website's first-party cookies with the app cookies. Drop a website cookie when its lowercase name equals any app cookie's lowercase name.

Report if fewer than 50 eligible websites exist for an app.

### 5.3 Orderings and tests needed

- **Model:** descending `P(authentication)`. Break ties with a deterministic SHA-256 ordering of `seed|app|website|cookie key`.
- **Rules:** cookies labeled authentication first, ordered by descending rules score; all remaining cookies follow in a seeded random order. Break authentication-score ties with the same deterministic hash. Random seed namespace: `2026111410`.
- **Random:** do not simulate an ordering. Use the exact expected first-login position `(n + 1) / (k + 1)`, where `n` is the total cookies in the mix and `k` is the number of app login cookies.

For model and rules, tests needed is the 1-based position of the first app login cookie. Website cookies never sign the user out.

Report mean and median tests, share of mixes reaching a login cookie within the first 3 tests, and median mix size, for each app and overall. For random, the within-3 probability is `1 - C(n-k, 3) / C(n, 3)` when `n >= 3`, with the direct finite-population equivalent when `n < 3`.

## 6. Chunking, resume, and privacy

`score_cookies.mjs` processes top-level records in their JSON insertion order in chunks of 10,000. It writes `predictions/chunk-NNN.jsonl` atomically only after a complete chunk. On restart it verifies existing chunk metadata and hashes, then resumes at the first absent chunk.

Each JSONL row contains only:

- record index;
- opaque website ID derived as SHA-256 of the first-party website string, not the website string itself;
- cookie name and domain;
- truth label;
- full model probability vector;
- rules label and score;
- lifetime seconds.

No value, path containing a value, first-party URL, or token is saved. During scoring, keep every cookie value of at least 8 characters in an in-memory set. After output is complete, scan every non-raw output file for exact occurrences. `value_check.json` records files checked, values checked, and files with hits; the required hit-file count is zero.

## 7. Freeze and reproducibility

After approval and before scoring, append to `locks.txt`:

1. UTC timestamp;
2. SHA-256 of this protocol;
3. dataset MD5 and SHA-256;
4. model SHA-256;
5. core package version;
6. all fixed seeds.

After each completed chunk, append its SHA-256. `analyze.py` reads saved prediction chunks and frozen local-app files only and reproduces `results.json` and `results.md`. It does not load cookie values or rerun the model.

## 8. Required reporting

`results.md` reports every result, favorable or unfavorable:

- run date and elapsed scoring and analysis times;
- checksums, cookie and website counts, label and exclusion counts;
- tracker metrics and 95% ranges for Views A, B, and C;
- View C F1 difference interval and fixed-rule verdict;
- per-app and overall semi-synthetic tests-saved metrics;
- median mix size;
- 20 most common names the model gets wrong and rules get right;
- 20 most common names rules get wrong and model gets right;
- one review-only slide line and one answer to “How is this better than a simple rule?” for both win and no-win outcomes;
- the dataset and paper citation.

Citation: Bollinger, Kubicek, Cotrini, and Basin, “Automating Cookie Consent and GDPR Violation Detection,” USENIX Security 2022. Dataset: Zenodo record 5838646, CC BY 4.0.

## 9. Limitations fixed in advance

- Consent-banner labels can be wrong.
- The data is from 2021.
- “Necessary” combines login cookies with other essential cookies, so tracker detection does not directly test login-cookie detection.
- Measurement 2 is semi-synthetic.
- The app study contains only five apps, including one single-cookie app.
- View C's unseen-name definition detects literal name overlap, not semantic or pattern overlap.

## 10. Stop point

No CookieBlock record may be passed to the model or rules until Avelyn approves this protocol, including the dataset-specific expiry interpretation. After approval, freeze the protocol hash before writing any prediction chunk.
