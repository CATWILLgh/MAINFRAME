# HTTP service concerns

Read only when the changed contract involves one of these concerns.

## Idempotency

Use an idempotency key when a client may safely retry an operation whose duplicate execution would cause harm: payments, order creation, subscription changes, or externally triggered jobs. Preserve the project's existing contract; do not add the header to every POST by default. Scope stored keys to the caller and operation, compare a request fingerprint, retain the authoritative outcome, and set a deliberate expiry.

Stripe's all-POST behavior is one API's policy, not a universal REST rule.

## Pagination

- Offset pagination supports page jumps but becomes expensive at large offsets and can drift under concurrent writes.
- Cursor pagination suits ordered feeds and exports but needs a deterministic, unique ordering and explicit forward or backward semantics.
- A cursor should prevent clients from constructing unsafe ordering state when that matters. Base64 is encoding, not integrity protection; use a signed or server-issued cursor when forgery affects correctness or access.

## Rate limits

Return `429` and a useful `Retry-After` contract when the caller may retry. Choose identity from the abuse boundary: user, tenant, credential, route, IP, or a combination. A process-local limiter is not a distributed limit across workers or instances. Preserve an established gateway or limiter instead of adding a second one.

## Health

Keep liveness cheap and independent of downstream availability. Readiness may check dependencies required to serve traffic. Preserve platform-specific paths and response shapes; do not rename a working contract merely to use `/live` and `/ready`.

## Configuration

Use the project's established typed configuration layer and fail early on missing required values. When Pydantic is already used, `pydantic-settings` can validate environment-backed configuration and `SecretStr` can reduce accidental display. Neither replaces correct secret storage or log filtering.

## Sources

- Stripe idempotent requests — https://docs.stripe.com/api/idempotent_requests
- RFC 6585 — https://www.rfc-editor.org/rfc/rfc6585
- Kubernetes probes — https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/
- Pydantic settings — https://docs.pydantic.dev/latest/concepts/pydantic_settings/
