# Runtime and packaging

Work from the nearest package that owns the behavior, not automatically from the repository root. Inspect its `pyproject.toml`, lockfile, legacy setup metadata, requirements files, package layout, entrypoints, container or process command, and effective project instructions.

Preserve the established interpreter range and environment manager. PEP 621, Poetry, PDM, Hatch, uv, Pipenv, and requirements-based layouts describe dependencies differently; do not rewrite one into another as incidental cleanup. Distribution names and import names may differ, and declared metadata may be dynamic.

Identify whether the server boundary is WSGI, ASGI, a worker, a scheduler, a CLI, or a combination. Preserve the active process model and import path. Trace application factories, router or URL registration, middleware ordering, startup and shutdown hooks, and any generated files before editing them.

Match the established sync/async boundary. An `async def` declaration does not make blocking I/O non-blocking, and a synchronous framework may use a short-lived event loop or adapter with different lifecycle rules. Do not share request-scoped objects across threads, tasks, or processes without documented support.

Use the project's existing formatting, linting, typing, and test commands. Preserve configured mypy, Pyright, basedpyright, Ruff, or other conventions rather than starting a broad typing or style migration. Inspect inherited configuration before concluding that a direct setting is effective.

Do not edit generated clients, migrations, schemas, stubs, or artifacts until ownership is known. Change the canonical source and regenerate through the project's native command when regeneration is in scope; otherwise report the required follow-up precisely.
