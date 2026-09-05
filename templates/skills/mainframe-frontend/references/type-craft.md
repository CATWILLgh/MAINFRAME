# Type craft

The implementation layer above [typography.md](typography.md) (scale, measure, hierarchy). Apply these techniques through the project's existing CSS and token system; Tailwind-specific syntax is relevant only when that project already uses Tailwind.

## Crisp rendering

- **Font smoothing is a trade-off, not a "crisper" switch.** `-webkit-font-smoothing: antialiased` and `-moz-osx-font-smoothing: grayscale` can make text appear lighter on supported platforms and can reduce perceived weight. Apply deliberately through the project's base styles rather than cargo-culting them as a universal sharpening control.
- **Typeface choice drives legibility more than smoothing CSS.** Inspect x-height, apertures, character differentiation, language coverage, available weights, and rendering on target platforms. Do not force a named family when the project already has a suitable one.

## Fluid, responsive type

- `clamp()` can express a bounded fluid step when type should scale continuously. Use fixed role tokens when density and predictability matter more; fluid type is not mandatory.

## Data & numerals

- **`tabular-nums`** (`font-variant-numeric: tabular-nums`) helps changing counters and aligned numeric columns. Proportional numerals can remain preferable in prose, marketing prices, or isolated values.
- `slashed-zero` where 0 / O ambiguity matters (codes, IDs, keys).

## Variable fonts

- `font-optical-sizing: auto` — variable fonts with an `opsz` axis thicken small text and refine large text automatically. Declare in `@layer base`.
- Prefer standard `font-weight` so the browser maps the requested weight through the font's supported axis. Use `font-variation-settings` for axes that standard properties do not expose. Avoid synthesized bold or italic when typographic fidelity matters and the real face is available.

## Pairing

- Give every family a stable semantic role. Additional families increase loading and consistency cost, but there is no universal numeric limit.
- Pairings need enough intentional relationship or contrast to read as one system. Similar faces can work when subtle continuity is the goal; verify with representative content rather than a pairing formula.

## Sources

- MDN — font-smooth (smoothing trade-off) — https://developer.mozilla.org/en-US/docs/Web/CSS/font-smooth
- web.dev — clamp() fluid type — https://web.dev/articles/min-max-clamp
- MDN — font-variant-numeric (tabular-nums) — https://developer.mozilla.org/en-US/docs/Web/CSS/font-variant-numeric
- MDN — font-optical-sizing — https://developer.mozilla.org/en-US/docs/Web/CSS/font-optical-sizing
- Butterick — Mixing fonts — https://practicaltypography.com/mixing-fonts.html
