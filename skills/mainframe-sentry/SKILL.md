---
name: mainframe-sentry
description: Plan, install, configure, upgrade, recover, or troubleshoot self-hosted Sentry and its event ingestion. Use for Sentry server operations; not standalone SDK instrumentation or Sentry product development.
---

# Operate self-hosted Sentry

Resolve the requested outcome and the actual deployment before choosing commands:
environment and host, self-hosted release/commit, deployment owner and topology,
local overrides, persistent storage, public URL, and permitted changes. Reuse
established authority. Reading this skill does not authorize deployment,
destructive maintenance, sending events, or contacting alert recipients.

The maintained Docker Compose distribution is the starting point for ordinary
self-hosted operations. An existing Kubernetes or custom deployment remains its
own target; do not replace it or assume Compose commands apply. The upstream
distribution targets modest installations and supplies no availability guarantee.
Capacity and high availability require evidence from the actual workload and
storage layout, not a successful startup on the documented minimum hardware.

## Read for the current decision

| Task | Reference |
| --- | --- |
| Choose errors-only/full features, external infrastructure, or air-gap/egress policy | [Deployment choices](references/deployment-choices.md) |
| Install, size, upgrade, back up, restore, or move a deployment | [Lifecycle](references/lifecycle.md) |
| Configure TLS/proxy/email, diagnose missing events, inspect queues or manage retention | [Operations](references/operations.md) |

These references preserve decision points, not a frozen release runbook. Verify
release-sensitive commands, hard stops, service names and configuration against
the selected `getsentry/self-hosted` tag and current official documentation.
Do not mix a release's Compose file with arbitrary newer component images.

## Work against the correct evidence

- Use the deployment's existing configuration and backup owners. Inspect selected
  non-secret fields; full environment, Compose expansion, logs and event payloads
  can expose credentials or personal data.
- Separate configuration health, service health, ingestion, processing and query
  visibility. A login page, `/_health/` response or accepted envelope proves only
  its own boundary. Validate the behavior the user actually needs.
- Before migrations or storage changes, establish the recovery point and which
  data it covers. A Sentry configuration export is not a backup of event history.
  Rollback may require restoring data as well as old images.
- Diagnose failures before changing state. Queue offset resets, topic deletion,
  volume removal and blind installer retries can lose data or repeat migrations.
  An interrupted operation requires inspection of its partial result first.

Finish with the exact target/release, changes or diagnosis, observations that
support the result and remaining gaps. For a plan, give the next executable
step and its prerequisites without claiming a live installation was tested.

Official orientation: [self-hosted documentation](https://develop.sentry.dev/self-hosted/)
and [release repository](https://github.com/getsentry/self-hosted).
