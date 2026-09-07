# Canonical installation guide

This guide is the single maintained documentation route for adapting MAINFRAME
from this repository into one agent product's global environment. It supports
the executable bootstrap in [ADAPT-MAINFRAME.md](../../ADAPT-MAINFRAME.md); it is
not itself global product payload.

MAINFRAME has no prebuilt target adapters. You must translate canonical
semantics into the installed product's current native mechanisms and prove the
result. Never make the canonical source imitate one product.

## Authority map

| Source | Owns | Does not own |
| --- | --- | --- |
| [ADAPT-MAINFRAME.md](../../ADAPT-MAINFRAME.md) | Fixed entry path, sequence, state loop, completion boundary | Per-product syntax or component semantics |
| [ADAPTATION.example.json](../../ADAPTATION.example.json) | Exact installable identities, source paths, and state shape | Discovery mechanics or evidence |
| This guide | Adaptation method, native orientation, verification, and recovery | Canonical component behavior |
| Canonical component source | Product-neutral behavior and boundaries | Target paths, metadata, registration, or permissions |
| Component tests | Executable source guarantees covered by those tests | Native discovery or host enforcement |
| [README.md](../../README.md) | Human-facing product overview | Installation procedure |

When text conflicts, do not combine both versions. Identify the owner in this
table, use current evidence, and correct or escalate the actual owner.

## Progressive reading route

Do not load the whole documentation tree for every component. Use this route:

1. Read [process.md](process.md) once for a new installation or when resuming
   unfamiliar state.
2. Read [verification.md](verification.md) before assigning any final status.
3. For the active inventory entry, read one component guide and one native
   product page.
4. Read the canonical component source and its directly linked resources.
5. Open one problem note only when its `Use when` condition matches.
6. Perform the native probe and update state immediately.

This route is both a context budget and an ownership rule. A native page is an
orientation map, not permission to skip current official documentation.

## Component guides

- [Credentials](components/credentials.md)
- [Global instruction](components/instructions.md)
- [Skills](components/skills.md)
- [Agents and subagents](components/agents.md)
- [Commands](components/commands.md)
- [Hooks](components/hooks.md)
- [Integrations, runtime, settings, and permissions](components/integrations.md)

## Native product pages

Each page records a dated orientation to likely native mechanisms and the
questions that still require verification against the installed version.

- [Codex](native/codex.md)
- [Claude Code](native/claude-code.md)
- [OpenCode](native/opencode.md)
- [Antigravity](native/antigravity.md)
- [Pi](native/pi.md)

If the product is not listed, apply [process.md](process.md) directly and add a
native page only after authoritative documentation and a reproducible probe
establish a stable mapping. Do not derive a new product from a similar one.

## Problem notes

- [Existing installation](problems/existing-installation.md)
- [Ownership collision](problems/ownership-collision.md)
- [Discovery and reload](problems/discovery-and-reload.md)
- [Desktop and CLI divergence](problems/desktop-cli-divergence.md)
- [Permissions and secrets](problems/permissions-and-secrets.md)
- [Unsupported capability](problems/unsupported-capability.md)
- [Rollback and recovery](problems/rollback-and-recovery.md)

Every problem note uses the same shape: `Use when`, `Desired result`, `Inspect`,
`Adapt`, `Verify`, `Record`, and `Never do`. Keep fixes bounded to the exact
failure instead of restarting the full installation or scanning unrelated user
data.

## Repository and payload boundary

The repository is both canonical product source and installation workspace.
Only entries in [ADAPTATION.example.json](../../ADAPTATION.example.json) are
globally installable. Root instructions, this documentation, adaptation state,
tests, installers, templates, local `.agents/` knowledge, archives, tickets,
caches, and Git data remain repository support.

The exception is not a directory: the inventory explicitly lists the exact
`shared/credentials/secret` file as payload. Its sibling installer, template,
index, and tests remain here.

## Maintaining this guide

Update the narrow owner whenever product behavior changes:

- inventory or source identity: `ADAPTATION.example.json`;
- canonical behavior: the component and its tests;
- cross-product adaptation rule: the matching component guide;
- documented product mechanism: the matching dated native page;
- repeated recovery case: the matching problem note;
- fixed trajectory or completion boundary: `ADAPT-MAINFRAME.md`.

Do not paste the same rule into several layers. Link to its owner and keep the
caller readable from zero prior context.
