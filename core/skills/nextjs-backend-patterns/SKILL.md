---
name: nextjs-backend-patterns
user-invocable: false
disable-model-invocation: true
description: "Next.js App Router server-layer patterns — recon-driven dispatch across Route Handlers, Server Actions, RSC data fetching, caching / revalidation, middleware, server-side auth (Auth.js / NextAuth v5, the Data Access Layer pattern), and ORM access in serverless (Prisma singleton / connection pooling, Drizzle HTTP drivers). Cross-cutting: server-as-canonical, authorize-in-the-DAL-not-middleware-alone, `NEXT_PUBLIC_` secret-leak ban, `server-only` boundary, Zod at every boundary, TypeScript strict. Covers what is DISTINCT to Next's server model — defers generic Node/ORM depth to the standalone backend skill. Loaded by `nextjs-backend-engineer` agent only; closed to main-context auto-invocation."
when_to_use: "A Next.js App Router backend task is in flight inside the `nextjs-backend-engineer` sub-agent — Route Handlers (`app/api`), Server Actions, RSC data fetching, caching / `revalidate`, `middleware.ts`, server auth / session, or ORM access in a serverless context. Triggered via agent frontmatter `skills:` preload, not by direct user invocation. Out of scope: the client React UI (`react-frontend-engineer`); standalone NestJS / Express / Fastify / Python APIs (separate backend agents)."
---

# Next.js backend patterns — App Router server layer

Preloaded into the `nextjs-backend-engineer` sub-agent. Dispatch from project recon to per-concern files, plus universal principles. Scope: the server layer of a Next app — the client React UI is `react-frontend-engineer`'s. This skill covers what is *distinct* to Next (the RSC / Server-Action / caching / Route-Handler model); it does not re-teach generic Node/ORM/validation depth — that lives in the standalone backend skill.

## How to use

1. **Recon first.** Run [recon.js](recon.js) — `node ~/.claude/skills/mainframe/skills/nextjs-backend-patterns/recon.js [project_root]` — for a deterministic parse of `package.json` + Next version + router. Manual fallback — [recon.md](recon.md) holds the by-hand stack-detection steps — when the script is unavailable.
2. **Apply universal principles** (below) — they hold across the surface.
3. **Dispatch by recon + task** — read only the relevant supporting file(s). Do NOT pre-read irrelevant ones (token discipline).
4. **Caching is version-sensitive** — confirm defaults against current docs (Context7); they changed between Next 14 and 15.
5. **Test** per [testing.md](testing.md).

## Dispatch table

| Task / recon outcome | Read this |
|---|---|
| API endpoint (`app/api/.../route.ts`) | [route-handlers.md](route-handlers.md) |
| Mutation / form action (`'use server'`) | [server-actions.md](server-actions.md) |
| Server-component data fetching | [rsc-data.md](rsc-data.md) |
| Caching / `revalidate` / stale data | [caching.md](caching.md) |
| `middleware.ts` | [middleware.md](middleware.md) |
| Auth / session / protecting routes | [auth.md](auth.md) |
| ORM / DB / connection handling | [data.md](data.md) |
| Any testing task | [testing.md](testing.md) |
| `router: pages` detected | flag legacy; basic `pages/api` only — App Router is the supported target |

## Universal principles (apply across the surface)

Cross-reference the umbrella CLAUDE.md rules (CQS, debug residue, marker bans, boundary validation) — they apply here too, not duplicated.

### The server is canonical
Authority, state transitions, and computed values live server-side. Inbound data at the trust boundary is untrusted — validate with Zod in the Route Handler / Server Action before any business logic (CLAUDE.md "data at system boundaries… must be validated"). Client code is a UX accelerator only.

### Layer split
`Route Handler / Server Action` (entry + HTTP) → `use-case / service` (business logic) → `data-access layer` (`server-only`) → `ORM`. Business logic NEVER lives in a Route Handler, a Server Action body, or a Server Component. Server Components fetch through the data layer, they don't embed queries inline for anything non-trivial.

### Authorize in the data layer — middleware is NOT the gate
Every privileged Server Action / Route Handler / data-access function checks the session itself (the Data Access Layer pattern: a `server-only` module that calls `await auth()` / `verifySession()` before touching data). Middleware must never be the sole authorization layer — it is bypassable (a known middleware auth-bypass class, e.g. CVE-2025-29927) and runs before you know the data. Middleware is for coarse UX redirects; real authz is at the data boundary. Per the Next.js Data Security guide.

### Server Actions are public endpoints
A `'use server'` function compiles to a public POST route. Treat every one as an untrusted HTTP endpoint: validate args (Zod) and authorize inside the action, every time — the caller is not to be trusted, even if a button is hidden in the UI.

### Secrets are server-only
Any `NEXT_PUBLIC_`-prefixed env var is inlined into the client bundle at build — never put secrets there. Server-only secrets stay unprefixed and are read only in server modules. Mark server data modules with `import 'server-only'` so an accidental client import fails the build instead of leaking server code.

### Caching is explicit and version-aware
In Next 15, `fetch` and GET Route Handlers are not cached by default (changed from 14). Opt into caching deliberately (`fetch(..., { cache: 'force-cache' })`, segment `export const revalidate`), and invalidate via `revalidatePath` / `revalidateTag`. Never assume a default — confirm against current docs. See [caching.md](caching.md).

### Standard backend discipline still applies
Eager-load relations (N+1 is the prime backend regression). Throw typed errors, never leak raw ORM errors to the client. One consistent response/envelope shape. TypeScript strict mode is the floor; `any` / `as` / `@ts-ignore` banned per umbrella CLAUDE.md.

## Out of scope

- The client React UI of a Next app (components, hooks, client state, forms) — `react-frontend-engineer`.
- Standalone NestJS / Express / Fastify / Python APIs — the other backend agents.
- Deep generic ORM / PostgreSQL tuning — the standalone backend skill owns that; here, only the Next-serverless-specific data concerns ([data.md](data.md)).
- Infrastructure ownership (Vercel config beyond app code, full IaC) — `devops-engineer`.

## Sources

Per-file authoritative URLs are at the bottom of each supporting file. Umbrella references:
- Next.js App Router docs — https://nextjs.org/docs/app
- Next.js Data Security / DAL guide — https://nextjs.org/docs/app/guides/data-security
- Next.js caching — https://nextjs.org/docs/app/building-your-application/caching
- Auth.js (NextAuth v5) — https://authjs.dev/
- Prisma serverless / best practices — https://www.prisma.io/docs/orm/more/best-practices
- OWASP Input Validation + Authorization Cheat Sheets — https://cheatsheetseries.owasp.org/
