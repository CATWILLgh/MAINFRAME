---
name: mainframe-project-instructions-audit
description: Audit project instructions for conflicting rules, duplication, stale references, and unnecessary context when guidance maintenance is requested. Do not use for ordinary code review.
---

# Audit project guidance

First consult the current official documentation for the product's instruction
loading, precedence, skills, and active surface. Reconstruct the instructions
actually received in representative working directories, including inherited
global rules. Keep unrelated global configuration read-only.

Check meaningful contradictions, repeated instructions, misplaced scope,
unreachable guidance, broken references, stale tool or agent names, excessive
always-loaded text, and role assumptions that do not fit all recipients.
A word or line count alone is not proof of a semantic defect.

If the task is audit-only, return findings with their owning files and practical
consequences. If maintenance is authorized, repair supported defects and
simplify wording while preserving meaning and user edits. Ask only when a
conflict changes a product decision, authority, or another unresolved user
choice. Do not turn each semantic improvement into mandatory approval.

Reconstruct the changed chains again and verify links, discovery, effective
precedence, and representative use where available. Report the affected
scope, actual checks, footprint changes, and unresolved limits without claiming
that static validation proved model behavior.
