---
id: b332ae65
title: The ZCode builder test file executes no tests and reports success
status: open
priority: high
component: tools
discovered: 2026-08-08
discovered-from: []
tags: ["tests", "ci", "zcode", "silent-pass"]
---

# b332ae65: The ZCode builder test file executes no tests and reports success

## What was observed

`tools/test_build_zcode.py` defines 10 tests and has **no `if __name__ == "__main__"` runner**, unlike its sibling suites. Running it the documented way prints nothing and exits 0:

```
$ python3 tools/test_build_zcode.py ; echo $?
0
```

CI runs it in exactly that way — the hook-suite loop at `.github/workflows/ci.yml:53` iterates `tools/test_*.py` and this file is not in the exclusion list — so the step is green while executing zero assertions. The tests only run under `python3 -m pytest`, which CI never invokes (`pytest` appears nowhere in the workflow).

Proven by a live breakage: a change to `build.CORE_INSTRUCTION_FILES` on 2026-08-08 broke `test_missing_instruction_part_and_invalid_skill_fail_closed`, which pins the builder's fail-closed guard. Every direct run stayed green. The failure surfaced only when the file was invoked through pytest by hand:

```
$ python3 -m pytest -q tools/test_build_zcode.py
1 failed, 9 passed
```

The file also imports `pytest` at module level, which is why it cannot simply be added to the stdlib-only step.

## Why it is a problem

These 10 tests cover the ZCode projection's fail-closed behaviour — unmapped neutral instruction parts, missing instruction parts, invalid skill frontmatter, tool-evidence limits, deterministic partitioning of private methods. That is precisely the class of guard whose whole value is failing when someone changes the source layout. It has been reporting success without checking anything.

It is worse than a merely red suite. A red suite trains people to skim; a suite that is green while inert gives active false assurance, and nothing distinguishes it from a real pass.

## Why it is not a duplicate

- [#65f72bdc](65f72bdc-telemetry-full-suite-isolation.md) — flaky tests that fail under full-suite load; those at least run.
- [#d887a55e](d887a55e-codexstate-process-test-timeout.md) — a genuinely executing test with a timing-dependent result.

Both are about tests that run and give a wrong answer. This one never runs.

## What probably needs to be done

- Decide the runner contract for `tools/test_*.py`: either every file carries a `__main__` block and CI keeps invoking them directly, or CI adopts `pytest` for the files that need it. Requires verification — the stdlib-only step exists so a dependency-free subset stays runnable, and `pytest` at module level conflicts with that.
- Audit every file under `tools/` for the same shape: no `__main__` block, or a `__main__` block that does not propagate a non-zero exit. Count how many assertions CI has been skipping.
- Whichever contract is chosen, add a check that fails when a `tools/test_*.py` file would execute zero tests under the documented invocation.

## Acceptance criteria

- `python3 tools/test_build_zcode.py` executes all 10 tests and exits non-zero when any fails.
- Deliberately breaking one assertion turns CI red.
- No other file under `tools/` can execute zero tests and report success; a check enforces it.

## Sources

- `tools/test_build_zcode.py` — 10 `def test_*`, no `__main__` block, `import pytest` at module level
- `.github/workflows/ci.yml:53-78` — the loop and its exclusion list
- Live evidence 2026-08-08: direct run green, pytest run `1 failed, 9 passed`
