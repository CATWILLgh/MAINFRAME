# Flask + Flask-smorest patterns

Sync-first by default. ORM: SQLAlchemy 2.0 → [sqlalchemy.md](sqlalchemy.md). Validation: Marshmallow (typical) or Pydantic 2 → [validation.md](validation.md).

## App factory

Single `create_app()` function in `app.py`. Register blueprints, JWT handlers, error handlers, observability inside the factory. Avoid module-level state. Configuration via env-vars + `app.config.from_*`.

## Blueprints via Flask-smorest

- `Blueprint` per resource. Use `MethodView` for class-based routes.
- Decorators `@blp.arguments(SchemaIn)` for input, `@blp.response(200, SchemaOut)` for output — give OpenAPI spec for free.
- Split large blueprint into a package (`api/<resource>/`) when the file exceeds the umbrella file-size rule (CLAUDE.md): one module per concern (crud, lifecycle, attachments, etc).

```python
@blp.route("/")
class JobList(MethodView):
    @blp.arguments(JobListArgs, location="query")
    @blp.response(200, JobOutSchema(many=True))
    @role_required("operator")
    def get(self, args): ...
```

## Auth — Flask-JWT-Extended

- `@jwt_required()` on protected routes. Tenant + role data go into JWT claims; extract via `get_jwt()` or a custom `@role_required` decorator.
- Refresh-token rotation: register a `@jwt.token_in_blocklist_loader` to revoke old refresh tokens after rotation.
- Never accept `organization_id` from request body for tenant scoping — always from JWT.

## Request lifecycle

- `before_request` — set tenant context (e.g. PostgreSQL GUC for RLS, or `flask.g.tenant_id`).
- `after_request` — log response metadata (status, duration). Do NOT log bodies (may contain secrets).
- `teardown_appcontext` — close DB sessions.

## Error handling

- Domain exceptions raised in services → caught by error handlers, mapped to 4xx with localised messages.
- Flask-smorest `abort(400, message="...")` for validation/business errors.
- `IntegrityError` discrimination → 409 (unique) vs 400 (FK) vs 422 (CHECK). See [sqlalchemy.md](sqlalchemy.md).

## Async caveat

Flask 2+ supports `async def` views via `asgiref`, but the WSGI server still runs each request on a thread. Real async requires switching to ASGI (Quart, FastAPI). Do NOT use `async def` with sync DB driver — no benefit, possible event-loop blocking under ASGI.

## Sources

- Flask docs — https://flask.palletsprojects.com/
- Flask-smorest — https://flask-smorest.readthedocs.io/
- Flask-JWT-Extended — https://flask-jwt-extended.readthedocs.io/
