---
name: shadcn
user-invocable: false
disable-model-invocation: true
description: "shadcn/ui composition layer — when, what, and how to compose shadcn components in a Vite + React project. Provides the CLI workflow (search → view → add → docs), the corrected `info --json` schema fields needed for project-aware decisions (framework, Tailwind version, aliases, base, RSC flag), critical composition rules (Field / InputGroup / asChild / variants / icon discipline), and the strict no-MCP, npx-only invocation model. Defers per-component detail to live `npx shadcn@latest docs <component>` so it never goes stale."
when_to_use: "A UI composition task is in flight inside the `react-frontend-engineer` sub-agent — adding a new component, fixing existing markup, applying a variant, composing a form with Field / FieldGroup, choosing between Dialog / Sheet / Drawer, debugging a styling violation against shadcn rules. Triggered via agent frontmatter `skills:` preload, not by direct user invocation. Out of scope: building a design system from scratch, authoring registries, MCP server setup."
allowed-tools: Bash(npx shadcn@latest *), Bash(pnpm dlx shadcn@latest *), Bash(bunx --bun shadcn@latest *)
---

# shadcn — composition layer

Preloaded into the `react-frontend-engineer` sub-agent. Companion to `react-frontend-patterns` — that skill owns logic (state, validation, data, architecture); **this** skill owns UI composition (which component, how to compose, markup-level rules).

The shadcn primitives are added to the user's project **as source code** via the CLI. The CLI is not installed globally; it is invoked via the project's package runner — `npx shadcn@latest …` / `pnpm dlx shadcn@latest …` / `bunx --bun shadcn@latest …`. Pick the one matching the project's `packageManager` field. Do not install `-g`.

## Workflow

1. **Get project context.** Run `npx shadcn@latest info --json` (substitute the package runner). Cache the parsed JSON for the rest of this work item. The schema is documented below — the fields you care about most are `project.framework`, `project.rsc`, `project.tailwindVersion`, `project.importAlias`, `config.aliases`, `config.style`, `config.base`, `config.iconLibrary`, `config.resolvedPaths`, and top-level `components`.
2. **Check what's already installed** — `components` (top-level array) lists installed component names. Don't re-add. Don't import components not in this list.
3. **Search registries** when looking for something — `npx shadcn@latest search @shadcn -q "sidebar"`. Community registries (`@tailark`, `@magicui`, etc.) require explicit registry name from the user — never default a registry on their behalf.
4. **View before adding** — `npx shadcn@latest view @shadcn/<name>` for items you haven't installed.
5. **Get docs and examples live** — `npx shadcn@latest docs <component>` returns the URLs of the upstream docs and examples. Fetch those URLs to get current API and usage patterns. **Always do this before authoring non-trivial markup with a component** — it ensures you're against the current API, not a memorised version.
6. **Add** — `npx shadcn@latest add <component>`. For updates: `--dry-run` and `--diff` first. Never `--overwrite` without explicit user approval.
7. **Review what the CLI added.** For community registries — check imports inside non-UI files for hardcoded `@/components/ui/...` paths that don't match `config.aliases.ui`. The CLI rewrites paths for its own UI files, third-party registry items often do not.

## `info --json` schema — verified against shadcn 4.x source

