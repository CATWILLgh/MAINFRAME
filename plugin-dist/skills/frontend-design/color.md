# Color — semantic tokens, contrast, palettes

Owns the *values* behind shadcn's semantic tokens. `shadcn` says "use tokens, no raw colour"; this is how to choose what those tokens resolve to. Tailwind v4 stores them as OKLCH CSS variables.

## Token model (shadcn)

Every surface token has a paired `-foreground`: `background/foreground`, `card`, `popover`, `primary`, `secondary`, `muted`, `accent` — plus `destructive`, `border`, `input`, `ring`, `sidebar-*`, `chart-1..5`. Per shadcn theming, the base token is the surface and `-foreground` is the text/icon on it. Components consume `bg-primary text-primary-foreground` — never raw hex.

## Contrast floors (WCAG 2.2 — non-negotiable)

| Pair | AA | AAA |
|---|---|---|
| Body text (`*-foreground` on its `*`) | 4.5:1 | 7:1 |
| Large text (≥ 24px, or ≥ 18.5px bold) | 3:1 | 4.5:1 |
| UI component / focus ring / icon vs adjacent (`border`, `ring`) | 3:1 | — |

Every `<token>` / `<token>-foreground` pair must clear 4.5:1. `border`, `input`, `ring` vs their surface must clear 3:1 (SC 1.4.11) — low-contrast borders are the most common silent failure.

## Method (don't fabricate a palette)

1. Start from shadcn's default token scaffold — broadly-accessible OKLCH neutrals.
2. Substitute the brand hue into `primary` (and optionally `accent`); set `primary-foreground` to near-white or near-black — whichever clears 4.5:1.
3. Re-verify every pair with a contrast checker (WebAIM, or an OKLCH lightness-delta tool) before shipping. Never assert a ratio you did not measure.
4. Author light and dark independently — dark is not an inversion (WCAG + Material 3); verify each theme's pairs separately.

## Archetype directions (starting hues — then verify)

- **Trust / SaaS** — blue `primary`, neutral-slate surfaces, one warm `accent` for the CTA.
- **Growth / commerce** — green `primary`; split success vs urgency across `accent` + `destructive`.
- **Premium** — near-black `primary` on warm-neutral surfaces, restrained gold `accent`.

Pick semantic intent first, hue second. Never more than one `accent`. `destructive` always reads as danger and clears 4.5:1.

## Sources

- WCAG 2.2 SC 1.4.3 / 1.4.11 / 1.4.6 — https://www.w3.org/TR/WCAG22/
- shadcn theming (token pairs, OKLCH) — https://ui.shadcn.com/docs/theming
- Material 3 color roles — https://m3.material.io/styles/color/roles
