# Safe migrations — zero-downtime, recoverable, reversible

The target is NOT "idempotent everywhere". It is **safe** (no long locks, no data loss), **recoverable** (survives a mid-run failure or a deploy retry), and **reversible** (a real `down`). Idempotency is required only where it counts (below), never as a blanket guard on every DDL.

## Unsafe op → safe rewrite (PostgreSQL)

Each op on the left holds a lock that blocks writes for its duration — most take `ACCESS EXCLUSIVE` (reads blocked too); `CREATE INDEX` takes `SHARE` and FK validation `SHARE ROW EXCLUSIVE` (writes only) — or it rewrites the table. On a large table that is downtime.

| Unsafe | Safe rewrite |
|---|---|
| `CREATE INDEX` | `CREATE INDEX CONCURRENTLY` — `SHARE UPDATE EXCLUSIVE`, concurrent r/w; **cannot run inside a transaction** |
| `SET NOT NULL` (full scan) | `ADD CONSTRAINT ck CHECK (col IS NOT NULL) NOT VALID` → next migration `VALIDATE CONSTRAINT ck` (`SHARE UPDATE EXCLUSIVE`) |
| `ADD CONSTRAINT` FK/CHECK (scans all rows) | `... NOT VALID` (instant) → next migration `VALIDATE CONSTRAINT` |
| `ALTER COLUMN TYPE` / rename / `DROP COLUMN` | expand-contract across releases (below) |
| `ADD COLUMN` with a volatile default (rewrite) | nullable column → batch-backfill → constraint |

`ADD COLUMN` nullable, or with a **constant** default, does not rewrite on PG 11+ — safe as-is.

**Expand-contract** (Fowler ParallelChange) for rename / type-change / drop, across separate deploys: add new structure → app writes both old + new → backfill old rows in batches → switch reads to new → drop old in a later migration (ship the app that stops referencing the column first, or it errors on boot).

**Guard the lock wait:** `SET lock_timeout = '2s'` before DDL, so the migration fails fast instead of queueing behind a long query and blocking every connection stacked behind it.

**MySQL note:** each DDL auto-commits (no transactional rollback), so a failed multi-step migration leaves partial state — one change per migration, re-runs must survive. PostgreSQL rolls a failed migration back cleanly.

## Idempotency — where it counts

- **Data backfills:** re-runnable — `UPDATE ... WHERE new_col IS NULL`, never `SET x = x + 1`. Batched (1k–10k rows), each batch committed **outside** the schema transaction.
- **Retry-safe deploy step:** when k8s/CI can re-invoke the runner, the migration must survive a re-run.
- **Anti-pattern:** blanket `IF [NOT] EXISTS` on every DDL in a framework-tracked migration — the migrations table is already the idempotency layer; per-statement guards mask schema drift and defeat fail-fast.

## Per-tool

- **TypeORM** — `up`/`down` both required (no auto-`down`). CONCURRENTLY can't run in a wrapped transaction, so it needs `migrationsTransactionMode: "each"` (or `"none"`) on the DataSource **plus** `transaction = false` on the migration (`transaction = false` is ignored under the default `all` mode); then either raw `queryRunner.query("CREATE INDEX CONCURRENTLY ...")` or an `@Index({ concurrent: true })` declaration — both still require that non-`all` mode. `migration:generate` emits destructive DROP+CREATE (drops on rename, never CONCURRENTLY) — review before commit.
- **Prisma** — no `down`/revert (roll back with a new forward migration). It never generates CONCURRENTLY: run `migrate dev --create-only`, hand-edit the SQL to add it, and keep that statement in its own migration that runs outside a transaction block (CONCURRENTLY can't run in one — Prisma's docs flag this as a manual step). Generated SQL drops+recreates on rename — review.
- **Drizzle** — `drizzle-kit generate` emits plain SQL (never CONCURRENTLY); hand-edit the file or apply via an external runner (psql/Atlas) you control. No `revert`; reverse with a new forward migration.

## Sources

- PostgreSQL — ALTER TABLE / Explicit Locking / fast default — https://www.postgresql.org/docs/current/sql-altertable.html
- Fowler, ParallelChange (expand-contract) — https://martinfowler.com/bliki/ParallelChange.html
- strong_migrations op catalog — https://github.com/ankane/strong_migrations
