---
id: 29b3de49
title: recon.py collect() mislabels package_manager as "poetry" for any pyproject with a [tool.*] section
status: closed
priority: low
component: skills
discovered: 2026-06-14
discovered-from: []
tags: ["python", "recon", "bug", "package-manager"]
---

# 29b3de49: recon.py collect() mislabels package_manager as "poetry"

## What was observed

In `plugin-dist/skills/python-backend-patterns/recon.py`, `collect()` sets
`package_manager = "poetry"` for essentially any project that has a `pyproject.toml`
with any `[tool.*]` section — even a pip / PEP 621 project with no Poetry at all.

Surfaced via the type-check-gate smoke (ADR 0083): a fixture with `[tool.pyright]` and
`[project]` (no Poetry, no lockfile) reported `package_manager: poetry`.

Root cause — `recon.py:39-42`:
```python
poetry_deps = data.get("tool", {}).get("poetry", {}).get("dependencies", {})
if isinstance(poetry_deps, dict):   # always True — .get(..., {}) returns a dict
    deps.extend(poetry_deps.keys())
    pm = "poetry"
```
`isinstance(poetry_deps, dict)` is always true (the `.get(..., {})` chain always yields a
dict), so the `pm = "poetry"` branch runs whenever `pyproject.toml` exists, unless later
overridden by `[tool.uv]` / `uv.lock` / `poetry.lock` / `Pipfile.lock`. A PEP 621 + pip
project with no lockfile is therefore mislabeled `poetry`.

## Why it is a problem

Low severity — `package_manager` is advisory recon context, not a gate; nothing breaks. But
it is wrong, and the type-check-gate work (ADR 0083) suggests install hints keyed on the
package manager (`uv add --dev` vs `pip install`) — a wrong pm could yield a wrong hint.

## Why it is not a duplicate

`rg -i 'package_manager|poetry|recon' docs/tickets/` — no prior match. Distinct from the
type-checker detection added in ADR 0083 (that code is correct and tested); this is a
pre-existing flaw in the adjacent `collect()` package-manager branch.

## What probably needs to be done

- Replace the meaningless `isinstance(poetry_deps, dict)` guard with a real presence check:
  set `pm = "poetry"` only when `[tool.poetry]` actually exists in `pyproject.toml`
  (`"poetry" in data.get("tool", {})`), not merely when the `.get` chain returns a dict.
- Add a `test_recon.py` case: PEP 621 + pip project (no Poetry) → `package_manager` is not
  `poetry`. (requires verification — confirm the intended default for a pip project: likely
  `pip` or `unknown`.)

## Acceptance criteria

- A fixture with `[tool.pyright]` + `[project]` and no Poetry / no lockfile does NOT report
  `package_manager: poetry`.
- Existing recon detections unchanged; `tools/test_recon.py` green including the new case.

## Sources

- `plugin-dist/skills/python-backend-patterns/recon.py:39-42`.
- Surfaced by ADR 0083 type-check-gate smoke.

## Resolution (2026-07-09)

**Implementer:** autonomous session (Fable 5)
**Commits:** `a1335ab5b75130206315cfa41f516ea455ebb6ba`
**Summary:** detection keyed on the actual `[tool.poetry]` section instead of
the always-truthy chained `.get(..., {})` default; dependencies extend only
when a real dependencies table exists. Red test reproduced the mislabel
before the fix (PEP 621 + `[tool.pyright]` fixture → was `poetry`, now
`unknown`); a companion test pins genuine poetry detection.
**Claims to verify on audit:**
- `python3 tools/test_recon.py` — 11/11 incl.
  `test_pep621_project_without_poetry_is_not_labeled_poetry` and
  `test_poetry_section_still_detected`.
- `python3 tools/render_core.py --check` — in sync.
