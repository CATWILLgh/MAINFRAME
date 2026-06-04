# RSC data fetching — server components

Server Components fetch on the server; nothing reaches the client unless passed as a serializable prop.

## The server/client boundary

- **`import 'server-only'`** at the top of every server data module → a build error if a Client Component imports it. Per Next: *"causes a build error if the module is imported in the client environment."* This is the mechanical guard against leaking server code / secrets.
- **Never pass raw DB rows to a Client Component.** Map to a minimal DTO first — *"Return only the public fields."* A row carrying `passwordHash` handed to a client prop is a leak.
- Secrets: only `NEXT_PUBLIC_`-prefixed env reaches the client; keep secrets unprefixed, read server-side only.

## Data Access Layer (DAL) — the recommended pattern

A `server-only` module that is the single door to data. Per Next, a DAL should: *"Only run on the server. Perform authorization checks. Return safe, minimal Data Transfer Objects (DTOs)."* Server Components, Server Actions, and Route Handlers all go through it — **authorization lives here, not in middleware** (see [auth.md](auth.md)).

## Fetching

- **Request Memoization** (stable): identical `fetch` calls within one render pass are deduped automatically — this is dedupe, NOT the persistent Data Cache (see [caching.md](caching.md)).
- A request is dynamic by default (Next 15) and blocks render unless wrapped in `<Suspense>` or cached.
- N+1: eager-load relations in the DAL; don't fetch in a loop across components.

## Sources

- Data security (`server-only`, DTOs, DAL) — https://nextjs.org/docs/app/guides/data-security
- Fetching data / memoization — https://nextjs.org/docs/app/getting-started/fetching-data
