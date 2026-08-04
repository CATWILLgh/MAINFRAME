# Type craft — crisp, expressive, professional

The professional layer above [typography.md](typography.md) (scale, measure, hierarchy). These techniques make type read *crisply* and behave under real conditions. Wire in Tailwind v4 via `@theme` / `@layer base`.

## Crisp rendering

- **Font smoothing is a trade-off, not a "crisper" switch.** `-webkit-font-smoothing: antialiased` + `-moz-osx-font-smoothing: grayscale` make text **lighter** (helps light-on-dark), are a **no-op on Windows**, and can reduce perceived weight. Apply deliberately in `@layer base` — don't cargo-cult it as "sharper".
- **Typeface choice drives legibility more than any CSS.** Prefer faces built for screens: tall x-height, open apertures, ink traps (Inter, Geist, or the `system-ui` stack). This is the single biggest crispness lever.

## Fluid, responsive type

- Size steps with `clamp(min, idealVw, max)` — one declaration replaces breakpoint overrides. v4: `@theme { --text-h1: clamp(2rem, 5vw, 3.5rem); }`.

## Data & numerals

- **`tabular-nums`** (`font-variant-numeric: tabular-nums`; Tailwind utility `tabular-nums`) on every price, counter, timer, and table column — equal-width figures stop layout shift as numbers change.
- `slashed-zero` where 0 / O ambiguity matters (codes, IDs, keys).

## Variable fonts

- `font-optical-sizing: auto` — variable fonts with an `opsz` axis thicken small text and refine large text automatically. Declare in `@layer base`.
- Use real weight axes (`font-variation-settings: "wght" 550`); never **faux bold** — `font-weight` on a non-variable face synthesises strokes and muddies rendering.

## Pairing

- **Max 2 families**, almost never 3+ (Butterick).
- Pair faces that are *identifiably different* (geometric sans + humanist serif); two similar sans read as a mistake, not a pair. Deliberate lower contrast can beat high contrast.

## Sources

- MDN — font-smooth (smoothing trade-off) — https://developer.mozilla.org/en-US/docs/Web/CSS/font-smooth
- web.dev — clamp() fluid type — https://web.dev/articles/min-max-clamp
- MDN — font-variant-numeric (tabular-nums) — https://developer.mozilla.org/en-US/docs/Web/CSS/font-variant-numeric
- MDN — font-optical-sizing — https://developer.mozilla.org/en-US/docs/Web/CSS/font-optical-sizing
- Inter — screen legibility — https://rsms.me/inter/
- Butterick — Mixing fonts — https://practicaltypography.com/mixing-fonts.html
