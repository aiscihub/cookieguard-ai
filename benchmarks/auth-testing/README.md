# Auth-testing benchmark

Does adding CookieGuard make the login and session tests Claude Code writes catch more real
authentication-cookie flaws? Each run asks Claude Code to add tests to a small app that has
one seeded flaw, then replays the tests it wrote against the fixed app and every flawed
version. A flaw counts as caught only if the agent's own `npm test` fails on it and passes
on the fixed app.

The design, metrics, and analysis plan are fixed in [PROTOCOL.md](PROTOCOL.md) before any
run.

## Files

| Path | Contents |
| --- | --- |
| [`fixture/`](fixture) | Acme Notes, the Express app the agent works on (the fixed version) |
| [`variants.mjs`](variants.mjs) | The flawed versions, as exact edits to the fixed app |
| [`bench.mjs`](bench.mjs) | The harness: `matrix`, `prepare`, `agent`, `score`, `redact`, `summarize` |
| [`score.mjs`](score.mjs) | Scoring: the replay result, transcript metrics, summaries |
| [`validate.mjs`](validate.mjs), [`reference/`](reference) | Reference test suites with known results, replayed before every dispatch |
| `results/` | Scored results, added after the pilot runs |

## Running it

The runs happen in GitHub Actions, one fresh VM per run:

1. Add one repository secret:
   - `ANTHROPIC_API_KEY`, billed per use. A key with a spend limit is recommended.
   - Or `CLAUDE_CODE_OAUTH_TOKEN`, from `claude setup-token`, which uses a Claude plan.
2. Dispatch the workflow. The pilot defaults are 4 versions × 2 conditions × 2 repeats, which is 16 runs:

   ```bash
   gh workflow run auth-testing-benchmark.yml
   ```

3. Each run uploads `run-<version>-<condition>-<repeat>`, with the transcript, the
   workspace diff, the replayed test logs, and `score.json`. The `summary` artifact and the
   job summary aggregate them.

To validate the scoring locally (free; needs npm and Playwright's Chromium):

```bash
node benchmarks/auth-testing/validate.mjs
```

## Safety

- **Isolation:** the agent and its tests run as an unprivileged user. That user cannot read
  the checkout or the run record, and their environment holds only allow-listed variables
  plus the agent credential.
- **Credential check:** before upload, every run record is searched for the credential and
  for any `sk-ant-` key, and matches are removed. `meta.json` records how many files changed.
- **Synthetic data only:** the app's session IDs and tokens are synthetic and exist only on
  the run's VM.

## Results

None yet. The pilot results will go here and in `results/`.
