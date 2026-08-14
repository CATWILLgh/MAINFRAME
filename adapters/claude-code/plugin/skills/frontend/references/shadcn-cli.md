# CLI workflow

Use the package runner already selected by the project: `npx shadcn@latest`, `pnpm dlx shadcn@latest`, or `bunx --bun shadcn@latest`. Do not install the CLI globally.

1. Run `info --json` once for the work item. Important fields are `project.framework`, `project.rsc`, `project.tailwindVersion`, `project.importAlias`, `config.aliases`, `config.style`, `config.base`, `config.iconLibrary`, `config.resolvedPaths`, and top-level `components`.
2. Do not re-add a component already present in `components` or the local inventory.
3. Search with `search @shadcn -q <need>`. Do not choose a community registry without an explicit project or user decision.
4. Inspect an uninstalled item with `view @shadcn/<name>`.
5. Run `docs <component>` and read the returned current upstream pages before non-trivial markup.
6. Add only the selected item with `add <component>`.
7. Before updating existing source, use `--dry-run` and `--diff`. Never use `--overwrite` without an explicit user command.
8. Review added imports against `config.aliases.ui`; community items can contain assumptions that the CLI does not rewrite.

The current JSON output uses `rsc`, `tailwindConfig`, `tailwindCss`, and `importAlias`; it does not use `isRSC`, `tailwindCssFile`, or `aliasPrefix`. `packageManager` is not part of `info --json`; infer it from the package manifest and lockfile.

If installed CLI output differs, treat the current `collectInfo` implementation linked from the skill entrypoint as authoritative and update the local understanding before continuing.
