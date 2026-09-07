---
name: mainframe-frontend
description: Develop, debug, review, test, or visually refine client-facing React web applications and established React layers. Use proactively for user journeys, components, browser state, accessibility, responsive behavior, UI and UX, and focused frontend tests. Do not use for React Native, substantial backend work, infrastructure ownership, or standalone design-system development.
---

# Frontend engineering

Apply this method whenever the active work matches the description, whether you are the primary implementer, a delegated engineer, or a reviewer. Follow the scope and authority supplied through the current execution path; this skill does not expand either.

Deliver one coherent user-facing result. Treat implementation, interaction quality, visual language, accessibility, component reuse, and verification as parts of the same frontend task.

## Establish the active surface

Identify the nearest package that owns the affected route or surface. Run the bounded [recon script](scripts/recon.mjs) against that explicit package root, or follow [manual reconnaissance](references/recon.md). Treat its report as routing evidence, not runtime proof.

Trace the changed journey through its route, rendering boundary, component tree, state, browser APIs, server contract, reachable states, and existing tests. Inspect the running product, nearby surfaces, tokens, primitives, representative content, and effective project instructions before choosing an implementation or visual direction.

Several routers, state libraries, validators, or component systems may legitimately coexist. Resolve ownership from imports, providers, configuration, registration, runtime wiring, and affected files. Surface a decision only when evidence cannot resolve a product, business, data, infrastructure, permission, or assigned visual-direction choice with material consequences.

## Preserve and extend one product language

Preserve the installed framework, rendering model, router, architecture, state, validation, styling, primitives, accessibility conventions, and visual language unless changing them is part of the assigned result. Do not introduce a competing library or design system for convenience.

Start from user purpose and behavior, not a component library. Search existing primitives, variants, and call sites before creating a component. When the same semantic role already exists, extend its canonical owner instead of creating a near-duplicate that differs only in pixels, styling, or props. Do not abstract without a real shared contract; native HTML is preferable when it already supplies the required semantics.

Keep tokens, typography, spacing, geometry, density, iconography, motion, states, and action hierarchy coherent across the changed surface. Optimize first for comprehension, task completion, recoverable errors, and predictable interaction. Distinctive graphics support product meaning; they do not excuse inconvenient or inaccessible behavior.

## Load only the relevant detail

| Changed concern | Read |
|---|---|
| Package, framework, routing, Server or Client Components, hydration, or module ownership | [architecture and rendering](references/architecture-and-rendering.md) |
| Remote data, browser state, mutations, optimistic UI, forms, or validation | [data, state, and forms](references/data-state-and-forms.md) |
| Reachable states, feedback, semantics, keyboard, focus, reflow, or contrast | [flows and accessibility](references/flows-and-accessibility.md) |
| Established visual system, new direction, typography, hierarchy, or graphic character | [visual direction](references/visual-direction.md) |
| Responsive composition, density, overflow, alignment, type craft, or animation | [layout, type, and motion](references/layout-type-and-motion.md) |
| Native controls, shared primitives, variants, component libraries, overlays, or interaction states | [components and interaction](references/components-and-interaction.md) |
| Editors, Markdown, tables, charts, files, PWA, offline state, realtime, or device APIs | [complex UI and browser capabilities](references/complex-ui-and-browser-capabilities.md) |
| Client trust boundaries, secrets, storage, untrusted HTML, URLs, or third-party scripts | [browser safety](references/browser-safety.md) |
| Choosing the smallest faithful automated evidence | [testing](references/testing.md) |
| Visually and interactively accepting the rendered result | [browser verification](references/browser-verification.md) |

## Complete and verify the journey

Implement every affected location inside the assigned boundary. Represent the loading, empty, pending, error, retry, stale, forbidden, offline, success, and recovery states that are actually reachable. Keep the server authoritative for permissions, durable business state, and protected transitions; keep substantial server work with its backend owner.

Use the project's native commands and the smallest faithful failing evidence when practical. Then run the focused proof and nearest relevant fast checks. For any visual or interactive change, also exercise the actual rendered result through the browser-verification route; a build, unit test, DOM snapshot, or screenshot alone is not user-level proof.

Do not replace completion with TODOs, placeholders, weakened checks, suppressions, invented product state, duplicate components, or an unrecorded follow-up. Keep secrets out of bundles, storage, logs, errors, fixtures, telemetry, and browser traces. Preserve unrelated work and report every material verification gap.
