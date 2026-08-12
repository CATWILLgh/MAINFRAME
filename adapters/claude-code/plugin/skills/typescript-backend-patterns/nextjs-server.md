# Next.js server layer

- Confirm the installed Next.js major and active router before using version-sensitive APIs. Do not copy caching, request, or route conventions across majors blindly.
- Route Handlers and Server Actions are public server boundaries: validate input and authorize the specific operation inside the server path.
- Keep non-trivial business behavior outside Route Handlers, Server Actions, and Server Components. Use server-only modules for data and secrets.
- Return only fields safe for the client. Never pass raw rows, secrets, or internal errors through the React Server Component boundary.
- Treat middleware or proxy redirects as coarse request handling, not the sole authorization gate.
- Make caching, revalidation, and invalidation explicit from the changed behavior's freshness contract. Verify exact APIs against the installed major.
- Use Node or edge runtime only when dependencies support it. Most database and Node-native libraries require the Node runtime.
- Small client changes coupled to a server contract may stay with the task; route substantial client-only UI to frontend work.

Sources:
- Next.js App Router — https://nextjs.org/docs/app
- Next.js data security — https://nextjs.org/docs/app/guides/data-security
- Next.js caching — https://nextjs.org/docs/app/guides/caching
