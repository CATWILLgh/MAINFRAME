# Project recon — detect the stack

First step on activation. Two paths.

## Preferred: deterministic script

```bash
python3 ~/.claude/skills/mainframe/skills/python-backend-patterns/recon.py [project_root]
```

Parses `pyproject.toml` (PEP 621 + Poetry + uv) and `requirements.txt`. Emits the RECON block to stdout deterministically — same input always gives same output. Read its source [recon.py](recon.py) if you need to extend detection signals.

## Manual fallback

If the script is unavailable, fails (custom layout, malformed TOML), or the project uses `Pipfile` / `setup.py` only — Read these files yourself in order, stop on first hit: `pyproject.toml`, `requirements.txt`, `setup.py` / `setup.cfg`, `Pipfile`. Match dependency names (lowercase) against:

| Category | Signal → Conclusion |
|---|---|
| Framework | `fastapi` / `django` / `flask` / `litestar` |
| ORM | `sqlalchemy` 2.x / `tortoise-orm` / `sqlmodel` / Django (implicit) |
| Validation | `pydantic` ≥2 / `marshmallow` / `djangorestframework` |
| Async driver | `asyncpg` (async) / `aiomysql` (async) / `psycopg2` (sync) — `async def` + `psycopg2` is a CRITICAL mismatch |
| Background workers | `celery` / `arq` / `taskiq` / `rq` / `dramatiq` |
| Caching | `redis` / `python-memcached` / `cachetools` |
| Error reporting | `sentry-sdk` |
| Observability | `structlog` + `opentelemetry-*` |
| OpenAPI gen | `flask-smorest` (Flask) / `drf-spectacular` (Django) / built-in (FastAPI) |
| Config | `pydantic-settings` / `dynaconf` |
| Testing | `pytest` (+ optional `testcontainers` for real-DB) |
| Type checker | `[tool.pyright]` / `pyrightconfig.json` → pyright; `[tool.mypy]` / `mypy.ini` / `setup.cfg [mypy]` → mypy (config presence, not a dep string) |
| Multitenancy | `organization_id` / `tenant_id` columns OR PostgreSQL RLS policies |

## Output block — same shape either path

```
RECON:
  python_version: <spec from requires-python>
  package_manager: <uv|poetry|pipenv|unknown>
  framework: <fastapi|django|flask|niche|none>
  orm: <sqlalchemy-2|django|tortoise|sqlmodel|none>
  validation: <pydantic-2|marshmallow|drf|none>
  async_driver: <async|sync|none>
  background_workers: <celery|arq|taskiq|rq|dramatiq|none>
  caching: <redis|memcached|in-process|none>
  error_reporting: <sentry|none>
  observability: <structlog|otel|none>
  openapi_gen: <flask-smorest|drf-spectacular|apispec|none>
  config: <pydantic-settings|dynaconf|none>
  testing: <pytest+testcontainers|pytest|none>
  type_checker: <pyright|mypy|basedpyright|ty|none>
  multitenancy: <rls|app-filter|none>
```

## Immediate red flags

- `async def` handlers + sync DB driver (`psycopg2`, sync `pymysql`) → event-loop blocked. CRITICAL — surface before any further work.
- Mixed Marshmallow + Pydantic without clear boundary → which one validates inbound, which serialises out? Ask.
- `pyproject.toml` declares both `tool.poetry` AND `tool.uv` → migration in progress; do not change dependency files without asking.

## When recon is ambiguous

If a signal points two ways (e.g. both `flask` and `fastapi` declared) — ask the user which is the primary entry point. Do not guess.
