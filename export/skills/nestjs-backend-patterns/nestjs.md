# NestJS patterns

Opinionated DI-first framework. Decorators throughout. Per State of JS 2024 — 30% adoption among JS backend devs. Pairs with TypeORM / Prisma / Drizzle (recon-detect), class-validator (default) or Zod (via `nestjs-zod`).

## Module / controller / service layering

- One feature module per bounded context (`jobs.module.ts` imports `JobsController`, `JobsService`).
- `Controller` — HTTP orchestration only; parse request, call service, format response. No business logic.
- `Service` — business logic + transactions. Inject repositories / clients.
- `Repository` — data access. Use `@InjectRepository(Entity)` (TypeORM) or inject `PrismaService`.

```typescript
@Controller("jobs")
export class JobsController {
  constructor(private jobs: JobsService) {}
  @Post() @UseGuards(JwtAuthGuard, RolesGuard) @Roles("operator")
  create(@Body() dto: CreateJobDto, @Req() req: Request) {
    return this.jobs.create(req.user, dto);
  }
}
```

## DI scopes — singleton by default

- **DEFAULT (singleton)** — one instance for the entire app lifetime, 0-cost. Use for stateless services. Per NestJS docs «a single instance of the provider is shared across the entire application».
- **REQUEST** — one instance per HTTP request. Propagates up the dependency chain — every consumer becomes REQUEST-scoped. **Adds overhead.** Use only for genuine per-request mutable state.
- **TRANSIENT** — new instance per injection point. Niche.

**Prefer `AsyncLocalStorage` (or NestJS `ClsModule` wrapping it) over REQUEST scope** for carrying request-scoped context like tenant ID — no propagation cost. See [multitenancy.md](multitenancy.md).

## Pipes — validation at the boundary

- Global `ValidationPipe` (in `main.ts`) auto-applies to every endpoint. `whitelist: true` drops unknown fields. `forbidNonWhitelisted: true` rejects them — usually correct for `*In` DTOs.
- Custom pipes for parsing (e.g. `ParseIntPipe`, `ParseUUIDPipe`) — apply per-param.

## Guards + Interceptors

- `Guard` (e.g. `JwtAuthGuard`, `RolesGuard`) — auth/authz gates, run BEFORE the handler.
- `Interceptor` — wraps handler; use for logging, transforming response, timing. Avoid for auth (that's a guard).
- Order: middleware → guards → interceptors (before) → pipes → handler → interceptors (after) → filters.

## Exception filters

Throw NestJS exceptions (`BadRequestException`, `NotFoundException`, `ConflictException`) — auto-mapped to HTTP status. For custom domain errors: `@Catch(MyDomainError)` filter mapping to 4xx with localized message.

## Sources

- NestJS docs — https://docs.nestjs.com/
