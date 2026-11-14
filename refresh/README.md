# Monthly dataset and model refresh

Part A builds timestamped cookie datasets and optional model artifacts. It does not change
the classifier shipped by any package. The implementation lives in this directory; the
Actions workflow and small release-history section in `database.html` are the integration points.

## 1. Checkpoint 1

Worktree: `~/git/cookieguard-ai-refresh`, branch `monthly-refresh`, created from
`origin/main` at `989c3c33f97f9fe731672a34fae75002b11979b1`. The pinned checkout, other branches,
`waicy_2026/`, and `research/` were read only.

The local run is in [`.work/checkpoint-1/REPORT.md`](.work/checkpoint-1/REPORT.md), with
[`grep-proof.txt`](.work/checkpoint-1/grep-proof.txt) and the SHA-256 inventory in
[`privacy-audit.json`](.work/checkpoint-1/privacy-audit.json). These local artifacts are ignored
by Git. No push, PR, asset upload, or package publication has occurred.

- Tranco `Y897G`, seed `202611`, two shards of 50 sites; concurrency four per shard.
- Exactly 100 public sites attempted, zero usable sites. No repeat public crawl was made.
- The checkpoint 1 code classified 69 sites as `robots-unavailable`; it did not retain their
  HTTP statuses or redirect chains. Another 28 had no supported CMP; one each was blocked,
  failed navigation, or had no observed cookie matching its declaration. The fixes below do
  not change this historical evidence or infer the missing causes.
- Health fails. Accuracy and paired intervals are unavailable, so both regression gates fail.
  This result cannot establish candidate accuracy or justify a release.
- The candidate trained on 320,993 historical rows, excluding this month's crawl, and passed
  ONNX parity on 1,000 rows (maximum absolute difference approximately `4.80e-7`).
- All 133 npm tests and the real Browser Use insecure/secure canaries passed with the candidate
  loaded. A separate in-memory browser fixture exercises a usable crawl; its synthetic row
  is never included in the public dataset or its yield.

The state file contains the frozen Tranco `947N2` top 20,000 domains plus these 100 attempted
domains. Failures count as visited. The training gzip and attribution sidecar are built locally
under `.work/inputs/`; `training-source.json` records their SHA-256. The owner approved the
upload on November 14, 2026: the gzip and its attribution sidecar are the release assets of
`refresh-inputs-2021`, the public download matches the pinned SHA-256, and `uploadApproved` is true.

## 2. Code map

| File | Responsibility |
|---|---|
| `build_inputs.py` | Read frozen inputs and produce the value-free, attributed training asset and November 2026 study references |
| `frame.mjs` | Latest Tranco ID/hash, uniform seeded sampling without replacement, exclusions, shard assignments |
| `crawl.mjs`, `cmp.mjs`, `robots.mjs` | Bounded browser visits, consent APIs, declaration matching, 38 features |
| `privacy.mjs` | Incremental in-memory cross-scan of all batches, fixed credential checks, fail-closed receipts |
| `merge.py`, `health.py` | Verify receipts and hashes; count visited sites, robots failures, and CMP families; export datasets and update exclusions |
| `evaluate.py`, `score_rules.mjs` | Freeze production/reference scores before training; compare candidate with paired site bootstraps |
| `train.py`, `lookup.py` | Historical-only C2 training, name-grouped threshold validation, N1 table, ONNX parity |
| `candidate.mjs`, `browser_canary.py`, `canaries.py` | Test-only candidate loading and isolated real Browser Use canaries |
| `gate.py` | Fixed gates, report, candidate model card; missing evidence fails promotion |
| `privacy_audit.py` | Structural checks, actual grep, binary and decompressed scans, output hash inventory |
| `ci.py` | Guarded Actions-only reservations and PR creation; no remote mutation in local execution |
| `../.github/workflows/monthly-refresh.yml` | Monthly schedule and dispatch, 16 shards with at most eight running together |

## 3. Local setup and reproducibility

Use Node 24 and Python 3.12. Install dependencies in the new worktree only:

