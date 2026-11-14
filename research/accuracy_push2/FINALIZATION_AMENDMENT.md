# Accuracy push 2: early stop and verified recollection

Decision recorded November 10, 2026, before any fresh-test model scores. The user accepted the recommendation to stop sample expansion, resolve validation, and finish the results, then instructed: “you can start the next step”. The original `PROTOCOL.md` and every existing locked artifact remain unchanged.

## 1. Early stop

The interrupted crawl completed Tranco ranks 1–3,300: 179 sites yielded 4,129 retained records and 846 normalized names. The incomplete rank-3,301 batch is excluded. The original 1,000-usable-site / 20,000-attempt target is not claimed to have been met. This early stop is a resource decision made without examining fresh model predictions or performance.

## 2. Privacy evidence cannot be reconstructed retrospectively

The interrupted coordinator no longer holds the original cookie values. A revisit may produce new values and cannot prove a scan against the historical values. The original crawl is preserved as preliminary, with its final exact-value leakage check unestablished. It will not supply rows to the final model evaluation.

The recovery pass revisits only the 179 previously usable sites, selected by their saved attempt status before any model scores. No additional site enters the sampling frame. Each site receives one bounded attempt under the original public-home-page, consent-API, four-concurrent-site and 30-second limits. No login, form submission, CAPTCHA bypass, TLS bypass, proxy change, or additional browsing is authorized. HTTPS-to-HTTP fallback retains the original condition.

All new observed cookies, declarations and features are collected again. Failed revisits remain in the report and are not replaced. Original and recovery records are never mixed. The new test therefore describes a successful-revisit subset of the original consent-platform sample, not a representative sample of the entire web. The original selection and recovery attrition will both be disclosed.

## 3. New evidence and privacy gate

New outputs live in `finalization/`. One live coordinator retains all newly observed cookie values of at least eight characters only in memory. Each completed collection batch is checked before acceptance. A complete scan checks the new data, logs, features, embeddings, models and reports before final completion. Matches in name/domain/numeric fields are counted; other matches fail. No values or value hashes are saved. Original unvalidated files and pinned pre-existing inputs are not relabeled as validated by this new scan.

If this coordinator is interrupted or the required scan cannot pass, the recovery study is marked incomplete; visiting sites again is not treated as reconstruction of lost values. A machine-readable status and heartbeat distinguish running, failed and completed work. Completion requires a successful final scan and validated output hashes, not merely a background process exit.

## 4. Freeze and model discipline

The recovery frame, source inventory and this amendment are hashed before collection. Recovery rows and the test manifest are frozen before fitting or scoring any model. The four variants, training/validation split, random seeds, threshold-selection rule, simplicity preference, paired bootstrap, and model replacement rule remain those in the original protocol. No fresh labels or results are used for model design or selection. Only the existing CookieBlock training partition supplies training and validation data.

Implementation corrections are allowed before fitting and must be recorded. In particular, the embedding input is the actual cookie name transformed by the already specified separator/camel-case rules. Normalized names control partitioning and F-B grouping; distinct raw spellings receive their own deterministic embeddings. Reproducibility checks use training names only. This corrects the unexecuted preparation script's use of normalized names as language-model input and prevents fresh names entering the training-side reproducibility check.

The optional cloud comparison is omitted. The final report must state the actual recovered record/name/site counts, uncertainty, consent-platform coverage, interruption and recovery limitations, every candidate result, and the unchanged pass/fail rule for a model replacement. No product model, demo, submission or published material is changed by this work.
