#!/usr/bin/env python3
"""Return bounded Fallow advice for an exact TypeScript/JavaScript edit scope.

This canonical detector is a stateless completion advisory. An adapter supplies
the normalized project root, the explicit paths changed by one native execution
scope, and an in-memory unified diff reconstructed from that scope. Fallow reads
the diff on stdin. With no Git commit, complexity advice can use verified new
files as its baseline.

Audit findings must be attributed as newly introduced and intersect the supplied
paths. Without a base commit, only measured complexity on a verified new file
is reported. Unused-file findings are reported only for files
the adapter identifies as wholly created or replaced by the same scope. Missing
tools, invalid input, timeouts, analyzer errors, and unsupported output return a
bounded unavailable-check advisory and never block completion.

Product events, edit-scope capture, subagent lineage, delivery encoding, and
deduplication belong to the installed adapter. This source creates no state,
logs, telemetry, baseline files, or repository changes.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import time
from typing import Iterable, NamedTuple


JS_EXTENSIONS = frozenset(
    {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".mts", ".cts", ".vue", ".svelte"}
)
MAX_DIFF_BYTES = 2_000_000
MAX_PATHS = 64
MAX_MESSAGE_ROWS = 6
MAX_ROW_CHARS = 240
ANALYZE_TIMEOUT_SECONDS = 180
CREATION_DIFF_PREFIX = "--- /dev/null\n+++ b/"
UNRESOLVED_HEAD_MESSAGE = "could not determine changed files for base ref 'HEAD'. Verify the ref exists in this git repository"


class FallowResult(NamedTuple):
    advisory: str | None = None
    unavailable: str | None = None


def _unavailable() -> FallowResult:
    return FallowResult(
        unavailable=(
            "Fallow structural review was unavailable for the current TS/JS "
            "edit scope. Completion was not blocked; do not treat this missing "
            "advisory as proof that the change is structurally clean."
        )
    )


def _inside(root: Path, value: str | os.PathLike[str]) -> Path | None:
    try:
        candidate = Path(value)
        if not candidate.is_absolute():
            candidate = root / candidate
        candidate = candidate.resolve(strict=False)
        candidate.relative_to(root)
        return candidate
    except (OSError, RuntimeError, TypeError, ValueError):
        return None


def _paths(
    root: Path,
    values: Iterable[str | os.PathLike[str]],
) -> set[Path] | None:
    try:
        raw = list(values)
    except (TypeError, ValueError):
        return None
    if len(raw) > MAX_PATHS:
        return None
    result: set[Path] = set()
    for value in raw:
        path = _inside(root, value)
        if path is None:
            return None
        result.add(path)
    return result


def _finding_path(root: Path, value: object) -> Path | None:
    if not isinstance(value, str) or not value or "\n" in value or "\r" in value:
        return None
    return _inside(root, value)


def _display(root: Path, value: object) -> str:
    path = _finding_path(root, value)
    if path is None:
        return "?"
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return "?"


def _introduced(rows: object) -> list[dict[str, object]]:
    if not isinstance(rows, list):
        return []
    return [
        row
        for row in rows
        if isinstance(row, dict) and row.get("introduced") is True
    ]


def _supported_report(report: object) -> bool:
    if not isinstance(report, dict) or report.get("kind") != "audit" or report.get("error") is True:
        return False
    collections = {
        "dead_code": (
            "unused_files", "circular_dependencies", "boundary_violations",
            "boundary_call_violations",
        ),
        "complexity": ("findings",),
        "duplication": ("clone_groups",),
    }
    for key, names in collections.items():
        section = report.get(key)
        if section is None:
            continue
        if not isinstance(section, dict):
            return False
        for name in names:
            rows = section.get(name)
            if rows is None:
                continue
            if not isinstance(rows, list) or any(
                not isinstance(row, dict) or not isinstance(row.get("introduced"), bool)
                for row in rows
            ):
                return False
    return True


def _bounded_row(value: str) -> str:
    safe = "".join(character if character.isprintable() else "?" for character in value)
    if len(safe) <= MAX_ROW_CHARS:
        return safe
    # Keep the finding kind and the diagnostic location/measurement at the end.
    prefix = (MAX_ROW_CHARS - 3) // 2
    suffix = MAX_ROW_CHARS - 3 - prefix
    return safe[:prefix] + "..." + safe[-suffix:]


def _number(value: object) -> str:
    return str(value) if type(value) is int and 0 <= value <= 1_000_000_000 else "?"


def _touches(root: Path, finding: dict[str, object], owned: set[Path]) -> bool:
    values: list[object] = []
    for key in ("path", "from_path", "to_path", "callee"):
        value = finding.get(key)
        if value:
            values.append(value)
    for key in ("files", "instances"):
        value = finding.get(key)
        if isinstance(value, list):
            for item in value:
                values.append(item.get("file") if isinstance(item, dict) else item)
    return any(_finding_path(root, value) in owned for value in values)


def _complexity_row(root: Path, finding: dict[str, object]) -> str:
    return (
        f"complexity: {_display(root, finding.get('path'))}:{_number(finding.get('line'))} "
        f"`{finding.get('name', '?')}` (cyclomatic {_number(finding.get('cyclomatic'))})"
    )


def _bounded_advice(rows: list[str], introduction: str) -> str | None:
    if not rows:
        return None
    shown = [_bounded_row(row) for row in rows[:MAX_MESSAGE_ROWS]]
    remainder = len(rows) - len(shown)
    more = f"\n  - ...and {remainder} more" if remainder else ""
    return (
        "Fallow advisory (non-blocking). Verify findings before acting; resolve "
        "in-scope findings and report evidenced out-of-scope issues via the "
        "project's configured issue route.\n"
        + introduction + ":\n  - " + "\n  - ".join(shown) + more
    )


def build_advisory(
    report: object,
    project_root: str | os.PathLike[str],
    affected_paths: Iterable[str | os.PathLike[str]],
    *,
    wholly_owned_paths: Iterable[str | os.PathLike[str]] = (),
) -> str | None:
    """Build advice from one Fallow audit envelope without changing state."""
    try:
        root = Path(project_root).resolve(strict=True)
    except (OSError, RuntimeError, TypeError, ValueError):
        return None
    affected = _paths(root, affected_paths)
    wholly_owned = _paths(root, wholly_owned_paths)
    if not affected or wholly_owned is None:
        return None
    wholly_owned &= affected
    if not _supported_report(report):
        return None

    dead = report.get("dead_code") or {}
    complexity = report.get("complexity") or {}
    duplication = report.get("duplication") or {}
    if not isinstance(dead, dict) or not isinstance(complexity, dict) or not isinstance(duplication, dict):
        return None

    unused = [
        row
        for row in _introduced(dead.get("unused_files"))
        if _finding_path(root, row.get("path")) in wholly_owned
    ]
    cycles = [
        row
        for row in _introduced(dead.get("circular_dependencies"))
        if _touches(root, row, affected)
    ]
    boundaries = [
        row
        for row in _introduced(
            list(dead.get("boundary_violations") or [])
            + list(dead.get("boundary_call_violations") or [])
        )
        if _touches(root, row, affected)
    ]
    complex_rows = [
        row
        for row in _introduced(complexity.get("findings"))
        if _touches(root, row, affected)
    ]
    duplicate_rows = [
        row
        for row in _introduced(duplication.get("clone_groups"))
        if _touches(root, row, affected)
    ]

    rows: list[str] = []
    for finding in unused:
        rows.append(f"unused file: {_display(root, finding.get('path'))}")
    for finding in cycles:
        paths = [
            _display(root, value)
            for value in finding.get("files", [])
            if isinstance(value, str)
        ]
        rows.append("import cycle: " + " -> ".join(paths[:3]))
    for finding in boundaries:
        rows.append(
            "boundary: "
            f"{_display(root, finding.get('from_path') or finding.get('path'))}:"
            f"{_number(finding.get('line'))} -> "
            f"{_display(root, finding.get('to_path') or finding.get('callee'))}"
        )
    for finding in complex_rows:
        rows.append(_complexity_row(root, finding))
    for finding in duplicate_rows:
        instances = finding.get("instances") or []
        first = instances[0] if isinstance(instances, list) and instances else {}
        first = first if isinstance(first, dict) else {}
        rows.append(
            "duplication: "
            f"{_display(root, first.get('file'))}:{_number(first.get('start_line'))} "
            f"({_number(finding.get('line_count'))} lines)"
        )

    return _bounded_advice(
        rows, f"Found {len(rows)} newly introduced issue(s) in current TS/JS edit scope"
    )


def _creation_advice(report: object, root: Path, created: Path) -> FallowResult:
    if not isinstance(report, dict) or report.get("kind") != "health" or report.get("error") is True:
        return _unavailable()
    findings = report.get("findings")
    if not isinstance(findings, list) or any(
        not isinstance(row, dict) or not isinstance(row.get("path"), str)
        or not isinstance(row.get("exceeded"), str) for row in findings
    ):
        return _unavailable()
    # Fallow's estimated coverage can raise a score in the first edit. Only
    # report measured complexity thresholds on files created by this edit.
    rows = [
        _complexity_row(root, row) for row in findings
        if _finding_path(root, row["path"]) == created and row["exceeded"] in {"cyclomatic", "cognitive", "both", "all"}
    ]
    return FallowResult(advisory=_bounded_advice(rows, "High complexity in newly created file"))


def analyze(
    project_root: str | os.PathLike[str],
    affected_paths: Iterable[str | os.PathLike[str]],
    diff_text: str,
    *,
    wholly_owned_paths: Iterable[str | os.PathLike[str]] = (),
    executable: str | None = None,
    timeout_seconds: int = ANALYZE_TIMEOUT_SECONDS,
) -> FallowResult:
    """Run Fallow for one exact edit scope and return advisory-only output."""
    try:
        root = Path(project_root).resolve(strict=True)
        affected = _paths(root, affected_paths)
        wholly_owned = _paths(root, wholly_owned_paths)
        if affected is None or wholly_owned is None:
            return _unavailable()
        relevant = {path for path in affected if path.suffix.lower() in JS_EXTENSIONS}
        if not relevant:
            return FallowResult()
        if not isinstance(diff_text, str):
            return _unavailable()
        if not diff_text:
            return FallowResult()
        if len(diff_text.encode("utf-8", errors="replace")) > MAX_DIFF_BYTES:
            return _unavailable()
        binary = shutil.which(executable or "fallow")
        if not binary:
            return _unavailable()
        environment = os.environ.copy()
        environment["FALLOW_TELEMETRY"] = "off"
        environment["FALLOW_TELEMETRY_DISABLED"] = "1"
        environment["FALLOW_UPDATE_CHECK"] = "off"
        options = ["--root", str(root), "--diff-stdin", "--format", "json", "--quiet", "--no-cache"]
        timeout = max(1, int(timeout_seconds))
        started = time.monotonic()
        process = subprocess.run(
            [binary, "audit", "--base", "HEAD", "--gate", "new-only", *options],
            input=diff_text,
            capture_output=True,
            text=True,
            cwd=root,
            env=environment,
            timeout=timeout,
            check=False,
        )
        if process.returncode not in (0, 1):
            report = json.loads(process.stdout)
            if (process.returncode != 2 or not isinstance(report, dict)
                    or report.get("error") is not True or report.get("message") != UNRESOLVED_HEAD_MESSAGE):
                return _unavailable()
            # A single explicit creation header cannot be confused with lines
            # inside a multi-file diff. Whole-file ownership also covers updates.
            if not diff_text.startswith(CREATION_DIFF_PREFIX) or len(relevant) != 1:
                return _unavailable()
            relative = diff_text[len(CREATION_DIFF_PREFIX):].partition("\n")[0]
            path = _finding_path(root, relative)
            if path is None or path not in wholly_owned or path not in relevant:
                return _unavailable()
            remaining = timeout - (time.monotonic() - started)
            if remaining <= 0:
                return _unavailable()
            health = subprocess.run(
                [binary, "health", "--complexity", *options], input=diff_text,
                capture_output=True, text=True, cwd=root, env=environment, timeout=remaining, check=False,
            )
            if health.returncode not in (0, 1):
                return _unavailable()
            return _creation_advice(json.loads(health.stdout), root, path)
        report = json.loads(process.stdout)
        if not _supported_report(report):
            return _unavailable()
        note = build_advisory(
            report,
            root,
            relevant,
            wholly_owned_paths=wholly_owned,
        )
        return FallowResult(advisory=note)
    except (
        OSError,
        RuntimeError,
        subprocess.SubprocessError,
        TypeError,
        ValueError,
    ):
        return _unavailable()
