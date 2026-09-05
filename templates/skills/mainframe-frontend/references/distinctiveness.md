# Distinctiveness

Make the interface specific to its product without sacrificing clarity, reuse, or accessibility. Distinctiveness comes from a coherent relationship among content, typography, layout, color, imagery, and interaction—not from a quota of unusual decisions.

## Establish character

- Derive character from the subject, audience, content, user job, and existing product language.
- For a new direction, define a small coherent set of durable choices in the token and primitive layers. Do not fork components to manufacture variety.
- Establish a dominant reading or action path. A complex operating surface may legitimately contain several priorities; hierarchy should clarify their order rather than pretend only one exists.
- Use de-emphasis as well as emphasis. More size, saturation, weight, shadow, and motion are not the only ways to create hierarchy.
- Apply restraint contextually. Count-based limits can reveal inconsistency during review, but they are not universal acceptance criteria.

## Generic tell → intentional move

Directional, not mandatory — each move is a corrective to consider when the tell appears, not an order to apply blindly.

| Generic tell (reads as default) | Intentional move |
|---|---|
| Untouched scaffold with no project rationale | Deliberate token choices tied to product or brand intent |
| Even spacing everywhere | Generous around the focal block, tight in dense data — rhythm, not uniformity |
| Centred-everything hero | Editorial: flush-left type mass, or a type-only hero, no stock image |
| One weight + one size | Real type contrast — heavy display vs light body (see [type-craft.md](type-craft.md)) |
| `rounded-lg` on everything | One radius for controls, none/small for containers — radius contrast is signal |
| Mixed / emoji icons | One icon family at one weight — or no icons (type-only looks intentional) |
| A card around everything | Cards only for card-shaped content; elevate by whitespace + type, not borders |
| Muted-grey-on-white throughout | One zone that breaks the scheme (ink-dark footer, a saturated header) |

## Use judgment, not a style blacklist

Do not mechanically inject novelty or ban a recognizable pattern merely because it is common. Cards, centered composition, blue, gradients, serif italics, eyebrows, large type, and decorative motion can be right or wrong depending on meaning and execution. Require a reason for the choice and judge its effect on the actual user journey.

Intentional moves may include an oversized typographic headline, an asymmetric section, a dense operational layout, a quiet editorial measure, or a saturated zone among neutrals. Use them when they support the content and mode, not to satisfy a checklist.

## Reuse — one component per role

Don't ship a second implementation of a component that already exists — two
near-identical buttons are a slop tell and a maintenance cost. The operative
reuse and variant rules live in the [shadcn composition](shadcn-composition.md)
route; placement follows the project's existing [architecture](architecture.md).
Here it is a consistency concern.

## Sources

- Refactoring UI (Wathan & Schoger) — personality levers, de-emphasise to emphasise — https://www.refactoringui.com/
- NN/g — Visual Hierarchy — https://www.nngroup.com/articles/visual-hierarchy-ux-definition/
- NN/g — 5 Principles of Visual Design — https://www.nngroup.com/articles/principles-visual-design/
- Smashing — design communicates, not decorates — https://www.smashingmagazine.com/2012/03/symptoms-of-epidemic-web-design-trends/

The examples above are design heuristics, not standards violations. Confirm them against the project brief and rendered evidence.
