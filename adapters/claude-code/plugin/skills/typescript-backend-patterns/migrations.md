# Database migrations

- Treat schema and data migrations as rollout contracts, not just generated files. Inspect deployed-version compatibility when old and new application versions may overlap.
- Prefer expand, backfill, switch, and contract for destructive or large changes. Do not combine irreversible cleanup with the first compatible rollout.
- Keep migration ordering and ownership in the project's established tool. Do not rewrite an applied migration unless the repository explicitly permits it.
- Check locks, table size, index-build behavior, defaults, nullability, and transaction support for the actual PostgreSQL version and migration tool.
- Make backfills restartable and observable when they can outlive one process. Bound batches from measured behavior, not a universal number.
- Test the relevant migration path against real PostgreSQL. A mocked repository cannot prove DDL, constraint, index, or locking semantics.
- Require explicit authority before applying a migration to a shared or production database.

Sources:
- PostgreSQL documentation — https://www.postgresql.org/docs/current/
- Prisma migrations — https://www.prisma.io/docs/orm/prisma-migrate
- TypeORM migrations — https://typeorm.io/docs/advanced-topics/migrations/
