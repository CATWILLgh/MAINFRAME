---
id: f9d6a8b0
title: Claude Code plugin skill registry can diverge from model context in a live session
status: open
priority: medium
component: claude-code-layer
discovered: 2026-07-15
discovered-from: []
tags: ["claude-code", "desktop", "cli", "vscode", "skills", "session", "delivery", "verification"]
---

# f9d6a8b0: Claude Code plugin skill registry can diverge from model context in a live session

## What was observed

Fresh probes currently show `mainframe@skills-dir` loaded in all three supported local runtimes: standalone CLI 2.1.177, Claude Desktop Code Local 2.1.209, and the official VS Code extension 2.1.210. The VS Code log reports all 18 MAINFRAME skills, and fresh Desktop and VS Code session transcripts include `surface-ticket` in the model-visible skill listing.

That healthy startup state does not cover long-running or resumed sessions. A real VS Code transcript from 2026-07-14 on Claude Code 2.1.208 records both `Unknown skill: mainframe:task-workflow` and `Unknown skill: task-workflow`. The model retained enough MAINFRAME context to know which skill to request, while the `Skill` tool could no longer resolve it. This matches the user's broader symptom class: an agent knows that a MAINFRAME skill should exist but cannot load it. The transcript does not prove that context compaction caused the failure.

The exact recent `Unknown skill` result for `surface-ticket` has not yet been recovered. An older Desktop 2.1.170 occurrence used the invalid name `plugin:mainframe:surface-ticket`, so that particular event was caller error. The confirmed failure concerns `task-workflow`, but demonstrates that plugin registration can diverge from model context inside a live session.

The plugin root moved from `plugin-dist/` to `dist/claude-code/plugin` on 2026-07-14, while `.claude-plugin/plugin.json` has remained at version `0.1.0`. Stale cache identity after a path or content change is therefore a candidate cause, not a confirmed cause. A June incident also records the whole MAINFRAME plugin unloading mid-session.

## Why it is a problem

Startup validation and `plugin list` can be green while an active agent has lost the executable skill registry. This silently bypasses mandatory workflows such as task orchestration and ticket creation. Specialized MAINFRAME agents are especially exposed because several receive `surface-ticket` through agent `skills:` preload and do not have a separate `Skill` tool fallback.

The current installer verifies links, not the behavior of fresh, resumed, and compacted sessions in each official local host. It therefore cannot catch this state split.

## Why it is not a duplicate

- [#553bad8e](553bad8e-actionable-skills-hidden-from-slash-menu.md) covers deterministic manual-command visibility caused by `user-invocable: false`; this ticket covers model/tool resolution failing after the skill was known.
- [#f125085c](f125085c-installer-public-contract-tests-missing.md) covers installer filesystem contracts, not live-session skill registry stability.
- [#c4b061ba](c4b061ba-reconcile-subagent-skill-preload-docs.md) covers preload semantics, not live-session registry divergence.

## What probably needs to be done

- Build a local parity probe for standalone CLI, official VS Code, and Desktop Code Local that exercises an actual MAINFRAME skill in fresh, long-running, resumed, and deliberately compacted sessions.
- Reproduce the 2.1.208 live-session failure with a small marker skill before changing MAINFRAME delivery.
- Isolate cache variables in bounded experiments: unchanged versus incremented plugin version, stable versus moved plugin root, and direct directory versus symbolic-link registration.
- Verify specialized-agent `skills:` preload independently from top-level `Skill` calls.
- Add a diagnostic that distinguishes filesystem delivery, plugin component discovery, session model listing, and actual `Skill` resolution.
- Record any upstream Claude Code defect with the exact host, embedded version, session transition, and minimal reproduction.

## Acceptance criteria

- The same MAINFRAME marker skill resolves in fresh, long-running, resumed, and deliberately compacted sessions in all three supported local runtimes.
- A regression check exercises a plugin content and root-path update in active and resumed sessions, then either confirms skill resolution or emits an explicit restart recommendation.
- `surface-ticket` is demonstrably preloaded into every specialized agent that declares it in `skills:`.
- The regression check records host versions and tests real skill activation, not only `plugin list`, `plugin details`, or filesystem links.
- Any required plugin versioning or restart contract is encoded in the build/install workflow and documented.

## Sources

- `~/.claude/projects/-Users-user-Documents-projects-Prodtrack/bcb9d341-759a-4ed6-b8d7-a47bd3cdece5.jsonl:41845-41854` — `Unknown skill` failures inside a live VS Code Claude Code 2.1.208 session.
- `~/Library/Application Support/Code/logs/20260707T234423/window3/exthost/Anthropic.claude-code/Claude VSCode.log:42671-42820` — Claude Code 2.1.210 loads MAINFRAME hooks and all 18 plugin skills.
- `workspace/reference/20260620-200951-WeBuy-mid-session-filesystem-eperm-mainframe-plugin-unload.md` — prior whole-plugin unload during a live session.
- Commit `4eda1ea` — plugin root migration on 2026-07-14.
- [Extend Claude with skills](https://code.claude.com/docs/en/slash-commands)
- [Claude Code Desktop](https://code.claude.com/docs/en/desktop)
- [Claude Code IDE integrations](https://code.claude.com/docs/en/ide-integrations)

## Re-occurrence noted (2026-07-15)

**Noticed during:** Claude plugin manifest source and validation repair (`#09b19ada`)
**Where:** `adapters/claude-code/plugin.json`, `core/README.md`, and Claude Code validation CI
**Additional details:** The manifest now has a guarded authored source and strict official validation, but its explicit `0.1.0` version was deliberately left byte-identical. Version advancement and active/resumed-session cache behavior remain owned by this parity ticket; source ownership and schema validity alone do not prove live registry stability.
