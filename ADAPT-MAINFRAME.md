# Adapt MAINFRAME to your global environment

This is the executable bootstrap for the agent product running in this
repository. Complete the installation or update; do not stop after describing a
plan.

## Use the only supported trajectory

1. The user downloads or clones MAINFRAME.
2. The user opens this repository itself as the current project in the product
   to be configured.
3. You install the canonical MAINFRAME components into that product's global
   environment.

Do not run this protocol from another project or install MAINFRAME into a
receiving project. Do not search the home directory, other repositories,
archives, backups, recovery directories, mounted volumes, or Trash for another
MAINFRAME checkout.

Resolve the current project root through the active workspace or Git. Continue
only when the same root contains this file, `ADAPTATION.example.json`,
`docs/installation/`, `instructions/`, `skills/`, `agents/`, `commands/`,
`hooks/`, and `shared/`. Normalize that absolute path as `MAINFRAME_ROOT`.

Treat tracked repository files as immutable input during installation.
Product-specific paths, metadata, permissions, wrappers, and registrations
belong only in globally installed copies. Repository-local writes are limited to
the ignored product state, centralized non-secret credential index, and later
feedback records explicitly described by the component guides.

## Read the canonical installation guide

Read [docs/installation/README.md](docs/installation/README.md), then follow its
progressive route. The guide owns installation mechanics and problem recovery.
Canonical component sources own behavior. Tests own executable source
guarantees.

Do not preload every guide or component. For each component, read only:

1. its row in your adaptation state;
2. the matching component guide;
3. the page for your installed product;
4. the canonical source and directly required resources;
5. a problem note only when its `Use when` condition matches.

## Initialize or resume exact state

Determine a stable lowercase product identifier. Desktop and CLI share it only
when they are interfaces of the same product and actually share configuration.
Use `ADAPTATION.<product-id>.json` in this repository root and verify that exact
path is ignored before writing it.

If absent, copy `ADAPTATION.example.json`. If present, reconcile it with the
example by stable component identity and source path:

- add new entries as `pending`;
- retain status only for an unchanged identity and source;
- reset changed entries to `pending`;
- remove entries no longer in the example;
- never copy target-specific state back into the example.

Record the resolved root, product/version/install method, Desktop and CLI
surfaces, whether those surfaces share configuration, and exact native global
destinations. Keep the file a small state document. Do not add transcripts,
timestamps, command output, telemetry, secret values, or diagnostic history.

Only these states are valid:

- `pending`: not yet installed and natively verified;
- `installed`: installed and proven through native discovery or behavior;
- `unsupported`: the installed product cannot represent the required
  capability, with the exact reason in a short `note`.

File presence, valid syntax, a successful build, or a plausible path is not
enough for `installed`.

## Establish the target and preserve it

Use current official documentation plus the installed product's own version,
help, and harmless probes. Determine the effective global instruction, skills,
agents, commands, hooks, integrations, permissions, and settings layers. Treat
Desktop and CLI as separate proof surfaces when their runtime differs.

Inspect only this product's known relevant global roots. Preserve its existing:

- authentication, accounts, credentials, history, sessions, memories, drafts,
  projects, and worktrees;
- user-owned instructions and built-in or application-generated components;
- unrelated skills, agents, commands, hooks, MCP servers, plugins, permissions,
  settings, and native caches;
- unrelated Git work and local files in this repository.

Never print secret values. Create a rollback copy only for a file you will
change, store it outside tracked content with suitable protection, and remove it
after verification. Never create a full-profile archive or rewrite a Git
worktree as part of installation.

## Process the complete inventory

First run the bounded inventory check in the guide. Then process one component
at a time in this order:

1. shared credentials support;
2. skills;
3. agents;
4. commands;
5. hooks;
6. MCP, plugins, runtime support, settings, and permissions;
7. the global instruction;
8. final Desktop and CLI verification.

Within a category, keep state-file order. Complete this loop before moving on:

1. Read the matching [component guide](docs/installation/README.md#component-guides).
2. Recheck the relevant [native product page](docs/installation/README.md#native-product-pages)
   against current official documentation and installed behavior.
3. Inspect the canonical source and only its required resources.
4. Inspect the existing native registration with the same stable identity.
5. Adapt a copy into the exact native global owner; never modify canonical
   product-neutral source for one target.
6. Merge or replace only the MAINFRAME-owned identity. Preserve unrelated state
   and prevent duplicate files, registrations, permissions, and aliases.
7. Run source validation, reload through the documented native mechanism, and
   prove the smallest safe native discovery or behavior.
8. Immediately record `installed`, `unsupported`, or the precise `pending`
   blocker.

Do not ask for confirmation between ordinary successful components. Continue
past an independently unsupported component. Stop when proceeding requires a
secret-storage decision, destructive ambiguity, missing authority, unavailable
canonical material, or a semantic choice that belongs to the user.

## Finish only on evidence

Follow [verification.md](docs/installation/verification.md) and
[rollback-and-recovery.md](docs/installation/problems/rollback-and-recovery.md).
Remove temporary staging, verified obsolete MAINFRAME-owned adapter residue,
stale links, stopped test processes, targeted rollback copies, and empty
MAINFRAME-owned directories. Keep the product state file and native
application-owned caches. Never create a permanent archive unless requested.

Installation is complete only when every inventory entry is `installed` or
`unsupported` with a precise reason. Any `pending` entry means incomplete work.

Return one concise evidence-based report covering the target and surfaces,
validated root and destinations, installed evidence, unsupported limitations,
credentials integration without values, permissions, preservation and cleanup,
and any exact remaining blocker. Separate observations, documentation-backed
mappings, inferences, and unknowns.
