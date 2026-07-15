---
id: 3efdbdb9
title: Remove Claude-only guarantees from projected Antigravity skills
status: approved
priority: medium
component: antigravity-projection
discovered: 2026-07-15
discovered-from: []
tags: ["antigravity", "skills", "projection", "permissions", "documentation"]
---

# 3efdbdb9: Remove Claude-only guarantees from projected Antigravity skills

## What was observed

The Antigravity builder copies every core skill and applies broad string
substitutions. The generated `secrets-handling` skill still claims that direct
credential reads are mechanically denied by `settings.json`, while the layer
documentation explicitly says Antigravity permissions remain user-owned and are
not projected. The builder also changes a verified Claude Bash statement into an
unverified generic claim that the Antigravity shell reads `~/.zshenv`.

## Why it is a problem

The plugin presents operational and security guarantees that the target runtime
does not enforce. An agent may rely on a nonexistent denial boundary or expect
environment variables to be available when the actual shell startup differs.
Blind substitution makes future Claude-specific claims easy to miss.

## Why it is not a duplicate

- [#c4b061ba](c4b061ba-reconcile-subagent-skill-preload-docs.md) concerns
  subagent skill preload wording, not permissions or shell behavior.
- [#6b0a68eb](6b0a68eb-contain-antigravity-builder-symlinks.md) concerns source
  containment, not the meaning of accepted Markdown.

## What probably needs to be done

1. Inventory runtime-sensitive skills and claims about permissions,
   `settings.json`, shell startup, denied paths, and delivery paths.
2. Introduce an explicit projection allowlist, per-runtime overlays, or exclusions.
3. Remove claims that cannot be supported by Antigravity's public contract or a
   recorded installed-runtime experiment.
4. Validate generated artifacts for banned Claude-only guarantees.
5. Document which skills are unchanged, adapted, or unavailable per runtime.

## Acceptance criteria

- Generated Antigravity skills make no claim that its permission settings were
  installed or mechanically enforce Claude Code deny patterns.
- Shell environment claims are backed by a repeatable Antigravity 2.2.1 test or
  replaced with runtime-neutral instructions.
- A generator test fails when known Claude-only phrases reappear.
- Every runtime-sensitive skill has an explicit projection decision.
- Claude Code source skills remain unchanged and their verified guarantees intact.

## Sources

- `adapters/antigravity-2/skill_projection.py:14-127`
- `adapters/antigravity-2/skill_projection.py:130-336`
- `adapters/antigravity-2/build_antigravity.py:117-145`
- `adapters/antigravity-2/build_antigravity.py:148-224`
- `tools/test_build_antigravity.py:266-341`
- [Antigravity permissions](https://antigravity.google/docs/permissions?app=antigravity)
- [Antigravity 2.0 slash commands](https://antigravity.google/docs/workspaces)
- [Antigravity settings](https://antigravity.google/docs/settings?app=antigravity)
- [Antigravity plugins](https://antigravity.google/docs/plugins)
- [Antigravity skills](https://antigravity.google/docs/skills)
- [Antigravity hooks](https://antigravity.google/docs/hooks?app=antigravity)

## Resolution (2026-07-15)

**Implementer:** Codex
**Commit:** f8144307c225924b2237d84d64402329ce2f7137
**Summary:** Antigravity skill projection now has an explicit inventory and
per-skill policy. Runtime-sensitive overlays replace unsupported permission,
shell, plan-mode, and reviewer guarantees with documented Antigravity-native
bindings. Every Markdown source and delegated skill is validated after
projection; exact overlay anchors and required files fail closed on source drift.

**Compatibility evidence:** The generated `task-workflow` retains recon, the
three independent review checkpoints, TDD, verification, ticketing, the
edge-case sweep, git safety, commit discipline, explicit written-plan approval,
and the persistent audit copy. Step 6a routes through `delegate-decision-reviewer`, so
the original specialist methodology and capability restrictions remain intact;
the native `/goal` command remains an autonomous execution boundary.
Core skills and the Claude Code, Codex, and OpenCode adapters were not changed.

**Claims to verify on audit:**
- Known Claude-only guarantees are rejected case-insensitively in both source
  and delegated skill projections, including uppercase `.MD` inputs.
- Runtime-sensitive skills cannot appear without an explicit projection policy;
  overlay targets and source anchors fail closed.
- Generated `secrets-handling` makes policy claims without claiming installed
  Antigravity permissions or undocumented shell-startup behavior.
- The focused builder suite passes 19 tests; all 38 Python test files and both
  Node.js suites pass with Ruff, render, skill, hook, link, native 2.2.1, and
  generated-artifact checks green.

## Audit (2026-07-15)

**Auditor:** Independent Codex reviewer (`final_projection_audit_approved`)
**Verdict:** Approved
**Verified:**
- Generated `task-workflow` preserves the original approval distinction:
  `/goal` automatically approves a written plan, ordinary written plans require
  an explicit go, and inline plans without a file retain their original path.
- `/goal` launches the autonomous execution phase without intermediate
  questions, matching the official Antigravity 2.0 contract.
- Step 6a routes through `delegate-decision-reviewer`, preserving the specialist
  methodology, read-only capability contract, and required method skills.
- Policy inventory, exact overlay anchors, required overlay files, and
  case-insensitive post-projection validation fail closed for source and
  delegated skills, including uppercase `.MD` inputs.
- Commit scope is limited to the Antigravity builder, projection module, and
  tests; core and the Claude Code, Codex, and OpenCode adapters are unchanged.
**Regression scan:** The auditor independently passed 19/19 focused tests,
Ruff, native Antigravity 2.2.1 validation, generated drift checking, and
`git diff --check`. The implementation run passed all 38 Python test files,
both Node.js suites, render and skill validators, hook smoke, generated scans,
and relative-link checks.
