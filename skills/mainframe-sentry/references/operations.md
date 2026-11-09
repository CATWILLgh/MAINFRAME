# Self-hosted operations

Research baseline: 2026-10-29. The upstream developer documentation and `master`
examples move independently of installed releases. Resolve the target's checked-out
tag, image versions, Compose profiles and local overrides before adapting any
setting or command here. Treat the matching release's files as implementation
evidence; do not transplant the current service inventory into an older install.
Current developer-doc source is
[`getsentry/sentry-docs/develop-docs`](https://github.com/getsentry/sentry-docs/tree/master/develop-docs);
the older `getsentry/develop` repository is archived.

## Configuration that changes operational behavior

- Terminate TLS at the existing dedicated proxy/load balancer. Align
  `system.url-prefix` with the public scheme/hostname and the release's SSL/proxy
  settings in `sentry/sentry.conf.py`. Test an authenticated write for CSRF, beyond
  loading the login page. Enumerate required browser origins in
  `CSRF_TRUSTED_ORIGINS`; keep CSRF enabled. Trust forwarded client identity and
  scheme only across the intended proxy boundary.
  [Reverse proxy](https://develop.sentry.dev/self-hosted/production-enhancements/reverse-proxy/),
  [CSRF troubleshooting](https://develop.sentry.dev/self-hosted/troubleshooting/sentry/#csrf-verification-failed).
- The public URL and internal service URL have different purposes. Changing a
  public hostname does not imply changing `system.internal-url-prefix`. Inspect
  `SENTRY_BIND` together with proxy routing. Inspect active configuration locally;
  do not paste rendered Compose configuration or environment values into reports.
  [Upstream configuration template](https://github.com/getsentry/self-hosted/blob/master/sentry/config.example.yml).
- Keep the existing system secret stable across ordinary restarts and upgrades.
  The template supports `SENTRY_SYSTEM_SECRET_KEY`; inspect precedence in the
  installed release. Rotation invalidates sessions and affects cryptographic
  operations, so treat it as its own authorized change, never a troubleshooting
  shortcut. Preserve secrets through protected backup/delivery without displaying
  values. [Python configuration template](https://github.com/getsentry/self-hosted/blob/master/sentry/sentry.conf.example.py).
- Inspect release-specific shared credentials too: current configuration documents
  `LAUNCHPAD_RPC_SHARED_SECRET` as an install-unique secret whose shipped default
  is unsuitable for production. Configure all participants consistently; do not
  assume replacing the main system key covers every component.
  [Shared-secret configuration](https://develop.sentry.dev/self-hosted/configuration/#launchpad-rpc-shared-secret).
- Email is an account lifecycle dependency as well as an alert channel. Configure
  the existing SMTP choice and sender identity, then verify delivery through an
  authorized recipient. `mail.use-tls` and `mail.use-ssl` are mutually exclusive.
  File defaults can override UI mail changes; `SENTRY_MAIL_HOST` also influences
  sender settings. Inspect all relevant layers before changing the same setting
  twice. Built-in outbound SMTP does not establish deliverability or reputation.
  [Email](https://develop.sentry.dev/self-hosted/configuration/email/),
  [Mail configuration comments](https://github.com/getsentry/self-hosted/blob/master/sentry/config.example.yml).

Retain the deployment's actual env-file selection for every Compose command.
`.env.custom` alone and `.env` followed by `.env.custom` have different fallback
behavior; check how the installer and operational command each load them.
Reconcile new upstream defaults during upgrades rather than blindly replacing
local settings. [Environment configuration](https://develop.sentry.dev/self-hosted/configuration/#customize-dotenv-env-file).

For applied configuration changes, upstream recommends rerunning `./install.sh`
to account for configuration and migrations rather than assuming a blanket
`docker compose restart` is sufficient. That script is a mutating installation
operation: inspect its release, intended effects and rollback first; a read-only
diagnostic assignment does not authorize it.
[Configuration](https://develop.sentry.dev/self-hosted/configuration/#updating-basic-configuration).

## Diagnose before changing state

Derive service names and enabled components from the actual Compose deployment.
Use bounded, timestamped logs for the relevant services and incident window;
avoid collecting every service's entire history. Correlate observations by event
ID, timestamp, project and data category, with sensitive payloads excluded.
For example, preserve the existing Compose/env-file context while using
`docker compose ps`, `docker compose config --services`, and
`docker compose logs --since 15m --tail 200 --timestamps <actual-service>`.
Inspect and redact log content locally before sharing it.

`/_health/` is documented to return 200 when up or 500 with problems. This proves
neither searchable event storage nor alert delivery. Test the intended
client-to-project path separately.
[Health checks](https://develop.sentry.dev/self-hosted/production-enhancements/reverse-proxy/#health-checks).

Use the documented data flow as a diagnostic map, then resolve exact processes,
topics and storage backends from the installed release:

| Observation | Next boundary to inspect |
| --- | --- |
| SDK never sends | Initialization, runtime DSN, SDK filters/sampling, browser blockers, shutdown/flush behavior |
| Transport fails | Client DNS/TLS, proxy route and body limits, response status and rate-limit headers |
| Relay rejects or cannot resolve project | DSN/project validity, project configuration retrieval and its producing tasks |
| Ingestion accepted but event absent | Relevant category's Kafka producer/consumer progress, lag, processing failures and persistent storage |
| Search works but event details fail | Query/index path versus raw payload/blob path |
| Event exists but notification absent | Rule conditions, asynchronous task progress, provider delivery and recipient outcome |

Relay receives SDK envelopes; downstream ingestion, storage/query and task
execution are separate boundaries. An admin test email from the web process
does not exercise the background alert path.
[Data flow](https://develop.sentry.dev/self-hosted/data-flow/),
[Relay project-config failures](https://develop.sentry.dev/self-hosted/troubleshooting/sentry/#relay-rejects-envelope-events).

For authorized ingestion acceptance, submit one synthetic event containing no
private data through the actual SDK/client network, with a unique marker and
captured event ID. Bound the wait and look up that exact event in the intended
project, environment and time window. Confirm its expected fields and stack
resolution when those are part of the task. A CLI/server-side send proves its
own network path; a local test capture proves only local instrumentation. If
notifications are in scope, use an authorized recipient and separately confirm
the expected rule and receipt. Record unobserved stages as gaps. Do not repeatedly
resend when the ingestion outcome is unknown.

When exposing ingestion while keeping the UI private, use the release's required
endpoint set, including the categories actually used. Route through the bundled
ingress component rather than bypassing it to the web process. Validate browser
transport separately. Self-hosted lacks SaaS spike protection; use the existing
proxy's agreed ingestion limits and verify SDK rate-limit behavior.
[Proxy boundaries](https://develop.sentry.dev/self-hosted/production-enhancements/reverse-proxy/).

## Capacity and maintenance

Measure the pressured resource and its owner before choosing cleanup: durable
event data, queued work, uploaded artifacts and container logs have different
lifecycles. Backlog and disk growth require a time series and input rate, not a
single utilization percentage. Monitor disk latency/IO wait as well as free space,
memory pressure and queue age; the documented minimum install size is not a
workload capacity guarantee. [Resource guidance](https://develop.sentry.dev/self-hosted/#required-minimum-system-resources).

`SENTRY_EVENT_RETENTION_DAYS` controls the documented event cleanup period (90
days by default). Verify that scheduled cleanup runs and which datasets it
covers in the installed release. Reducing retention discards history and is not
a promise of immediate disk recovery. Kafka retention is a separate processing
window: do not shorten it below the recovery backlog you need to preserve.
[Event retention](https://develop.sentry.dev/self-hosted/configuration/#event-retention),
[Kafka retention](https://develop.sentry.dev/self-hosted/troubleshooting/kafka/).

Upstream identifies disk/memory exhaustion and
processing delays beyond Kafka retention as causes of out-of-range consumer
offsets. Resetting offsets can lose data; removing volumes destroys queued data.
Do not turn those documented recovery examples into a generic repair command.
For an authorized targeted recovery, identify every active consumer sharing the
affected group, capture the before state, choose the exact topic/partition and
offset policy with its loss/replay consequence, and inspect a dry run before
execution. Validate resumed progress and a new event afterward. Avoid all-group
resets and volume deletion as speculative fixes.
[Kafka troubleshooting](https://develop.sentry.dev/self-hosted/troubleshooting/kafka/).

Before destructive maintenance, establish the data loss budget and a recoverable
backup for the actual storage layout. Use [lifecycle recovery guidance](lifecycle.md#backup-and-recovery)
for export exclusions, storage coverage and restore side effects.

## Known documentation drift

- Current data-flow prose names PostgreSQL nodestore in one section and SeaweedFS
  in another; current self-hosted `master` config selects S3-compatible nodestore.
  Inspect `SENTRY_NODESTORE` and actual mounts before applying PostgreSQL nodestore
  cleanup. [Data flow](https://develop.sentry.dev/self-hosted/data-flow/),
  [Configuration source](https://github.com/getsentry/self-hosted/blob/master/sentry/sentry.conf.example.py).
- Kafka troubleshooting describes a 24-hour default while the inspected current
  Compose source sets `KAFKA_LOG_RETENTION_HOURS` to `3`. Use the target's effective
  broker/topic configuration; do not size a recovery window from prose alone.
  [Kafka guide](https://develop.sentry.dev/self-hosted/troubleshooting/kafka/),
  [Compose source](https://github.com/getsentry/self-hosted/blob/master/docker-compose.yml).
- Older PostgreSQL cleanup examples include version-specific packages and
  operations requiring additional temporary disk. Check backend, database major,
  locks and free-space requirements before considering them; a disk-full system
  cannot safely assume repacking or `VACUUM FULL` will fit.
  [PostgreSQL troubleshooting](https://develop.sentry.dev/self-hosted/troubleshooting/postgres/).
