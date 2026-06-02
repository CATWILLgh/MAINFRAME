# SQLAlchemy 2.0 patterns

Cross-framework ORM patterns (Flask, FastAPI). Django ORM has its own conventions — see [django.md](django.md).

## Eager loading by cardinality

- `joinedload()` — many-to-one (single related object). LEFT OUTER JOIN, one query.
- `selectinload()` — one-to-many / many-to-many (collections). Second `SELECT ... WHERE id IN (...)`. Avoids row multiplication.
- Anti-pattern: `joinedload()` on a collection → cartesian product, exploding row count, broken pagination.

```python
query = Machine.query.options(joinedload(Machine.shop))           # many-to-one OK
query = Shift.query.options(selectinload(Shift.jobs))             # collection OK
query = Job.query.options(joinedload(Job.downtimes))              # BAD: cartesian
```

## Locking + eager loading — incompatible

`with_for_update()` + `joinedload()` is officially **unsupported** by SA 2.0 (per ORM Querying Guide). Pair `with_for_update()` with `populate_existing()` and load relations separately.

```python
stmt = select(Shift).where(Shift.id == sid).with_for_update().execution_options(populate_existing=True)
shift = session.execute(stmt).scalar_one_or_none()
# load relations after if needed: session.refresh(shift, ["jobs"])
```

## Partial loads

`load_only()` / `with_entities()` when only specific columns are needed. Combine with `selectinload` for related-collection column reduction.

```python
stmt = select(User).options(load_only(User.id, User.email), selectinload(User.roles).load_only(Role.name))
```

## Transaction discipline

- `session.begin()` / `with Session(...)` for full write transactions.
- `session.begin_nested()` + `except IntegrityError` to skip duplicate inserts without rolling back the outer transaction.
- Typed exceptions: `except IntegrityError` (not `except Exception`). For pgcode discrimination (unique vs FK vs CHECK) — psycopg-level; SA wraps but does not classify.

```python
for row in batch:
    try:
        with session.begin_nested():
            session.add(Model(**row))
    except IntegrityError:
        continue  # row already exists; outer txn intact
```

## Aggregates in SQL

`func.sum`, `func.count`, `func.avg`, `case()` expressions. Python loops over result sets are an anti-pattern except for logic SQL cannot express (e.g. `datetime.now()`-based active-time calculation).

```python
stmt = select(Job.status, func.count(Job.id)).group_by(Job.status)
```

## Migrations

Alembic is the migration runner for SQLAlchemy. Safety doctrine — non-blocking DDL, expand-contract, batched/idempotent backfills, plus Alembic specifics (`autocommit_block`, paired `downgrade`) — see [migrations.md](migrations.md).

## Sources

- SQLAlchemy 2.0 ORM Querying Guide — https://docs.sqlalchemy.org/en/20/orm/queryguide/
