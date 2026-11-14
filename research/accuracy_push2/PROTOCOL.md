# Accuracy push 2 protocol

Protocol date: November 10, 2026. Hard report deadline: November 15, 2026.

The user instructed Codex to write this protocol and “then go ahead.” That instruction is recorded as advance approval to continue after this exact document is hashed. No crawl, fresh-test record, dictionary feature, embedding, split-dependent fit, or model score was computed before this document.

## 1. Purpose and fixed boundaries

This study asks whether private cookie-name knowledge improves the current C2 model and measures every frozen model once on a fresh 2026 dataset. The old CookieBlock test split will not be scored, inspected for errors, or used for any choice again.

- Work only in `waicy_2026/accuracy_push2/`.
- Do not change `packages/`, `integrations/`, `extension-standalone/`, `backend/`, `examples/`, submission materials, or models outside this folder.
- Keep HEAD at `1f0ede1`; do not pull, switch branches, commit, push, submit, or publish.
- The only outward actions are the pinned-source downloads and the public home-page crawl described here.
- Cookie values may exist in memory only. No output may contain a value or reversible value representation.
- Preserve all unsuccessful variants, exclusions, crawl failures, and unfavorable results.

## 2. Locked sources and licenses

After this protocol is hashed, download each source once into ignored input storage and verify the identity below before use.

| Source | Frozen identity | License and use |
|---|---|---|
| Tranco | Daily list `947N2`, created `2026-11-09T22:00:01.753741`, top 20,000 download; expected SHA-256 `c264ec165cccb4b2b1e615e6dacc57bfc004f14600b85c865a9a403000a7150f` | Tranco research list; record its citation and terms in the report |
| CookieBlock crawler logic | `dibollinger/CookieBlock-Crawler-Prototype` commit `da7e1d3167c131555203a664d4a5dac2b9e6ea54`, license SHA-256 `6ff15a3c37f0788769547926cb3400db0eeb9740630265a3507d0a894b7a2709` | BSD 3-Clause; inspect and reimplement only the bounded declaration logic |
| Open Cookie Database | `jkwakman/Open-Cookie-Database` commit `7786335566460016f07a50705a92fc781c976f6f`, CSV SHA-256 `ed4836ea285719d77c7340582be68d355f7358edded50e6b96bb3139fc0eb8c0`, license SHA-256 `c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4` | Apache-2.0 |
| `all-MiniLM-L6-v2` | Hugging Face revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41` | Apache-2.0 |

The MiniLM files are pinned as follows:

| File | Required SHA-256 |
|---|---|
| `onnx/model.onnx` | `6fd5d72fe4589f189f8ebc006442dbb529bb7ce38f8082112682524616046452` |
| `tokenizer.json` | `be50c3628f2bf5bb5e3a7f17b1f74611b2561a3a27eeab05e5aa30f411572037` |
| `tokenizer_config.json` | `acb92769e8195aabd29b7b2137a9e6d6e25c476a4f15aa4355c233426c61576b` |
| `special_tokens_map.json` | `303df45a03609e4ead04bc3dc1536d0ab19b5358db685b6f3da123d05ec200e3` |
| `config.json` | `953f9c0d463486b10a6871cc2fd59f223b2c70184f49815e7efbcab5d8908b41` |

Reuse Python 3.9.6 from `waicy_2026/retrain_test/.venv` and Node packages from `waicy_2026/local_apps_test/node_modules`. Record every installed package and version. `tokenizers` may be added to the reused environment; PyTorch, TensorFlow, and `sentence-transformers` must not be installed.

## 3. Crawl scope and conduct

Process Tranco ranks 1 through 20,000 in order and stop after 1,000 sites produce at least one usable matched cookie, or after rank 20,000. If fewer than 300 unseen normalized names exist by November 13, freeze and report what exists.

- Visit only `https://<domain>/`, falling back once to `http://<domain>/` only when HTTPS navigation fails before a document response.
- Use Playwright Chromium with a normal stable desktop-Chrome user-agent string recorded in metadata. Do not reuse a personal browser profile.
- Use at most four simultaneous sites, a 30-second whole-site deadline, and at most one retry for transient navigation/network failure.
- Do not log in, submit forms, follow site links, evade geolocation, change proxies, bypass TLS errors, or work around rate limits, CAPTCHAs, access-denied pages, bot challenges, or consent-region blocks.
- On a CAPTCHA or block page, stop that site immediately and record only a categorical failure reason.
- The only permitted interaction is affirmative consent through the detected CMP's own JavaScript API.
- Save no page HTML, screenshot, response body, declaration body, URL path/query, CAPTCHA text, or console/network transcript.

