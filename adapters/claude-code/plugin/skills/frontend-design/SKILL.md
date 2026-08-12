---
name: frontend-design
user-invocable: false
description: "Evidence-based UX and visual-quality guidance for user-facing interfaces across application, marketing, reading, and showcase surfaces. Routes frontend work by user purpose while preserving established product language, accessibility, responsive behavior, feedback states, component reuse, and intentional visual character."
when_to_use: "Use whenever implementation or review changes something a person sees or operates: a page, component, form, navigation path, loading or error state, responsive layout, visual hierarchy, typography, color, motion, or accessibility behavior. Do not use for backend-only behavior or component-library mechanics with no user-facing effect."
---

# Frontend design

Protect the user's journey, not only the screenshot. Preserve an established product's visual language unless the assigned task explicitly includes redesign.

## Establish the local contract

Before making a consequential visual or interaction decision, inspect the existing product, its user-facing behavior, design tokens, canonical components, nearby surfaces, and relevant project documentation. Read [context and direction](context-and-direction.md) when the product intent, design language, or scope of a surface is not already clear.

Do not create a parallel design system or restate the whole product in skill context. Reuse the project's source of truth and load only the part needed for the current surface.

## Route the work

Choose the active surface by its primary user purpose, not by the whole product:

| Surface purpose | Read |
|---|---|
| Complete tasks, operate data, administer a system | [Operate](modes/operate.md) |
| Understand an offer and decide whether to act | [Persuade](modes/persuade.md) |
| Read, learn, or navigate substantial content | [Read](modes/read.md) |
| Explore visual work, media, or an expressive experience | [Experience](modes/experience.md) |

Then read the matching branch in [workflows.md](workflows.md): preserve/refine, new surface, new visual direction, redesign, or audit. A page may contain more than one mode; use one dominant mode per region instead of blending all styles everywhere.

## Always required

- Trace the complete changed flow and the states a user can actually reach. Use [flows and feedback](quality/flows-and-feedback.md).
- Reuse the project's design tokens, primitives, patterns, and icon family. Extend a canonical component or variant instead of creating a near-duplicate.
- Treat accessibility as an implementation boundary, not a final polish pass. Keep semantic structure, labels, keyboard behavior, visible focus, contrast, target size, reflow, and motion preferences intact. Use [accessibility](accessibility.md) when interaction changes.
- Create hierarchy through content, size, spacing, and contrast before decoration. Keep density appropriate to the surface mode.
- Verify the affected states at realistic narrow and wide widths. Use browser evidence when layout, focus, motion, or interaction is the risk. Read [review and evidence](quality/review-and-evidence.md) for an audit or high-impact visual change.

## Load only the needed craft reference

| Concern | Read |
|---|---|
| Product character, anti-generic choices, reuse | [Distinctiveness](distinctiveness.md) |
| Semantic colors and measured contrast | [Color](color.md) |
| Type hierarchy and readable measure | [Typography](typography.md) |
| Expressive and precise type implementation | [Type craft](type-craft.md) |
| Motion and reduced-motion behavior | [Motion](motion.md) |
| Spacing, density, hierarchy, responsive layout | [Layout](layout.md) |

Do not load every reference by default. Treat aesthetic guidance as a heuristic unless the project brief makes it a requirement. A non-trivial constraint must be supported by current primary documentation, measured interface evidence, or an established project contract rather than taste alone.

## Sources

- [WCAG 2.2](https://www.w3.org/TR/WCAG22/)
- [Apple Human Interface Guidelines](https://developer.apple.com/design/human-interface-guidelines/)
- [Material Design 3](https://m3.material.io/)
