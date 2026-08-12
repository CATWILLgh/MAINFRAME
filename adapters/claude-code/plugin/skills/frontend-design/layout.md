# Layout

## Spacing and grouping

Reuse the project's spacing scale. A 4px sub-unit or 8px rhythm is a common implementation choice, not a universal law. Prefer scale values because they preserve rhythm and maintainability; use an exception when optical alignment, a third-party constraint, or a real layout requirement justifies it. Proximity communicates grouping before borders do.

## Responsive behavior

Start with the narrowest meaningful layout and add capacity as content needs it. Reuse project breakpoints instead of assuming framework defaults are product requirements. Choose breakpoints where content or interaction stops working, and use container queries when component space matters more than viewport width.

## Width

- Set shell width from the task, density, and target displays; do not impose a universal 1280px cap.
- Keep long-form measure readable. Roughly 45–75 characters per line is a useful starting range, then verify with the actual typeface, language, size, and content.
- Preserve usable reflow and avoid horizontal scrolling at narrow widths except where two-dimensional content genuinely requires it.

## Visual hierarchy — levers in order

Use content order, size, spacing, weight, contrast, alignment, and color together. Never rely on color alone. A surface may have more than one important action; make their priority and relationship understandable instead of enforcing a numerical limit.

## Density by surface

Tighter spacing can support data-dense surfaces where comparison and repeated work matter; more generous spacing can support persuasion or reading. Density may change intentionally between regions, but repeated structures should remain predictable.

## Sources

- Tailwind spacing + responsive — https://tailwindcss.com/docs/responsive-design
- Screen-space / density — https://www.nngroup.com/articles/utilize-available-screen-space/
- WCAG reflow — https://www.w3.org/WAI/WCAG22/Understanding/reflow.html
