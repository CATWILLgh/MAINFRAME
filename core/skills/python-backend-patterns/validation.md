# Validation patterns

Per-stack choice. Universal principle: validate at system boundaries (untrusted input), trust type-system inside.

## Pydantic 2 (FastAPI, Litestar, standalone)

- Core in Rust → 5-20× faster than Pydantic 1.
- Use `BaseModel` for inbound (request, mutation): full validation, field-level errors with paths.
- For read-heavy response models (nested collections) — `TypedDict` + `TypeAdapter` is faster than nested `BaseModel`. Tradeoff: looser typing in IDE.
- Distinct `*In` / `*Out` models per resource. Never reuse same model for request and response — write fields and read fields differ (e.g. `password_hash` write-only, `created_at` read-only).
- `Field(...)` for constraints (`gt=0`, `min_length=1`, `max_length=255`); `field_validator` / `model_validator` for cross-field invariants.
- Sensitive fields: omit from `Out` model entirely. Per FastAPI docs, fields not declared in `response_model` are dropped from JSON.

```python
class UserOut(BaseModel):
    id: int
    email: EmailStr
    # password_hash deliberately absent

class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12)
```

## Marshmallow (Flask, when Pydantic not adopted)

- Schemas separate from models (unlike Django serializers / Pydantic). `class Schema(Schema): ...` with declarative fields.
- `load()` to deserialise → dict; `dump()` to serialise → dict. Flask-smorest does this around routes via `@blp.arguments` / `@blp.response`.
- `meta` `unknown=EXCLUDE` to silently drop unknown input fields; `unknown=RAISE` (default) to surface them as validation errors — usually correct for `*In` schemas.
- `validates_schema` for cross-field invariants. Numeric fields: `Range(min=...)` + `gt`.

## DRF serializers (Django)

- `ModelSerializer` for direct model mapping; `Serializer` for non-model contracts (filters, queries, action payloads).
- `read_only_fields` / `write_only_fields` to separate read/write surface — same model class, different lenses.
- `validate_<field>` for single-field; `validate(self, attrs)` for cross-field.
- For nested writes — disable by default (overrides are easy footgun); prefer separate endpoints per related resource.

## Universal anti-patterns

- Trusting client-supplied IDs / foreign keys without ownership check.
- Reusing one schema for in + out → leaks write-only fields or accepts read-only inputs.
- Silent unknown-field drop on `*In` when audit/compliance requires strict input — set `extra="forbid"` (Pydantic) / `unknown=RAISE` (Marshmallow).

## Sources

- Pydantic — https://docs.pydantic.dev/latest/
- Marshmallow — https://marshmallow.readthedocs.io/
- DRF — https://www.django-rest-framework.org/api-guide/serializers/
