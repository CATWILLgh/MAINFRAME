---
id: 6b0a68eb
title: Keep Antigravity builder inputs inside their declared source roots
status: open
priority: medium
component: antigravity-builder
discovered: 2026-07-15
discovered-from: []
tags: ["antigravity", "builder", "symlink", "supply-chain", "security"]
---

# 6b0a68eb: Keep Antigravity builder inputs inside their declared source roots

## What was observed

The builder accepts any `rglob()` entry for which `is_file()` is true, then reads
its bytes. A controlled skill containing `linked.txt -> ../outside.txt` copied
the external file's contents into the generated plugin. There is no resolved-path
containment check for skills, detectors, rules, or other copied trees.

## Why it is a problem

An accidental or malicious symbolic link can package private local data or
unreviewed code into a globally loaded plugin. The generated manifest gives no
indication that bytes came from outside the repository.

## Why it is not a duplicate

- Portable memory rejects symbolic-link targets at runtime, but that protection
  does not apply to build inputs.
- [#3efdbdb9](3efdbdb9-correct-antigravity-runtime-skill-guarantees.md) covers
  semantic projection of legitimate files, not filesystem containment.

## What probably needs to be done

1. Resolve every discovered source and require it to remain within the declared
   source root before reading.
2. Decide whether contained symbolic links are copied by value or rejected.
3. Reject external, broken, and cyclic links with a precise source-path error.
4. Apply one helper consistently to `_copy_tree`, `_copy_skill`, and rule input.
5. Ensure generated provenance names the repository-relative source only.

## Acceptance criteria

- Tests cover contained, external, broken, cyclic, file, and directory links.
- No generated file can originate outside its declared repository source root.
- A rejected build names the offending relative path without exposing the
  external file contents.
- Ordinary source trees generate byte-identical output.
- CI checks both representative skills and detector/runtime trees.

## Sources

- `adapters/antigravity-2/build_antigravity.py:115-148`
- `adapters/antigravity-2/build_antigravity.py:151-170`
- `tools/test_build_antigravity.py`
