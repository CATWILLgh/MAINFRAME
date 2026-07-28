---
id: f6391df5
title: Security Stop gates omit untracked Python and JavaScript source files
status: open
priority: high
component: gates
discovered: 2026-07-15
discovered-from: []
tags: ["security", "gates", "git", "untracked-files", "test-gap"]
---

# f6391df5: Security Stop gates omit untracked Python and JavaScript source files

## What was observed

`changed_files()` builds the scanner input from `git diff HEAD --name-only --diff-filter=AM`. Git does not include untracked files in that result. Both Python and Node.js security Stop gates return early when this list is empty, even though `changed_line_ranges()` separately knows how to classify untracked files.

A direct audit probe created an untracked source file and observed an empty Stop-gate input list. The existing helper test stages its new file before asserting discovery, so it does not cover this path.

## Why it is a problem

New source files can contain the highest-risk code in a change, yet the final security gate can silently skip them. The later delta classifier cannot repair the omission because the external scanner never receives those files.

## Why it is not a duplicate

- [#74beb0fb](74beb0fb-opencode-stop-gate-emulation.md) covers OpenCode end-of-turn emulation; it does not cover the shared file-selection defect.

## What probably needs to be done

- Make the shared file selector union tracked changes with `git ls-files --others --exclude-standard`.
- Preserve extension filtering, existence checks, deterministic ordering, and the existing fail-safe behavior when Git is unavailable.
- Add public-contract tests for untracked, staged-new, modified, ignored, deleted, and unrelated-extension files across both Stop gates.

## Acceptance criteria

- An untracked `.py`, `.js`, or `.ts` file is scanned by the corresponding Stop gate.
- Ignored, deleted, and unsupported files remain excluded.
- The Python and Node.js security delta suites pass without weakening findings.

## Sources

- `core/gates/detectors/_hooklib.py:167-191`, `core/gates/detectors/_hooklib.py:197-237`
- `core/gates/detectors/python-security-stop-gate.py:122-130`
- `core/gates/detectors/nodejs-security-stop-gate.py:150-158`
- `tools/test_hooklib.py:138-150`
- Direct audit probe, 2026-07-15: an untracked source file produced an empty `changed_files()` result.
