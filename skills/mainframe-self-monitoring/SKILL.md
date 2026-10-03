---
name: mainframe-self-monitoring
description: Design, implement or repair an application's System/Diagnostics page with service health, resource metrics, logs and optional scoped container controls or data previews. Use for embedded operational consoles and misleading diagnostic states; not standalone monitoring-platform deployment or one-off infrastructure diagnosis.
---

# Embedded system diagnostics

Build a useful operator view in the receiving application's stack and design
system. Start with observation; add container mutations and data browsing only
where the requested product needs them and their separate permissions are defined.
Do not automatically install Docker access, database explorers, a metrics platform
or a different frontend/backend framework. This method is not a replacement for
external monitoring: a failed application cannot reliably report its own outage.

Inspect existing health checks, telemetry, identities, tenants, resource ownership,
deployment and operator workflows. Establish the exact target environment and
which users may see each class of information. Reuse current instrumentation,
clients and authorization. Development authority does not grant permission to
restart production resources, delete images, browse unrelated data or expose a
privileged daemon socket.

## Read for the current decision

- [Signals](references/signals.md): bounded collection, health semantics, freshness,
  units, missing data and failure isolation.
- [Docker and Compose](references/docker.md): optional runtime adapter, actual
  target identity, scope enforcement, actions and configuration display.
- [Data previews](references/data-previews.md): optional PostgreSQL, Redis and
  Kafka inspection with explicit cost, disclosure and access boundaries.
- [Interface and verification](references/interface-verification.md): operator
  journey, truthful actions, tests and actual UI/runtime acceptance.

Use the relevant backend/frontend engineering method and `mainframe-testing` for
implementation checks. Use `mainframe-infrastructure` for actual platform access
or changes, `mainframe-k3s` for Kubernetes operations and `mainframe-clickhouse`
for that database's query safety. Use `mainframe-notifications` only if this work
also requires event-driven outbound alerts.

## Complete the slice

Define a small typed server contract for each enabled capability: authorized
resource identity, observation time, freshness, status, optional value/unit and
safe error. Enforce authorization and resource scope server-side for every
request, including direct IDs and background jobs. UI visibility is not a guard.
Separate metadata, logs/data and mutations; an authenticated account is not
sufficient permission for host-wide information.

Implement bounded collectors and safe projections, then the native page and its
loading, unavailable, stale, forbidden and partial-failure states. Keep unknown
measurements unknown. Prevent the page's polling from amplifying an outage.
Use operator actions that name the target/environment and report observed outcomes.

Verify hostile resource IDs, sensitive fields, unavailable dependencies, collection
limits and action races. Render and exercise the actual application with synthetic
data; distinguish mocked checks, authorized live reads and actual mutation proof.
Report missing acceptance explicitly. Do not copy example source or claims of
production readiness without adapting and validating their contracts.
