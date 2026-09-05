# Schema and data migrations

Design for the actual database, table size, traffic, deployment order, and migration runner. A migration must have an honest failure and recovery plan; a syntactic downgrade that loses data is not reversibility.

## Preparation

- Inspect the generated operations, current schema, dependent code, indexes, constraints, and rollout order.
- Establish lock and rewrite behavior from the target database version rather than a generic recipe.
- Keep old and new application versions compatible during rolling deployment when both can run concurrently.
- Separate a long data backfill from lock-sensitive schema work when their operational behavior differs.

## PostgreSQL patterns

- Use expand-and-contract across releases for destructive renames, type changes, and column removal when uninterrupted service matters.
- Create large indexes concurrently when normal index locking is unacceptable; PostgreSQL forbids concurrent index creation inside a transaction block.
- Add expensive constraints without validation and validate later when that reduces blocking for the real version and operation.
- Make backfills restartable from durable state, process bounded batches, and verify completion before tightening constraints or switching reads.
- Set a deliberate lock timeout for production DDL so a migration does not wait indefinitely behind traffic.

## Runner-specific boundaries

- Review Alembic autogeneration; it cannot infer every rename, constraint, server default, or data transition. Use its autocommit support for operations PostgreSQL forbids in a transaction.
- Review Django-generated migrations and use PostgreSQL-specific concurrent operations only with their documented non-atomic requirements.
- Provide downgrade or reverse code when it is truthful and operationally supported. Otherwise document and test the forward recovery path rather than pretending lost information can be restored.

## Sources

- PostgreSQL ALTER TABLE — https://www.postgresql.org/docs/current/sql-altertable.html
- PostgreSQL explicit locking — https://www.postgresql.org/docs/current/explicit-locking.html
- Alembic cookbook — https://alembic.sqlalchemy.org/en/latest/cookbook.html
- Django migration operations — https://docs.djangoproject.com/en/stable/ref/migration-operations/
- Parallel change — https://martinfowler.com/bliki/ParallelChange.html
