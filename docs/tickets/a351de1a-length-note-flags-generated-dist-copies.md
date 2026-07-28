---
id: a351de1a
title: length-quality-note flags generated dist/bundle copies whose debt is ticketed under the source path
status: open
priority: low
component: hooks
discovered: 2026-07-23
discovered-from: []
tags: ["hooks", "false-positive", "length-gate", "generated-output"]
---

# a351de1a: length-quality-note flags generated dist/bundle copies whose debt is ticketed under the source path

## What was observed

The Stop advisory `length-quality-note.py` flagged
`dist/opencode/bundle-v2/plugins/mainframe-gates.js` (405 lines) with "No ticket
currently names these files". The file is a generated bundle copy (produced by
`adapters/opencode/build_bundle.py` during install); its source,
`adapters/opencode/plugins/mainframe-gates.js` (401 lines), IS already ticketed as
length debt in [#057688a7](057688a7-mainframe-gates-length-and-event-complexity.md).
The ticket suppression (`tickets_mentioning`) matches by path text, so the
different-path generated copy escapes suppression.

## Why it is a problem

Noise in the advisory channel: every session that leaves a stale generated bundle in
the tree re-surfaces already-acknowledged debt under a path nobody should edit
(`dist/` is render-only by repo policy — fixing the copy is forbidden; fixing the
source is already tracked). Repeated known-stale advisories train the reader to skim
past the note, which erodes the signal for genuinely new violations.

## Why it is not a duplicate

- [#057688a7](057688a7-mainframe-gates-length-and-event-complexity.md) — tracks the
  length/complexity debt of the gates plugin source itself; this ticket is about the
  length hook's suppression logic missing generated copies of ticketed sources.
- [#e43819ea](e43819ea-length-gate-non-python-function-length.md) — tracks the
  function-length language-scope gap; unrelated mechanism.

## What probably needs to be done

Pick one (requires a design decision):

1. Exclude generated render/bundle outputs from the scan — skip paths under `dist/`
   when the repository is the hub itself, or more generally support a per-repo
   exclusion convention. Simplest, but hub-specific paths must not leak into the
   shared detector (agnosticism) — needs a neutral mechanism (e.g. honor
   `.gitignore`-untracked build dirs, or a marker file).
2. Keep scanning but map a flagged file to tickets by basename as a fallback when the
   full path finds no ticket (`mainframe-gates.js` would then match #057688a7).
   Cheaper, small false-suppression risk on generic basenames.

## Acceptance criteria

- A stale generated copy of an already-ticketed over-length source no longer
  produces an advisory note (verified by a fixture test mirroring the real layout:
  ticket names the source path, scan sees the generated copy).
- Genuinely new over-length files (tracked or untracked, outside generated outputs)
  still fire — existing tests in `tools/test_length_quality_note.py` stay green.

## Sources

- `dist/claude-code/plugin/hooks/scripts/length-quality-note.py` — the advisory hook
- `dist/claude-code/plugin/hooks/scripts/_length_check.py` — shared length lib
- `adapters/opencode/plugins/mainframe-gates.js:1` — 401-line ticketed source
- `adapters/opencode/build_bundle.py` — produces the flagged bundle copy
