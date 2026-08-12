# Python backend testing

Use the project's existing pytest setup and fixtures. Protect the behaviour
changed by the task with the smallest test that can catch its regression.

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

## Completion

For a bug or changed business rule, observe the focused test fail for the
intended reason before the fix when an automated reproduction is practical.
Then observe it pass and run the nearest relevant fast suite with the project's
native command. Do not weaken assertions, duplicate the same rule across
levels, or leave skipped tests and temporary markers.

## Sources

- pytest — https://docs.pytest.org/
- HTTPX ASGI transports — https://www.python-httpx.org/advanced/transports/
- PostgreSQL concurrency control — https://www.postgresql.org/docs/current/mvcc.html
