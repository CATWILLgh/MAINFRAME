---
name: mainframe-frontend
description: Design, build, review, polish, or debug React web interfaces, including screens, components, dashboards, landing pages, and product demos. Use for visual planning and screenshot reviews as well as implementation.
---

# React frontend design and engineering

Use this as the single design and engineering method for React web interfaces.
Apply it to visual discussions, screenshot reviews, small edits, new screens,
and redesigns. Build new interfaces and demos in React using the project's
existing components and styles. Start with
[Unslop visual direction](references/visual-direction.md) before making or
judging visual decisions. Use the existing product language for a small edit
and develop a clear direction for a new surface or a redesign.

For an authored product illustration or demo, also use
[Stageshow for product demos](references/product-demos.md). It guides the scene
inside the page. Use Unslop for the surrounding page and for real product UI.
Both workflows use local files, existing project assets, and available local
verification tools. Use local CSS, SVG, or a product preview when an asset is
missing. Do not require a subscription, external service, API, CDN, or new tool
installation for these workflows.

Keep the caller's scope. For discussion and review, give concrete observations,
recommendations, or a design proposal without starting implementation. For
authorized visual edits, compare the result in the browser with the relevant
baseline, constraints, or intended hierarchy. Use
[browser verification](references/browser-verification.md) for the observations
that matter. For a behavior-only React fix, go straight to the affected behavior.

## Work with the product

Identify the package and trace the affected user journey, its contracts, and
tests. When ownership is unclear, use [reconnaissance](references/recon.md) or
the [recon script](scripts/recon.mjs). Resolve ownership from imports, providers,
registration, and runtime wiring when multiple systems coexist.

Reuse the installed architecture, design tokens, and canonical component
owners. Extend the existing primitive or use native semantics where suitable.
A design improvement can change grouping, hierarchy, density, navigation, and
interaction within its scope. Preserve unaffected contracts and unrelated work.
Resolve ordinary design decisions from product evidence. Ask only when a
material decision remains with the caller.

Keep the server authoritative for permissions and durable business state.
Cover the reachable interaction and recovery states. For behavior changes,
apply `mainframe-testing` and use the [frontend testing reference](references/testing.md)
to select focused evidence. Exercise changed interactions in the browser.

## Read for the decision at hand

| Changed concern | Read |
| --- | --- |
| Responsive layout, density, overflow, typography, or motion | [Layout, type, and motion](references/layout-type-and-motion.md) |
| Accessibility, keyboard, focus, feedback, or reachable states | [Flows and accessibility](references/flows-and-accessibility.md) |
| Shared controls, component variants, or overlays | [Components and interaction](references/components-and-interaction.md) |
| Package, framework, routing, hydration, or server/client rendering | [Architecture and rendering](references/architecture-and-rendering.md) |
| Remote or browser state, mutations, forms, or validation | [Data, state, and forms](references/data-state-and-forms.md) |
| Editors, tables, charts, files, PWA, realtime, or device APIs | [Complex UI and browser capabilities](references/complex-ui-and-browser-capabilities.md) |
| Client trust, secrets, storage, untrusted HTML, URLs, or scripts | [Browser safety](references/browser-safety.md) |
