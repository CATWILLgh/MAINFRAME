---
id: 09b19ada
title: Claude plugin manifest has no source mapping or CI validation
status: approved
priority: medium
component: claude-code-delivery
discovered: 2026-07-15
discovered-from: []
tags: ["claude-code", "plugin", "manifest", "render", "ci"]
---

# 09b19ada: Claude plugin manifest has no source mapping or CI validation

## What was observed

`dist/claude-code/plugin/.claude-plugin/plugin.json` is the registration root for the shipped Claude Code plugin, but it is maintained directly inside a tree declared generated-only. It has no source mapping in `tools/render_core.py`. CI validates render mappings, skills, and the umbrella instructions, but neither validates the manifest schema nor runs `claude plugin validate`.

## Why it is a problem

Deleting or corrupting this single file can stop the entire plugin from registering in the Claude CLI, official extension, and Desktop Code Local while all current repository checks remain green. Direct ownership inside `dist/` also contradicts the repository's source-of-truth rule.

## Why it is not a duplicate

[#643a4490](643a4490-render-check-guard-residual-gaps.md) addressed an orphan inside the mapped hook tree. [#f9d6a8b0](f9d6a8b0-claude-desktop-mainframe-verification-gap.md) covers live-session registration behavior. Neither gives the manifest a source or a validation gate.

## What probably needs to be done

- Move the manifest to an authored Claude adapter path and render it into `dist/claude-code/plugin/.claude-plugin/`.
- Add manifest drift and schema tests.
- Run the installed CLI's plugin validator in a compatible CI job or add an equivalent hermetic validator, with the CLI check retained in local release verification.
- Define how the manifest version is advanced; the static-version symptom also belongs to [#f9d6a8b0](f9d6a8b0-claude-desktop-mainframe-verification-gap.md).

## Acceptance criteria

- The manifest has exactly one authored source outside `dist/`.
- `render_core.py --check` fails if the rendered manifest is absent, changed, or orphaned.
- CI rejects a malformed manifest and a plugin that fails registration validation.
- The three local Claude hosts still validate and load the rendered plugin.

## Sources

- `dist/claude-code/plugin/.claude-plugin/plugin.json:1-10`
- `tools/render_core.py:37-62`, `tools/render_core.py:509-520`
- `.github/workflows/ci.yml:61-95`

## Resolution (2026-07-15)

**Implementer:** Codex
**Commit:** `ff0f09b7108844e42b7ec01db9207dcd833af50c`
**Summary:** The Claude plugin manifest now has one authored adapter source, participates in the bidirectional render contract, and is validated by the pinned official Claude Code CLI in an isolated CI home. The delivered manifest bytes and hash remain unchanged.
**Claims verified:**
- `adapters/claude-code/plugin.json` is the sole authored source and maps byte-for-byte to `dist/claude-code/plugin/.claude-plugin/plugin.json`.
- Missing source, missing render, byte drift, and an orphan sibling all fail the Tier 1 manifest contract tests.
- CI installs `@anthropic-ai/claude-code@2.1.177` and runs `claude plugin validate --strict` with isolated `HOME` and `CLAUDE_CONFIG_DIR`.
- The source and delivered manifest both retain SHA-256 `db678d166914343228c776760c6d0391050a2c71e42f7ebc456e74255cee44de`.
- Plugin version changes remain explicitly deferred to the live-session parity probe `#f9d6a8b0`; this repair does not change live delivery.

## Audit (2026-07-15)

**Auditor:** Independent read-only subagent
**Verdict:** Approved after one Low documentation defect was corrected.
**Evidence:**
- All 30 Python test files passed; the manifest suite passed 5/5 and renderer suite 36/36.
- `render_core.py --check`, skill validation, umbrella-instruction validation, Ruff, the OpenCode JavaScript gate suite, YAML parsing, marker scan, and `git diff --check` passed.
- Installed Claude Code 2.1.177 accepted the rendered plugin with `plugin validate --strict` under a temporary home.
- The initial audit found a Markdown link to the gitignored ticket directory in `core/README.md`; it was replaced by the plain identifier `#f9d6a8b0`, and the follow-up audit approved the result.
- Extension and Desktop were not relaunched during this repair. Their fresh-load evidence is recorded in `#f9d6a8b0`, and the plugin bytes they consume were proven unchanged here.