```sh
export COOKIEGUARD_USAGE_METRICS=0 DO_NOT_TRACK=1 ORT_DISABLE_TELEMETRY=1
npm ci --no-audit --no-fund
npm ci --prefix refresh --no-audit --no-fund
npx --no-install playwright install chromium
python3.12 -m venv refresh/.venv
node integrations/python/scripts/vendor_engine.mjs
refresh/.venv/bin/python -m pip install -r refresh/requirements.lock -r refresh/requirements-browser.txt -e './integrations/python[test]'
```

The local asset builder only reads the frozen checkout:

```sh
refresh/.venv/bin/python refresh/build_inputs.py --frozen-root ~/git/cookieguard-ai
```

The 2021 source stores lowercase feature names; the builder recovers exact case by validated
`recordIndex` from the original input in memory. Only names, normalized names, binary labels,
38 numeric features, and site identifiers are exported. CookieBlock original labels 2 and 3
map to tracker. The attribution sidecar records every source digest and CC BY 4.0 credit.
OCD is frozen at commit `7786335566460016f07a50705a92fc781c976f6f` with its Apache license.

The completed crawl used the following frame command and two shard invocations. **Do not
rerun its public visits.** `frame.json`, `ranking.csv`, `exclusions.txt`, shard receipts, and
`execution.json` preserve the exact inputs and crawler source digests. Started shards refuse
to run again. Reproducing the frame algorithm does not reproduce changing website contents.

After the public dry run, the privacy matcher was made linear in scanned text using the
frozen crawler's multi-pattern algorithm, so full-size shards do not compare every field
against every retained string separately. Its admission rules are unchanged; overlap,
Unicode, later-batch leaks, and the usable browser fixture were rechecked locally. The
original execution digest and final code snapshot distinguish those versions without
revisiting any public site.

```sh
node refresh/frame.mjs --month 2026-11 --sites 100 --shards 2 --out refresh/.work/checkpoint-1 --csv refresh/.work/downloads/tranco-Y897G.csv --list-id Y897G --dry-run
node refresh/crawl.mjs --shard 1 --of 2 --frame refresh/.work/checkpoint-1/frame.json --out refresh/.work/checkpoint-1/shards
node refresh/crawl.mjs --shard 2 --of 2 --frame refresh/.work/checkpoint-1/frame.json --out refresh/.work/checkpoint-1/shards
```

The two crawl processes were run concurrently. The remaining stages are local; they use
`--run refresh/.work/checkpoint-1` and `--release` or `--releases` under
`refresh/.work/checkpoint-1/releases`. Order: merge; evaluate `--phase baseline`; train;
evaluate `--phase candidate`; canaries; gate; privacy audit. Baseline and candidate creation
refuse overwrites. Reports and audits may be regenerated without visiting any site.

Local verification:

```sh
node --test refresh/tests/core.test.mjs refresh/tests/network.test.mjs
node --test refresh/tests/browser.test.mjs
refresh/.venv/bin/python -m unittest discover -s refresh/tests -v
refresh/.venv/bin/python refresh/canaries.py --run refresh/.work/checkpoint-1
refresh/.venv/bin/python refresh/gate.py --run refresh/.work/checkpoint-1 --release refresh/.work/checkpoint-1/releases/2026-11
refresh/.venv/bin/python refresh/privacy_audit.py --run refresh/.work/checkpoint-1 --release refresh/.work/checkpoint-1/releases/2026-11
```

## 4. Interpretation and privacy

Robots policy is checked before navigation. Up to five redirects are followed, including
across hosts, within a five-second request budget. A 2xx policy is parsed; a wildcard disallow
for `/` skips the site. All 4xx responses, including 401/403, impose no restrictions. Server
errors, unhandled protocol errors, redirect loops/limits, and bodies over 500 KiB skip the site.
DNS failures, refused/reset/unreachable connections, and timeouts are `unreachable`; TLS or
certificate failures are `tls-error`. Other request errors are `network-error`. Classification
matches error messages in memory and never stores or prints them. TLS classification takes
precedence when an error also mentions a reset or timeout.

Every attempt records only a `robotsStatus` code: `allowed`, `disallowed`, `absent-4xx`,
`server-error`, `network-error`, `redirect-limit`, `too-large`, `unreachable`, or `tls-error`;
response bodies are never saved.

