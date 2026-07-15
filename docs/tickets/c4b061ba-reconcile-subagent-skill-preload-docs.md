---
id: c4b061ba
title: Reconcile contradictory subagent skill preload documentation
status: open
priority: medium
component: docs-layers-agents
discovered: 2026-07-15
discovered-from: []
tags: ["documentation", "subagents", "skills"]
---

# c4b061ba: Reconcile contradictory subagent skill preload documentation

## What was observed

`docs/layers/agents.md:83` and `docs/layers/skills.md:102` say that a
subagent's `skills:` entries inject full skill content at startup. The later
empirical result in `docs/layers/agents.md:286` explicitly corrects that model:
the skill became available for the subagent to read, but its content was not
reliably present before that read.

## Why it is a problem

The two models imply different context-cost and availability decisions. A
maintainer following the older text may overestimate startup context, omit an
explicit read that is actually required, or make an incorrect bloat decision.

## Why it is not a duplicate

No existing ticket tracks this internal contradiction in the layer
documentation.

## What probably needs to be done

Re-run a minimal probe against the current installed Claude Code version, check
the installed bundle and current official subagent documentation, then
supersede all conflicting statements with one verified contract. Preserve the
distinction between access through the `Skill` tool and availability through
the agent's `skills:` declaration.

## Acceptance criteria

- `docs/layers/agents.md` and `docs/layers/skills.md` describe one consistent
  `skills:` lifecycle.
- The current statement cites an installed-runtime experiment and an official
  source, with any conflict named explicitly.
- Guidance for agents without the `Skill` tool follows the verified behavior.

## Sources

- `docs/layers/agents.md:83`
- `docs/layers/agents.md:286`
- `docs/layers/skills.md:102`
- <https://code.claude.com/docs/en/sub-agents>
