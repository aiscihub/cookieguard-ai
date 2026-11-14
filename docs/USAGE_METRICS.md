# Usage metrics: PostHog pilot

CookieGuard 0.4.0 enables usage reporting **on by default** in its instrumented integrations.
Each accepted audit invocation attempts one small `cookieguard_invoked` event.
Downloading, installing, or importing a package does not report usage.
Cookie analysis and policy decisions remain local. Reporting failures never
change audit findings, exit codes, or agent-visible results.

To disable reporting, set either environment variable before starting the process:

```bash
export COOKIEGUARD_USAGE_METRICS=0
# Alternatively:
export DO_NOT_TRACK=1
```

An explicit API `false` also disables reporting. These opt-outs take precedence
over enable settings; see [reporting controls](#reporting-controls).

## Current status

This is the **0.4.0 release candidate; publication is pending**. Both Node.js and Python bundle
the public ingestion token for [CookieGuard's PostHog project](https://us.posthog.com/project/735326/home):
project ID **735326**, region **US Cloud** (`us`). Accepted audit invocations
attempt reporting to that project unless disabled. Installing the 0.4.0 release is required before consumers can report.
Existing npm and Python 0.3.0 installations do not acquire instrumentation retroactively. Registry downloads cannot be
converted into past invocation counts.

**Release behavior change:** 0.4.0 will enable this outbound
usage request by default. Disclose that change and the opt-out settings in the
release notes and package documentation. This source change does not publish or
upgrade any package.

The public token permits event ingestion only. Project ID `735326` identifies
the project in management APIs; reading events, changing settings, or creating
dashboards requires authenticated PostHog access. Local configuration does not
by itself verify event receipt or create a dashboard.

Live transport verification on November 13, 2026 ran two synthetic CLI audits
through the actual package hook and unchanged production sender in the earlier
0.2.0 source checkout. These were CLI pilot probes, not 0.4.0 release validation. Both audits
passed and received HTTP 200; the final response was `{"status":"Ok"}`.
The [verification record](USAGE_METRICS_VERIFICATION.json) contains timestamps
and the two synthetic invocation IDs, without the project token or cookie data.
The owner subsequently supplied a PostHog activity screenshot displaying both
exact invocation IDs, confirming end-to-end delivery and stored-event visibility
for these CLI audits. Exclude those two IDs from adoption counts. Project-level
privacy settings and saved-dashboard creation remain unverified.

This guide supersedes the collector recommendation in the
[original investigation](USAGE_METRICS_PLAN.md). No PostHog project or private
dashboard is created by installing CookieGuard or running the configuration script.

## Reporting controls

No enable setting is required. For explicit enablement, the trusted environment
that launches an instrumented package may set:

```bash
export COOKIEGUARD_USAGE_METRICS=1
```

`COOKIEGUARD_USAGE_METRICS=0` and `DO_NOT_TRACK=1` each override API enablement.
An explicit API `false` also wins over environment enablement. An omitted API
setting, JavaScript `null`, or Python `None` follows the environment; an unset
`COOKIEGUARD_USAGE_METRICS` defaults to on. For compatibility, an explicitly set
value other than the exact `0` or `1` does not enable reporting by itself. An
explicit API `true` can enable reporting in that case, but cannot override either
environment opt-out. Changing the environment later does not retract events
already queued or delivered.

| Integration | Trusted API setting | What counts once |
| --- | --- | --- |
| Python Browser Use | `CookieGuardAudit(..., usage_metrics=False)` disables; `None` follows the environment/default | An accepted `start()` after lifecycle and browser-session validation, before engine startup |
| Playwright | `usageMetrics: false` on `startCookieAudit()` or `auditPage()` disables; `null` or omission follows the environment/default | The collector's first `collect()` or `evaluate()` |
| MCP | `"usageMetrics": false` in the startup configuration file disables; `null` or omission follows the environment/default | An admitted audit operation; a `BUSY` rejection does not count |
| CLI | Environment opt-out above | Accepted `scan` or `gate` dispatch after validating arguments and the applicable target/policy or gate configuration |
| GitHub Action | Environment opt-out on the Action step | Accepted Action audit after policy and target validation |
| Direct core API | Explicit `reportUsage()` from `@aiscihub/cookieguard-core/usage`; `enabled: false` disables, `null` or omission follows the environment/default | Only the application's explicit reporting call |

MCP agents cannot change reporting through tool arguments. Help, capabilities,
explanations, Python construction/imports, provisional checks, result writing,
and policy assertions do not create new events. A counted invocation can still
fail or be cancelled later; it is not a completion or successful-audit count.

The Python compatibility package `cookieguard-browser-use` re-exports the
canonical `cookieguard` class. Both import spellings report as `cookieguard`
with integration `browser-use`; the import spelling is not measured. The
compatibility package adds no event. Its nested Node engine receives forced opt-outs.
The Playwright fixture delegates to the same collector, so it adds no second event.
CLI scanners and the core evaluator do not
automatically emit nested events. Direct `evaluateCookiePolicy()` stays free of
automatic reporting; applications using the explicit helper should call it only
at their own invocation boundary and use the trusted core package version.

## Configure the pilot project

The bundled defaults already target project `735326` in US Cloud. These steps
describe how maintainers review or change the project configuration.

1. Use the existing pilot project, or create a dedicated PostHog Cloud project
   in the US or EU region for a separate deployment. Obtain its
   **public project token** beginning with `phc_`. Do not use a personal,
   administrative, or project secret API key; private `phx_` tokens are rejected.
   The public capture API uses the project token to accept events.
   [PostHog capture API](https://posthog.com/docs/api/capture)
2. Before collecting events, open **Settings → Project → General → IP data
   capture configuration** and select client-IP discard. Also disable the
   project's **GeoIP enrichment transformation**. IP discard alone still allows
   location enrichment before discard. Keep the project and dashboard private;
   do not add identity, location, or browser-capture enrichment to this pilot.
   [PostHog data collection controls](https://posthog.com/docs/privacy/data-collection)
3. In this repository, set the public configuration and generate the bundled
   defaults for the release:

   ```bash
   export COOKIEGUARD_POSTHOG_PROJECT_TOKEN='phc_YOUR_PUBLIC_PROJECT_TOKEN'
   export COOKIEGUARD_POSTHOG_REGION='us' # or eu, matching the project
   npm run configure:usage
   ```

   Replace the placeholder with the actual public token. The script writes
   `packages/core/src/usage-config.js` and
   `integrations/python/src/cookieguard/_usage_config.py`.
   It does not change the reporting controls, publish packages, or send an event.
   Subsequent accepted audits use the default-on reporting behavior. The public
   ingestion token is intentionally distributable and grants no dashboard access.
4. Run the existing mocked reporting tests and review the generated defaults.
   For a deliberate live pilot, use an authorized local audit with reporting
   enabled; inspect the received event before rollout.
   Publish an instrumented release through the normal release process when ready.
   Release the updated Node packages together and update their pinned internal
   dependencies, including MCP's CLI dependency, to the new package versions.
   Each Node adapter must use core 0.4.0, which exports `./usage`. Release
   `cookieguard` and its compatibility package `cookieguard-browser-use` together
   at 0.4.0 with the exact dependency `cookieguard==0.4.0`. The Python package
   retains the separately sandboxed, published npm engine 0.3.0; telemetry runs
   in Python, outside that engine.
   Update version pins and release documentation as part of that release,
   including the default-on change and how to disable reporting.

The two configuration environment variables also override bundled defaults at
runtime. An empty token, invalid token, or unsupported region silently disables
delivery. Only `us` and `eu` are accepted; arbitrary collector URLs are unsupported.
Endpoints are fixed:

| Region | HTTPS ingestion endpoint |
| --- | --- |
| `us` | `https://us.i.posthog.com/i/v0/e/` |
| `eu` | `https://eu.i.posthog.com/i/v0/e/` |

## Exact event payload

The event contains exactly these client-supplied fields. The version shown is
illustrative; each integration supplies its actual package version.

```json
{
  "api_key": "phc_YOUR_PUBLIC_PROJECT_TOKEN",
  "event": "cookieguard_invoked",
  "distinct_id": "a fresh random UUIDv4 for this invocation",
  "properties": {
    "$process_person_profile": false,
    "$geoip_disable": true,
    "$ip": "0.0.0.0",
    "schema_version": 1,
    "package": "cookieguard",
    "package_version": "0.4.0",
    "integration": "browser-use"
  }
}
```

`distinct_id` is regenerated for every invocation. It is not stored on disk or
reused to identify a person, installation, machine, repository, or session.
`$process_person_profile: false` requests events without person-profile
processing. [PostHog anonymous capture](https://posthog.com/docs/api/capture#anonymous-event-capture)

| `integration` | `package` |
| --- | --- |
| `browser-use` | `cookieguard` |
| `cli` | `cookieguard-ci` |
| `github-action` | `cookieguard-ci` |
| `playwright` | `@aiscihub/cookieguard-playwright` |
| `mcp` | `@aiscihub/cookieguard-mcp` |
| `core` | `@aiscihub/cookieguard-core` |

No cookie names, values, or attributes, URLs, origins, filenames, repository names,
credentials, prompts, screenshots, raw errors, audit status, findings, operating
system, runtime version, or persistent identifiers are included. The reporter
constructs this fixed object instead of serializing an audit or configuration.
PostHog assigns receipt metadata; this list describes the outbound client payload.

## Transport and delivery boundaries

The clients use a direct HTTPS POST with standard TLS verification, without the
PostHog browser SDK, autocapture, session replay, cookies, authentication context,
proxy configuration, or redirect following. Node uses an unreferenced worker;
Python uses a daemon worker. Queues hold at most 16 waiting events, with no
durable files or retries. Node delivery has a 500 ms deadline; Python sockets
have a 0.5-second timeout. These are delivery limits, not audit deadlines.

Disabled reporting creates no reporting worker, timer, file, DNS lookup, or
socket. An enabled process may lose events when offline, when the queue is full,
on timeout, or when it exits. CLI and Action shutdown include a short bounded
flush. Library callers can optionally use
`await flushUsage(timeoutMs)` from `@aiscihub/cookieguard-core/usage` or
`flush_usage_metrics(timeout_seconds=0.5)` from either Python import. Both cap an
explicit wait at one second. Draining a queue does not prove server acceptance.

The HTTPS connection still exposes a source IP to PostHog and its network
infrastructure. The fixed `$ip`, disabled GeoIP property, and required project
settings minimize event data; they do not hide transport metadata or promise
that provider infrastructure keeps no logs. Review provider handling and
retention separately. CookieGuard stores no local telemetry log. Browser Use's
own telemetry, model providers, and caller-enabled traces have separate controls.
The legacy browser extension has no usage-reporting hook.

## Read the dashboard as invocation counts

1. In PostHog Product Analytics, create a **Trends** insight for
   `cookieguard_invoked`, filtered to `schema_version = 1`.
2. Select **Total count**. Save daily totals and number cards for today, the last
   7 days, and the last 30 days to a private dashboard.
3. Add separate breakdowns by `integration`, `package`, and `package_version`.
   Filter to one package when comparing its versions, and annotate the rollout
   date and reporting default.

These controls are described in [PostHog Trends](https://posthog.com/docs/product-analytics/trends/overview).
Label charts **Reported audit invocations**. Fresh IDs make unique-user, active-user,
installation, retention, and session counts unsuitable. No success rate or failure
rate can be calculated from this event.

Counts cover only reports that arrive from instrumented versions with reporting
enabled. Old releases, opt-outs, offline runs, dropped events, and modified clients remain
unobserved. A public ingestion token also allows anyone to forge events; counts
are an adoption signal, not authenticated proof of execution or a billing meter.
Restrict dashboards to expected events/package combinations, review anomalies,
and set appropriate project usage limits before expanding the pilot.
