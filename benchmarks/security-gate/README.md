# Security-gate study

Does CookieGuard add value as a login-test gate that a developer installs, compared with
ordinary Playwright assertions or a small hand-written fixture? The design is in
[`PROTOCOL.md`](PROTOCOL.md), the results in [`results/`](results).

## Part 1: deterministic comparison

No agent and no API key. It needs Node 24 and Chromium:

```bash
npm ci
DEPS=$PWD/.work/deps OUT=$PWD/.work/out
node benchmarks/security-gate/run.mjs matrix  --deps "$DEPS" --out "$OUT" --repeats 3
node benchmarks/security-gate/run.mjs tamper  --deps "$DEPS" --out "$OUT"
node benchmarks/security-gate/run.mjs privacy --deps "$DEPS" --out "$OUT"
node benchmarks/security-gate/run.mjs summarize --out "$OUT"
```

In CI: `gh workflow run auth-testing-benchmark.yml -f study=gate-comparison`.

## Part 2: fix and retest

Paid: one Claude Code session per run. Each run's spend is capped by `max_budget_usd`.

```bash
gh workflow run auth-testing-benchmark.yml -f study=fix-retest -f conditions=N,C \
  -f flaws=no-httponly,logout-kept,js-token -f repeats=2 -f max_budget_usd=0.6
```

## Files

| File | What it is |
| --- | --- |
| [`variants.mjs`](variants.mjs) | The 11 app versions, as exact edits to the pilot's fixture |
| [`approaches/`](approaches) | The three approaches' test code, and the login steps they share |
| [`privacy/idioms.spec.js`](privacy/idioms.spec.js) | 14 common native cookie assertions |
| [`run.mjs`](run.mjs) | Part 1 runner and summary |
| [`agent.mjs`](agent.mjs) | Part 2 harness, which reuses the pilot's isolation and redaction |
