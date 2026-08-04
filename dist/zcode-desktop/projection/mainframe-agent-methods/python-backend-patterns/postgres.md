# PostgreSQL — indexing, EXPLAIN, JSONB, upsert

App-level PostgreSQL an engineer gets wrong. Concurrency, pooling and the ops boundary live in [postgres-concurrency.md](postgres-concurrency.md).

## Indexing

- **Index selective WHERE / JOIN / ORDER BY columns; do not over-index.** Every index is maintained on INSERT/DELETE and on any UPDATE that changes an indexed column (a HOT update changing none skips index work) — so N indexes multiply write cost. Drop unused ones.
- **Composite index = leftmost-prefix.** `(a, b)` serves filters on `a` and on `a, b`, but NOT on `b` alone. Put the most selective equality column first.
- **B-tree** for equality / range / sort; **GIN** for JSONB, arrays, full-text (multi-value columns).
- **Partial index** to skip common values: `CREATE INDEX ... WHERE status = 'active'`. The predicate must match the query's WHERE *exactly* — Postgres has no theorem prover for equivalent expressions.
- **Covering / index-only scan:** `CREATE INDEX t_x ON t(x) INCLUDE (y)` lets a query reading only `x, y` skip the heap (confirm with `Heap Fetches: 0`).

## Reading EXPLAIN

`EXPLAIN (ANALYZE, BUFFERS)` runs the query and prints **actual** rows/time beside planner **estimates**. Read for:
- **Estimate vs actual rows far apart** → stale stats or a bad plan; run `ANALYZE`.
- **Seq Scan** on a large table with a selective filter → missing/unused index. A Seq Scan on a *small* table is correct — don't "fix" it.
- **Bitmap Heap Scan** = many scattered matches (fine); an **Index Scan** with high `Rows Removed by Filter` → the index doesn't cover the filter.

## JSONB

- JSONB when the shape is dynamic/sparse; normalized columns when you filter or constrain individual fields hard. Don't model a fixed schema as JSONB to "save a migration".
- GIN index: default `jsonb_ops` supports key-exists (`?`), containment (`@>`), jsonpath; `jsonb_path_ops` is smaller/faster but only `@>` + jsonpath. Query containment with `@>` (`WHERE doc @> '{"k":"v"}'`).
- Anti-pattern: a B-tree on the whole JSONB column (useless for containment), or an expression index per key (over-indexing).

## Upsert

`INSERT ... ON CONFLICT (col) DO UPDATE SET ...` is an atomic insert-or-update even under high concurrency. It requires a real UNIQUE / exclusion constraint on `col` (a `conflict_target` is mandatory for `DO UPDATE`).
**Gotcha:** `ON CONFLICT DO NOTHING ... RETURNING` returns **nothing** for the conflicting row — you don't get the existing id back. Use `DO UPDATE ... RETURNING` or a follow-up SELECT.

Per-ORM: SQLAlchemy `Index(..., postgresql_using="gin")` + `pg_insert(...).on_conflict_do_update()`; Django `GinIndex` + `bulk_create(update_conflicts=True)` (note `update_or_create` is app-level, NOT atomic). JSONB containment: SQLAlchemy `col.op("@>")`, Django `field__contains`.

## Sources

- PostgreSQL — index types / partial / index-only-scans / EXPLAIN / JSONB — https://www.postgresql.org/docs/current/indexes-types.html
- use-the-index-luke.com — concatenated keys, EXPLAIN — https://use-the-index-luke.com/
