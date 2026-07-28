---
id: 9fb130c1
title: Skill user-visibility policy contradicts all shipped metadata
status: open
priority: low
component: skill-architecture
discovered: 2026-07-15
discovered-from: ["#553bad8e"]
tags: ["skills", "visibility", "documentation", "frontmatter", "policy"]
---

# 9fb130c1: Skill user-visibility policy contradicts all shipped metadata

## What was observed

`docs/layers/skills.md` says `user-invocable: false` is the default except for side-effecting skills such as commit, deploy, and scaffold workflows. All 18 current MAINFRAME skills declare `user-invocable: false`, including `git-conventional-commits`, whose documented workflow executes commits.

The user has explicitly clarified that `surface-ticket` should remain hidden, so side effects alone are not the intended product criterion. No current document defines which, if any, skills should be first-class user commands.

## Why it is a problem

The architectural rule and shipped behavior cannot both be correct. A future maintainer following the layer guide would expose some skills, while the present metadata and the user's desired interface expose none. This ambiguity also makes visibility regressions impossible to test against a stable expected set.

## Why it is not a duplicate

[#553bad8e](553bad8e-actionable-skills-hidden-from-slash-menu.md) resolves only that `surface-ticket` is correctly absent from the user menu. [#7e88d75a](7e88d75a-subagent-only-skills-leak-to-main-agents.md) covers main-agent versus subagent isolation in OpenCode and Codex. This ticket defines the user-command policy across the skill catalog.

## What probably needs to be done

- Replace the broad side-effect rule with the actual product criterion for a user-facing command.
- Classify every current skill as user-visible, main-agent-only, or designated-subagent-only.
- Encode the expected user-visible set in validator and installed-runtime checks without changing subagent visibility by accident.

## Acceptance criteria

- `docs/layers/skills.md` and the metadata of all shipped skills agree.
- The expected user command set is explicit; an empty set is valid if that is the chosen interface.
- Side effects do not automatically imply user visibility unless the documented policy deliberately says so.
- Tests distinguish user command visibility, main-agent discovery, and designated-subagent preload.

## Sources

- `docs/layers/skills.md:134-140`
- `core/skills/git-conventional-commits/SKILL.md:1-5`, `core/skills/git-conventional-commits/SKILL.md:21-28`
- [#553bad8e](553bad8e-actionable-skills-hidden-from-slash-menu.md)
