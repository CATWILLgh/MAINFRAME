# Python backend testing

Read this branch when the testing baseline in `SKILL.md` is not enough to
choose the correct test boundary or keep the suite economical. Preserve the
project's existing pytest setup and fixtures.

## HTTP and service behaviour

- Prove the intended success result.
- Add invalid-input, unauthorised, forbidden, missing-resource, conflict, or
  failure scenarios only when that branch exists in the changed contract.
- Keep business-rule variations at the service or pure-function level when an
  HTTP test would only repeat the same guarantee more slowly.
- Use `httpx.AsyncClient` or the framework's in-process client when the HTTP
  boundary matters but a real socket does not.

## PostgreSQL boundary

Use real PostgreSQL only for behaviour a fake cannot represent faithfully:
migrations, SQL shape, constraints, indexes, RLS, JSONB, transactions, locking,
isolation, triggers, or concurrent writes. Prefer the project's established
local database path. Do not introduce Testcontainers or another service merely
to satisfy a generic testing pattern.

When the change prevents a race, write a concurrent test against the real
database and assert the business outcome. The implementation detail
(`SELECT FOR UPDATE`, an atomic update, or a constraint) is not the assertion.

Do not add arbitrary waits or duplicate the same guarantee across several test
levels merely to increase test count.

## Sources

- pytest — https://docs.pytest.org/
- HTTPX ASGI transports — https://www.python-httpx.org/advanced/transports/
- PostgreSQL concurrency control — https://www.postgresql.org/docs/current/mvcc.html
