# GitOps operations and recovery

Read before deployment, configuration changes, drift repair or removal.

## Keep one declarative owner

Inspect the Application spec, owner references, parent app and ApplicationSet
template/generator. Change the actual Git/controller owner instead of patching
the child and expecting it to persist. A generated child's auto-sync toggle
normally does not change the ApplicationSet template. Disabling automatic
sync alone does not fence all owners or cancel an already running operation.

Check automation explicitly: `automated.enabled: false` disables automatic sync;
an omitted/null enabled field within an automated policy is treated as enabled.
Prune, self-heal and allow-empty are independent choices. Do not enable any just
to clear OutOfSync. A source push/merge may deploy and prune without a manual
sync. Emergency imperative changes need release authority, reconciliation control
at the real owner, a bounded expiry and durable source repair.

Sources: [automated sync](https://argo-cd.readthedocs.io/en/stable/user-guide/auto_sync/),
[ApplicationSet modification](https://argo-cd.readthedocs.io/en/stable/operator-manual/applicationset/Controlling-Resource-Modification/).

For multi-source apps use `spec.sources`, not the ignored singular `source`.
Record each repository/chart/values revision and overrides. Duplicate resource
identities produce a warning and the last source wins; do not accept a clean
status without checking which source actually supplied the resource.
Source: [multiple sources](https://argo-cd.readthedocs.io/en/stable/user-guide/multiple_sources/).

## Preview the actual release boundary

Resolve revision(s) immutably where practical. Inspect rendered differences,
sync options at both app and resource levels, hooks, ordering, stateful resources,
shared/cluster-scoped resources and the applicable sync window. Do not deploy a
different revision or option set from the one reviewed.

Prune deletes resources absent from desired state. `Replace=true` and
`Force=true` can recreate resources; `Validate=false`,
`SkipDryRunOnMissingResource=true` and diff-ignore changes are not generic fixes.
Resolve the schema/CRD/ownership problem first. Protect relevant Namespace/PVC
and data identities, account for reclaim policy and restore requirements. A
non-pruning command does not neutralize existing destructive resource options.
Source: [sync options](https://argo-cd.readthedocs.io/en/stable/user-guide/sync-options/).

Hooks and sync waves can run Jobs, migrations and external effects; inspect their
idempotency and failure behavior. Selective resource sync skips hooks and is not
recorded in deployment history, so it cannot be rolled back through history.
It is not equivalent to a full release. Distinguish it from version-specific
`ApplyOutOfSyncOnly` behavior rather than treating both as the same optimization.
Sources: [phases and waves](https://argo-cd.readthedocs.io/en/stable/user-guide/sync-waves/),
[selective sync](https://argo-cd.readthedocs.io/en/stable/user-guide/selective_sync/).

Respect project sync windows; inspect the applicable window rather than changing
policy or enabling a manual override to get past it. A window is not a lock
against every external write. Source: [sync windows](https://argo-cd.readthedocs.io/en/stable/user-guide/sync_windows/).

## Diagnose before retrying

Distinguish render/repository failures, comparison failure, legitimate drift,
RBAC/transport failure, hook failure and unhealthy runtime resources. Read narrow
conditions, operation/resource results and authorized events/logs. Do not expose
credentials or full manifests to obtain this evidence.

An OutOfSync application is not necessarily broken; Synced can coexist with
unhealthy resources. Identify the blocked wave/resource, readiness cause and
revision before deciding to change infrastructure. Failed sync can be partial.
Terminating an operation stops further orchestration, not previously applied
changes or all external effects; it requires authority and post-checks.

After rollout, verify expected revisions/image identities, operation result,
relevant resource readiness and the actual user-facing behavior. Custom health
checks and ignored differences can make a badge incomplete evidence.

## Rollback and removal are different operations

Prefer a reviewed Git revert or forward fix at the owner. Native rollback uses
a deployment history ID, not a Git SHA, and is unavailable with automated sync
enabled. Do not silently disable policy to make rollback possible. Record all
source versions and durable desired state so reconciliation cannot immediately
undo the recovery. Neither native rollback nor Git revert reverses a database
migration or restores deleted data; assess schema compatibility and restore
separately. Sources: [rollback CLI](https://argo-cd.readthedocs.io/en/stable/user-guide/commands/argocd_app_rollback/),
[automated sync](https://argo-cd.readthedocs.io/en/stable/user-guide/auto_sync/).

`argocd app delete` defaults to cascading deletion. Before any authorized removal,
inventory exact child resources and finalizers, parent/generator recreation,
data effects and the intended preservation/deletion outcome. Choose cascade
explicitly. Non-cascading deletion leaves resources; it is not complete teardown
or backup. Background propagation still deletes children. ApplicationSet owner
references and resource finalizers can delete workloads when generated apps or
the set disappear. Do not strip finalizers to escape a stuck deletion without
investigating its controller, resources and permissions.

Sources: [delete CLI](https://argo-cd.readthedocs.io/en/stable/user-guide/commands/argocd_app_delete/),
[app deletion](https://argo-cd.readthedocs.io/en/stable/user-guide/app_deletion/),
[ApplicationSet deletion](https://argo-cd.readthedocs.io/en/stable/operator-manual/applicationset/Application-Deletion/).
