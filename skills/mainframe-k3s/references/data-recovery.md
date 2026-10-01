# Persistent data and recovery

## Separate three recovery owners

Treat cluster datastore, workload volume contents, and external application data
as separate backup/restore responsibilities. K3s local-path volumes bind data to
a node; additional servers do not turn them into replicated storage. Select
local or distributed storage from durability, latency and recovery requirements.
Inspect actual StorageClasses, PV affinity and reclaim policies before deleting
PVCs, draining nodes or changing storage. Application-consistent backups are
needed for databases; file copies of a running database are not assumed valid.

Sources: [K3s storage](https://docs.k3s.io/add-ons/storage),
[PersistentVolumes](https://kubernetes.io/docs/concepts/storage/persistent-volumes/).

## Build a usable backup

Identify SQLite, embedded etcd or external datastore first. Back up the server
token associated with the database backup: it decrypts bootstrap data. Preserve
relevant configuration securely. Use the datastore's proper consistent backup
method: embedded-etcd snapshots, external DB tooling, or a consistent copy of the
SQLite DB directory. Coordinate live-copy consistency instead of assuming a
random directory copy is recoverable.
Source: [backup types and token](https://docs.k3s.io/datastore/backup-restore).

For embedded etcd, inspect snapshot schedule, success, retention and off-node
availability. Treat snapshot plus token as highly sensitive. Verify recovery
credentials are available outside the failed cluster; the S3 configuration
Secret cannot be fetched from an unavailable API during restore. Check local
versus S3 restore flags explicitly.

For multi-server recovery, stop servers, restore one selected server from a
trusted snapshot with its matching token, restart normally without reset flags,
then rebuild peer etcd membership using the official procedure. Preserve peer
state before authorized cleanup and verify actual data-dir. `--cluster-reset`
without a restore path resets membership, not data from a snapshot. Do not use
it during routine diagnosis. Resolve restore-version compatibility from current
docs; do not claim every restore requires an identical binary version.
Source: [snapshot and restore procedure](https://docs.k3s.io/cli/etcd-snapshot).

## Prove recovery

Test the backup in an explicitly disposable, isolated recovery environment with
no production endpoints or controllers that can affect external systems. Check
API objects, credentials, storage attachment and application-level data/results.
Record demonstrated RPO/RTO and gaps. A successful snapshot command proves
creation, not restore success or workload recovery.

For rollback across a Kubernetes minor upgrade, plan the pre-upgrade snapshot,
matching token and binary/configuration recovery together. Downgrading binaries
alone is not a general rollback method. Recovering cluster state does not undo
external database migrations or workload writes.
Source: [rollback](https://docs.k3s.io/upgrades/roll-back).
