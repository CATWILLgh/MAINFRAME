# Typography — scale, measure, hierarchy

Owns type decisions; `shadcn` sets none. Declare fonts in Tailwind v4 via `@theme { --font-sans: …; --font-heading: …; }`.

## Scale

Build a modular scale from a 16px base with a **1.333 (Perfect Fourth)** ratio — 5–6 steps cover label → display. Body stays 16px (never below for primary text). Map every size to a scale step; no arbitrary one-off sizes.

## Measure & leading

- Body line length **50–75 characters**, target ~60–66 (`max-w-prose` ≈ 65ch).
- Body `line-height` ~**1.5** (sound default); the layout must not break when a user overrides line-height to 1.5× (WCAG SC 1.4.12, Text Spacing — an adaptability requirement, not an authoring floor). Headings tighten **1.1–1.3** as size grows.

## Hierarchy — weight first

Express level by **weight → size → colour**, not size alone (Apple HIG):

- Body 400, labels / UI 500–600, headings 600–700.
- Secondary text = `text-muted-foreground`, not a lighter grey hex.
- One or two families maximum — more families collapse hierarchy, not strengthen it.

## Pairing archetypes (by genre — choose, then load)

| Genre | Heading | Body |
|---|---|---|
| Clinical-warm | geometric sans | humanist sans |
| Editorial | high-contrast serif | low-contrast grotesque |
| Technical | slab serif | monospaced |

## Loading

`font-display: swap` to avoid invisible text (FOIT). `<link rel="preload">` only the one or two above-the-fold fonts — preloading every weight regresses load.

## Sources

- Type scale ratios — https://typescale.com/
- Material 3 type roles — https://m3.material.io/styles/typography/applying-type
- Line length (measure) — https://baymard.com/blog/line-length-readability
- Line-height SC 1.4.12 — https://www.w3.org/WAI/WCAG22/Understanding/text-spacing.html
- HIG typography (weight hierarchy) — https://developer.apple.com/design/human-interface-guidelines/typography
- font-display: swap — https://developer.chrome.com/docs/lighthouse/performance/font-display
- Tailwind font-family — https://tailwindcss.com/docs/font-family
