# Typography

Preserve the project's typographic contract. For a new direction, choose type from the content, language, platform, brand character, readability, and loading constraints—not from a fixed scale or fashionable pairing.

## Scale

Use a small coherent set of semantic roles such as body, label, heading, and display. A modular scale can help, but no single ratio or base size fits every typeface, language, density, or platform. Reuse tokens and introduce an exception only when the content hierarchy needs it.

## Measure & leading

- Roughly 45–75 characters per line is a useful starting range for long-form text; verify with the actual language, typeface, size, and reading task.
- Choose line height for the typeface and measure. The layout must remain usable when users apply the overrides in WCAG SC 1.4.12; those values are an adaptability test, not mandatory authored spacing.

## Hierarchy — weight first

Express hierarchy with a deliberate combination of content order, weight, size, spacing, contrast, and style. Do not rely on color alone. Use real available weights and verify that secondary text remains readable. Multiple families are acceptable when each has a stable role; unnecessary near-duplicates usually weaken coherence.

## Pairing examples

| Genre | Heading | Body |
|---|---|---|
| Clinical-warm | geometric sans | humanist sans |
| Editorial | high-contrast serif | low-contrast grotesque |
| Technical | sturdy sans or slab serif | sans or monospaced where the content benefits |

These are prompts for exploration, not genre rules.

## Loading

Choose `font-display` and preload behavior from the product's tolerance for invisible text, fallback mismatch, layout shift, and caching. Preload only fonts proven critical to the first render; unnecessary font and weight downloads compete with more important resources.

## Sources

- Material 3 type roles — https://m3.material.io/styles/typography/applying-type
- Line length (measure) — https://baymard.com/blog/line-length-readability
- Line-height SC 1.4.12 — https://www.w3.org/WAI/WCAG22/Understanding/text-spacing.html
- HIG typography (weight hierarchy) — https://developer.apple.com/design/human-interface-guidelines/typography
- font-display: swap — https://developer.chrome.com/docs/lighthouse/performance/font-display
- Tailwind font-family — https://tailwindcss.com/docs/font-family
