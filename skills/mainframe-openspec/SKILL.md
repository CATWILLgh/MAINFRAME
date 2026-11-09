---
name: mainframe-openspec
description: Use OpenSpec for a substantial change when the user chooses that workflow, or resume an assigned OpenSpec change. Covers collaborative specification, implementation handoff, and archive.
---

# Develop a change with OpenSpec

Use OpenSpec when the user opts in for the change or assigns an existing
OpenSpec package. Ordinary feature work and idea capture keep their existing
workflow. Size or uncertainty alone does not select OpenSpec.

## Resolve the planning location

- Identify the active repository and worktree. Check `.docs/openspec/` and
  root `openspec/` for existing configuration, changes, and specs. For new
  adoption, track artifacts under `<repo>/.docs/openspec/`. Resume existing
  changes in their assigned tree. Resolve ownership before creating a second
  tree, moving artifacts, or using a shared store. Check resolved paths for
  symlink and store redirects outside the assigned worktree.
- Run every OpenSpec command from the parent of the selected `openspec/` tree.
  Use `<repo>/.docs` for the MAINFRAME layout or `<repo>` for an assigned root
  layout. Use the actual repository and its normal entrypoints for source
  inspection, implementation, and project checks.
- Use the project's approved OpenSpec executable if it specifies one. Otherwise
  use the shared MAINFRAME executable at
  `~/.local/share/mainframe/runtime/bin/openspec` when present, then check
  `openspec` on `PATH`. Check its version and relevant command help. Use the
  resolved executable for every `openspec` command in this skill. For an
  authorized first proposal, create `.docs`
  if needed, then run `openspec init --tools none` from `.docs`. This delegates
  project structure to OpenSpec and keeps agent integration with MAINFRAME.
  Before changing a package, verify the local config and the root reported by
  `openspec list --json` or an equivalent read-only command in that release.
  If the CLI is missing, request the shared OpenSpec runtime through the
  maintained MAINFRAME installer. Keep CLI installation outside the project.
  If the CLI root cannot be verified, report the specific gap. Exploration can
  continue in chat while setup is resolved.

## Explore, propose, and revise

**Explore.** Work with the user on decisions that change the outcome. Read the
relevant code, existing contracts, and tests. Separate observed behavior from
the desired behavior and ask focused questions about consequential unknowns.
Keep exploration read-only until the user requests artifacts.

**Propose or revise.** Use `openspec list --json` to find the existing change
before starting another. For a new one, run `openspec new change <id>`. Follow
the selected schema and its dependency order using
`openspec status --change <id> --json` and
`openspec instructions <artifact> --change <id> --json`. Write to the resolved
artifact paths after checking they belong to the intended change. Iterate in
place as decisions settle, starting from the current artifacts when resuming.

In the default schema, the proposal defines why and scope, delta specs define
observable changes to capabilities, design captures technical decisions when
needed, and tasks map the agreement to implementation and checks. Use actual
capability paths and scenarios with observable outcomes. Keep the full intended
requirement when modifying it, including existing scenarios that still apply.
For a change with no specification-level behavior change, use the selected
schema's supported no-spec path when available. Leave implementation for apply.

Keep a single authoritative description of each behavior. Resolve ownership
with the user before bringing an already-documented contract into OpenSpec.
If asked to update a related `/todo` entry, link to the change package and keep
the entry brief.
Project governance and durable working agreements stay with their project
instruction or skill owner. Update those only when a durable decision changes
their guidance and the current scope permits it.

## Apply, verify, and archive

- **Apply** when the user authorizes implementation. In a fresh session, use the
  exact change ID, reload the current artifacts, and get
  `openspec instructions apply --change <id> --json`. Resolve missing or blocked
  prerequisites before changing code. Work through the tasks using the project's
  normal verification. Mark tasks complete when their result and required checks
  are evidenced. When implementation exposes a material change to the agreed
  behavior, reconcile the artifacts with the user before implementing it.
- **Verify** the affected change with
  `openspec validate <id> --type change --strict`. Inspect findings even on a
  zero exit code, including any reported archive merge conflicts. Check actual
  behavior against the affected scenarios with project tests or appropriate
  evidence. Report any gap separately from structural validation.
- **Archive** the exact change ID when authorized. Read
  `openspec instructions archive --change <id> --json` when supported. Resolve
  unchecked tasks, validation failures, and deltas that conflict with the same
  requirements before running `openspec archive <id>`. In a non-interactive
  shell, use `--yes` only after those checks pass because it also accepts
  warnings about incomplete work. Inspect the resulting current specs and
  archived folder. On failure, inspect both and the active package before retrying.

Use the installed release's help and the official [CLI reference](https://openspec.dev/docs/cli)
for version-specific flags, the [schema guide](https://openspec.dev/docs/schemas/spec-driven)
for artifact formats, and the [quickstart](https://openspec.dev/docs/quickstart)
for the workflow. Manage the shared CLI version through MAINFRAME. Follow the
receiving project's tooling policy for any project-specific dependency change.