Authoritative source: [`packages/shadcn/src/commands/info.ts`](https://github.com/shadcn-ui/ui/blob/main/packages/shadcn/src/commands/info.ts) (`collectInfo` function). The published `4.8.x` line matches this shape:

```ts
{
  project: {                              // null if not a shadcn project
    framework: string                      // e.g. "Vite + React", "Next.js App Router"
    frameworkName: string                  // canonical key, e.g. "vite", "next-app"
    frameworkVersion: string | null
    srcDirectory: boolean
    rsc: boolean                           // NOT "isRSC". React Server Components in use?
    typescript: boolean
    tailwindVersion: string | null         // "v3" or "v4"
    tailwindConfig: string | null          // path. NOT "tailwindConfigFile"
    tailwindCss: string | null             // path. NOT "tailwindCssFile"
    importAlias: string | null             // NOT "aliasPrefix"
  } | null,
  config: {                                // contents of components.json
    style: string                          // e.g. "default", "nova", "vega"
    base: string                           // "radix" or "base"
    rsc: boolean
    typescript: boolean
    iconLibrary: string | null             // e.g. "lucide", "tabler", "hugeicons"
    rtl: boolean
    aliases: {
      components: string                   // "@/components"
      utils: string                        // "@/lib/utils"
      ui: string | null                    // "@/components/ui"
      lib: string | null
      hooks: string | null
    }
    resolvedPaths: {                       // absolute filesystem paths
      cwd, tailwindConfig, tailwindCss, utils, components, lib, hooks, ui
    }
    registries: Record<string, string>
  } | null,
  preset: object | null,
  components: string[],                    // installed component names
  links: { docs, components, ui, examples, schema }
}
```

The Anthropic-authored shadcn skill that ships in `inbox/` references `isRSC`, `tailwindCssFile`, `aliasPrefix`, and `packageManager` — those names are **wrong** at the JSON output layer. They are internal types inside the CLI source, not what `--json` emits. Use the names above. `packageManager` is NOT in this output — detect it from the lockfile (handled by `react-frontend-patterns/recon.js`).

When the CLI version diverges from this skill: re-read `collectInfo` at the source URL above and update this section. The CLI runs every shadcn project's skill on every interaction, per upstream design — schema drift is a real risk.

## Critical composition rules — always enforced

### Styling / Tailwind

- `className` controls **layout** (gap, position, size), never component **colors or typography** — those live in variants and semantic tokens.
- **No `space-x-*` / `space-y-*`** — use `flex` (or `flex flex-col`) with `gap-*`.
- **Use `size-N`** when width and height are equal, not `w-N h-N`.
- **Use `truncate`** shorthand, not `overflow-hidden text-ellipsis whitespace-nowrap`.
- **No manual `dark:` color overrides.** Use semantic tokens — `bg-background`, `text-muted-foreground`, `border-input`.
- **Use `cn()`** for conditional classes, not template-literal ternaries.
- **No manual `z-index`** on overlay components (Dialog, Sheet, Popover) — they handle their own stacking.

### Forms

- Layout via `<FieldGroup>` + `<Field>` — never raw `<div>` with `space-y-*` or `grid gap-*`.
- `<InputGroup>` uses `<InputGroupInput>` / `<InputGroupTextarea>` — not raw `<Input>` / `<Textarea>` inside.
- Buttons inside inputs use `<InputGroup>` + `<InputGroupAddon>`.
- Option sets of 2–7 choices use `<ToggleGroup>` — never a `Button` loop with manual active state.
- Grouped checkboxes / radios use `<FieldSet>` + `<FieldLegend>`, not a `<div>` with a heading.
- Field validation: `data-invalid` on `<Field>`, `aria-invalid` on the control. For disabled: `data-disabled` on `<Field>`, `disabled` on the control.

(Form **state** and **schema** live in the companion `react-frontend-patterns/forms.md` — this skill stops at markup.)

### Composition / structure

- Items inside their Group — `<SelectItem>` → `<SelectGroup>`. `<DropdownMenuItem>` → `<DropdownMenuGroup>`. `<CommandItem>` → `<CommandGroup>`.
- Custom triggers: `asChild` (Radix `base`) or `render` (non-Radix `base`). Check `config.base` from `info --json`.
- Overlays — `<Dialog>`, `<Sheet>`, `<Drawer>` — always need a Title (`<DialogTitle>`, etc.). Use `className="sr-only"` if visually hidden — required for accessibility.
- Full `<Card>` composition: `<CardHeader>` / `<CardTitle>` / `<CardDescription>` / `<CardContent>` / `<CardFooter>`. Don't dump everything into `<CardContent>`.
- `<Button>` has no `isPending` / `isLoading` prop — compose with `<Spinner>` + `data-icon` + `disabled`.
- `<TabsTrigger>` must live inside `<TabsList>`, not directly in `<Tabs>`.
- `<Avatar>` always has `<AvatarFallback>` for image-failure case.

### Use components instead of custom markup

- Callouts → `<Alert>`. Empty states → `<Empty>`. Toast → `toast()` from `sonner`. Separators → `<Separator>`, not `<hr>` / `<div className="border-t">`. Loading placeholders → `<Skeleton>`, not custom `animate-pulse` divs. Status pills → `<Badge>`, not custom styled spans.

### Icons

- Icons inside `<Button>` use `data-icon="inline-start"` or `data-icon="inline-end"`.
- **No sizing classes on icons** inside shadcn components — the component handles icon sizing via CSS. No `size-4`, no `w-4 h-4`.
- Pass icons **as components**, not as string keys — `icon={CheckIcon}`, not a string lookup.
- The icon library is `config.iconLibrary` — `lucide` → `lucide-react`, `tabler` → `@tabler/icons-react`. Never assume `lucide-react`; check `info --json`.

### Status colors

`<Badge variant="...">` and semantic tokens, never raw color classes. `<Badge variant="secondary">+20.1%</Badge>` — correct. `<span className="text-emerald-600">+20.1%</span>` — wrong.

## Component-selection cheat sheet

| Need | Use |
|---|---|
| Action / button | `Button` with the appropriate `variant` |
| Form inputs | `Input` / `Select` / `Combobox` / `Switch` / `Checkbox` / `RadioGroup` / `Textarea` / `InputOTP` / `Slider` |
| 2–5 mutually-exclusive options | `ToggleGroup` + `ToggleGroupItem` |
| Data display | `Table` / `Card` / `Badge` / `Avatar` |
| Navigation | `Sidebar` / `NavigationMenu` / `Breadcrumb` / `Tabs` / `Pagination` |
| Overlays | `Dialog` (modal) / `Sheet` (side panel) / `Drawer` (bottom sheet) / `AlertDialog` (confirmation) |
| Feedback | `sonner` (toast) / `Alert` / `Progress` / `Skeleton` / `Spinner` |
| Command palette | `Command` inside `Dialog` |
| Charts | `Chart` (wraps Recharts) |
| Layout primitives | `Card` / `Separator` / `Resizable` / `ScrollArea` / `Accordion` / `Collapsible` |
| Empty state | `Empty` |
| Menus | `DropdownMenu` / `ContextMenu` / `Menubar` |
| Hover / tooltip / info | `Tooltip` / `HoverCard` / `Popover` |

## Anti-patterns the agent must catch

- A new styled `<div>` that re-implements `<Alert>` / `<Badge>` / `<Empty>` / `<Skeleton>` — replace.
- `space-y-*` for vertical stacks — replace with `flex flex-col gap-*`.
- `w-N h-N` where `N` is equal — replace with `size-N`.
- Raw color (`text-blue-500`, `bg-red-100`) instead of semantic token — replace.
- `<DialogTitle>` missing on a `<Dialog>` — accessibility violation, add (`sr-only` if visually unwanted).
- `<Avatar>` without `<AvatarFallback>` — required for image-fail UX.
- `forwardRef`-wrapped primitives copied from old shadcn snippets when the project is on Tailwind v4 — primitives now use `React.ComponentProps<T>` + `data-slot`.

## Out of scope

- Authoring a registry (use the upstream guide if asked).
- Building / theming a design system from scratch — that's the design-system role.
- Configuring the shadcn MCP server — the hub chose **CLI-only**; the MCP is not used, no setup, no client config.
- React Native / Expo UI — different toolchain.

## Sources

- shadcn/ui — https://ui.shadcn.com
- `info` command source — https://github.com/shadcn-ui/ui/blob/main/packages/shadcn/src/commands/info.ts
- shadcn CLI — https://ui.shadcn.com/docs/cli
- shadcn skills design — https://ui.shadcn.com/docs/skills
- Tailwind v4 migration — https://ui.shadcn.com/docs/tailwind-v4
