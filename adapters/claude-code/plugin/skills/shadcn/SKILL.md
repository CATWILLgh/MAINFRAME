---
name: shadcn
user-invocable: false
description: "Project-aware shadcn/ui component reuse and composition guidance for React applications. Detects whether the active package is a shadcn project, inventories its installed UI source and imports, then routes current CLI work, composition, forms, icons, variants, and component selection without multiplying primitives."
when_to_use: "Use when frontend work may touch an existing shadcn component, components.json, UI primitive, form control, overlay, menu, field, variant, icon, or shadcn CLI operation. In a project without components.json, the inspection ends this branch without imposing shadcn. Do not use for general React state or visual direction."
---

# shadcn

This is the component-reuse layer. It does not choose product style or frontend architecture.

## First: cheap local applicability check

Run [`scripts/inspect-ui.mjs`](scripts/inspect-ui.mjs) against the active package root before changing UI primitives:

```bash
node <skill-root>/scripts/inspect-ui.mjs <package-root>
```

The script reads local configuration and source imports only. If it returns `"shadcn": false`, stop this branch and follow the established component system. Do not initialize shadcn unless the assigned task explicitly requires it.

If it returns `true`:

1. Reuse an installed primitive before adding another abstraction.
2. Inspect the primitive source and its existing call sites before changing its contract.
3. Extend canonical variants when the same semantic role repeats; do not create a near-identical second primitive.
4. Read only the relevant reference below.

| Work | Read |
|---|---|
| Inspect, search, view, add, or update through the current CLI | [CLI workflow](references/cli.md) |
| Compose primitives, variants, overlays, icons, and status UI | [Composition](references/composition.md) |
| Build accessible shadcn form markup | [Forms](references/forms.md) |
| Choose the nearest existing primitive | [Component map](references/component-map.md) |

For visual hierarchy, interaction quality, and surface purpose, use the preloaded `frontend-design` route. For state, validation, data, and tests, use `react-frontend-patterns`.

## Stable completion boundary

- No duplicate or near-identical primitive was introduced.
- Existing imports and call sites remain compatible, or their deliberate migration is complete.
- Semantic tokens and the configured icon library are used instead of assumed colors or packages.
- Changed interactive states are keyboard-operable and have an accessible name.
- CLI output and current upstream documentation, not remembered APIs, support version-sensitive markup.

## Sources

- [shadcn/ui documentation](https://ui.shadcn.com/docs)
- [shadcn CLI](https://ui.shadcn.com/docs/cli)
- [shadcn skills](https://ui.shadcn.com/docs/skills)
- [`info` command source](https://github.com/shadcn-ui/ui/blob/main/packages/shadcn/src/commands/info.ts)
