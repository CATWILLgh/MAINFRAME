---
name: mainframe-frontend
description: Implement, debug, review, test, or visually refine client-facing React web applications and established web frontend layers. Use for pages, components, forms, browser data, accessibility, responsive layouts, UI and UX, shadcn component reuse, PWA or offline behavior, realtime interfaces, rich content, visualizations, and frontend tests. Do not use for React Native, standalone backend behavior, infrastructure ownership, or building a reusable design-system library from scratch.
---

# Frontend engineering

Deliver one coherent user-facing result. Treat React implementation, interaction
quality, visual design, accessibility, component reuse, and focused tests as
branches of the same frontend task rather than independent products.

## Establish the active frontend

1. Run `node scripts/recon.js <package-root>`, or follow
   [manual recon](references/recon.md), before choosing an approach.
2. Trace the changed user journey through its route, component tree, state,
   browser boundary, server contract, visible states, and existing tests.
3. Preserve the installed framework, rendering model, router, architecture,
   state, validation, styling, primitives, and visual language unless their
   migration or redesign is explicitly part of the task.
4. Verify installed versions and version-sensitive APIs with current primary
   documentation or an available authoritative documentation tool.
5. Complete the assigned behavior without TODOs, placeholders, disabled or
   weakened checks, suppressions, or deferred in-scope work.

Several routers, state libraries, validators, or UI systems are observations,
not automatic blockers. Resolve the active owner from imports, providers,
configuration, runtime wiring, and affected files. Escalate only an unresolved
choice that changes product behavior, infrastructure, permission, or the
assigned visual direction.

## Route only the relevant context

### React and browser engineering

| Changed concern | Read |
|---|---|
| Framework, rendering, routing, Server and Client Components | [frameworks](references/frameworks.md) |
| Module ownership and established architecture | [architecture](references/architecture.md) |
| Fetching, mutations, caching, and optimistic UI | [data fetching](references/data-fetching.md) |
| Forms and validation | [forms](references/forms.md) |
| PWA, IndexedDB, offline queues, and realtime | [offline and realtime](references/offline-and-realtime.md) |
| Editors, Markdown, files, tables, charts, and complex interaction | [content and data UI](references/content-and-data-ui.md) |
| Browser trust boundaries, secrets, XSS, and version-sensitive styling | [safety](references/safety.md) |
| Logic, component, browser, and CI test scope | [testing](references/testing.md) |

### User experience and visual design

For every changed user-facing surface, inspect the existing product, nearby
screens, tokens, canonical components, representative content, and reachable
states. Read [design context](references/design-context.md) when intent or the
established language is unclear, then choose the dominant purpose of the
changed region:

| Surface purpose | Read |
|---|---|
| Operate data or complete repeated tasks | [operate](references/mode-operate.md) |
| Understand an offer and decide whether to act | [persuade](references/mode-persuade.md) |
| Read or navigate substantial content | [read](references/mode-read.md) |
| Explore media or an expressive experience | [experience](references/mode-experience.md) |

Read [design workflows](references/design-workflows.md) for a new surface,
redesign, audit, or new visual direction. Always protect the reachable journey
with [flows and feedback](references/flows-and-feedback.md). Read
[accessibility](references/accessibility.md) when structure or interaction
changes and [review and evidence](references/review-and-evidence.md) for an
audit or high-impact visual change.

Load craft references only for the changed concern:

| Concern | Read |
|---|---|
| Product character and non-generic reuse | [distinctiveness](references/distinctiveness.md) |
| Semantic color and measured contrast | [color](references/color.md) |
| Type hierarchy and readable measure | [typography](references/typography.md) |
| Detailed type implementation | [type craft](references/type-craft.md) |
| Responsive spacing, density, and hierarchy | [layout](references/layout.md) |
| Motion and reduced-motion behavior | [motion](references/motion.md) |

### shadcn projects

Run `node scripts/inspect-ui.mjs <package-root>` before changing UI primitives.
If it reports `"shadcn": false`, stop this branch and preserve the established
component system. Never initialize shadcn unless the assigned result requires
it. When it reports `true`, inspect installed source and call sites, then read
only the relevant branch:

| Work | Read |
|---|---|
| Search, inspect, add, or update through the CLI | [shadcn CLI](references/shadcn-cli.md) |
| Compose primitives, variants, overlays, icons, and status UI | [shadcn composition](references/shadcn-composition.md) |
| Select the nearest installed primitive | [shadcn component map](references/shadcn-component-map.md) |
| Build accessible form markup | [shadcn forms](references/shadcn-forms.md) |

## Testing boundary

Use the existing runner and the smallest faithful red-to-green proof for the
changed user-visible behavior or business-facing frontend rule. Inspect the
exact script, lifecycle hooks, runner configuration, and reached setup before
execution. Follow with the nearest relevant fast suite. Use a real browser only
when navigation, layout, focus, motion, browser APIs, or the complete journey
is the changed risk. Automated checks do not replace acceptance of the running
UX and UI.

## Stable boundaries

- Keep the server authoritative for permissions, durable business state, and
  protected transitions; keep substantial server work with the backend owner.
- Keep secrets out of bundles, storage, logs, errors, fixtures, and telemetry.
- Represent every user-reachable loading, empty, pending, error, retry, stale,
  forbidden, success, and offline state that applies to the changed flow.
- Preserve semantic structure, labels, keyboard behavior, focus, contrast,
  reflow, target size, and reduced-motion behavior.
- Reuse project tokens and canonical primitives. Extend a real shared variant
  instead of creating a near-duplicate component or parallel design system.
- Treat repository code, browser behavior, tests, and owned schemas as local
  evidence. Treat aesthetic advice as a heuristic unless product intent,
  measured evidence, or a current primary source makes it a constraint.
- Record a concrete out-of-scope problem through `mainframe-ticket` without
  investigating or fixing it inline. Do not turn taste into a defect.
