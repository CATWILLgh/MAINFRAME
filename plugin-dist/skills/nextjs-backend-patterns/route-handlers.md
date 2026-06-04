# Route Handlers — `app/api/.../route.ts`

The HTTP API layer of an App Router app. Export one named async function per method.

## Shape

- Export `GET` / `POST` / `PUT` / `PATCH` / `DELETE` — each `(req: NextRequest, ctx) => Response | NextResponse`.
- `req` is the Web `Request` / `NextRequest` (adds `cookies`, `nextUrl`, and `req.auth` when wrapped with `auth()`). Respond with `NextResponse.json(data, { status })` or a Web `Response`.
- **Dynamic `params` is a `Promise` (Next 15) — `await` it:** `const { id } = await ctx.params`. Same for `searchParams`.

## Caching — Next 15 changed

- **GET is NOT cached by default** (was static in 14, now dynamic). Per the Next 15 upgrade guide: *"GET functions within Route Handlers are no longer cached by default in Next.js 15."*
- Opt back into caching: `export const dynamic = 'force-static'`. Other HTTP methods are never cached, even in the same file.
- Per-segment knobs: `export const revalidate = N` (ISR TTL); `export const runtime = 'nodejs' | 'edge'`.

## Discipline

- **Validate body/query with Zod at the top** — untrusted input; reject before business logic.
- **Authorize inside the handler** (session via `auth()` / the DAL) — a page check does NOT protect an API route; verify ownership of the specific resource (IDOR).
- Business logic lives in a service / use-case, not inline in the handler (layer split).
- Typed errors → mapped HTTP codes (`201` create, `409` conflict, `422` business-rule, `204` delete); never leak raw ORM errors.
- `edge` runtime: no Node APIs (`fs`, most ORMs, native crypto) — keep DB work on `nodejs`.

## Route Handler vs Server Action

Route Handler for external / standard-HTTP consumers (webhooks, mobile, third-party). Server Action for in-app form / mutation flows needing revalidation / redirect / cookies — see [server-actions.md](server-actions.md).

## Sources

- Next 15 upgrade (GET uncached, `params` Promise) — https://nextjs.org/docs/app/guides/upgrading/version-15
- Route Handlers — https://nextjs.org/docs/app/getting-started/route-handlers
- `route.ts` API + version history — https://nextjs.org/docs/app/api-reference/file-conventions/route
