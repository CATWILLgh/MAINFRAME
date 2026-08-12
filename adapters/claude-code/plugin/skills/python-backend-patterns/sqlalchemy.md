# SQLAlchemy

Establish the installed major, sync or async engine, session ownership, and existing query style before editing. Do not mix legacy and current APIs opportunistically.

## Loading and query shape

- Choose loading from relationship cardinality, result size, pagination, and actual access. `joinedload` often suits a single related object; `selectinload` often avoids row multiplication for collections.
- Collection joins can multiply rows and interact with pagination or result uniqueness. Inspect emitted SQL and result handling rather than banning them universally.
- Use `load_only` only when reduced columns materially help and deferred access will not trigger surprise queries.
- Count and aggregate in SQL when the database already owns the necessary data; keep application calculation when the rule genuinely depends on application-only context.

## Transactions and errors

- Align one session or unit of work with the business transaction. Commit ownership should be clear and not hidden across helpers.
- Use nested transactions or savepoints only when partial recovery is part of the intended contract.
- Catch the narrow database exception you can translate or recover from. Read driver-specific attributes through SQLAlchemy's wrapped original error and preserve the exception chain.
- Do not turn every integrity failure into the same HTTP status: map the known business meaning at the boundary and leave unknown operational failures visible to diagnostics.

## Concurrency

Keep row locks and the predicate they protect inside one transaction.
SQLAlchemy does not recommend combining `with_for_update` with joined eager
loading because the joined table may also be locked depending on the database.
Load only what the locked operation requires and verify the generated SQL and
lock scope against the active backend.

Use [migrations.md](migrations.md) for Alembic and [postgres-concurrency.md](postgres-concurrency.md) when transaction isolation or contention is the risk.

## Sources

- SQLAlchemy relationship loading — https://docs.sqlalchemy.org/en/20/orm/queryguide/relationships.html
- SQLAlchemy sessions — https://docs.sqlalchemy.org/en/20/orm/session_basics.html
- SQLAlchemy exceptions — https://docs.sqlalchemy.org/en/20/core/exceptions.html