Each attempt is written atomically as one result record. Resume data collection by verifying completed chunk hashes and skipping their ranks. Chunks contain 100 attempted ranks. The crawler writes periodic counts but no model score. The privacy scan has a stricter recovery rule in section 14 because values and value hashes cannot be checkpointed.

## 4. CMP detection, declaration endpoints, and consent

Support only Cookiebot and OneTrust-family deployments detected on the loaded home page.

### 4.1 Cookiebot

Detect a valid UUID from a script `data-cbid`, a `consent.cookiebot.com/<UUID>/cc.js` URL, or a `cbid=<UUID>` query parameter. Retrieve only:

`https://consent.cookiebot.com/<UUID>/cc.js?referer=<final-home-host>`

with the home page as the HTTP Referer. Parse only the five arrays used by the pinned CookieBlock prototype:

- `cookieTableNecessary` → not tracker;
- `cookieTablePreference` → not tracker;
- `cookieTableStatistics` → tracker;
- `cookieTableAdvertising` → tracker;
- `cookieTableUnclassified` → exclude.

If `window.Cookiebot.submitCustomConsent` exists, call `submitCustomConsent(true, true, true)` for preferences, statistics, and marketing. Otherwise exclude the site; do not simulate a banner click.

### 4.2 OneTrust, Optanon, CookiePro, and CookieLaw

Detect `data-domain-script` and its script source, or a directly referenced consent script, only on these pinned CookieBlock host families:

- `cdn.cookielaw.org`;
- `cmp-cdn.cookielaw.org`;
- `optanon.blob.core.windows.net`;
- `cookie-cdn.cookiepro.com`;
- `cookiepro.blob.core.windows.net`;
- `cdn-ukwest.onetrust.com`.

For JSON/ruleset deployments retrieve:

1. `<source>/consent/<domain-id>/<domain-id>.json`;
2. the first English ruleset at `<source>/consent/<domain-id>/<ruleset-id>/{en|en-gb|en-us}.json`.

For directly referenced deployments retrieve only the already referenced `<source>/consent/<UUID><suffix>.js`. Do not discover or crawl unrelated endpoints.

Use the CookieBlock prototype's ordered English group-name mapping: advertising patterns first, then necessary, analytical, functional, and unclassified. The fixed default OneTrust group-ID interpretation is:

| Group ID | Default category | Binary truth |
|---|---|---|
| `C0001` | Strictly Necessary | not tracker |
| `C0002` | Performance/Analytics | tracker |
| `C0003` | Functional | not tracker |
| `C0004` | Targeting/Advertising | tracker |
| `C0005` | Social Media/Advertising | tracker |

For any custom or renamed ID, map only when its English `GroupName` matches the pinned crawler's ordered patterns: advertising, ads, targeting, marketing, tracking, tracker, fingerprint, or sale of personal data → tracker; measurement, analytic, anonymized, research, or performance → tracker; necessary, essential, or required → not tracker; functional, preference, security, or secure → not tracker; uncategorized or unknown → exclude. Exclude every other group as unknown. When declarations conflict, tracker takes precedence, matching CookieBlock's less-privacy-preserving rule.

If `window.OneTrust.AllowAll` exists, call it and wait for `OneTrustGroupsUpdated`; otherwise, if `window.Optanon.AllowAll` exists, call that API. If neither exists, exclude the site; do not click the banner.

