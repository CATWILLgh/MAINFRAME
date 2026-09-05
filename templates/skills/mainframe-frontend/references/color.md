# Color

Use the project's semantic color contract. When the project uses shadcn, its paired tokens provide the vocabulary; this file guides the values and verification behind them.

## Token model (shadcn)

Every shadcn surface token has a paired `-foreground`: `background/foreground`, `card`, `popover`, `primary`, `secondary`, `muted`, and `accent`, alongside functional roles such as `destructive`, `border`, `input`, `ring`, sidebar, and chart tokens. Components should consume semantic roles rather than duplicate literal colors. Literal values remain valid inside the token definition and in bounded data-visualization, illustration, or third-party contexts where no semantic role fits.

## Contrast floors

| Pair | AA | AAA |
|---|---|---|
| Body text (`*-foreground` on its `*`) | 4.5:1 | 7:1 |
| Large text (≥ 24px, or ≥ 18.5px bold) | 3:1 | 4.5:1 |
| Visual information required to identify a UI component or state | 3:1 | — |

Measure the pairs that are actually rendered. A token is not required to clear 4.5:1 against every other token; its use determines the criterion. Decorative boundaries need not meet SC 1.4.11, while a boundary or state indicator required to identify a control does.

## Method (don't fabricate a palette)

1. Preserve an established brand and token system unless the task includes changing it.
2. For a new direction, choose roles from product character and communication needs rather than an industry cliché or an untouched scaffold.
3. Measure rendered contrast with a tool that computes the WCAG ratio; an OKLCH lightness difference alone is not a WCAG contrast measurement.
4. Author and verify light, dark, high-contrast, and other supported themes independently rather than assuming an inversion preserves behavior.

## Choose a palette with a point of view (not a cliché)

- **Pick color by product meaning, not automatic industry mapping.** Familiar color can still be correct when trust, convention, or brand recognition supports it.
- **Use temperature, saturation, and lightness intentionally.** Their relationships shape mood, hierarchy, and legibility; verify them in the complete palette rather than judging an isolated swatch.
- **Use a limited role set deliberately.** More than one accent can be appropriate for charts, statuses, brands, or multi-product systems when each role remains understandable.
- Reserve destructive color for destructive meaning. Verify the rendered text, icon, and control state according to their actual contrast requirement.

Whatever you choose, run every pair through the contrast floors above — personality never overrides legibility.

## Sources

- WCAG 2.2 SC 1.4.3 / 1.4.11 / 1.4.6 — https://www.w3.org/TR/WCAG22/
- shadcn theming (token pairs, OKLCH) — https://ui.shadcn.com/docs/theming
- Material 3 color roles — https://m3.material.io/styles/color/roles
