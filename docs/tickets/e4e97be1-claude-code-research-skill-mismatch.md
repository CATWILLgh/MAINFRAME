---
id: e4e97be1
title: claude-code-research skill path contains Codex-only instructions
status: open
priority: low
component: codex-local-runtime
discovered: 2026-07-15
discovered-from: []
tags: ["skills", "research", "claude-code", "codex", "routing"]
---

# e4e97be1: claude-code-research skill path contains Codex-only instructions

## What was observed

The available skill is stored at `.agents/skills/claude-code-research/SKILL.md`, but its frontmatter name is `Codex-research`, its description and procedure repeatedly target Codex, and its "When NOT to use" section excludes non-Codex questions. Selecting it for a Claude Code Desktop investigation therefore routes to the wrong installed binary and documentation surface.

The `.agents/` directory is local and untracked, so the source that generated or installed this mismatch still requires identification.

## Why it is a problem

The filename and catalog position invite Claude Code research while the body instructs the opposite. An agent can confidently inspect Codex internals and cite irrelevant evidence for a Claude Code decision.

## Why it is not a duplicate

- [#d84dc65e](d84dc65e-code-audit-dimension-naming-gaps.md) covers audit-dimension terminology, not skill identity or routing.

## What probably needs to be done

- Locate the source-of-truth that installs `.agents/skills/claude-code-research`.
- Either restore a real Claude Code procedure under that path or rename the directory/catalog entry to `codex-research` and add the missing Claude Code skill separately.
- Add validation that the directory name, frontmatter `name`, description, and declared target product agree.

## Acceptance criteria

- Invoking Claude Code research selects a procedure that inspects the installed Claude Code binary and official Anthropic documentation.
- Codex research remains available under an unambiguous Codex name.
- A validator fails on a product-name mismatch between the skill path and frontmatter/body.

## Sources

- `.agents/skills/claude-code-research/SKILL.md:1-30`
- Observed during the Claude Code Desktop investigation, 2026-07-15.

## Re-occurrence noted (2026-07-15)

**Noticed during:** Claude plugin manifest source and validation repair (`#09b19ada`)
**Where:** `.agents/skills/claude-code-research/SKILL.md`
**Additional details:** The repository instructions required the Claude Code research procedure for manifest behavior, but the selected skill again routed exclusively to Codex and named unavailable `Codex-guide` and `mainframe:web-search` roles. The investigation had to fall back to the installed `claude` CLI and official Claude Code documentation.
