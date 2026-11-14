# CookieGuard AI: A Real-World Cookie Dataset and a Session-Cookie Verification Toolkit for AI Browser Agents

Target: ACM CODASPY 2027, Dataset/Tool paper, **6 pages** (ACM double column, about 4,000 words
of body plus 3 figures and 3 tables). Submission deadline **November 26, 2026**. Internal freeze
November 24. Every number in the paper comes from a frozen results file under `research/` or
`data/`; nothing new is measured for this paper.

## Rules for drafting

- No claim without a file. Each number carries a comment naming its source
  (`research/name_knowledge/results.json`, `data/stats.json`, …).
- The dataset is **consent-declared cookies**, labeled tracker / not-tracker by the site's own
  banner declaration. It is not an authentication-cookie dataset. Never imply otherwise.
- The real-site login study scored 0 of 5 sites. It is stated in Limitations, not hidden.
- Cookie values appear nowhere: not in the paper, not in the artifact.
- Plain words over jargon; a reviewer outside web security should follow Sections 1, 3, and 4.

## Page budget and sources

| Pages | Section | Content | Sources |
|---|---|---|---|
| 0.5 | **1 Introduction** | The gap: secure sign-in protects the password; nothing checks the session cookie the agent carries afterwards. Contributions: (a) the toolkit, (b) the dataset, (c) the evaluation: a local lookup + model ties a frontier cloud model on identical cookies at ~100,000× the speed with no data egress. Availability. | this outline; README |
| 0.5 | **2 Background and related work** | Cookie attributes; session hijacking/fixation in two sentences. CookieBlock (USENIX Sec 2022): same label source, 2021 data. Cookie classification work. Agent security: credential isolation (Browser Use secret bindings), sandboxing. Position: others protect credentials or classify trackers; we verify the session artifact behind an agent. | user writes; cite CookieBlock, Tranco, OCD |
| 1.25 | **3 The toolkit** | **Fig. 1** architecture (from `resource/site/architecture.svg`). AI layer: known-name lookup → Random Forest (150 trees, 38 structural features, never the value). Decision layer, no AI: cross-check (Agree / Verify first; 74.1% vs 54.7% accuracy), deletion proof (remove → reload → still signed in? → restore), session probes (rotation at login, revocation at logout), checks CG001–CG012 (**Table 1**). Surfaces: Browser Use CDP observer with `assert_policy()`, MCP server, CLI/CI, extension. Fail-closed: INCOMPLETE ≠ PASS; the false-success agent case. Privacy: values reach only the local engine over a pipe. | README rule table; `research/combination_check/results.md` §agreement; `integrations/python/docs/how-it-works.md` |
| 1.25 | **4 The dataset** | **Fig. 2** collection pipeline (from `resource/site/data-pipeline.html`, scenes 2–6). Tranco top-20,000 (`947N2`, 2026-11-09); Cookiebot/OneTrust declaration = label; attrition 7,440 → 359 usable with reasons; three rank-disjoint crawls (**Table 2**). Schema: flags, scope, lifetime, value shape, 38 features, `seenInTraining`/`seenInTuning`. Known-names table: 12,481 raw / 7,835 normalized names from 246,505 labeled rows, plus 2,261 OCD entries, with votes. Label noise: 266 of 1,620 names declared both ways; `__cf_bm` Necessary 164× vs Advertising 123×. Privacy by construction: values in memory only, 1,860 incremental scans, 0 leaks. License CC BY 4.0; OCD Apache-2.0; CookieBlock CC BY 4.0. | `data/README.md`, `data/stats.json`, `research/name_knowledge/test/manifest.json`, `research/name_knowledge/results.md` §3, §5 |
| 1.5 | **5 Evaluation** | Method: preregistered, hashed protocols; split by normalized name; single test opening; paired bootstrap 95% CIs (1,000 draws; sites for M-A, names for M-B). **Table 3** balanced accuracy: mix-test (lookup+model 80.6 [78.6, 82.5]; model 76.0; rules 71.7; shipped v1 63.3; everything-tracker 50.0) and unseen-test (model 65.6; rules 62.1; v1 59.9; combiners K2–K5 65.2–65.4, none better than the model). Lookup gain +4.6 pts [3.8, 5.4]. Cloud (GPT-6, max reasoning, 3 runs, majority) on 300 identical rows: 76.1 vs 71.3, difference 4.7 [−1.0, 10.2]; unseen subset 74.3 vs 54.3. Timing: 0.037 ms/cookie warm vs 5.49 s cloud. Toolkit evaluation, scoped: 4 open-source apps, 4/4 first guess; Campus Market conditions PASS / FAIL CG001 / FAIL CG011; agent claiming success without logging in → INCOMPLETE. *If completed by Nov 21:* CookieBlock's public classifier scored on the same mix-test rows. | `research/name_knowledge/results.{md,json}`, `research/combination_check/results.{md,json}`, `research/accuracy_push/results.md`, `waicy_2026/local_apps_test/results.md`, Campus Market `.evidence/` |
| 0.5 | **6 Limitations** | Two consent managers; 4.8% of attempted sites usable; one visit, one US location; labels are declarations and disagree; tracker ≠ login cookie; the real-site login study attempted 5 sites and scored 0 (automated sign-in detection failed); unseen names at 2 in 3; PASS means configured checks passed, not that the app is secure. | `waicy_2026/real_site_test/results.md`; `research/*/results.md` §limitations |
| 0.25 | **7 Availability and conclusion** | PyPI `cookieguard`, npm `cookieguard-ci` and `@aiscihub/cookieguard-mcp`, MCP Registry `io.github.aiscihub/cookieguard`; data at `/data/`; protocols, crawlers, analysis at `/research/`; MIT code, CC BY 4.0 data. | — |

## Figures and tables (exactly these)

- **Fig. 1** Two-layer architecture. Source `resource/site/architecture.svg`; redraw in grayscale-safe palette, 1 column.
- **Fig. 2** Collection pipeline and attrition funnel. Source: walkthrough scenes 2, 4, 5, 6; 1 column.
- **Fig. 3** Balanced accuracy with 95% CIs, mix-test vs unseen-test, five methods; 1 column. From `results.json` files.
- **Table 1** Checks CG001–CG012: rule, what it checks, severity, how it is confirmed. From README.
- **Table 2** The three crawls: rank range, attempted, usable sites, rows, normalized names, job. From the three manifests.
- **Table 3** Accuracy results with CIs and the cloud comparison. From `results.json`.

## Work split and dates

| By | Who | What |
|---|---|---|
| Nov 15 | Claude | `research/` folder public (this PR); outline agreed |
| Nov 17 | Codex | `paper/tables/` (Tables 2–3 as LaTeX, generated from `results.json`, with a script); Fig. 3 as PDF |
| Nov 18 | Claude | Sections 1, 3, 4, 6 drafted in `paper/main.tex` (ACM `sigconf`) |
| Nov 20 | user | Section 2 and related-work citations; first full read |
| Nov 21 | Codex | CookieBlock classifier on mix-test rows, with a one-page protocol first; else a sentence in §2 explaining why not |
| Nov 23 | all | Figures final; second read; page fit |
| Nov 24 | — | Freeze |
| Nov 25 | user | Submit (one day of buffer before Nov 26) |

## Open items

- Authorship and order (Avelyn Jing is the entrant and first author of the WAICY work).
- Anonymization rules of the track (double-blind would require removing the live URLs from the PDF and using an anonymized artifact link).
- Page limit confirmation: 6 pages including references, or plus references.
