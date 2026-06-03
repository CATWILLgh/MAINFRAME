---
name: frontend-design
user-invocable: false
disable-model-invocation: true
description: "Design / visual-quality layer for the React frontend engineer — the third layer beside `shadcn` (which component / markup) and `react-frontend-patterns` (state / data / architecture). Owns the decisions those two defer: what the semantic colour tokens resolve to (WCAG-safe palettes on shadcn's token names, OKLCH), type scale and pairing, accessibility beyond what Radix enforces (contrast, target size, labels, focus order, custom-widget ARIA), motion (reduced-motion, compositor-only, duration budget), and layout (8pt spacing, responsive, visual hierarchy, density). Authored from primary sources (WCAG 2.2, Material 3, Apple HIG, shadcn theming, Tailwind)."
when_to_use: "A visual-design or UX-quality decision is in flight inside the `react-frontend-engineer` sub-agent — choosing or verifying colour palettes and theme tokens, type scale / font pairing, accessibility (contrast, target size, labels, focus, motion), spacing / responsive layout, or matching a design posture to product type (marketing vs dashboard vs data tool). Triggered via agent frontmatter `skills:` preload, not direct user invocation. Out of scope: building a design-system primitive library, component markup (that's `shadcn`), state / data logic (that's `react-frontend-patterns`)."
---

# frontend-design — design / visual-quality layer

Preloaded into the `react-frontend-engineer` sub-agent. The **third design layer**:

- `shadcn` — which component, how to compose it, markup rules.
- `react-frontend-patterns` — state, validation, data, architecture.
- **`frontend-design` (this)** — the *visual & UX quality* of what gets composed: colour, type, accessibility, motion, layout.

`shadcn` says "use semantic tokens, never raw colour" and defers theming to "the design-system role"; this skill is the doctrine for making those design decisions well. Authored for the Tailwind v4 + shadcn token model; the principles are stack-agnostic.

## Dispatch — read only what the task needs

| Decision | File |
|---|---|
| Colour tokens, palettes, contrast | [color.md](color.md) |
| Type scale, pairing, hierarchy | [typography.md](typography.md) |
| A11y beyond Radix (contrast, targets, labels, focus, ARIA) | [accessibility.md](accessibility.md) |
| Animation, transitions, reduced-motion | [motion.md](motion.md) |
| Spacing, responsive, visual hierarchy, density | [layout.md](layout.md) |

## Always-on design principles

1. **Tokens, never raw values.** Colour and type live in semantic tokens (`bg-primary`, `text-muted-foreground`), never one-off hex or arbitrary sizes.
2. **Accessibility is a floor, not a polish pass.** WCAG 2.2 AA contrast, keyboard, labels, target size are requirements — designed in, not retrofitted.
3. **Hierarchy by size → spacing → contrast → colour.** Never colour alone. One primary action per view.
4. **Motion is purposeful and reduced-motion-safe.** Subtle, compositor-only, switch-off-able.
5. **Consistency over novelty.** One spacing rhythm, one type scale, one icon family, one motion vocabulary per product.
6. **Cite, don't taste.** Non-trivial design rules trace to WCAG / Material 3 / HIG / shadcn — not memory.

## Posture by product type

| Type | Spacing | Type / emphasis | Priority |
|---|---|---|---|
| Marketing / landing | generous whitespace | large display type, one CTA | conversion |
| SaaS / app | moderate density | scannable groups, consistent nav | task completion |
| Data tool / dashboard | tight, tabular | small functional type, alignment | glanceability |

Match the posture first — it sets spacing, density, and type scale. A dashboard built with marketing spacing wastes the screen; a landing page built with dashboard density feels cramped.

## Pre-delivery design check

- Every colour / type value is a semantic token; no raw hex / off-scale size.
- Token pairs and focus ring verified ≥ 4.5:1 / 3:1 (measured, not assumed); light and dark checked separately.
- Keyboard-only pass reaches and operates everything; visible focus; custom controls ≥ 24px.
- Inputs have visible labels; errors are text near the field.
- Motion gated on `prefers-reduced-motion`; only `transform` / `opacity` animated.
- One spacing rhythm, one type scale, posture consistent across the surface.

## Sources

WCAG 2.2 (w3.org/TR/WCAG22) · Material Design 3 (m3.material.io) · Apple HIG (developer.apple.com/design) · shadcn theming (ui.shadcn.com/docs/theming) · Tailwind (tailwindcss.com) · NN/g (nngroup.com) · Refactoring UI. Per-topic citations live in each supporting file.
