# Project recon — detect the stack

First step on activation. Two paths.

## Preferred: deterministic script

```bash
node ~/.claude/skills/mainframe/skills/nestjs-backend-patterns/recon.js [project_root]
```

Parses `package.json` + tsconfig + lockfile signal. Emits the RECON block to stdout deterministically. Read its source [recon.js](recon.js) if you need to extend detection signals.

## Manual fallback

If the script is unavailable (custom layout, missing Node) — Read `package.json` yourself. Match dependency names (lowercase) in `dependencies` + `devDependencies`:

| Category | Signal → Conclusion |
|---|---|
| Framework | `@nestjs/core` → nestjs / `express` → express / `fastify` → fastify / `koa` / `@adonisjs/core` → niche |
| ORM | `typeorm` / `@prisma/client` → prisma / `drizzle-orm` → drizzle / raw `pg`/`postgres` → no-ORM |
| Validation | `class-validator` / `zod` / `joi` (legacy) |
| Auth | `passport` + `@nestjs/passport` / `passport-jwt` / `jsonwebtoken` direct |
| Background workers | `bullmq` / `bull` (legacy) / `agenda` / `bee-queue` |
| Caching | `redis` / `ioredis` / `cache-manager` / `keyv` |
| Error reporting | `@sentry/node` / `@sentry/nestjs` |
| Observability | `pino` + `@opentelemetry/api` |
| API doc gen | `@nestjs/swagger` / `@fastify/swagger` / `swagger-ui-express` |
| Testing | `jest` + optional `supertest` + `testcontainers` |
| WebSockets | `socket.io` / `@nestjs/websockets` / `ws` |
| Real-time | `@nestjs/graphql` / `apollo-server` |
| Package manager | `pnpm-lock.yaml` → pnpm / `yarn.lock` → yarn / `bun.lockb` → bun / `package-lock.json` → npm |
| Node version | `engines.node` in `package.json` or `.nvmrc` / `.node-version` |
| TS strict | parse `tsconfig.json` — `strict: true`? `noUncheckedIndexedAccess: true`? |

## Output block — same shape either path

```
RECON:
  node_version: <spec from engines or .nvmrc>
  package_manager: <pnpm|npm|yarn|bun|unknown>
  framework: <nestjs|express|fastify|niche|none>
  orm: <typeorm|prisma|drizzle|none>
  validation: <class-validator|zod|joi|none>
  auth: <passport+jwt|jwt-direct|none>
  background_workers: <bullmq|bull|agenda|none>
  caching: <redis|memcached|in-process|none>
  error_reporting: <sentry|none>
  observability: <pino+otel|pino|console|none>
  openapi_gen: <nestjs-swagger|fastify-swagger|swagger-ui-express|none>
  testing: <jest+testcontainers|jest|unknown>
  websockets: <socket.io|nestjs-ws|ws|none>
  ts_strict: <true|false|partial>
```

## Immediate red flags

- `strict: false` in tsconfig — surface as technical debt (`surface-ticket`).
- Both `typeorm` AND `@prisma/client` declared — pick the active one, ask user.
- `bull` (legacy) instead of `bullmq` — flag migration opportunity.
- No `pino` + ad-hoc `console.log` — observability gap, recommend setup.

## When recon is ambiguous

If a signal points two ways (e.g. both `express` and `fastify` declared) — ask user which is the primary entry point. Do not guess.
