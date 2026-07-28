---
id: 95878fc4
title: Codex permission render emits an invalid deny decision and the whole policy fails to load
status: approved
priority: high
component: codex-adapter
discovered: 2026-07-15
discovered-from: []
tags: ["codex", "permissions", "execpolicy", "rules", "runtime-validation", "security"]
---

# 95878fc4: Codex permission render emits an invalid deny decision and the whole policy fails to load

## What was observed

`adapters/codex/build_codex.py` copies the neutral source tier name directly into each Codex `prefix_rule`. This produces `decision="deny"` entries in `dist/codex/rules/mainframe.rules` and the installed `~/.codex/rules/mainframe.rules`.

The installed Codex CLI 0.144.1 rejects that value. A direct parser check:

```text
codex execpolicy check --rules ~/.codex/rules/mainframe.rules -- git status
```

fails at the first deny entry with `invalid decision: deny`. The supported restrictive decision is `forbidden`; interactive review uses `prompt`. Because parsing stops at line 79, the complete MAINFRAME rules file fails to load, including the valid allow prefixes before that line.

The builder also omits every source `ask` rule on the assumption that Codex prompts by default instead of projecting it to `prompt`. Unit tests compare generated strings but never run the installed Codex policy parser, so all 28 test files pass while the deployed policy is invalid.

## Why it is a problem

The Codex adapter claims to deliver MAINFRAME safety policy through `mainframe.rules`, but the runtime cannot parse the file. This creates false assurance around destructive-command restrictions and removes the entire projected permission layer rather than weakening only one rule.

Hooks still provide some independent protection, but they do not make an invalid permission policy acceptable or equivalent.

## Why it is not a duplicate

- [#4f9a48cc](4f9a48cc-codex-observability-docs-incomplete.md) covers missing Codex inventory and observability, not an invalid installed policy.
- [#b86bf383](b86bf383-codex-gates-v1-followups.md) covers Codex hook behavior, not `execpolicy` parsing.
- [#d189a02a](d189a02a-adapter-metadata-parser-drift.md) covers shared frontmatter parsing, not permission decision values.

## What probably needs to be done

- Map neutral decisions explicitly per target: `allow` to `allow`, `deny` to `forbidden`, and `ask` to `prompt` where a safe prefix is projectable.
- Stop using source tier names as target decision strings.
- Run `codex execpolicy check` against the complete generated file as a build and installation gate.
- Add representative behavioral checks for one allowed, one prompted, and one forbidden command.
- Make installation fail before linking when the installed Codex parser rejects the generated policy.

## Acceptance criteria

- `codex execpolicy check --rules dist/codex/rules/mainframe.rules -- <command>` parses the complete file without error.
- A projected deny rule returns `forbidden`, an ask rule returns `prompt`, and an allow rule returns `allow` on representative commands.
- The installed `~/.codex/rules/mainframe.rules` passes the same parser and behavioral checks.
- Tests invoke the real installed parser when available and have a deterministic schema/fixture fallback when it is not.
- `install.sh --codex` cannot report success after generating an invalid policy.

## Sources

- `adapters/codex/build_codex.py:578-637` — current tier projection and direct decision rendering.
- `dist/codex/rules/mainframe.rules:79` — first invalid `decision="deny"` entry.
- Live probe, 2026-07-15: Codex CLI 0.144.1 rejects both rendered and installed MAINFRAME rules with `invalid decision: deny`.
- `tools/test_build_codex.py` — generator tests do not invoke `codex execpolicy check`.
- [Rules — Codex documentation](https://developers.openai.com/codex/rules) — valid decisions are `allow`, `prompt`, and `forbidden`.

## Resolution (2026-07-15)

**Implementer:** Codex
**Commits:** `039251d62556df3ba6c8e344141e251cae6da74d`
**Summary:** The adapter now maps neutral tiers explicitly to `allow`, `prompt`, and `forbidden`, validates the complete rules file with the installed Codex parser before publication, and returns a failed installer status when that validation fails. Rules publication is atomic, and deterministic fallback tests cover environments without Codex.
**Claims to verify on audit:**
- The rendered and installed rules parse with Codex CLI 0.144.1 and return `allow`, `prompt`, and `forbidden` for the three representative probes.
- Native validation completes before the first generated-output write, and validation failure preserves the existing output.
- All 29 Python test files, the neutral-core render check, shell syntax, and the Codex installer dry run pass.
- The commit contains no user-owned `dist/claude-code/settings.json`, `.agents/`, or `.codex/` changes.

## Audit (2026-07-15)

**Auditor:** Codex independent reviewer (`codex_rules_final_review`)
**Verdict:** Approved
**Verified:**
- Runtime decisions — confirmed with Codex CLI 0.144.1 against both `dist/codex/rules/mainframe.rules` and the installed `~/.codex/rules/mainframe.rules`: `git add .` returned `allow`, `sudo true` returned `prompt`, and `rm -rf /` returned `forbidden` while also matching the broader `prompt` rule.
- Publication ordering — confirmed by inspection of `adapters/codex/build_codex.py`: rendering and native validation complete before `_write_skills` and the atomic rules write. `test_native_validation_failure_precedes_all_publication` confirmed that a decision mismatch leaves the existing rules unchanged and creates no skills output.
- Regression checks — confirmed: all 29 `tools/test_*.py` files passed; `tools/test_build_codex.py` passed 26/26 tests; `tools/test_install_codex.py` passed 2/2 tests; `python3 tools/render_core.py --check`, `bash -n install.sh`, and `./install.sh --codex --dry-run` all exited successfully.
- Commit scope — confirmed with `git show --name-status 039251d62556df3ba6c8e344141e251cae6da74d`: only the six implementation, test, documentation, and CI files named in the resolution were committed. User-owned `dist/claude-code/settings.json`, `.agents/`, and `.codex/` remained outside the commit.
**Regression scan:** Full Python test-file sweep completed with 29 files and 0 failures. The commit also passed `git diff --check`; no added suppression markers, placeholder markers, or debug residue were found.
**Notes:** No blocking or minor audit findings. The installed rules path is a symlink to the verified rendered rules file, and both paths were nevertheless probed independently.
