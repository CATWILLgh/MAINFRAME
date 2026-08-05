---
id: ac703f8b
title: Merge ZCode agent updates with local user preferences
status: open
priority: medium
component: zcode-desktop
discovered: 2026-08-05
discovered-from: ["#aeb5d9b0"]
tags: ["zcode", "subagents", "configuration", "merge", "ownership"]
---

# ac703f8b: Merge ZCode agent updates with local user preferences

## What was observed
ZCode stores local model, color, and tool selections in the same Markdown file
as the MAINFRAME-generated agent prompt. A live edit added those frontmatter
fields and rewrote the YAML formatting while leaving the generated body intact.

The first safe regular-file lifecycle can detect that the file changed and
preserve it as a whole. It cannot update the managed prompt while retaining
only the user's fields because the current ownership registry stores release
and artifact identity, not the base document or field-level provenance.

## Why it is a problem
After any local preference change, whole-file preservation prevents future
MAINFRAME prompt and permission fixes from reaching that agent automatically.
Blind two-input merging has the opposite failure mode: it can overwrite a user
edit when both the release and the user changed the same field or body region.

## Why it is not a duplicate
- [#aeb5d9b0](aeb5d9b0-zcode-subagent-symlinks-not-discovered.md) restores
  native discovery with writable regular files and preserves changed files as
  configuration conflicts. This ticket covers a later semantic update path for
  those already customized files.
- [#0e9af5a9](0e9af5a9-zcode-plugin-delivery-contract.md) evaluates read-only
  plugin packaging, which does not provide editable user-agent preferences.

## What probably needs to be done
Define a strict ZCode agent-document schema and a three-way merge contract using
the previous managed document, the new release document, and the live user
document. Give every generated frontmatter field and the managed body an
explicit ownership rule. Preserve unknown fields and formatting where the YAML
library permits it; surface same-field and body conflicts instead of choosing a
winner silently.

Keep this document policy outside the generic filesystem transaction. The
transaction should publish only a fully resolved candidate and retain the same
rollback, recovery, and content-identity guarantees as other writable files.

## Acceptance criteria
- Tests cover user-only, release-only, identical, and conflicting edits for
  every managed field and the prompt body.
- Local model, color, and explicitly selected tools survive a compatible
  MAINFRAME update.
- Managed prompt and description updates land when the corresponding live
  regions still equal the previous managed version.
- Ambiguous YAML, duplicate keys, unsupported constructs, and same-region
  conflicts preserve the live file and produce an actionable preview.
- Uninstall and purge behavior states exactly whether customized agent data is
  retained, backed up, or removed, and requires confirmation before deletion.

## Sources
- `adapters/zcode-desktop/build_zcode.py:143-176`
- `internal/linkownership/registry.go:25-32`
- `docs/tickets/aeb5d9b0-zcode-subagent-symlinks-not-discovered.md`
- Live ZCode Desktop 3.6.5 edit of `decision-reviewer` on 2026-08-05
