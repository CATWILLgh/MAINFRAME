# Operational data stores

Application schema, query, and migration implementation belongs with the
application change. This branch covers the operational layer: capacity,
pooling, autovacuum and bloat, partition maintenance, replication, backups,
restore, failover, and Redis persistence or eviction.

Before a production-affecting operation, establish the exact instance, role,
current topology, available backup or rollback, expected locking or downtime,
and the observation that will prove success. Use the map for orientation and a
read-only live query or platform view for current state.

PostgreSQL:

- use the real PostgreSQL version's official documentation for DDL, locking,
  maintenance, replication, and configuration behaviour;
- do not prescribe partitioning, pooling, or autovacuum changes from a generic
  threshold; measure the workload and current configuration;
- treat `VACUUM FULL`, failover, restore, destructive DDL, and changes that can
  block writes as explicit maintenance or approval decisions;
- test migrations against real PostgreSQL when PostgreSQL semantics are the
  reason for the change, but keep that outside the ordinary fast test loop.

Redis:

- choose eviction and persistence from the data's role, not a universal
  default;
- verify memory pressure, persistence mode, restart behaviour, and client
  expectations before changing policy;
- never treat a cache and a durable store as interchangeable merely because
  both currently contain the same data.

Sources:

- PostgreSQL administration: https://www.postgresql.org/docs/current/admin.html
- PostgreSQL routine vacuuming: https://www.postgresql.org/docs/current/routine-vacuuming.html
- Redis persistence: https://redis.io/docs/latest/operate/oss_and_stack/management/persistence/
- Redis eviction: https://redis.io/docs/latest/develop/reference/eviction/
