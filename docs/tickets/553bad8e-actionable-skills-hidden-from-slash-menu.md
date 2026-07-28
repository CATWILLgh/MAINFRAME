---
id: 553bad8e
title: Surface-ticket slash-menu absence matches the intended visibility policy
status: approved
priority: medium
component: claude-code-layer
discovered: 2026-07-15
discovered-from: ["#f9d6a8b0"]
tags: ["claude-code", "desktop", "vscode", "skills", "slash-menu", "user-invocable", "visibility-policy"]
---

# 553bad8e: Surface-ticket slash-menu absence matches the intended visibility policy

## What was observed

`surface-ticket` currently declares `user-invocable: false`. All 18 shipped MAINFRAME skills declare the same value, so current Claude Code semantics result in zero MAINFRAME skills in the `/` menu. Official documentation defines this field as the opt-out from user invocation while preserving model invocation. For plugin skills, the namespaced manual command would otherwise be `/mainframe:surface-ticket`.

Zero user-visible commands does not mean that all 18 skills should be exposed. MAINFRAME already documents three distinct activation scopes:

- user and main agent — `user-invocable: true` without `disable-model-invocation`;
- main agent only — `user-invocable: false` without `disable-model-invocation`;
- designated subagent only — `user-invocable: false` plus `disable-model-invocation: true`, with the skill named in that subagent's `skills:` preload.

Eight current skills use the third, intentionally isolated form, including the stack-pattern skills and `decision-review`. They must remain absent from both the user's menu and the main agent's model-visible skill set. This ticket concerns the narrower mismatch for `surface-ticket`, not a request to expose the complete plugin.

The user clarified that `surface-ticket` is not intended to be a user command. Its absence from the slash menu is therefore the expected result, while its lack of `disable-model-invocation: true` keeps it available to the Claude Code main agent.

The user's report that this used to work matches MAINFRAME's own recorded Phase 7 check. On 2026-05-31, standalone Claude Code 2.1.158 was recorded as displaying `mainframe:surface-ticket` and nine other MAINFRAME skills in the session slash list even though those files already had `user-invocable: false`. Current Desktop 2.1.209 and VS Code 2.1.210 hide `surface-ticket`, matching today's documented semantics. The old observation conflicts with both contemporaneous frontmatter and the documented meaning of the flag, so the exact historical mechanism requires revalidation rather than being treated as a proven Claude Code semantics change.

No repository change flipped this flag: `surface-ticket` has been `false` since the first public source commit. The mismatch therefore comes from historical runtime behavior, the old verification record, or both; it does not come from a recent edit to the skill.

The distinct live-session failure class remains real: a model can know that a skill exists while the active registry returns `Unknown skill`. That behavior is tracked in [#f9d6a8b0](f9d6a8b0-claude-desktop-mainframe-verification-gap.md), not inferred from slash-menu absence.

## Why it is a problem

The original report treated user visibility, main-agent discovery, and
designated-subagent preload as one contract. That ambiguity could prompt a
change exposing implementation skills as user commands and break intended
subagent isolation. Investigation established that the current
`surface-ticket` metadata already expresses the desired main-agent-only
behavior in Claude Code.

## Why it is not a duplicate

- [#f9d6a8b0](f9d6a8b0-claude-desktop-mainframe-verification-gap.md) covers model/tool registry divergence observed inside a live session. This ticket covers deterministic user-facing visibility while the skill remains loaded for the model.
- No existing ticket defines which MAINFRAME skills must be directly invocable across the three official local Claude Code surfaces.

## What probably needs to be done

- Keep `surface-ticket` at `user-invocable: false` without `disable-model-invocation`.
- Do not expose all MAINFRAME skills as user commands.
- Preserve Claude Code's designated-subagent form: `user-invocable: false`, `disable-model-invocation: true`, and agent `skills:` preload.
- Track OpenCode and Codex isolation loss separately in [#7e88d75a](7e88d75a-subagent-only-skills-leak-to-main-agents.md).

## Acceptance criteria

- `surface-ticket` remains absent from the user `/` menu.
- Fresh standalone CLI, official VS Code, and Desktop Code Local installations register the skill as part of the plugin.
- Automatic main-agent invocation and designated-subagent preload are treated as behavioral contracts tracked by [#f9d6a8b0](f9d6a8b0-claude-desktop-mainframe-verification-gap.md) and [#7e88d75a](7e88d75a-subagent-only-skills-leak-to-main-agents.md), not inferred from manifest validation.

## Sources

- `core/skills/surface-ticket/SKILL.md:1-5` — current `user-invocable: false` declaration.
- `docs/layers/skills.md:36,64-66,138` — intended frontmatter semantics and side-effect exception.
- `docs/layers/skills.md:93-103,109-115,134-139` — access versus preload, current skill roles, and the subagent-only pattern.
- `docs/layers/decision-tree.md:25-44,65-75` — explicit main-context versus designated-subagent placement and bloat prevention.
- `docs/decisions/0064-plugin-migration-hybrid-symlink-architecture.md:244-254` — Claude Code 2.1.158 Phase 7 result showing `mainframe:surface-ticket` in the slash list.
- Commit `ab656cf` — earliest public source already has `user-invocable: false`.
- `~/.claude/cache/changelog.md:3028` — Claude Code documents slash-menu visibility with `user-invocable: false` as the opt-out.
- [Extend Claude with skills](https://code.claude.com/docs/en/slash-commands)
- [Create plugins](https://code.claude.com/docs/en/plugins)

## Resolution (2026-07-15)

**Implementer:** Codex primary agent
**Commits:** None — local ticket correction only
**Summary:** The user clarified that `surface-ticket` is not intended to be a user command. Its current `user-invocable: false` value is therefore correct. No skill or adapter change is required; the original finding confused command-menu visibility with runtime availability.
**Claims to verify on audit:**
- `surface-ticket` remains absent from the user `/` menu.
- `surface-ticket` remains available to the main agent because it does not set `disable-model-invocation: true`.
- In Claude Code, designated subagent-only skills remain isolated through `disable-model-invocation: true` plus agent `skills:` preload.

> Related: #7e88d75a — OpenCode and Codex do not currently preserve the same subagent-only boundary.

## Audit (2026-07-15)

**Auditor:** independent adapter contract and performance reviewers
**Verdict:** Approved for the slash-menu classification only
**Verified:**
- `surface-ticket` has `user-invocable: false` in source, rendered, and installed Claude Code copies.
- It does not set `disable-model-invocation: true`, which expresses model invocability in the Claude Code metadata contract; actual invocation was not proven by this audit.
- Standalone CLI 2.1.177, official VS Code 2.1.210, and Desktop Code Local 2.1.209 each validate the plugin and report `surface-ticket` among all 18 registered skills.
**Regression scan:** all 28 repository test files pass; `render_core.py --check` reports source/render parity.
**Notes:** Registration is not behavioral activation. Live-session skill resolution remains open in #f9d6a8b0, and cross-adapter subagent isolation remains open in #7e88d75a; neither reopens this user-menu non-issue.
