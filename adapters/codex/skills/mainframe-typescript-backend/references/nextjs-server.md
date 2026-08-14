# Next.js server layer

- Confirm the installed Next.js major, active router, and runtime before using
  version-sensitive APIs.
- Treat Route Handlers, Server Actions, Pages API Routes, and server-side data
  loading as public server boundaries: validate input and authorize the exact
  operation inside the server path.
- Preserve an established Pages Router or App Router architecture. Do not begin
  a router migration as incidental cleanup.
- Keep non-trivial business behavior outside Route Handlers, Server Actions,
  and Server Components. Keep data access and secrets in server-only modules.
- Return only client-safe fields across the React Server Component boundary.
- Treat middleware or proxy redirects as coarse request handling, not the sole
  authorization gate.
- Make caching, revalidation, and invalidation explicit from the required
  freshness behavior and verify exact APIs against the installed major.
- Select Node or edge runtime only when dependencies support it. Database and
  Node-native libraries commonly require Node.
- Keep small client changes coupled to a server contract in scope; route
  substantial client-only UI to frontend work.

Sources: [Next.js App Router](https://nextjs.org/docs/app),
[Pages Router](https://nextjs.org/docs/pages),
[data security](https://nextjs.org/docs/app/guides/data-security), and
[caching](https://nextjs.org/docs/app/guides/caching).
