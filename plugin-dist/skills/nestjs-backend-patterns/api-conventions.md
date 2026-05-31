# API conventions — situational

Read when building or reviewing an HTTP endpoint and one of these concerns is in scope. Not always-on background discipline.

## Idempotency keys for POST

State-changing POST operations should accept an `Idempotency-Key` header. Server stores request hash + response for N hours; replays return the cached response without re-executing. Per Stripe API docs: «All `POST` requests accept idempotency keys.»

```typescript
const key = req.headers["idempotency-key"];
if (key && (cached = await idemStore.get(orgId, key))) return res.status(cached.status).json(cached.body);
const result = await handler(req);
if (key) await idemStore.put(orgId, key, result, 24 * 3600);
```

Critical: payment / charge / order create / subscription change endpoints.

## Pagination

Offset-based (`?page=N&perPage=K`) — admin UIs where jumping to page is needed; cost grows with offset, drift under concurrent writes. Cursor-based (`?after=<opaque>&limit=K`) — append-mostly feeds, infinite scroll, exports; no random access, stable under writes. Cursor opacity: never expose raw row ID — encode (signed token) so client cannot probe / forge.

## Rate limiting

Per RFC 6585: «The 429 status code indicates that the user has sent too many requests in a given amount of time ('rate limiting').» Pair with `Retry-After` header.

Implementation: `@nestjs/throttler` (NestJS), `@fastify/rate-limit` (Fastify), `express-rate-limit` (Express). Authenticated — limit per `userId`, NOT per IP. Unauthenticated — per IP.

## Health and readiness probes

Per Kubernetes: «If the liveness probe fails, the container will be restarted… If the readiness probe fails, the pod will be marked unready and will not receive traffic from any services.»

- `GET /live` — process alive; minimal work, returns 200.
- `GET /ready` — process ready (DB reachable, Redis reachable, deps up). Failure → traffic gated off, no restart.

Anti-pattern: single `/health` conflating both — restart loops on transient downstream issues.

## Configuration

`@nestjs/config` (NestJS) wraps `dotenv` with type-safe schema. For Express / Fastify: `dotenv` + Zod parse at startup:

```typescript
const env = z.object({
  DATABASE_URL: z.string().url(),
  JWT_SECRET: z.string().min(32),
  REDIS_URL: z.string().url(),
}).parse(process.env);
```

Type validation at startup → fail fast vs cryptic mid-request errors. Twelve-factor `III. Config` materialised in TS idiom.

## Sources

- Stripe Idempotent Requests — https://docs.stripe.com/api/idempotent_requests
- RFC 6585 — https://www.rfc-editor.org/rfc/rfc6585
- Kubernetes Probes — https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/
