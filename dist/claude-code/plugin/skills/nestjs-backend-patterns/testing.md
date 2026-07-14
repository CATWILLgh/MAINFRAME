# Testing patterns (Node / TS backend)

Jest is the universal base. `supertest` for HTTP contract tests via in-process server (no socket bind). `testcontainers-node` for real-DB integration tests when DB semantics matter (RLS, FK, advisory locks, JSONB triggers).

Tier orientation per hub `testing-strategy` skill — Tier 1 (no real environment: in-process unit + `supertest`) is the default and the continuous-regression gate; a real-DB / external tier is reached only when a cross-boundary contract demands it. Cheaper is not less important — the higher tier guards risk Tier 1 cannot.

## Per-endpoint contract — 4 mandatory scenarios

| Scenario | Expected |
|---|---|
| Happy path | 200 / 201, response shape matches schema |
| Unauthorized | 401 (no token) or 403 (insufficient role) |
| Not found | 404 with a stable error envelope |
| Invalid input | 400 / 422, field-level errors in body |

## NestJS HTTP tests via supertest

```typescript
const moduleRef = await Test.createTestingModule({ imports: [AppModule] }).compile();
const app = moduleRef.createNestApplication();
await app.init();
const res = await request(app.getHttpServer()).post("/v1/jobs").send({ ... }).expect(201);
```

Express + Fastify: `request(app).post(...)` — app is the framework's app instance.

## Real-DB integration via testcontainers

For PostgreSQL-specific semantics (RLS, FK, advisory locks, JSONB, `LISTEN/NOTIFY`):

```typescript
let container: StartedPostgreSqlContainer;
beforeAll(async () => { container = await new PostgreSqlContainer("postgres:16").start(); });
afterAll(async () => { await container.stop(); });
beforeEach(async () => { await dataSource.synchronize(true); });
```

Per-suite container startup amortises cost. Per-test schema reset OR per-test transaction wrap → instant cleanup.

## Race-condition tests for `SELECT FOR UPDATE`

Status-changing operations are vulnerable to read-then-write races. Test with concurrent attempts — one wins, the rest fail (409 / 422):

```typescript
const results = await Promise.allSettled([
  request(app).post(`/v1/shifts/${id}/complete`),
  request(app).post(`/v1/shifts/${id}/complete`),
]);
const successes = results.filter(r => r.status === "fulfilled" && r.value.status === 200);
expect(successes).toHaveLength(1);
```

## What NOT to test

Framework primitives (`req.body` parsing), pure ORM mappings without business logic, internal call structure (see CLAUDE.md "Test the public contract").

## Sources

- Jest — https://jestjs.io/
- supertest — https://github.com/ladjs/supertest
- testcontainers-node — https://node.testcontainers.org/
