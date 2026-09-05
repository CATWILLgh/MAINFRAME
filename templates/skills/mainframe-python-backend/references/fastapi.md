# FastAPI

Preserve the project's data library and sync or async execution model. Establish the installed FastAPI and Pydantic versions before using version-sensitive APIs.

## Application boundaries

- For new application-wide startup and shutdown behavior, use the current `lifespan` mechanism. Preserve established event wiring unless migration is assigned.
- Organize `APIRouter` boundaries around existing modules; do not force one router per resource.
- Use dependencies for request-scoped identity, configuration, or data units of work when that matches the project.
- Keep non-trivial business behavior outside path functions so workers and commands can share it.

## Contracts and security

- Validate input and declare an intentional response contract. Separate request and response models when their writable and readable fields differ.
- Treat response filtering as defense in depth, not permission enforcement.
- Verify identity, operation permission, and resource ownership server-side. A tenant identifier supplied by the request is not authorization.
- Use `Security` when OAuth scopes are part of the documented contract; otherwise preserve the established dependency mechanism.

## Concurrency and background work

- Match the path function to the libraries it calls: awaitable I/O belongs in `async def`; blocking I/O should use a normal `def` path or an explicitly managed thread boundary. FastAPI supports both.
- Do not call a blocking database driver directly inside `async def`. Keep SQLAlchemy async engine and `AsyncSession` use consistent on an async path.
- `BackgroundTasks` runs inside the application process. Durable, retryable, expensive, or independently scalable work needs the project's durable worker mechanism.

## Sources

- FastAPI concurrency — https://fastapi.tiangolo.com/async/
- FastAPI lifespan — https://fastapi.tiangolo.com/advanced/events/
- FastAPI response models — https://fastapi.tiangolo.com/tutorial/response-model/
