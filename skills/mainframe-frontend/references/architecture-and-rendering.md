# Architecture and rendering

Work from the package and route that own the changed journey, not automatically from the repository root. Trace public module boundaries, providers, layouts, router registration, rendering entrypoints, data ownership, and generated files before moving code.

Preserve the installed framework and router. Vite, Next.js App Router, Next.js Pages Router, Remix, Astro, and React Router have different ownership and rendering contracts; verify the installed versions and current primary documentation.

In server-rendered or React Server Component systems, identify the server/client boundary before editing. Add a client boundary only where state, effects, events, custom hooks, or browser APIs require it. Never pull secrets, database code, Node-only modules, or unnecessary server trees into the client bundle; cross the boundary with minimal serializable data.

Keep hydration deterministic. Storage, media queries, locale, clocks, random values, and browser-only APIs require an explicit client strategy rather than mismatched server and client markup.

Keep code close to the user capability that owns it. Share a module only when multiple real consumers need the same contract. Preserve established public imports and architecture; a local correction is not authority for a broad reorganization.
