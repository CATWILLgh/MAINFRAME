---
id: 34dc48ba
title: Two independent guards define where a component may write
status: open
priority: medium
component: installer
discovered: 2026-08-06
discovered-from: []
tags: ["ownership", "boundary", "mcp", "release-contract", "drift"]
---

# 34dc48ba: Two independent guards define where a component may write

## What was observed

"Which files may this component touch" is answered by two separate, unlinked
tables.

`tools/release_component_roots.py:8-19` holds `COMPONENT_ROOTS`, checked by
`validate_component_targets` (`:30-48`) over `install_units`, `legacy_artifacts`
and `resources`. It locks each adapter to its own configuration root, and adds
two narrow exceptions: `credential-tools` may reach `home` (further restricted to
the three exact filenames in `COMPONENT_ROOT_PATHS`) and `user-bin`, and
`mainframe-cli` may reach `user-bin`.

`mcp_projections` are **not** in that loop. They are validated instead by
`validate_manifest_projections` against a hardcoded per-`(component, codec)`
table in `tools/release_mcp_projection.py:14-69`, which pins an exact target
file. That table lets `claude-code` target `("home", ".claude.json")` — a root
`COMPONENT_ROOTS` forbids that component from touching anywhere else.

Both guards are individually sound: the codec table is in fact stricter than the
root guard, since it pins one exact file rather than a whole root. The problem is
that they are two answers to one question, and nothing makes them agree.

## Why it is a problem

The write boundary is the property the maintainer actually relies on — the reason
a broad apply is acceptable at all is the belief that each component only touches
its own area. A reviewer checking that belief reads `COMPONENT_ROOTS`, concludes
"claude-code is confined to `claude-config`", and is wrong: the shipped Claude
Code bundle writes into `~/.claude.json`.

This is the same failure class as
[#a7c96692](a7c96692-gate-mapping-drift-three-tools.md): a rule expressed more
than once drifts silently, and the copy nobody reads is the one that governs.
Here the risk is asymmetric — the unguarded surface is the user's home
directory, and a future codec entry would face no root check at all.

## Why it is not a duplicate

- [#a7c96692](a7c96692-gate-mapping-drift-three-tools.md) — same drift class, but
  gate detector-to-event routing, not write boundaries.
- [#20e75df1](20e75df1-model-managed-target-directories.md) — closed; covered
  creating and rolling back managed directories, not who may declare them.
- [#5c53fd0f](5c53fd0f-per-adapter-cross-layer-audit.md) — the umbrella sweep
  that would enumerate this; this ticket is the one defect already found.

## What probably needs to be done

- Make one table the source of the boundary and derive the other from it, or
  validate MCP projection targets against `COMPONENT_ROOTS` in addition to the
  codec table. Requires verification: whether `claude-code` should gain a
  path-restricted `home` entry in `COMPONENT_ROOTS` (mirroring the
  `credential-tools` pattern) or whether MCP targets deserve their own declared
  exception list.
- Add a test that fails when a codec entry names a target its component could
  not otherwise reach.
- State the complete write boundary in one place a reviewer can read, including
  the `user-bin` launchers and the three shell startup filenames.

## Acceptance criteria

- Exactly one declaration answers "may component X write to location Y", or a
  test proves the two agree for every shipped component and codec.
- Adding a codec entry outside its component's permitted roots fails validation.
- The documented boundary matches what the shipped bundles actually declare,
  verified against the manifests rather than from the source tables alone.

## Sources

- `tools/release_component_roots.py:8-19,30-48`
- `tools/release_mcp_projection.py:14-69,73`
- `tools/release_contract.py:223-229`
- `adapters/claude-code/build_bundle.py:174-193`
