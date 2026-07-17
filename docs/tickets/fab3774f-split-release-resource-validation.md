---
id: fab3774f
title: Split release resource validation into bounded stages
status: open
priority: low
component: installer
discovered: 2026-07-17
discovered-from: ["keyless Context7 semantic configuration planning"]
tags: ["release-contract", "maintainability", "python"]
---

# fab3774f: Split release resource validation into bounded stages

## What was observed

`tools/release_contract.py::_validate_resources` is 75 lines and combines
resource shape, source-file, lifecycle capability, external-state, shell, and
owned-JSON validation in one function.

## Why it is a problem

The mixed responsibilities make future release-schema changes harder to review
and exceed the project's 60-line function limit. A change to one resource
strategy must currently be checked against several unrelated branches in the
same function.

## Why it is not a duplicate

Existing release-contract tickets cover missing behavior, publication, or
authentication. None records the internal decomposition of resource validation.

## What probably needs to be done

- Extract source and target validation from lifecycle capability validation.
- Keep the existing exception order and messages stable where callers test them.
- Run every release, JSON ownership, and adapter bundle test after the split.

## Acceptance criteria

- Every resulting function is at most 60 lines.
- The bundle contract accepts and rejects the same fixtures as before.
- Full Python release and adapter bundle suites pass.

## Sources

- `tools/release_contract.py`
- `tools/test_release_contract.py`
- `tools/test_release_json.py`
- `tools/test_release_json_ownership.py`