Declaration requests follow redirects and send `Referer: page.url()`, retaining a seven-second
timeout and five-million-byte body cap. After robots permits HTTPS, an HTTPS navigation failure
before any document response may retry HTTP, after checking robots for that HTTP origin.
Certificate/TLS errors, sites that responded, and policy-blocked redirects never trigger this
fallback. If the initial HTTPS robots fetch itself is `unreachable`, the crawler checks
robots for the HTTP origin first, and navigates directly over HTTP only when permitted. A
`tls-error` never triggers fallback. A host that is unreachable over both origins is skipped.
The selected HTTP origin is not retried if its navigation fails.

The research user agent remains `CookieGuardResearch/1.0`. Monthly releases are not directly
comparable with the November study crawl, which used a Chrome user agent. Hosted Actions also
uses datacenter addresses; consent managers may treat either differently. The hosted pilot
measures the resulting coverage. Every report carries this qualification.

Navigation outside the sampled registrable domain is refused. No login, CAPTCHA solving,
browser trace, HAR, screenshot, storage-state snapshot, or page text is exported. The 30-second
deadline includes robots, navigation, consent, reload, and settling within a browser context.

`visited` means robots permitted an origin and document navigation started. Health requires
both usable sites / visited sites >= 3% and robots response/protocol failures / attempted
sites <= 20%. The latter counts only `server-error`, `redirect-limit`, `too-large`, and
`network-error`, once per site. It does not count the broad `status=robots-unavailable` field.
The denominator remains all attempted sites. Missing denominators fail closed.

`unreachable` plus `tls-error` is reported separately, with its share of attempted sites, as
the study's `navigation-failed` equivalent. There is no gate on this rate. Counts use the final
robots outcome after any fallback; a host recovered over HTTP is not counted as unreachable.
The manifest and report include these rates, all robots status codes, and detected CMP-family
counts (Cookiebot, OneTrust, none), including a detected family whose declaration fetch fails.

The exact row schema follows `data/cookies-2026.jsonl`, adding `crawlDate` and `trancoListId`.
Cookie contents only enter the feature engine and in-memory privacy scanner. Exports contain
numeric features, `valueLength`, and `valueCharacterSet`. No contents field is permitted.
CSV escapes spreadsheet formula prefixes; JSONL retains exact metadata.

The cross-scan follows the frozen crawler: observed strings at least eight characters long
are checked across earlier and current batches. Independent cookie-name/domain matches and
numeric coincidences are accounted for. Short contents are protected by schema rather than
substring matching. Any violation removes that shard's data and emits only a fixed failure
receipt. Unknown arbitrary strings cannot be proven absent by signature grep alone. The
supplied grep is supplementary to the live receipts and fixed-schema checks; no match text
is ever printed. It audits deliverables, including model binaries and the decompressed training
asset, rather than source code or installed dependencies that intentionally contain test data.

Every job and subprocess opts out of usage metrics. The Browser Use demo uses a scripted local
model, no API credentials, and an isolated copy of the bridge. Native ONNX loading is enabled
only in that test copy; the shipping bridge and package defaults are untouched. `test-shell.sh`
preloads the candidate into the existing npm test command, avoiding inheritance into child
CLI processes that verify telemetry opt-in behavior. Raw child logs are discarded.

Training always excludes the current and future monthly releases, dry runs, and quarantined
datasets. It includes the frozen 2021 pool and existing November study as historical inputs.
The fixed forest has 150 trees, depth 12, minimum split 5, minimum leaf 2, balanced weights,
and random state 42. A seeded 20% split holds out normalized names to select the threshold,
then refits the forest on historical rows. Lookup votes are rebuilt only from the same pool.

Accuracy uses website declarations as proxy labels. Metrics and their paired differences use
1,000 site-cluster bootstrap draws. Unseen comparisons use the intersection of rows unseen to
both methods, including lookup membership. Missing classes or too few valid draws yield N/A,
which cannot pass a regression gate. Both production rules and shipped v1 must meet the
lower-bound requirement. V1 membership conservatively uses the full supplied training source,
including validation names; the original exported model's exact fit membership was not recorded.

## 5. Future Actions runs and checkpoint 2

