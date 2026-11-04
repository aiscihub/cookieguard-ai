# Published-package comparison

This checks the installed PyPI wheels against a real local Chromium browser.
It does not install CookieGuard from this source checkout. The fixture suite
compares identical Browser Use Actor actions with and without the audit; the
[small integration example](../upstream/example/cookie_policy.py) separately
exercises the real `Agent` loop with a scripted model and no API key.

The commands below now install CookieGuard **0.1.0**, published November 4,
2026, with Browser Use **0.13.14**. The recorded 100-trial benchmark and its
original provenance used **0.1.0b1**. To repeat those historical package pins,
substitute `requirements-beta.txt` for `requirements.txt`. Stable-release
verification is recorded separately in [stable-release.json](evidence/stable-release.json);
the old measurements have not been relabeled as stable-release results.

The [PR review follow-up](evidence/review-fixes.json) records the exact-hostname
navigation fix, explicit POSIX setup requirements, and seven passing example
tests. The original benchmark and its source hashes remain unchanged.

From the CookieGuard repository root, with `uv`, Python 3.12, Node.js 24+, and
Chrome/Chromium available:

```bash
uv venv --python 3.12 artifacts/browser-use-validation/venv
uv pip install --python artifacts/browser-use-validation/venv/bin/python \
  -r integrations/browser-use/validation/requirements.txt
artifacts/browser-use-validation/venv/bin/browser-use install
export ANONYMIZED_TELEMETRY=false BROWSER_USE_CLOUD_SYNC=false BROWSER_USE_DISABLE_EXTENSIONS=1
artifacts/browser-use-validation/venv/bin/python -m pytest integrations/browser-use/tests -q
artifacts/browser-use-validation/venv/bin/python -m pytest integrations/browser-use/validation/test_benchmark.py -q
artifacts/browser-use-validation/venv/bin/python -m pytest integrations/browser-use/upstream/example/test_cookie_policy.py -q
artifacts/browser-use-validation/venv/bin/python integrations/browser-use/validation/benchmark.py \
  --repetitions 5 --output artifacts/browser-use-validation/benchmark.json
```

Use `Scripts/python.exe` on Windows. On Linux, install Chromium's system
dependencies as required by Browser Use. This investigation was run on macOS;
the new comparison has not been rerun on Linux or Windows. Ensure `node` is on
`PATH`, or set `COOKIEGUARD_NODE` to its executable. No account, API key, or
separately started web service is needed. The script binds only to loopback.
Do not run other browser tests concurrently with the timing benchmark.

The direct pins above allow platform-appropriate dependency resolution.
[The recorded dependency list](evidence/installed-requirements.txt) captures the
full beta benchmark environment, including validation tooling; it is an
environment record, not a portable cross-platform lock. Wheel hashes, source
comparison and test counts for that run are in [provenance](evidence/provenance.json).

## Fixture ground truth

The policy explicitly names `session_id`, fails on `medium` and above, requires
explicit `SameSite`, and limits lifetime to 30 days. The medium threshold and
explicit SameSite requirement are stricter than the package defaults. Secure loopback HTTP is a Chromium testing
exception; it provides no evidence about production TLS deployment.

| Fixture | Expected decision | Expected confirmed rules |
| --- | --- | --- |
| Secure, HttpOnly, SameSite=Lax | PASS | None |
| Secure, HttpOnly, SameSite=Strict | PASS | None |
| Secure session plus script-readable `theme` preference | PASS | None |
| Missing HttpOnly | FAIL | CG001 |
| Missing Secure | FAIL | CG002 |
| Missing both flags | FAIL | CG001, CG002 |
| SameSite=None under this policy | FAIL | CG003 |
| Omitted SameSite under this policy | FAIL | CG003 |
| Lifetime 31 days | FAIL | CG005 |
| No session cookie issued | INCOMPLETE | None |

The server verifies the issued token before displaying `Login succeeded`.
The missing-session case returns HTTP 401. Ground truth is declared in the
fixtures, independent of CookieGuard output. Each run checks final status,
confirmed rule IDs, server-declaration evidence, browser acceptance, and
`assert_policy()` enforcement. Review findings are reported separately.

## Measurement method

Each arm starts a new local website and browser profile. Both use the same
Actor navigation, button click and completion checks. Baseline instantiates
no audit and reports `NOT_AUDITED`; it is not a competing cookie detector.
The adapter is imported in both arms outside the timer, so import overhead is
excluded. There are two discarded warmup trials. Each case is repeated five
times with the baseline/guarded order alternating. Results use `perf_counter`.

The report retains every measured row and its timing components:

- `workflow_ms`: identical browser actions, with passive observation in the guarded arm.
- `audit_start_ms` and `audit_finish_ms`: measured observer/engine work, including Node startup and audit teardown.
- `audited_workflow_ms`: those three components combined, excluding browser launch/kill.
- `total_ms`: browser construction/start, the audited workflow, a browser-version probe, and browser cleanup.

A companion `.jsonl` journal saves each trial immediately, including execution
errors. Runs refuse to overwrite existing evidence; choose a fresh output path
for another attempt. Failed attempts are not retried or silently discarded.
They remain in detection denominators, are counted separately as execution
errors, and make the validation command exit 1. Timing distributions include
completed runs; paired differences require both arms to have completed.

Imports, server startup/shutdown, serialization, and the final assertion are
outside `total_ms`. Paired differences include the runtime variation of each
independent browser launch. Median, nearest-rank p95, minimum and maximum are
reported; a negative paired difference does not show that the audit speeds up
Browser Use. No throughput, memory, concurrent-session, Cloud, or paid-model
performance claim follows from these measurements.

Detection counts use positive fixture trials; false positives use negative
fixture trials. Missing evidence is scored separately and never counted as a
successful audit. Repetition tests reliability, not fixture diversity. These
handwritten cases do not estimate real-world precision or recall, and do not
cover every CookieGuard rule. Existing adapter tests cover additional cases.

Results and acceptance recommendations: [investigation](../upstream/INVESTIGATION.md).
