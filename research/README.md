# CookieGuard research studies

The preregistered studies behind CookieGuard AI's numbers, released as they were run: each
protocol was written and SHA-256-hashed **before** any crawl, fit, or score it governs
(`locks.txt` in each folder), every test set was opened once, and no file here contains a
cookie value. The folders keep their original names because the protocols refer to each other
by those names; several also carry the heading of the WAICY 2026 entry they were written for.
They are frozen documents and are published verbatim.

The datasets these studies produced are published separately, in [`data/`](../data/README.md).

| Folder | Question | Headline result |
|---|---|---|
| `retrain_test/` | Can the shipped extension model (v1) be improved by retraining on CookieBlock with a name-based split? | First retrained candidates; established the split and the normalized-name rule used everywhere after |
| `cookieblock_test/` | How does the shipped v1 model do on the CookieBlock test split? | Baseline for every later comparison |
| `accuracy_push/` | Which retrained candidate ships? | **C2** (Random Forest, 150 trees, depth 12, 38 features) selected on validation; 71.1% balanced accuracy on 2021 unseen names (T-B), 82.8% on all rows (T-A) |
| `accuracy_push2/` | The first 2026 crawl (Tranco ranks 1–3,300): does private name knowledge help, and how does C2 do on fresh data? | 167 usable sites, 4,043 rows; became the **tuning set** for everything after |
| `combination_check/` | On names never seen in training or tuning (ranks 3,401–12,560), does combining the model with the rules beat either? Same rows to a cloud model | Model 65.6% balanced accuracy; no combiner better; model–rule agreement is a reliability signal (74.1% right when they agree, 54.7% when not); GPT-6 majority 77.3% vs 64.7% on 300 identical rows |
| `name_knowledge/` | On the natural mix of real-site cookies (ranks 12,561–20,000), does a known-name lookup in front of the model help? | **Yes: 80.6% [78.6, 82.5] vs 76.0%**, +4.6 pts [3.8, 5.4]; 11,160 rows, 359 sites; GPT-6 76.1% vs 71.3% on 300 identical rows (difference includes zero); 0.037 ms vs 5.49 s per cookie |

## What each folder contains

- `PROTOCOL.md`, with `APPROVAL.md` or an amendment where one was issued, and `locks.txt`
  listing the SHA-256 of every file that was frozen and when.
- `results.md` and `results.json`: the single-opening report and the numbers behind it,
  including bootstrap intervals and paired differences.
- `analyze.py` (and `evaluate.py`): regenerates `results.json` and `results.md` from the
  frozen predictions **without** crawling, fitting, local inference, or cloud calls.
- `crawl.mjs` (and `coordinator.mjs`): the headless-Chrome crawler that visited each site
  once, read its Cookiebot or OneTrust declaration, accepted the banner through the consent
  API, reloaded, and matched observed cookies to declared entries. Values were held in memory
  only for the incremental leak scan and never written.
- `prepare_cloud.py`, `verify_prompts.py`, `run_cloud.py`, `score_cloud.py` and the `cloud/`
  folder: the identical-row cloud comparison. Prompts carry names, domains, flags, lifetime,
  and value *shape*; replies are Boolean objects. `run_cloud.py` drives the OpenAI model through
  the Codex CLI at a machine-specific path; it is included for provenance, not portability.
- `test/`: the frozen test manifest, schema, frame, restart log, final privacy receipt, and the
  per-row predictions and rule scores that `analyze.py` reads. The raw crawl rows are the
  published dataset in `data/`.
- `name_knowledge/dictionary/`: the known-name tables (D1 selection and deployment builds, the
  Open Cookie Database mapping, and source membership) with `build_selection.py` and
  `dictionary_matcher.py`.

## Rerunning the analysis

```bash
cd research/name_knowledge && python3 analyze.py     # rewrites results.json and results.md byte-for-byte
cd research/combination_check && python3 analyze.py
```

Python 3.9+ with NumPy and scikit-learn. Both scripts were rerun on this published copy:
`results.json` is byte-identical in both studies. In `name_knowledge/`, `results.md` differs
from the regenerated report in two sentences only: the frozen report's cloud-comparison
wording ("cloud AI was more accurate on at least one identical-row comparison") was
corrected after the run to state that the full-sample difference, 4.7 points [−1.0, 10.2],
is not statistically distinguishable from zero; `analyze.py` still prints the original
sentence, and no number changed.

The crawlers need the pinned Playwright Chromium and the vendored
CookieGuard engine referenced at the top of each script; they are published so the collection
can be read and audited, and they will not run without those local paths.

## Labels, in one paragraph

A row's label is the visited website's own declaration of that cookie in its consent banner:
Analytics, Statistics, or Advertising → `tracker`; Necessary, Functional, or Preference →
`not-tracker`. This is the CookieBlock convention (Bollinger et al., USENIX Security 2022).
Sites disagree about some names, and the dataset keeps the votes. The task these studies
measure is tracker classification, which is how CookieGuard's AI layer ranks cookies; it is
not login-cookie identification, which the toolkit proves at run time by removing the cookie
and reloading.

## Not included

`local_apps_test/`, `real_site_test/`, and `llm_baseline/` are earlier operational studies with
small samples (4 scored apps; 5 attempted real sites, 0 scored). Their results files are quoted
in the paper's limitations and can be published on request; they contain vendored third-party
applications and browser profiles that do not belong in this repository.
