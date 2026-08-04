# FastAPI patterns

Async-native ASGI framework. ORM: SQLAlchemy 2.0 with async session → [sqlalchemy.md](sqlalchemy.md). Validation: Pydantic 2 → [validation.md](validation.md).

## App + lifespan

Use the `lifespan` async context manager (Starlette pattern) for startup/shutdown — DB engine init, OTel setup, cache pool. The legacy `@app.on_event("startup")` is deprecated.

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    engine = create_async_engine(settings.db_url)
    yield {"engine": engine}
    await engine.dispose()
```

## Routers + dependency injection

- One `APIRouter` per resource; mount under a prefix.
- DI via `Depends(...)` — DB session, current user, tenant context.
- `Annotated[Session, Depends(get_db)]` is the current idiomatic typing (FastAPI ≥ 0.95).

```python
@router.get("/jobs", response_model=list[JobOut])
async def list_jobs(db: SessionDep, user: CurrentUser, args: JobListArgs = Depends()): ...
```

## Response_model — contract + filter

`response_model=` on the route both documents AND filters response — fields not declared in the model are silently dropped from the JSON. Per FastAPI docs: prevents accidental field leakage. Use distinct `*In` (request) and `*Out` (response) Pydantic models, never the same model both ways.

## Background tasks

- `BackgroundTasks` dep for fire-and-forget after-response work (logging, simple emails). Runs in the same process.
- Heavy or retryable work → real queue (Celery / ARQ / Taskiq). FastAPI's `BackgroundTasks` is NOT a job queue.

## Security utilities

- `OAuth2PasswordBearer` for OAuth2 password flow tokens.
- `Security(...)` over `Depends(...)` when scopes are involved (surfaces in OpenAPI as scopes).
- Tenant + role go in JWT claims. Verify in a dep, never accept `organization_id` from request.

## Async discipline

- ALL deps in an async route must be `async` or non-blocking. Sync DB driver (`psycopg2`) inside `async def` blocks the event loop.
- For SA async: `AsyncSession`, `select(...)`, `await session.execute(...)`. Do NOT mix sync `Session` and `AsyncSession`.

## Sources

- FastAPI docs — https://fastapi.tiangolo.com/
- Pydantic 2 docs — https://docs.pydantic.dev/latest/
