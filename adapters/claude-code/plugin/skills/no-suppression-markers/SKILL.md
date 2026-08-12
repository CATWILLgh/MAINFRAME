---
name: no-suppression-markers
user-invocable: false
description: Verify a coding change introduced no placeholder, suppression, skipped-test, or diagnostic-residue markers. Covers TODO/FIXME/HACK/XXX, commented-out code, skipped or focused tests (.skip/.only/xit/fit), and silenced type/lint checks (@ts-ignore, @ts-nocheck, eslint-disable, # type: ignore, # noqa, pylint: disable).
when_to_use: Trigger when wrapping up a coding task — before declaring it done, before a commit, when reviewing a diff, or when finalizing/auditing changed files for leftover shortcuts.
---

# No suppression / placeholder markers

A completion gate for code changes. It turns the product decision "No placeholder
or suppression markers in completed work" into a concrete, run-before-done check.

## What counts as a marker

- **Placeholders**: `TODO`, `FIXME`, `HACK`, `XXX`; commented-out code left "for later".
- **Stubs as pseudo-implementations** — a function whose body is a stand-in (`return null`, `return true`, `return {}`, `throw new Error("not implemented")`, Python `pass` / `raise NotImplementedError`, Java `return null` for an unimplemented contract) used **specifically as a placeholder for logic that should exist**. The nuance matters: `return null` is legitimate when null is a valid domain result (search-not-found, optional value); it is a stub when the function's contract obligates work that has not been written. Tell them apart by intent — if the docstring / signature promises behaviour the body does not deliver, it is a stub.
- **Skipped / focused tests**: `.skip(...)`, `.only(...)`, `xit`, `fit`, `xdescribe`, `fdescribe`, `@pytest.mark.skip`, `@unittest.skip`. A focused test (`.only`) silently disables every other test in the file.
- **Silenced checks**: `@ts-ignore`, `@ts-nocheck`, `eslint-disable*`, `# type: ignore`, `# noqa`, `pylint: disable`, `// nolint`.

## The rule

- These are **not allowed in work you declare complete**.
- A marker attached to behavior required by the current task means that behavior
  is unfinished. Replace it with the complete working implementation and its
  required tests. Deleting the marker, comment, or stub without delivering that
  behavior is not a resolution.
- Do not leave any marker in code delivered as complete. A genuinely unrelated
  observation belongs in the repository's ticket mechanism, not in a code marker;
  this exception cannot be used to reclassify a current task requirement as
  out of scope.
- A failing test or a type/lint error is a **contract signal**: surface it and discuss the fix. Silencing it hides the contract break instead of resolving it.
- Prefer self-documenting suppressions when one is genuinely justified and approved: e.g. `@ts-expect-error` (errors once the suppression is no longer needed) over `@ts-ignore`.

## How to check before declaring done

Scan only the files you changed, and only source files (skip docs/config — they
legitimately mention these markers):

```sh
git diff --name-only --diff-filter=d HEAD \
  | grep -Ei '\.(py|ts|tsx|js|jsx|mjs|cjs|dart|go|rb|rs|java|kt|swift|cs|cpp|c|h|scala|php|lua|sh|sql|vue|svelte)$' \
  | xargs -r grep -nE 'TODO|FIXME|HACK|XXX|@ts-(ignore|nocheck)|eslint-disable|#[[:space:]]*type:[[:space:]]*ignore|#[[:space:]]*noqa|pylint:[[:space:]]*disable|\.(skip|only)\(|\b(xit|fit|xdescribe|fdescribe)\(|\bNotImplementedError\b|throw new Error\(["'\'']TODO|throw new Error\(["'\'']not implemented'
```

Use `--cached` instead of `HEAD` to scan staged changes only. Adjust the extension
list to the project's languages.

## If markers are found

1. Deliver the behavior the marker stands for: implement the complete working
   path, restore or add the required tests, and fix the underlying type/lint
   error. The marker disappears as a consequence of finishing the work.
2. If the marker only annotated a genuinely unrelated observation, revert that
   annotation and record or update the appropriate ticket through the repository
   workflow without expanding the current task.
3. Re-run the scan until it is clean.

## Notes

- A non-blocking `PostToolUse` hook (`adapters/claude-code/plugin/hooks/scripts/scan-suppression-markers.py`)
  surfaces newly introduced markers per edit as an immediate reminder. This skill is the
  deliberate before-done gate — run it when finalizing, not just per edit.
- The hub's engineer agents in `adapters/claude-code/agents/` reference this gate in their pre-done
  verification; any agent that finalizes or reviews code should run it before declaring done.
