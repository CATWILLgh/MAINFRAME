# Canonical installation guide

This guide is the single maintained documentation route for adapting MAINFRAME
from this repository into one agent product's global environment. It supports
the executable bootstrap in [ADAPT-MAINFRAME.md](../../ADAPT-MAINFRAME.md); it is
not itself global product payload.

Use a maintained product installer when one exists. It translates canonical
sources through maintained native mappings; the agent handles semantic conflicts,
unexpected environments, current-surface discovery, and user activation handoffs.
Keep adapter acceptance separate from routine installation under
[verification.md](verification.md#routine-installation-and-adapter-validation). Keep
generated content out of the source tree and never make a canonical component
imitate one product.

## Authority map

| Source | Owns | Does not own |
| --- | --- | --- |
| [ADAPT-MAINFRAME.md](../../ADAPT-MAINFRAME.md) | Fixed entry path, sequence, state loop, completion boundary | Per-product syntax or component semantics |
| [ADAPTATION.example.json](../../ADAPTATION.example.json) | Exact installable identities, source paths, and state shape | Discovery mechanics or evidence |
| This guide | Adaptation method, native orientation, verification, and recovery | Canonical component behavior |
| [Maintained installer](../../install.py) | Deterministic packaging, owned writes, update, recovery, and executable checks | Rewriting canonical content, deciding user instruction conflicts, or assuming untested native behavior |
| Canonical component source | Product-neutral behavior and boundaries | Target paths, metadata, registration, or permissions |
| Component tests | Executable source guarantees covered by those tests | Native discovery or host enforcement |
| [README.md](../../README.md) | Human-facing product overview | Installation procedure |

When text conflicts, do not combine both versions. Identify the owner in this
table, use current evidence, and correct or escalate the actual owner.

## Progressive reading route

For Codex Desktop or CLI, use the [Codex procedure](codex-installer.md). For
ZCode Desktop, use the [ZCode procedure](zcode-installer.md). The selected
executable route owns the complete installation pass.

For DeepSeek Harness, use the separate [plugin package guide](dsh-adapter.md).
It covers source checks, independent `.tgz` archives, and profile installation
and lifecycle through DSH's native `plugin_manager`.

Products without a maintained installer require separately assigned adapter
development. Use native pages to orient that work and to verify adapter
behavior against the current product.

Do not load the whole documentation tree for every component. Use this route:

1. Read [process.md](process.md) once to establish how delivery and state work.
2. Read [verification.md](verification.md) before assigning any final status.
3. For the active inventory entry, read one component guide and one native
   product page.
4. Read the canonical component source and its directly linked resources.
5. Open one problem note only when its `Use when` condition matches.
6. For assigned native acceptance, record the result of each scoped probe.

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
- [ZCode Desktop](native/zcode.md)

These research notes support separately assigned adapter development.

- [Claude Code](native/claude-code.md)
- [OpenCode](native/opencode.md)
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
The [inventory](../../ADAPTATION.example.json) identifies the exact sources.
The Codex and ZCode adapters install the MAINFRAME components they support.
The inventory's four plugin entries are built separately for DSH profiles.
Root instructions, this documentation, adaptation state, tests, installers,
templates, local `.agents/` knowledge, archives, tickets, caches, and Git data
remain repository support.

A listed hook may require the maintained adapter's small native transport.
That support is installed only as part of its binding; it does not make the
whole installer directory or another component installable.

The exception is not a directory: the inventory explicitly lists the exact
`shared/credentials/mainframe-secret` file as payload. Its sibling installer, template,
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
