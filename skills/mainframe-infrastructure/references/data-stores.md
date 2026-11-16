# Operational data stores

Application schema and query implementation belongs with the application
change. This reference covers operational topology, capacity, connections,
locking, maintenance, persistence, replication, backups, restore, and failover.

Before an operation that can affect shared data, establish:

- exact instance, environment, engine version, endpoint, and server role;
- whether the resource is local test, shared development, staging, or
  production;
- current topology and dependent consumers;
- expected locks, downtime, replication effects, and failure modes;
- available backup, verified recovery path, and post-change observation.

A local database is disposable only when the effective instructions or current
task authority explicitly establish that boundary and the target satisfies its
conditions. Never infer disposability from localhost, a container name, or
test-looking data alone.

For PostgreSQL, use the exact version's official documentation for DDL,
vacuuming, locking, replication, and configuration. Measure workload and
current settings before recommending pooling, partitioning, autovacuum, bloat,
or capacity changes. Treat blocking maintenance, destructive DDL, restore, and
failover as separate operational decisions outside an expressly disposable
test boundary.

For Redis, establish whether the data is cache, queue, coordination state, or a
durable record. Verify memory pressure, eviction, persistence, replication,
restart behavior, and client expectations before changing policy. Do not treat
a cache and durable store as interchangeable because they currently contain
similar data.

## Own the backup lifecycle

Reuse an adequate recovery point when it covers the operation. Create a new
copy only for a concrete recovery need within the task's authority. Before
creation, settle the scope, protected destination, retention or expiry, and
cleanup owner. Verify access and encryption appropriate to the data, available
space, and workload impact on a shared host.

Verify completion and restorability at the level the operation depends on. Keep
the protected location, verification, and retention in the existing runbook
or task record. After acceptance, remove temporary copies whose recovery
purpose has ended when cleanup is already authorized. For a copy still needed
or awaiting disposal authority, report who owns it, where it is, and when it
should be reviewed. Preserve required recovery points.
