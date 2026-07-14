# Distinctiveness — intentional, not generic

The gap between "correct" and "good": why default-everything reads as generic ("AI slop"), and how to make design intentional **without breaking pattern quality**. Core idea: you earn character by *restraint* — limiting choices — not by adding quirks.

## Rules — apply literally (this IS the de-slop)

- **Anchor personality up front, in the token layer.** Before building components, fix ONE value each for: font classification, border-radius, accent hue, shadow presence. No token = no permission to use it. Consistency of these four is the personality.
- **One focal point per screen.** Raise it with size or colour; lower everything else (weight, size, contrast). Never add emphasis elsewhere — if everything is emphasised, nothing is.
- **Restraint by count:** ≤ 3 type sizes in view at once, ≤ 2 radius values, ≤ 1 accent colour per surface, ≤ 2 font families. Scarcity is what makes hierarchy legible.
- **De-emphasise to emphasise** — get contrast by lowering competitors, not raising the hero.
- **Every spacing decision answers a hierarchy question**, never just fills distance (see [layout.md](layout.md)).

## Generic tell → intentional move

Directional, not mandatory — each move is a corrective to consider when the tell appears, not an order to apply blindly.

| Generic tell (reads as default) | Intentional move |
|---|---|
| Default blue/violet primary (Tailwind/shadcn default) | One deliberate accent outside the safe blue band, used sparingly |
| Even spacing everywhere | Generous around the focal block, tight in dense data — rhythm, not uniformity |
| Centred-everything hero | Editorial: flush-left type mass, or a type-only hero, no stock image |
| One weight + one size | Real type contrast — heavy display vs light body (see [type-craft.md](type-craft.md)) |
| `rounded-lg` on everything | One radius for controls, none/small for containers — radius contrast is signal |
| Mixed / emoji icons | One icon family at one weight — or no icons (type-only looks intentional) |
| A card around everything | Cards only for card-shaped content; elevate by whitespace + type, not borders |
| Muted-grey-on-white throughout | One zone that breaks the scheme (ink-dark footer, a saturated header) |

## Distinctiveness is taste — examples, NOT quotas

Do not mechanically inject novelty: forced quirk is just a different generic, and worse on a dashboard. There is no "break the grid once" counter. When a design *earns* it, intentional moves look like — an oversized typographic headline carrying a page with no hero image; one full-bleed asymmetric section against an otherwise tight grid; a single saturated zone among neutrals. Reach for these when they serve the content, not to hit a number.

## Reuse — one component per role

Don't ship a second implementation of a component that already exists — two near-identical buttons are a slop tell and a maintenance cost. The operative rule + mechanism (use the one component with variants; don't reinvent) live in [shadcn](../shadcn/SKILL.md); the home is `shared/ui` ([fsd.md](../react-frontend-patterns/fsd.md)). Here it is a *consistency* concern.

## Sources

- Refactoring UI (Wathan & Schoger) — personality levers, de-emphasise to emphasise — https://www.refactoringui.com/
- NN/g — Visual Hierarchy — https://www.nngroup.com/articles/visual-hierarchy-ux-definition/
- NN/g — 5 Principles of Visual Design — https://www.nngroup.com/articles/principles-visual-design/
- Smashing — design communicates, not decorates — https://www.smashingmagazine.com/2012/03/symptoms-of-epidemic-web-design-trends/

Honest note: "generic / AI-slop tells" have no single authoritative source — the tells are assembled from the hierarchy / restraint literature above.
