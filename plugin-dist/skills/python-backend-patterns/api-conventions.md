# API conventions — situational

Read when building or reviewing an HTTP endpoint and one of these concerns is in scope. Not always-on background discipline.

## Idempotency keys for POST

State-changing POST operations should accept an `Idempotency-Key` header. Server stores request hash + response for N hours; replays return the cached response without re-executing. Per Stripe API docs: "All `POST` requests accept idempotency keys."

```python
key = request.headers.get("Idempotency-Key")
if key and (cached := idem_store.get(org_id, key)): return cached.response, cached.status
result = handler(...)
if key: idem_store.put(org_id, key, result, ttl=24*3600)
```

Critical: payment / charge / order create / subscription change endpoints. Optional but recommended for any state-creating POST.

## Pagination

Offset-based (`?page=N&per_page=K`) — admin / reporting UIs where jumping to page is needed; cost grows with offset, drift under concurrent writes. Cursor-based (`?after=<opaque>&limit=K`) — append-mostly feeds, infinite scroll, exports; no random access, stable under writes. Cursor opacity: never expose raw row ID — encode (encrypt or sign) so client cannot probe / forge.

## Rate limiting

Per RFC 6585: "The 429 status code indicates that the user has sent too many requests in a given amount of time ('rate limiting')." Pair with `Retry-After` header (seconds or HTTP-date).

Algorithm — token bucket (burst-tolerant, common for API gateways) or sliding window (smoother, slightly more expensive). Implement at the gateway layer (Cloudflare / Fastly / nginx `limit_req`) or via `slowapi` (FastAPI) / `flask-limiter` (Flask).

Authenticated users — limit per `user_id`, NOT per IP (shared NAT / corporate proxies cause collateral damage). Unauthenticated endpoints — per IP.

## Health and readiness probes

Per Kubernetes: "If the liveness probe fails, the container will be restarted… If the readiness probe fails, the pod will be marked unready and will not receive traffic from any services."

- `GET /live` — process alive; returns 200 with minimal work. Failure → restart.
- `GET /ready` — process ready to serve (DB reachable, cache reachable). Failure → traffic gated off, no restart.

Anti-pattern: single `/health` conflating both — restart loops on transient downstream issues. Keep separate.

## Configuration via pydantic-settings

Prefer `pydantic-settings` over ad-hoc `os.environ.get(...)`. Per official docs: "Fields not provided as keyword arguments will be read from environment variables."

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="APP_")
    database_url: PostgresDsn
    jwt_secret: SecretStr
```

Type validation at startup → fail fast vs cryptic mid-request errors. `SecretStr` masks values in logs. Twelve-factor `III. Config` materialised in Python idiom.

## Sources

- Stripe Idempotent Requests — https://docs.stripe.com/api/idempotent_requests
- RFC 6585 — https://www.rfc-editor.org/rfc/rfc6585
- Kubernetes Probes — https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/
- pydantic-settings — https://docs.pydantic.dev/latest/concepts/pydantic_settings/
