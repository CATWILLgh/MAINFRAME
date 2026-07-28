---
id: 4b83441a
title: Missing permission source produces OpenCode allow-all policy and replaces user rules
status: approved
priority: high
component: opencode-layer
discovered: 2026-07-15
discovered-from: []
tags: ["security", "permissions", "opencode", "fail-open", "configuration"]
---

# 4b83441a: Missing permission source produces OpenCode allow-all policy and replaces user rules

## What was observed

If `core/permissions/rules.json` is absent, `_load_json()` returns `None` and the generator substitutes an empty object. `project_permissions({})` still emits `bash: {"*": "allow"}`, and `merge_config()` replaces the user's complete `permission` block with that generated policy. Invalid JSON and ordinary read errors currently raise before the write; they are regression cases to preserve, not part of the reproduced fail-open defect.

## Why it is a problem

A missing security source is converted into a valid-looking permissive configuration. The same failure also destroys the user's stricter rules, so recovery requires external backup rather than a corrected rerun.

## Why it is not a duplicate

- [#6d09e7be](6d09e7be-install-sh-silent-success-on-missing-source.md) covers missing installer artifacts and dangling links, not missing permission input or policy replacement.

## What probably needs to be done

- Make the permission source mandatory and schema-validated before any output is written.
- Abort generation without touching the existing configuration when the source is absent; preserve the current fail-closed result for invalid or unreadable input.
- Separate hub-owned rules from user-owned rules so updates compose without replacing unrelated policy.

## Acceptance criteria

- Missing, invalid, or unreadable `rules.json` causes a non-zero generator exit and leaves the target configuration byte-for-byte unchanged; only the absent-file case is a current regression.
- An empty rule set cannot silently produce a broad allow policy.
- User-defined permission entries survive a successful hub update unless they conflict with an explicitly owned key.

## Sources

- `adapters/opencode/build_opencode.py:170-193`, `adapters/opencode/build_opencode.py:213-228`
- `adapters/opencode/build_opencode.py:334-348`

## Resolution (2026-07-15)

**Implementer:** Codex primary agent
**Commit:** `0624718440c09672542773675e48be31074cb040`
**Summary:** OpenCode generation now rejects missing, malformed, duplicate-key, empty, allow-only, and unprojectable permission sources before any output write. A versioned `0600` sidecar records only explicit top-level action ownership, so scalar policies, user actions, wildcard coverage, modifications, and deletions are preserved. Previously generated actions are updated or removed only while their current value still proves ownership.
**Claims to verify on audit:**
- Every invalid permission source and ownership state fails before configuration, state, backup, or agent output is written.
- First-run migration never adopts an existing action merely because its value resembles generated output.
- User scalar rules, exact actions, wildcard actions, modifications, and deletions survive repeated generation.
- Action matching follows OpenCode's slash, `*`, `?`, trailing ` *`, literal-regex-character, and platform case rules.
- The sidecar is secret-free, atomically replaced with mode `0600`, and dry-run creates nothing.
- No live render or installation was performed.

## Audit (2026-07-15)

**Auditor:** Independent read-only subagent (`opencode_permissions_final_review`)
**Verdict:** Approved after one rejected round and repair
**Verified:**
- The first review found a High-severity mismatch: Python's generic filename matcher mishandled OpenCode's optional trailing ` *` rule and bracket literals. Both directions were reproduced with failing tests before the implementation was replaced with OpenCode-equivalent action matching.
- The repaired matcher passed 26 curated cases, 2,000 deterministic randomized pairs, and 3,000 randomized patterns against the generated `bash` and `read` actions.
- Source and sidecar validation, conservative first-run migration, scalar and wildcard preservation, ownership updates/removals, user modification/deletion, dry-run behavior, secret isolation, file mode, and failure order were independently reviewed.
- `tools/test_build_opencode_config.py` passed 29/29; `tools/test_build_opencode.py` passed 14/14; all 31 `tools/test_*.py` files passed; syntax compilation, `render_core.py --check`, diff hygiene, line limits, and a real-repository dry run passed.
**Commit scope:** Only the OpenCode builder, its new permission helper, its focused tests, and permission-layer documentation were committed. User-owned `dist/claude-code/settings.json`, `.agents/`, and `.codex/` changes remained outside the commit.
**Known limit:** Cross-file configuration/sidecar publication is tracked in `#140f9466`; a state-write failure cannot delete user policy but may leave stale ownership metadata until recovery.
