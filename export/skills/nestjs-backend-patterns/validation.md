# Validation patterns

Two dominant choices in TS backend ecosystem 2026 — pick by stack and ergonomics. Both work, neither is strictly «better» across all axes. Per-stack defaults below.

## Zod — schema-first, type-inferred

```typescript
import { z } from "zod";
const JobCreateSchema = z.object({
  machineId: z.string().uuid(),
  durationHours: z.number().positive().max(24),
  partsTotal: z.number().int().nonnegative(),
});
type JobCreateDto = z.infer<typeof JobCreateSchema>;
```

- **Types flow FROM schema** — no decorators, no codegen. `z.infer<T>` produces the DTO type directly.
- Default for Express / Fastify / tRPC / plain TS backends; Hono / Astro / Next.js routes.
- NestJS integration: `nestjs-zod` package — works but is not first-class in the NestJS ecosystem.
- Refinements via `.refine((v) => ..., { message: "..." })` for cross-field invariants.

## class-validator + class-transformer — decorator-first

```typescript
export class JobCreateDto {
  @IsUUID() machineId: string;
  @IsPositive() @Max(24) durationHours: number;
  @IsInt() @Min(0) partsTotal: number;
}
```

- **NestJS default** — `ValidationPipe` (global) auto-applies. Tight integration with `@Body()`, `@Query()`, `@Param()`.
- Requires `experimentalDecorators` + `emitDecoratorMetadata` in tsconfig.
- Class is the source of truth — no `z.infer` step needed because class IS the type.
- `class-transformer` partner: `@Type(() => Date) startsAt: Date` — runtime parsing of nested types from JSON.

## When to pick which

| Scenario | Pick |
|---|---|
| NestJS project (especially new) | class-validator (zero-friction with framework) |
| Express / Fastify / standalone TS | Zod (no decorators needed) |
| Sharing schemas with frontend (tRPC, validation parity) | Zod |
| Codebase already on Zod with `nestjs-zod` glue | Stay on Zod even in NestJS |

## Universal anti-patterns

- Reusing one schema for inbound + outbound — write fields and read fields differ (`password` write-only, `createdAt` read-only). Distinct `*In` / `*Out` schemas.
- Trusting client-supplied IDs without ownership check — schema validation does NOT replace authorization checks (see [SKILL.md](SKILL.md) source-of-truth principle).
- Silent unknown-field drop on `*In` — enforce `whitelist: true` + `forbidNonWhitelisted: true` (NestJS) or `.strict()` (Zod) when audit / compliance matters.

## Sources

- Zod docs — https://zod.dev/
- class-validator — https://github.com/typestack/class-validator
- nestjs-zod — https://github.com/risen228/nestjs-zod