## 5. Observed cookies and declaration matching

For a usable declaration:

1. Start in a clean browser context and load the home page.
2. Invoke the CMP API to accept all.
3. Wait for the consent update, reload the final home page, then wait exactly 5 seconds after `domcontentloaded`.
4. Read browser-context cookies and keep the first observation per `(name, normalized domain, path)` in Playwright order.
5. Match declared and observed cookie names byte-for-byte. Normalize domains by lowercase, IDNA, one removed leading dot, and no trailing dot. A declaration with an empty domain matches by name; otherwise the observed domain must equal the declared domain or be its subdomain. Do not use fuzzy name matching.
6. If the same observed key has conflicting declared labels, tracker wins. Exclude unknown or unclassified labels.

Shape the cookie exactly as `waicy_2026/retrain_test/extract_features.mjs` does. Lifetime is `max(0, expirationDate − crawl timestamp)`; session cookies have null lifetime. `currentDomain` is the visited site's registrable eTLD+1 through the existing `tldts` package. Extract the same 38 ordered context features through the vendored CookieGuard engine.

Save only:

- record index and Tranco rank;
- site ID `SHA-256("947N2:" + rank + ":" + input domain)`;
- CMP family and declaration category/group ID;
- cookie name, normalized name, normalized cookie domain, and path;
- binary label;
- Secure, HttpOnly, SameSite, host-only, session status, lifetime seconds, and value length/character-set shape;
- the 38 numeric features;
- declaration-match method.

Never save the input site domain, final URL, page content, declaration description, cookie value, value hash, or value prefix.

## 6. Fresh-name exclusion and freeze

Use the corrected `normalize_name` function and its 20 tests from `retrain_test`. Exclude every record whose normalized name is assigned `train` in `waicy_2026/retrain_test/split.json`; this includes all candidate-training and outer-validation names in `accuracy_push/validation_split.json`. Also exclude any name missing from the old split mapping only when it duplicates another kept fresh normalized name for F-B; it remains available in F-A.

Report records and normalized names dropped for old-training overlap, unknown label, unmatched declaration, and duplicate observation. Do not exclude names merely because they occur in the old test split; the old test labels and predictions are never opened, but those names were never trained and remain eligible.

Write `fresh_test/chunk-*.jsonl`, `fresh_test/schema.json`, and `fresh_test/manifest.json` atomically. The manifest records every chunk SHA-256, crawl counters, source hashes, crawl timestamps, feature schema, and normalized-name count. Lock the manifest and all chunks before loading any fitted model or generating any model prediction. Fewer than 300 names triggers the prespecified small-sample report, not post-freeze crawling.

## 7. Fixed training and validation data

Reuse without change:

- `accuracy_push/features/` for 38 context features;
- `accuracy_push/validation_split.json` for candidate-training versus validation names;
- V-B's one-row-per-name selection using `random.Random(2026111004)`;
- C2 Random Forest settings: `n_estimators=150`, `max_depth=12`, `min_samples_split=5`, `min_samples_leaf=2`, `class_weight='balanced'`, `random_state=42`, `n_jobs=-1`;
- binary truth: analytics or advertising is tracker.

No fresh-test row may enter training, validation, threshold selection, feature design, dictionary processing, embedding checks, or model selection.

## 8. Variant A — Open Cookie Database

The task text says “7 features” but describes seven one-hot states plus a wildcard flag, which would total eight. To preserve the stated total, A has exactly seven features:

1. exact Functional;
2. exact Marketing;
3. exact Analytics;
4. exact Security;
5. exact Necessary;
6. exact Personalization;
7. wildcard-prefix match.

No exact match is encoded as six zeros; there is no separate none column. Exact matching is byte-for-byte after trimming the database field, with duplicate exact names resolved only when every entry agrees; conflicting exact entries encode none and are counted. The wildcard flag is 1 when the cookie name starts with any database entry whose `Wildcard match` field is true. Exact entries take priority for the six category indicators, while wildcard category is deliberately not inferred. Do not edit, supplement, or filter the database using CookieBlock or fresh-test labels.

