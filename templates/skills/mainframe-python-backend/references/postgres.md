# PostgreSQL queries and indexes

Base changes on the target PostgreSQL version, schema, representative data, and an observed query plan. An index is not automatically useful because a column appears in `WHERE`.

## Query evidence

- Use `EXPLAIN` for plan inspection and `EXPLAIN (ANALYZE, BUFFERS)` only when executing the statement is safe. `ANALYZE` actually runs writes as well as reads.
- Compare estimates with actual rows, loops, filtering, heap fetches, I/O, and total work. A sequential scan can be correct for a small table or broad result.
- Choose composite index order from the real equality, range, ordering, and access patterns. The simplistic rule “most selective column first” is not generally sufficient.
- Account for write amplification, storage, vacuum behavior, and overlap with existing indexes before adding one.

## PostgreSQL-specific data

- Use JSONB when flexible document structure is part of the domain. Prefer typed relational columns for frequently constrained, joined, or independently updated fields.
- Select GIN operator class from actual operators: default `jsonb_ops` supports more operators; `jsonb_path_ops` supports a narrower set with different size and performance characteristics.
- Use partial indexes only when the query predicate can use them, and verify that with the planner.

## Atomic writes

`INSERT ... ON CONFLICT` can express an atomic insert-or-update against a matching unique or exclusion constraint. Define what a conflict means and which values may be updated. `DO NOTHING ... RETURNING` returns no row for an existing conflict, so obtain an existing identifier through an intentional alternative when needed.

## Sources

- PostgreSQL indexes — https://www.postgresql.org/docs/current/indexes.html
- PostgreSQL EXPLAIN — https://www.postgresql.org/docs/current/using-explain.html
- PostgreSQL JSON — https://www.postgresql.org/docs/current/datatype-json.html
- PostgreSQL INSERT — https://www.postgresql.org/docs/current/sql-insert.html
