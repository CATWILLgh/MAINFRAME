# Next.js server layer

- Confirm the installed Next.js major, active App or Pages Router, and actual Node or edge runtime before relying on version-sensitive behavior.
- Treat Route Handlers, Server Actions, API Routes, server-side loaders, and other callable server paths as public trust boundaries. Validate their inputs and authenticate and authorize the concrete operation inside the server path.
- Preserve the established router. Do not begin an App Router, Pages Router, rendering, caching, or runtime migration as incidental cleanup.
- Keep data access, secrets, and non-trivial business rules in server-owned modules. Return only client-safe fields across React Server Component and serialization boundaries.
- Treat middleware, proxy redirects, hidden controls, and action identifiers as coarse gates rather than sole authorization for a privileged operation.
- Derive caching, revalidation, and invalidation from the required freshness and mutation contract. Verify the exact APIs and defaults against the installed major.
- Select Node or edge runtime from dependency compatibility and required behavior. Do not move database or Node-native code to edge by assumption.
- Keep small client changes required by a server contract in scope when appropriate; route substantial client-only UI and browser interaction to frontend work.
- When testing asynchronous Server Components or complete server-rendered journeys, verify what the installed tools can faithfully observe and use a browser boundary when lower-level tools cannot represent the behavior.

Current owning references: [Next.js data security](https://nextjs.org/docs/app/guides/data-security), [Next.js authentication](https://nextjs.org/docs/app/guides/authentication), and [Next.js testing](https://nextjs.org/docs/app/guides/testing).
