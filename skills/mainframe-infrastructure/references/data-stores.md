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

A local database is disposable only when the active task or project instruction
explicitly establishes that boundary. Never infer disposability from localhost,
a container name, or test-looking data.

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

For backups, prove the intended scope, destination, retention, encryption,
completion, and restorability. A successful backup command is not evidence that
the correct data can be restored.