The workflow first refuses to proceed while the training asset's `uploadApproved` flag is
false, and every job downloads the asset and rejects it unless its SHA-256 matches. Replace the
asset only together with a new pinned digest. No personal API key is required.

The schedule is `0 2 1 * *` (02:00 UTC on the first). Dispatch defaults to 10,000 sites,
16 shards, and dry run. Crawl jobs use concurrency four each, `max-parallel: 8`, and a
300-minute job timeout. First attempts on `main` only are accepted.

Before visiting sites, the workflow creates a durable reservation containing only the frame:
`refresh/reservations/YYYY-MM-pilot` for a hosted dry run, or
`refresh/reservations/YYYY-MM` for the real run. One pilot and one real run are allowed per
month. Both kinds of prior reservation join the exclusion set before sampling, even if a run
failed or its dataset PR remains unmerged. The real run therefore excludes the pilot's domains
without the pilot blocking the real reservation. Actions reruns remain prohibited. Do not
delete reservations or rerun a crawl to recover a failed run. The local checkpoints did not
create any remote reservation branches.

After an independent final privacy audit, a real run may open the timestamped dataset PR,
including its report, index entry, and cumulative exclusions. The model PR exists only when
every gate passes and always requires a person. It never receives `auto-merge`.

**The first real run creates draft PRs and requests no merge.** This implements checkpoint 2:
the owner must see the report and both eligible PRs before anything merges. If model gates
fail, there is no model PR; the report explains why. A dataset PR receives `auto-merge` only
when Health passes. If Health fails, it has no such label, requests no auto-merge, and its body
begins: "Health gate failed: a person must review this release." Later healthy dataset PRs
request GitHub native auto-merge only after verifying all four existing CI checks are required
from GitHub Actions with an up-to-date branch. Missing protections leave the PR open.

`GITHUB_TOKEN`-created PRs do not trigger ordinary PR workflows; the publisher explicitly
dispatches `cookieguard-ci.yml` on each new branch. Its only existing-workflow change is adding
`workflow_dispatch`. Tokens stay in the Actions environment, never command arguments or outputs.
The publisher verifies every audited file again before remote writes. No workflow publishes
npm/PyPI packages or makes Part B's default-model decision.

## 6. Checkpoint 1b

The worktree was moved with `git worktree move` to `~/git/cookieguard-ai-refresh`.
The environment was recreated there and its dependencies restored offline, with absolute
editable-install paths corrected. The pipeline was committed locally as `8f5331d4` before
applying the fixes. All checkpoint 1 evidence and all 20,100 excluded domains remain unchanged.

Review [the checkpoint 1b report](.work/checkpoint-1b/REPORT.md),
[fixes.diff](.work/checkpoint-1b/fixes.diff), and
[test-output.txt](.work/checkpoint-1b/test-output.txt). Run the replay with:

```sh
node refresh/tests/replay_robots.mjs
```

The replay uses 69 entirely synthetic in-memory cases: 23 bare-domain-to-www redirects,
23 HTTP 403 responses, and 23 HTTP 503 responses. The original run recorded only an aggregate
69 `robots-unavailable` cases, so this is a representative pattern test, not a reconstruction
of the historical sites. Its fake navigation counts and health demonstration are never
merged into any public dataset or cumulative crawl state. Checkpoint 1b makes zero public
requests and performs no push, PR creation, or upload.

## 7. Checkpoint 1c

The reachability correction separates unreachable and TLS-failing hosts from the robots
response/protocol cap, and enables the HTTP robots fallback before navigation. The new fake
scenarios verify that 25 unreachable plus 5 server errors in 100 attempts passes Health when
yield passes, while 21 server errors fails. Even a high unreachable/TLS share is diagnostic
only. No original crawl or exclusion state is changed.

Review [the checkpoint 1c report](.work/checkpoint-1c/REPORT.md),
[fixes.diff](.work/checkpoint-1c/fixes.diff), and
[test-output.txt](.work/checkpoint-1c/test-output.txt). All validation uses in-memory fakes,
including the existing isolated browser fixture. No public visit, push, PR, or upload is
performed. The changes are committed locally on `monthly-refresh` and stop at checkpoint 1c.
