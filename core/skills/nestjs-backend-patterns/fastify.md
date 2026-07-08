# Fastify patterns

Performance-oriented framework (15% State of JS 2024 backend). Pino is the framework's bundled default logger — auto-wired when you pass `logger: true`. Pick when raw throughput matters or you want schema-driven validation built in.

## App structure

- `fastify({ logger: true })` bootstraps the app — auto-wires pino.
- Routes via plugins: `fastify.register(jobsRoutes, { prefix: "/v1/jobs" })`. Plugins are the **encapsulation primitive** — local hooks / decorators do not leak to parent scope unless explicitly exposed.

## Schema-driven validation + serialization

Fastify's killer feature — JSON Schema (or Zod via `fastify-type-provider-zod`) at the route level for **both input validation AND output serialization**:

```typescript
fastify.post("/jobs", {
  schema: {
    body: JobCreateSchema,
    response: { 201: JobOutSchema },
  },
}, async (req, reply) => {
  const job = await jobsService.create(req.body, req.user);
  return reply.code(201).send(job);
});
```

Output schema → `fast-json-stringify` skips fields not declared → field filtering for free + 2-3× faster than `JSON.stringify`. Per OpenAPI: same schema feeds Swagger UI via `@fastify/swagger`.

## Hooks instead of middleware

Fastify hooks fire at specific lifecycle points: `onRequest`, `preHandler`, `preSerialization`, `onSend`, `onResponse`.

```typescript
fastify.addHook("preHandler", async (req, reply) => {
  await authPlugin.verify(req); // attach req.user
});
```

`preHandler` is the canonical place for auth + tenant context binding.

## Plugins for shared concerns

Auth plugin, DB plugin, observability plugin — each as a Fastify plugin via `fastify-plugin` (breaks encapsulation intentionally for app-wide concerns). Per-resource plugins (`jobsRoutes`) stay encapsulated.

## Async by default

All handlers are async — no Express-style middleware-error caveats. Return the response value or call `reply.send(...)`. Throw errors → Fastify error handler runs (override via `setErrorHandler`).

## Sources

- Fastify docs — https://fastify.dev/
