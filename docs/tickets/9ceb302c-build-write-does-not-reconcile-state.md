---
id: 9ceb302c
title: Render and build write commands do not fully reconcile desired output state
status: open
priority: medium
component: build-system
discovered: 2026-07-15
discovered-from: []
tags: ["build", "render", "generated-files", "desired-state", "drift"]
---

# 9ceb302c: Render and build write commands do not fully reconcile desired output state

## What was observed

`render_core.py --check` reports unmanaged orphan outputs, but `--write` only copies stale or missing targets and leaves those orphans in place. The OpenCode agent generator writes the current set without removing stale generated agents. Instruction composition is maintained by manual ordered lists, and installation does not first prove that committed outputs match their sources.

## Why it is a problem

The documented build command cannot always turn an old checkout into the declared state. Removed sources can remain globally delivered, while a direct installation can publish stale generated content that CI would reject later.

## Why it is not a duplicate

- [#643a4490](643a4490-render-check-guard-residual-gaps.md) fixed orphan detection in check mode. This ticket covers reconciliation in write and install paths.
- [#6d09e7be](6d09e7be-install-sh-silent-success-on-missing-source.md) covers missing required sources, not stale generated outputs.

## What probably needs to be done

- Give every generator an explicit managed-output boundary and remove stale entries only inside that boundary.
- Derive instruction fragments from a validated manifest or verify list completeness.
- Make installation fail before delivery when source and committed generated state differ.

## Acceptance criteria

- Starting from seeded orphan outputs, one documented write/build command produces the exact expected tree.
- Removed OpenCode agents do not remain in generated or installed output.
- Installation refuses stale renders and does not mutate global configuration on that failure.
- Tests prove user-owned files outside managed boundaries are preserved.

## Sources

- `tools/render_core.py:67-100`, `tools/render_core.py:200-225`
- `adapters/opencode/build_opencode.py:330-360`
- `install.sh:991-1037`
- `docs/tickets/643a4490-render-check-guard-residual-gaps.md`
