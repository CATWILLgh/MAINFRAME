# Layout — spacing, responsive, hierarchy

## Spacing — one scale

8px rhythm on a 4px sub-unit (the 8pt grid). Tailwind roots spacing at `--spacing: 0.25rem` (4px); use `gap` / `p` / `m` `{2,4,6,8,12,16}` (8–64px) as the rhythm, `1` (4px) only for hairline insets. Never an off-scale value (`p-[7px]`). Proximity communicates grouping before borders do — group with spacing first.

## Responsive — mobile-first

Tailwind breakpoints: `sm` 640 / `md` 768 / `lg` 1024 / `xl` 1280 / `2xl` 1536. Unprefixed = all sizes; add `md:` / `lg:` to scale up. Design the small layout first, then enhance — don't shrink a desktop layout down.

## Width

- App / content shell: cap at `max-w-7xl` (1280px); full-bleed only for backgrounds / hero.
- Long-form text column: `max-w-prose` (~65ch) — measure beats container width for reading.

## Visual hierarchy — levers in order

**Size → spacing → contrast → colour.** Never colour alone (a11y + clarity). Start with more whitespace than feels necessary, then remove (Refactoring UI). One primary action per view; subordinate the rest visually.

## Density by surface

Tighter spacing for data-dense surfaces (tables, dashboards) where glanceability wins; generous spacing for marketing / content where focus and calm win. Keep density consistent within a surface — mixed rhythm reads as broken.

## Sources

- 8pt grid — https://spec.fm/specifics/8-pt-grid
- Tailwind spacing + responsive — https://tailwindcss.com/docs/responsive-design
- Screen-space / density — https://www.nngroup.com/articles/utilize-available-screen-space/
- Whitespace & hierarchy — Refactoring UI (Wathan & Schoger), https://www.refactoringui.com/
