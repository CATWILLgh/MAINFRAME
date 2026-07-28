---
id: 4ec0108f
title: Recursive-delete gate misclassifies wrapper options, executable paths, and quoted operators
status: open
priority: high
component: permissions
discovered: 2026-07-15
discovered-from: []
tags: ["security", "destructive-actions", "command-parsing", "permissions"]
---

# 4ec0108f: Recursive-delete gate misclassifies wrapper options, executable paths, and quoted operators

## What was observed

The destructive-command detector recognizes a recursive delete only when the parsed command starts with the literal token `rm`. Its wrapper normalizer does not handle `env`, command paths such as `/bin/rm`, or wrapper-specific options. Plain `xargs rm -rf …` is normalized, but `xargs -0 rm -rf …` leaves `-0` as the leading token and is missed; `-I` and similar forms have the same structural problem. The shared permissions also broadly allow `Bash(env *)`.

Direct probes confirmed that a plain recursive delete outside the project reaches the confirmation branch, while equivalent `env`, absolute-path, and parameterized-`xargs` forms are deferred rather than classified as destructive.

The tokenizer also loses quote provenance: `shlex.split` removes quotes and `_split_operators` then splits operator characters that were originally quoted. A read-only parser probe turned `echo 'a|b'` into two subcommands and `rm -rf 'inside;name'` into an `rm` command targeting only `inside` plus a second command. This contradicts the function's own quote-aware contract and can make the safety decision describe a different command from the shell's actual command.

## Why it is a problem

The safety property depends on command spelling instead of command behavior. A destructive operation can therefore bypass the explicit acknowledgement boundary without using an exotic shell feature.

## Why it is not a duplicate

- [#b86bf383](b86bf383-codex-gates-v1-followups.md) asks how Codex treats an already-produced `ask` verdict. This ticket covers commands that never produce that verdict.

## What probably needs to be done

- Define and test the supported normalization boundary for executable paths, environment wrappers, and command delegation.
- Remove or narrow permission entries that bypass the detector until equivalent forms are classified safely.
- Prefer structured command analysis with conservative handling of ambiguous destructive forms.

## Acceptance criteria

- Direct, absolute-path, `env`-wrapped, plain-`xargs`, and parameterized-`xargs` recursive deletes receive the intended documented safety decision.
- Benign wrapper use does not become a blanket prompt source.
- Tests cover combined short flags, long flags, `--`, quoted and unquoted separators, wrappers, and paths outside the project.

## Sources

- `core/gates/detectors/path-validation.py:81-120`, `core/gates/detectors/path-validation.py:229-269`
- `core/permissions/rules.json:76`
- Direct command-shape and tokenizer probes, 2026-07-15.
