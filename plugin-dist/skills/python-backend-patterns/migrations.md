# Safe migrations — zero-downtime, recoverable, reversible

The target is NOT "idempotent everywhere". It is **safe** (no long locks, no data loss), **recoverable** (survives a mid-run failure or a deploy retry), and **reversible** (a real `downgrade` / reverse). Idempotency is required only where it counts (below), never as a blanket guard on every DDL.

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

- **Alembic** — write a real `downgrade()`, never leave it empty. For CONCURRENTLY: `op.create_index(..., postgresql_concurrently=True)` inside `with op.get_context().autocommit_block():` (or set `transaction_per_migration=True` in `env.py`) — it cannot run in the migration's transaction. Keep schema ops and data ops separate; backfill via `op.execute("UPDATE ... WHERE col IS NULL")`. `--autogenerate` misses server defaults, some type changes, and CHECK constraints — review the generated script before commit.
- **Django** — `AddIndexConcurrently` / `RemoveIndexConcurrently` (from `django.contrib.postgres.operations`) require `atomic = False` on the `Migration`. `RunPython` always paired `(forwards, reverse)`, `elidable=True` so squashing can drop it; reach models via `apps.get_model()`. Expand-contract: `SeparateDatabaseAndState` (state-vs-DB divergence) and `AddConstraintNotValid` → `ValidateConstraint` in two migrations. Batched backfill: `atomic = False` + `transaction.atomic()` per ~1k rows. Inspect generated migrations — Django emits redundant ops.

## Sources

- PostgreSQL — ALTER TABLE / Explicit Locking / fast default — https://www.postgresql.org/docs/current/sql-altertable.html
- Fowler, ParallelChange (expand-contract) — https://martinfowler.com/bliki/ParallelChange.html
- Django migrations — operations + postgres concurrent ops — https://docs.djangoproject.com/en/stable/ref/migration-operations/
- Alembic — autocommit_block / cookbook — https://alembic.sqlalchemy.org/en/latest/cookbook.html
