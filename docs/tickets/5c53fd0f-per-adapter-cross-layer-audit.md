---
id: 5c53fd0f
title: Audit every adapter layer by layer against the neutral core
status: open
priority: medium
component: adapters
discovered: 2026-08-06
discovered-from: []
tags: ["adapters", "parity", "audit", "projection", "layers"]
---

# 5c53fd0f: Audit every adapter layer by layer against the neutral core

## What was observed

The hub now projects a neutral core onto five runtimes — Claude Code, OpenCode,
Codex, ZCode Desktop and Antigravity 2.x — across six layers: instructions,
skills, agents, gates, permissions and MCP. Each adapter was built in its own
push, under its own deadline, and verified mainly against the runtime it targets.
No pass has ever walked one adapter end to end, layer by layer, asking of each
layer: does this projection still express what the core says, does it express it
in a form this runtime actually honours, and does it match what the sibling
adapters do with the same core material.

The queue already contains a spread of single-layer defects found by accident
rather than by systematic sweep: three independent detector-to-event mappings
that can drift apart, adapter metadata parsers with no shared contract, a
skill registry that can diverge from what the model actually sees, subagent-only
skills leaking into main-agent registries in two runtimes, and gate wiring in
two adapters that silently depends on a third adapter being installed. Each was
filed as its own symptom. Nothing owns the sweep that would have found them
together.

## Why it is a problem

A projection defect is silent by construction. The generator succeeds, the tests
pass, the files land — and the runtime quietly honours something other than what
the core intended. The `curl-requests` drift is the cheap version of this failure
(a stale sentence shipped for two days in a skill delivered to every project);
the expensive version is a gate that never fires or a permission that never
applies, where nothing visibly breaks and the loss is only discovered by the
incident it failed to prevent.

The risk grows with each adapter, because the number of core-to-runtime pairs
grows faster than the attention any single adapter change receives. Five runtimes
times six layers is thirty surfaces, and the project has never enumerated them.

## Why it is not a duplicate

- [#a7c96692](a7c96692-gate-mapping-drift-three-tools.md) — one layer (gate
  detector-to-event routing) across three tools; this ticket is the sweep that
  would enumerate that layer alongside the other five.
- [#d189a02a](d189a02a-adapter-metadata-parser-drift.md) — one layer
  (frontmatter parsing) and its missing parity test.
- [#f9d6a8b0](f9d6a8b0-claude-desktop-mainframe-verification-gap.md) — one
  adapter, one layer, live-session verification.
- [#7e88d75a](7e88d75a-subagent-only-skills-leak-to-main-agents.md) — one
  symptom of the skills layer in two adapters.

Those four are findings. This ticket is the method that produces findings —
closing it means the sweep exists and has been run once, not that any particular
defect is fixed.

## What probably needs to be done

- Write down the adapter-by-layer matrix explicitly: for each of the five
  adapters, for each of the six layers, what the core provides, what the
  projection emits, which runtime mechanism consumes it, and what evidence
  exists that the runtime honours it.
- For every cell, record the evidence class — live probe, generator test,
  documentation claim, or assumption. Cells resting on assumption are the
  finding; they need not be fixed inside this ticket, but they must be named.
- Run the sweep one adapter at a time rather than one layer at a time, so the
  reviewer holds a single runtime's semantics in mind throughout.
- File each concrete defect as its own ticket, cross-referenced here. Requires
  verification: whether the matrix belongs in `docs/layers/` as a living
  document or is a one-off audit artefact.
- Sequenced after the installer TUI work reaches its own boundary; the adapter
  surfaces are still moving until then.

## Acceptance criteria

- A committed matrix covers all five adapters across all six layers with no
  blank cells; every cell names its evidence class.
- Every cell whose evidence class is "assumption" has either been converted to a
  probe or test, or has a ticket.
- Defects found during the sweep are filed with `discovered-from: ["#5c53fd0f"]`.
- The sweep is reproducible: a later reader can tell which cells were checked
  against a running runtime and which were checked against documentation only.

## Sources

- `adapters/` — `antigravity-2`, `claude-code`, `codex`, `opencode`, `zcode-desktop`
- `docs/layers/` — per-layer specifications
- `docs/decisions/0085-neutral-core-restructure.md` — the core-to-adapter split
- `docs/tickets/fd61c474-curl-requests-generated-drift.md` — the cheap version of
  the silent-projection failure this sweep targets
