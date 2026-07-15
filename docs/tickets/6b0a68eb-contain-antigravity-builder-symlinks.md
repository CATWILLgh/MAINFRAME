---
id: 6b0a68eb
title: Keep Antigravity builder inputs inside their declared source roots
status: approved
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

- `adapters/antigravity-2/source_boundary.py:22-95`
- `adapters/antigravity-2/build_antigravity.py:122-160`
- `adapters/antigravity-2/build_antigravity.py:230-268`
- `tools/test_build_antigravity.py:105-224`
- [Python `Path.resolve()`](https://docs.python.org/3/library/pathlib.html#pathlib.Path.resolve)
- [Python `Path.rglob()`](https://docs.python.org/3/library/pathlib.html#pathlib.Path.rglob)

## Resolution (2026-07-15)

**Implementer:** Codex
**Commit:** 6cc2a37a54b742fc599261e801383ad506ea81c4
**Summary:** The Antigravity builder now resolves every projected source through
one adapter-owned boundary before reading. A source must stay inside both the
repository and its declared tree. Contained file links remain supported and are
copied by value under their lexical output path; directory, external, broken,
and cyclic links fail with a repository-relative source error. Rules, each
individual skill, agents, detector/rule/memory trees, and the shared bridge
directory all use the same validation path.

**Compatibility evidence:** The ordinary 18-file fixture and the complete
148-file repository projection were compared with the builder from the parent
commit and matched byte-for-byte. The Claude Code-derived core and its render
targets were not changed.

## Audit (2026-07-15)

**Auditor:** Independent Codex reviewer (`builder_ticket_audit`)
**Verdict:** Approved
**Verified:**
- Excluded `__pycache__`, `.pyc`, and `.pyo` entries are validated before they
  are omitted, so their names cannot hide a directory or external link.
- Oversized-rule, missing-bridge, invalid-link, and containment errors expose
  only lexical repository-relative source paths and suppress filesystem causes.
- Tests cover contained, external, broken, cyclic, file, nested-directory, and
  source-root links across rules, skills, agents, detectors, runtime rules,
  memory, and direct bridge files.
- Resolved paths are used for reads while output names and provenance remain
  lexical; the remaining concurrent-tree replacement window is proportionate
  to a local build whose input tree is already writable by the caller.

**Regression scan:** The final implementation passed all 38 Python test files,
both Node suites, Ruff, the neutral-core render check, the `CLAUDE.md` and skill
validators, generated Antigravity skill validation, `git diff --check`, and
native Antigravity 2.2.1 validation. The targeted builder suite passed 16/16.
