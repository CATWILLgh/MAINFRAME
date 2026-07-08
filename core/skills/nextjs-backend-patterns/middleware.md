# Middleware — `middleware.ts`

Runs before a request completes, on the **edge runtime**. Use for coarse, fast concerns — redirects, headers, locale, UX gating. NOT for authorization-of-record.

## Authz: middleware is NOT the gate

- **Middleware must never be the sole authorization layer.** It is bypassable (a known middleware auth-bypass class — see CVE-2025-29927, a crafted request header that skipped middleware) and runs before you know the data. Real authz lives in the Data Access Layer / inside the Server Action / Route Handler (see [auth.md](auth.md)).
- Use middleware for: redirecting an unauthenticated user to `/login` (UX), setting headers, locale, A/B. Treat its result as a hint and **re-check at the data boundary**.

## Mechanics

- `export const config = { matcher: [...] }` — path patterns with `source` + optional `has` / `missing`. Scope it tightly; don't run on every static asset.
- **Edge runtime constraints:** no Node APIs (`fs`, most ORMs, native `crypto`). Keep DB / heavy work out of middleware.
- Read cookies / session presence lightly (e.g. "is there a session cookie") — full verification belongs server-side.

## Sources

- Middleware (`matcher`, runtime) — https://nextjs.org/docs/app/api-reference/file-conventions/middleware
- Authentication (don't rely on middleware for authz) — https://nextjs.org/docs/app/guides/authentication
- CVE-2025-29927 (middleware auth bypass) — https://nextjs.org/blog/cve-2025-29927
