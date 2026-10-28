# Deployment choices and outbound data

Official documentation checked **2026-10-29**. Recheck the target release before
using feature flags or making availability promises.

## Match the requested feature set

The Compose distribution offers `COMPOSE_PROFILES=errors-only` from 24.8.0 and
`COMPOSE_PROFILES=feature-complete` as the default. Errors-only keeps error-related
issues, alerts, integrations, dashboards and releases; it does not provide the
full traces/profiles/replays feature set. Select it when that reduced outcome
fits the request, not as an invisible workaround for inadequate resources.
Inspect `.env` plus the selected release's Compose profiles before changing an
existing instance. [Errors-only mode](https://develop.sentry.dev/self-hosted/optional-features/errors-only/)

Self-hosting does not imply SaaS feature parity. The current overview excludes
billing-coupled features and closed AI/ML capabilities and describes limitations
for platform symbol sources and gaming integrations. Verify the exact needed
feature against the running version; an SDK's ability to send a data type does
not prove the server can process it.
[Self-hosted differences](https://develop.sentry.dev/self-hosted/#differences-between-self-hosted-and-saas)

For scaling, use upstream reference architectures as design inputs, not a
ready-to-apply highly available cluster. They explicitly leave external storage
dependencies to separate design. Moving filestore/object data out of the host
does not automatically externalize ClickHouse or PostgreSQL, or solve ingestion
capacity. Keep storage ownership, migration and recovery explicit.
[Reference architectures](https://develop.sentry.dev/self-hosted/reference-architecture/),
[external storage](https://develop.sentry.dev/self-hosted/production-enhancements/external-storage/)

External object storage also has its own retention policy: the external-storage
guide says `sentry cleanup` does not remove those objects. Align provider lifecycle
rules with the intended recovery and retention windows; do not expire artifacts
still referenced by retained events. The guide labels S3 support experimental
and unsupported; validate the exact backend/component rather than promising
universal S3 compatibility. Its `SENTRY_EVENTS_RETENTION_DAYS` spelling differs
from the main configuration's `SENTRY_EVENT_RETENTION_DAYS`; use the key in the
selected release, not the typo in the prose.
[External-storage limits](https://develop.sentry.dev/self-hosted/production-enhancements/external-storage/)

## Keep egress choices distinct

The installer asks whether to report self-hosted problems to Sentry. Automation
can supply `REPORT_SELF_HOSTED_ISSUES` or the documented
`--report-self-hosted-issues` / `--no-report-self-hosted-issues` options. Reporting
may include installation logs and runtime diagnostics. Preserve an existing
choice; if none exists, resolve it before an unattended installation rather than
silently enabling reporting.
[Installer monitoring](https://develop.sentry.dev/self-hosted/#self-hosted-monitoring)

The beacon is a separate outbound mechanism controlled by `SENTRY_BEACON` in
`sentry.conf.py`. The overview is internally inconsistent about its default
(one section says opt-in, another says enabled by default), so inspect the
selected release and effective configuration instead of asserting a universal
default. Reporting, beacon traffic, integrations, SMTP, symbol downloads and
image/package acquisition are separate egress paths.
[Beacon and proxy guidance](https://develop.sentry.dev/self-hosted/#self-hosted-beacon)

Air-gapped use needs a release-matched artifact/dependency transfer plan and
verification of actual egress. The documented `SENTRY_AIR_GAP = True` setting is
not evidence that every container, integration or installer is network-isolated.
Upstream gives only limited guidance for this deployment mode. Do not infer that
all features work offline. A Docker-daemon proxy change or restart affects other
workloads on the host; keep that blast radius inside the supplied authority.
[Air-gap and installation proxy](https://develop.sentry.dev/self-hosted/#air-gapped-installation)
