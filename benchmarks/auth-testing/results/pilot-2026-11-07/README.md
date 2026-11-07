# Pilot results, 2026-11-07

The 16-run pilot registered in [`../../PROTOCOL.md`](../../PROTOCOL.md), recorded as the
harness produced it. These files are not to be edited.

- **Run:** GitHub Actions run 42402122028, workflow `auth-testing-benchmark.yml`, at benchmark
  commit `4dd92f5`. All 16 jobs succeeded and validation passed.
- **Agent:** Claude Code 2.1.319, model `claude-sonnet-5-5`.
- **Cost:** $1.90 in total, as reported by the CLI.
- **Files:**
  - [`summary.md`](summary.md) and [`summary.json`](summary.json): the harness summary;
  - [`runs.jsonl`](runs.jsonl): every scored run;
  - [`validation.json`](validation.json): the reference suites;
  - [`runs/`](runs): each run's metadata, score, and workspace diff.
- **Changes from the uploaded artifacts:** only credential values, replaced with
  `sess_<redacted>` / `tok_<redacted>`. The values were synthetic and issued by the fixture.
  Transcripts are not copied; they remain in the run's artifacts until the retention period ends.

## What the pilot showed

The harness criteria were met: validation passed, 16/16 runs were scored, no harness
credential was uploaded, and the manual review found no scoring error. The comparison itself
was uninformative:

- **Flaws found but not enforced:** agents named the shown flaw in 6/6 flawed runs per
  condition. None left a failing test for it; most recorded it as a `node:test` `todo` test,
  which keeps `npm test` green.
- **The tool was not used:** in condition B the skill and MCP tools were listed, but 0/8 runs
  used them. Agents said the tests already asserted the flags directly, or that the MCP scan
  only audits preconfigured URLs. The MCP scan cannot log in, and the agents' tests ran the
  app on other ports.
- **Exposure:** the four runs that exposed a session ID (two per condition) were all
  `no-httponly` runs. The agent's own failing assertion printed the full `Set-Cookie` header.

The follow-up study is [`../../../security-gate/`](../../../security-gate).