Write and lock a dictionary manifest with source hash, license, row counts, category counts, duplicates, conflicts, wildcard count, and training/validation coverage before fitting A.

## 9. Variant B — local name embeddings

Transform each cookie name deterministically:

1. replace `_`, `.`, and `-` with spaces;
2. insert a space between a lowercase letter or digit and a following uppercase letter;
3. insert a space between an acronym and a following capitalized word;
4. collapse whitespace and trim.

Thus `_hjSessionUser_123` becomes `hj Session User 123`. The pinned uncased tokenizer handles case normalization. Encode with special tokens, truncation at 256 tokens, attention masks, and batch padding. Supply `input_ids`, `attention_mask`, and `token_type_ids` only when present in the pinned ONNX graph.

Use the ONNX model's `last_hidden_state`, mean-pool only tokens whose attention mask is 1, then L2-normalize the 384-vector. A zero norm stops the run. Save float32 embeddings by normalized name in atomic chunks of 2,000 names; save no token IDs or token strings. Verify interruption recovery by hashing each chunk. Before training, independently recompute 100 names selected with `random.Random(2026111401)` and require maximum absolute difference at most `1e-6`.

## 10. Four candidates and threshold selection

| ID | Input width | Features |
|---|---:|---|
| Base | 38 | context features |
| A | 45 | Base + 7 dictionary features |
| B | 422 | Base + 384 embedding numbers |
| A+B | 429 | Base + A + B |

Every variant uses the fixed binary C2 Random Forest. Select its threshold from `0.00, 0.01, …, 1.00` on the identical V-B rows, maximizing balanced accuracy; ties choose the value closest to 0.50, then the higher value.

Select the highest V-B balanced accuracy. Any variant within 0.005 of the maximum enters the simplicity tie set, ordered Base, A, B, A+B. Report all validation balanced accuracies, precision, recall, F1, PR-AUC, thresholds, fit times, inference times, and model sizes. Lock results and selection.

## 11. Final retraining and ONNX export

Retrain all four variants on every old `train` name—candidate training plus validation—using frozen features, settings, and thresholds. Export each Random Forest to ONNX with input `features`, output `probabilities`, no ZipMap, and widths 38, 45, 422, and 429.

Verify scikit-learn against ONNX on 1,000 outer-validation records selected with `random.Random(2026111402)`. Require maximum absolute probability difference at most `1e-5`. Metadata records feature order, class order, thresholds, source hashes, dimensions, training counts, versions, and the fact that B requires the separate pinned embedding runtime. Lock joblib, ONNX, metadata, and verification files before opening a fresh-test model score.

## 12. Single fresh-test evaluation

After model locking, open the frozen fresh test once.

- F-B: group by normalized name, sort names, and choose one record per name with `random.Random(2026111403)`. Bootstrap normalized-name rows 1,000 times with NumPy seed `2026111404`.
- F-A: use every kept record and bootstrap site-ID clusters 1,000 times with NumPy seed `2026111405`.

Evaluate Base, A, B, A+B, shipped model, M1, frozen accuracy-push C2, shipped rules, the approved fixed rules, and everything-is-a-tracker on identical rows. Report balanced accuracy, precision, recall, F1, and PR-AUC for probabilistic methods, with paired percentile 95% ranges for threshold metrics and balanced-accuracy differences.

The selected variant replaces C2 in the demo only if its F-B balanced accuracy is strictly higher than frozen C2 and the lower bound of the paired 95% range for `selected − C2` is above zero. Otherwise C2 stays. Always report C2's fresh result.

Report exact-name and wildcard coverage of the fresh names by the Open Cookie Database. Report the 10 most common normalized names that A or B changes from Base-wrong to correct, and the 10 most common names still missed by the selected variant; ties use normalized-name lexical order.

