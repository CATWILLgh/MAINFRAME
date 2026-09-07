#!/usr/bin/env python3
"""Return bounded Fallow advice for an exact TypeScript/JavaScript edit scope.

This canonical detector is a stateless completion advisory. An adapter supplies
the normalized project root, the explicit paths changed by one native execution
scope, and an in-memory unified diff reconstructed from that scope. The diff is
passed directly to ``fallow audit`` over stdin and is never persisted here.

Only findings that Fallow attributes as newly introduced and that intersect the
supplied paths are reported. Unused-file findings are reported only for files
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
from typing import Iterable, NamedTuple


JS_EXTENSIONS = frozenset(
    {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".mts", ".cts", ".vue", ".svelte"}
)
MAX_DIFF_BYTES = 2_000_000
MAX_PATHS = 64
MAX_MESSAGE_ROWS = 6
ANALYZE_TIMEOUT_SECONDS = 180


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
    if not isinstance(report, dict) or report.get("kind") != "audit":
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
            f"{finding.get('line', '?')} -> "
            f"{_display(root, finding.get('to_path') or finding.get('callee'))}"
        )
    for finding in complex_rows:
        rows.append(
            "complexity: "
            f"{_display(root, finding.get('path'))}:{finding.get('line', '?')} "
            f"`{finding.get('name', '?')}` "
            f"(cyclomatic {finding.get('cyclomatic', '?')})"
        )
    for finding in duplicate_rows:
        instances = finding.get("instances") or []
        first = instances[0] if isinstance(instances, list) and instances else {}
        first = first if isinstance(first, dict) else {}
        rows.append(
            "duplication: "
            f"{_display(root, first.get('file'))}:{first.get('start_line', '?')} "
            f"({finding.get('line_count', '?')} lines)"
        )

    if not rows:
        return None
    shown = rows[:MAX_MESSAGE_ROWS]
    remainder = len(rows) - len(shown)
    more = f"\n  - ...and {remainder} more" if remainder else ""
    return (
        f"Fallow structural review found {len(rows)} newly introduced issue(s) "
        "in the current TS/JS edit scope:\n  - "
        + "\n  - ".join(shown)
        + more
        + "\nVerify each finding before acting. Resolve what belongs to the current "
        "result and surface evidenced out-of-scope problems through the project's "
        "configured issue route. This is advisory and did not block completion."
    )


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
        process = subprocess.run(
            [
                binary,
                "audit",
                "--root",
                str(root),
                "--base",
                "HEAD",
                "--diff-stdin",
                "--gate",
                "new-only",
                "--format",
                "json",
                "--quiet",
                "--no-cache",
            ],
            input=diff_text,
            capture_output=True,
            text=True,
            cwd=root,
            env=environment,
            timeout=max(1, int(timeout_seconds)),
            check=False,
        )
        if process.returncode not in (0, 1):
            return _unavailable()
        report = json.loads(process.stdout)
        if not isinstance(report, dict) or report.get("error") is True:
            return _unavailable()
        note = build_advisory(
            report,
            root,
            relevant,
            wholly_owned_paths=wholly_owned,
        )
        if report.get("kind") != "audit":
            return _unavailable()
        return FallowResult(advisory=note)
    except (
        json.JSONDecodeError,
        OSError,
        RuntimeError,
        subprocess.SubprocessError,
        TypeError,
        ValueError,
    ):
        return _unavailable()
