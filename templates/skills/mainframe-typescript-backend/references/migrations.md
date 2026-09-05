# Database migrations

- Treat schema and data migrations as rollout contracts. Check compatibility
  when old and new application versions may overlap.
- Prefer expand, backfill, switch, and contract for destructive or large
  changes. Do not combine irreversible cleanup with the first compatible step.
- Preserve migration ordering and ownership. Do not rewrite an applied
  migration unless the repository explicitly permits it.
- Check locks, table size, index build behavior, defaults, nullability, and
  transaction support for the actual PostgreSQL and migration-tool versions.
- Make long backfills restartable and observable. Derive batch bounds from
  measured behavior rather than a universal number.
- Test relevant migration behavior against real PostgreSQL.
- Require explicit authority before applying a migration to a shared or
  production database.

Sources: [PostgreSQL](https://www.postgresql.org/docs/current/),
[Prisma Migrate](https://www.prisma.io/docs/orm/prisma-migrate),
[TypeORM migrations](https://typeorm.io/docs/advanced-topics/migrations/).
