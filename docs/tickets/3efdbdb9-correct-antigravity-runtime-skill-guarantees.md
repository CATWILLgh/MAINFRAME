---
id: 3efdbdb9
title: Remove Claude-only guarantees from projected Antigravity skills
status: open
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

- `adapters/antigravity-2/build_antigravity.py:30-75`
- `adapters/antigravity-2/build_antigravity.py:151-170`
- `dist/antigravity-2/plugin/skills/secrets-handling/SKILL.md:17-30`
- `docs/layers/permissions.md:14-21`
- <https://antigravity.google/docs/ide-settings>
