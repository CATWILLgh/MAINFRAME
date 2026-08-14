# Framework and rendering boundaries

- Preserve the installed framework and router. Vite, Next.js App Router, Next.js Pages Router, Remix, Astro, and React Router have different ownership and rendering contracts.
- In Vite applications, browser code owns rendering and routing; confirm base paths, environment exposure, code splitting, and dev/build behavior from the installed major.
- In Next.js, identify Server and Client Components before editing. Add `'use client'` only at the smallest boundary requiring browser state, effects, events, or browser APIs; do not pull an entire server tree into the client bundle.
- Do not import server-only modules, secrets, database code, or Node-only libraries into client code. Pass minimal serializable data across the server/client boundary.
- Use the active router's current navigation, params, search params, error, loading, and route conventions. React Router v6 and v7, and Next.js majors, are not interchangeable.
- Keep hydration deterministic. Browser-only values, storage, media queries, and timestamps require an explicit client strategy rather than server/client markup disagreement.
- For substantial server behavior in a Next.js application, coordinate with the TypeScript backend owner; small contract-coupled changes may remain in one task.

Sources:
- React client APIs — https://react.dev/reference/react/client
- Vite guide — https://vite.dev/guide/
- Next.js Server and Client Components — https://nextjs.org/docs/app/getting-started/server-and-client-components
- React Router — https://reactrouter.com/
