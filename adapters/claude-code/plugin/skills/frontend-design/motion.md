# Motion

Use motion to communicate cause, continuity, hierarchy, or intentional expression. Decorative motion is acceptable on an expressive surface when it supports the direction, remains controllable, and does not obscure content or operation.

## Accessibility and control

- Honor `prefers-reduced-motion` by removing or replacing non-essential movement while preserving state and meaning.
- Provide pause, stop, or hide controls for qualifying moving, blinking, scrolling, or auto-updating content under WCAG SC 2.2.2.
- Treat WCAG SC 2.3.3 Animation from Interactions as an enhanced AAA safeguard unless the project adopts it as a stronger requirement; do not mislabel it as part of the AA floor.
- Avoid flashes that violate WCAG seizure thresholds.

## Performance

Prefer `transform` and `opacity` for frequent or large animations because browsers can often composite them efficiently. Other properties are not categorically forbidden: measure them on representative devices and bound their affected area. Avoid layout thrashing, unnecessary layers, and long animation chains.

## Timing and vocabulary

Reuse the project's motion tokens. Choose duration and easing from distance, scale, complexity, frequency, and surface mode. Short responses commonly feel appropriate for direct manipulation, while larger spatial transitions can take longer. Material or platform ranges are starting points, not universal acceptance criteria. Verify perceived responsiveness rather than enforcing a fixed millisecond table.

## What to animate

State changes, feedback, spatial continuity, and selected expressive moments are useful candidates. Avoid motion everywhere at once, movement that hides causality, scroll hijacking, and effects whose performance or reduced-motion behavior is unknown.

## Sources

- prefers-reduced-motion — https://developer.mozilla.org/en-US/docs/Web/CSS/@media/prefers-reduced-motion
- WCAG SC 2.3.3 / 2.2.2 — https://www.w3.org/WAI/WCAG22/Understanding/animation-from-interactions.html
- Animation performance — https://web.dev/articles/animations-and-performance
- Material 3 duration / easing — https://m3.material.io/styles/motion/easing-and-duration
- HIG Motion — https://developer.apple.com/design/human-interface-guidelines/motion
