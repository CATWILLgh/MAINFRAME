# Testing patterns

`pytest` + (for async stacks) `pytest-asyncio` + `httpx.AsyncClient`. Real-DB tests via `testcontainers-python` when DB semantics matter (RLS, locking, JSONB, triggers). Pyramid orientation per hub `testing-strategy` skill — unit-first, integration only when a cross-boundary contract demands it.

## Per-endpoint contract — 4 mandatory scenarios

| Scenario | Expected |
|---|---|
| Happy path | 200 / 201, response shape matches schema |
| Unauthorized | 401 (no token) or 403 (insufficient role) |
| Not found | 404 with a stable error envelope |
| Invalid input | 400 / 422, field-level errors in body |

## Async tests (FastAPI, async SA)

`AsyncClient(app=app, base_url="http://test")` from `httpx` runs ASGI in-process, no socket — faster than a real server.

```python
@pytest.mark.asyncio
async def test_create_job(async_client, auth_header):
    r = await async_client.post("/jobs", json={...}, headers=auth_header)
    assert r.status_code == 201
```

## Real-DB integration via testcontainers

For PostgreSQL-specific semantics (RLS, FK, advisory locks, JSONB, `LISTEN/NOTIFY`):

```python
@pytest.fixture(scope="session")
def pg_url():
    with PostgresContainer("postgres:16") as pg:
        yield pg.get_connection_url()
```

Per-test transaction wrap → instant cleanup. Per-session container → fast amortised startup.

## Race-condition tests for `SELECT FOR UPDATE`

Status-changing operations are vulnerable to read-then-write races. Test with concurrent attempts — one wins, the rest fail (409 / 422):

```python
def test_complete_shift_race(client, shift):
    errors = []
    def w():
        r = client.post(f"/shifts/{shift.id}/complete")
        if r.status_code != 200: errors.append(r.json())
    ts = [Thread(target=w) for _ in range(2)]; [t.start() for t in ts]; [t.join() for t in ts]
    assert len(errors) == 1
```

For async: replace threads with `asyncio.gather` + multiple `AsyncClient` calls.

## Sources

- pytest — https://docs.pytest.org/
- pytest-asyncio — https://pytest-asyncio.readthedocs.io/
- testcontainers-python — https://testcontainers-python.readthedocs.io/
