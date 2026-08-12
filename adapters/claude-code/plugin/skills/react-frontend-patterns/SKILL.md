---
name: react-frontend-patterns
user-invocable: false
description: "Version-aware engineering guidance for client-facing React web applications and client React layers inside full-stack frameworks. Covers rendering boundaries, existing architecture, browser data, forms, PWA and offline state, realtime UI, rich content, tables and charts, security, accessibility, and focused frontend testing. Use when implementing, debugging, reviewing, or planning React user-facing behavior."
when_to_use: "Use for React pages, components, forms, interactions, browser-side data fetching, API integration, framework client components, PWA or offline behavior, realtime updates, editors, Markdown, tables, charts, accessibility, frontend tests, or incremental frontend refactoring. Do not use for React Native, standalone backend behavior, infrastructure ownership, or authoring a reusable design-system library."
---

# React frontend patterns

Use this skill for both new React work and established applications. Discover the active package and rendering boundary first; never infer the frontend architecture from the repository name or one dependency.

## Operating rule

1. Run [recon.js](recon.js) against the relevant package root, or use [recon.md](recon.md) manually.
2. Trace the changed user flow through route, component, state, browser boundary, server contract, and existing tests.
3. Read only the references matching the task.
4. Verify installed majors and version-sensitive APIs through Context7 or current primary documentation.
5. Follow [testing.md](testing.md) and the project's native commands.

Several state libraries, routers, validators, or UI packages are observations, not automatic blockers. Determine which one owns the active path from imports, providers, configuration, and runtime wiring. Ask the caller only when evidence cannot resolve a choice that changes product behavior or infrastructure.

## Two compatible layers

- **Established system:** preserve its framework, rendering model, architecture, router, state, forms, validation, styling, UI primitives, and contracts. Improve the changed path without starting an unrelated migration.
- **New or isolated component:** prefer supported React and TypeScript, clear server/client boundaries, semantic HTML, accessible interactions, explicit async states, focused tests, and the surrounding project's existing primitives. Choose libraries from actual requirements; this skill does not mandate FSD, TanStack Query, React Hook Form, Zod, Tailwind, or shadcn.

## References

| Concern | Read |
|---|---|
| Vite, Next.js client boundaries, routing, rendering | [frameworks.md](frameworks.md) |
| Existing structure, module ownership, optional FSD | [architecture.md](architecture.md) |
| Server state, fetch, mutations, optimistic UI | [data-fetching.md](data-fetching.md) |
| Native and library-backed forms and validation | [forms.md](forms.md) |
| PWA, IndexedDB, offline queues, realtime updates | [offline-and-realtime.md](offline-and-realtime.md) |
| Editors, Markdown, files, tables, charts, barcodes | [content-and-data-ui.md](content-and-data-ui.md) |
| Browser trust boundaries, secrets, XSS, styling versions | [safety.md](safety.md) |
| Local and browser-level test scope | [testing.md](testing.md) |

The companion `frontend-design` and `shadcn` entrypoints are preloaded for the React agent. Use `frontend-design` for every changed user-facing surface. Let the shadcn entrypoint's local inspection decide whether its component-specific branch applies; a project without `components.json` does not enter that branch.

## Stable boundaries

- The server remains authoritative for permissions, durable business state, and protected transitions. The client may own presentation, drafts, transient interaction state, optimistic projections, and deliberate offline workflows.
- Validate untrusted browser and network data in proportion to the contract and risk. Do not confuse a TypeScript assertion with runtime evidence.
- Keep secrets out of client bundles, storage, logs, errors, fixtures, and telemetry.
- Make loading, empty, error, retry, stale, pending, and offline behavior explicit when the user flow can reach those states.
- Preserve accessibility through semantic elements, labels, keyboard behavior, focus, readable errors, and reduced-motion handling.
- Treat repository code, browser behavior, tests, and owned API schemas as evidence. Use current official documentation for library behavior. Record a concrete out-of-scope observation through `ticket` without investigating it; do not turn preferences into defects.