## 13. Optional cloud comparison

Run only after the single fresh test is locked and only if time allows by November 14. Select 300 F-B names without replacement using `random.Random(2026111406)`, assign opaque IDs with `random.Random(2026111407)`, and use six batches of 50.

Show the same fields as accuracy push 1: name, cookie domain, third-party flag, Secure, HttpOnly, SameSite, lifetime, and value shape. State unambiguously: “Reply with one JSON object whose keys are the IDs and whose values are `true` or `false`, for example `{"C001": true, "C002": false}`.”

Run three fresh isolated `gpt-6-astra` sessions per batch at reasoning effort `max`, with the same disabled-tool method. Save all 18 replies before scoring. Missing, non-Boolean, or extra IDs are wrong; do not repair. Use bootstrap seed `2026111408`. Compare each cloud run and majority with the selected variant and C2, and report timing and information asymmetry plainly.

## 14. Strict privacy check

One coordinator process retains every distinct cookie value of at least 8 characters in memory only until the final exact-match scan completes. It scans each crawl chunk immediately and also scans every later generated output before that output is locked. It serializes neither values nor value hashes. If that coordinator is interrupted, resumable crawl records remain valid, but before generating or locking any later artifact the coordinator must revisit the already completed ranks under the same public-home-page conduct rules solely to reconstruct the complete in-memory value set. If reconstruction cannot be completed, the study stops and reports that the required leak check could not be established; per-chunk passes are not treated as a substitute for the final whole-output scan.

Search every generated feature, embedding, metadata, split, manifest, model, prediction, prompt, reply, result, gallery, coverage, and lock file. Parse structured fields:

- report exact matches in cookie-name, normalized-name, domain, or numeric fields;
- fail an exact match in every other field, prose location, prompt field, cloud reply, or binary model;
- do not reclassify schema-word or prose collisions as harmless;
- print counts, file paths, and field types but never matched values.

To make the strict rule feasible, generated prose is scanned before locking and any nonessential colliding wording is replaced with a fixed redaction marker. A collision required for an accurate result blocks completion and is reported rather than silently waived.

## 15. Report and reproducibility

`analyze.py` regenerates `results.json` and `results.md` from saved manifests, validation results, model metadata, fresh-test result, and optional cloud replies without loading raw values.

`results.md` includes:

- source versions, licenses, hashes, environments, and elapsed times;
- sites checked, CMP banners detected, usable sites, matched labeled cookies, overlap drops, cookies kept, unseen normalized names, CAPTCHA/block counts, timeout counts, and failure reasons;
- every validation variant and threshold;
- both fresh-test views, every baseline, paired differences, and swap verdict;
- Open Cookie Database exact and wildcard coverage;
- optional cloud table;
- the 10 fixed and 10 still-missed names;
- limits: declaration errors, only Cookiebot/OneTrust coverage, one crawl date, and tracker is not login;
- review drafts for both swap outcomes: “tested on N cookie names from today's websites,” and the on-device language-model story only if B or A+B wins.

## 16. Lock order and recovery

`locks.txt` records immutable SHA-256 entries in this order:

1. this protocol and environment;
2. downloaded sources, versions, and licenses;
3. every crawl chunk and strict per-chunk value check;
4. frozen fresh-test manifest;
5. dictionary and embedding chunks/manifests;
6. validation results and selection;
7. final models and ONNX verification;
8. single fresh-test result;
9. optional cloud sample, prompts, replies, and score;
10. final report and strict leak check.

Atomic temporary files are renamed only after validation. On resume, verify every existing artifact against `locks.txt`; never overwrite a locked chunk, feature manifest, selection, model, fresh-test result, or cloud reply.

## 17. Approval and execution gate

The user supplied advance approval in the same instruction that requested this protocol. After hashing this exact document, execution may continue without a second approval prompt. If a required source hash/license differs, if the crawl would need broader behavior, or if any model/test choice is underspecified beyond this protocol, stop and ask rather than silently substitute.
