# Motion — purposeful, accessible, cheap

Motion conveys cause and continuity; never decoration (Apple HIG). Default to subtle — most UI needs state transitions, not animation.

## Hard rules (specs, not taste)

- **Reduced motion** — wrap every non-essential transition in `@media (prefers-reduced-motion: reduce)` and drop or replace it. With Framer Motion, honour `useReducedMotion()`.
- **Disable-able** — interaction-triggered motion must be switch-off-able unless essential (WCAG SC 2.3.3); auto-playing motion over 5s needs pause / stop / hide (SC 2.2.2).
- **Compositor only** — animate `transform` and `opacity` only. Animating width / height / top / left / `box-shadow` triggers layout / paint and janks (web.dev). For a shadow or size illusion, transform a layer instead.

## Budget (convention — Material 3 token ranges)

| Use | Duration |
|---|---|
| Micro (hover, press, toggle) | 150–200ms |
| Standard (enter / expand, dialog) | 200–300ms |
| Large / complex transition | 300–500ms |

- Duration scales with travel distance / size; > 500ms feels sluggish for UI.
- Exit shorter than enter (~60–70%) — established convention, not a spec.
- Easing: `ease-out` entering, `ease-in` exiting; avoid `linear` for UI.

## What to animate

State changes (hover / expanded / selected), entrance of one or two focal elements, spatial continuity (a dialog scaling from its trigger). Not: everything at once, decorative loops, layout-shifting transforms.

## Sources

- prefers-reduced-motion — https://developer.mozilla.org/en-US/docs/Web/CSS/@media/prefers-reduced-motion
- WCAG SC 2.3.3 / 2.2.2 — https://www.w3.org/WAI/WCAG22/Understanding/animation-from-interactions.html
- Compositor-only properties — https://web.dev/articles/stick-to-compositor-only-properties-and-manage-layer-count
- Material 3 duration / easing — https://m3.material.io/styles/motion/easing-and-duration
- HIG Motion — https://developer.apple.com/design/human-interface-guidelines/motion

Hard specs: reduced-motion, SC 2.3.3 / 2.2.2, compositor-only. The ms ranges are convention (M3 token windows), not a mandate.
