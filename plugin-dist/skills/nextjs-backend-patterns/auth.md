# Auth — session + the Data Access Layer

Auth.js (NextAuth v5) is the common choice; the pattern generalizes (Clerk / Lucia).

## Getting the session (server-side)

- `await auth()` works in Server Components, Route Handlers, and Server Actions. Per Auth.js: *"By calling await auth() in a server component, you can check if a session exists."*
- Wrap a Route Handler with `auth((req) => { /* req.auth */ })` to get the session on `req.auth`.

## Authorize at the data boundary (DAL), not middleware

- Centralize checks in a `server-only` Data Access Layer: every privileged read/write calls `await auth()` (or a `cache()`-wrapped `verifySession()`) **before** touching data, and throws on failure. Per Next, the DAL should *"Perform authorization checks. Return safe, minimal Data Transfer Objects."*
- **Re-verify inside every Server Action** — a page-level check does not protect the action.
- Check **authorization** (owns this resource?) not just **authentication** (logged in?) — IDOR.
- `cache()` the verification so repeated calls within one render don't re-hit the session store.
- Middleware is a UX redirect only — never the authz of record (see [middleware.md](middleware.md)).

## Secrets

- Auth secrets (`AUTH_SECRET`, provider client secrets) are server-only env — never `NEXT_PUBLIC_`.

## Sources

- Auth.js v5 session / protecting — https://authjs.dev/getting-started/session-management/protecting
- Next.js authentication + DAL — https://nextjs.org/docs/app/guides/authentication
