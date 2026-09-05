#!/usr/bin/env python3
"""Asynchronous, non-blocking Semgrep advice for lines changed by one tool call."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from _hooklib import emit_note, load_payload, run
    from _notice_state import claim_once
except Exception:
    sys.stderr.write("Hook dependencies unavailable; check sibling modules.\n")
    sys.exit(1)


RULES = Path(__file__).resolve().parent.parent / "rules" / "semgrep-informational.yml"
SUPPORTED_EXTENSIONS = {".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx"}
MAX_FILE_BYTES = 1_000_000
MAX_FILES = 12
MAX_ROWS = 4
_PATCH_SECTION = re.compile(r"^\*\*\* (Add|Update) File:\s*(.+?)\s*$")


def _project_root(cwd: Path) -> Path:
    try:
        value = (
            subprocess.check_output(
                ["git", "rev-parse", "--show-toplevel"],
                cwd=cwd,
                stderr=subprocess.DEVNULL,
                timeout=2,
            )
            .decode()
            .strip()
        )
        return Path(value).resolve() if value else cwd
    except (OSError, subprocess.SubprocessError):
        return cwd


def _safe_path(value: str, cwd: Path, project: Path) -> Path | None:
    candidate = Path(value).expanduser()
    candidate = (candidate if candidate.is_absolute() else cwd / candidate).resolve()
    try:
        candidate.relative_to(project)
    except ValueError:
        return None
    try:
        if candidate.suffix.lower() not in SUPPORTED_EXTENSIONS:
            return None
        if not candidate.is_file() or candidate.stat().st_size > MAX_FILE_BYTES:
            return None
    except OSError:
        return None
    return candidate


def _matching_lines(text: str, value: str, *, replace_all: bool = False) -> set[int]:
    if not value:
        return set()
    starts = []
    offset = 0
    while True:
        index = text.find(value, offset)
        if index < 0:
            break
        starts.append(index)
        offset = index + max(1, len(value))
    if len(starts) > 1 and not replace_all:
        return set()
    lines = set()
    for index in starts:
        first = text.count("\n", 0, index) + 1
        last = first + value.count("\n")
        lines.update(range(first, last + 1))
    return lines


def _patch_targets(patch: str, cwd: Path, project: Path) -> dict[Path, set[int]]:
    additions: dict[str, list[str] | None] = {}
    current: str | None = None
    for line in patch.splitlines():
        match = _PATCH_SECTION.match(line)
        if match:
            current = match.group(2)
            additions.setdefault(current, [] if match.group(1) == "Update" else None)
            continue
        if current and line.startswith("+") and not line.startswith("+++"):
            if additions[current] is not None:
                additions[current].append(line[1:])
    result: dict[Path, set[int]] = {}
    for raw, added in list(additions.items())[:MAX_FILES]:
        path = _safe_path(raw, cwd, project)
        if path is None:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if added is None:
            result[path] = set(range(1, text.count("\n") + 2))
            continue
        wanted = Counter(added)
        present = Counter(text.splitlines())
        result[path] = {
            number
            for number, line in enumerate(text.splitlines(), 1)
            if line in wanted and present[line] <= wanted[line]
        }
    return {path: lines for path, lines in result.items() if lines}


def _targets(payload: dict) -> dict[Path, set[int]]:
    tool_name = str(payload.get("tool_name") or "")
    tool_input = payload.get("tool_input") or {}
    cwd = Path(payload.get("cwd") or os.getcwd()).resolve()
    project = _project_root(cwd)
    if tool_name == "apply_patch":
        patch = next(
            (
                value
                for key in ("patch", "input", "command")
                if isinstance((value := tool_input.get(key)), str) and "*** " in value
            ),
            "",
        )
        return _patch_targets(patch, cwd, project)
    if tool_name not in {"Edit", "MultiEdit", "Write"}:
        return {}
    raw = tool_input.get("file_path") or tool_input.get("path")
    path = _safe_path(raw, cwd, project) if isinstance(raw, str) else None
    if path is None:
        return {}
    text = path.read_text(encoding="utf-8", errors="replace")
    if tool_name == "Write":
        lines = set(range(1, text.count("\n") + 2))
    elif tool_name == "Edit":
        lines = _matching_lines(
            text,
            str(tool_input.get("new_string") or ""),
            replace_all=bool(tool_input.get("replace_all")),
        )
    else:
        lines = set()
        for edit in tool_input.get("edits") or []:
            if isinstance(edit, dict):
                lines.update(
                    _matching_lines(
                        text,
                        str(edit.get("new_string") or ""),
                        replace_all=bool(edit.get("replace_all")),
                    )
                )
    return {path: lines} if lines else {}


def _run_semgrep(targets: dict[Path, set[int]]) -> tuple[list[dict], int]:
    executable = shutil.which("semgrep")
    if executable is None:
        raise FileNotFoundError("semgrep")
    with tempfile.TemporaryDirectory(prefix="mainframe-semgrep-") as directory:
        temporary = Path(directory)
        mapping: dict[str, Path] = {}
        for index, path in enumerate(targets):
            copy = temporary / f"target-{index}{path.suffix.lower()}"
            copy.write_text(
                path.read_text(encoding="utf-8", errors="replace"), encoding="utf-8"
            )
            mapping[copy.name] = path
        command = [
            executable,
            "scan",
            "--config",
            str(RULES),
            "--oss-only",
            "--metrics",
            "off",
            "--disable-version-check",
            "--json",
            "--quiet",
            "--jobs",
            "1",
            "--timeout",
            "2",
            "--timeout-threshold",
            "1",
            "--max-memory",
            "256",
            "--max-target-bytes",
            str(MAX_FILE_BYTES),
            "--max-lines-per-finding",
            "1",
            "--max-chars-per-line",
            "120",
            str(temporary),
        ]
        completed = subprocess.run(command, capture_output=True, text=True, timeout=12)
        if completed.returncode != 0:
            raise RuntimeError(f"semgrep exit {completed.returncode}")
        value = json.loads(completed.stdout or "{}")
        if value.get("errors"):
            raise RuntimeError("semgrep reported scan errors")
        rows = []
        for finding in value.get("results") or []:
            source = Path(str(finding.get("path") or "")).name
            original = mapping.get(source)
            if original is None:
                continue
            start = int((finding.get("start") or {}).get("line") or 0)
            end = int((finding.get("end") or {}).get("line") or start)
            if not any(line in targets[original] for line in range(start, end + 1)):
                continue
            check_id = str(finding.get("check_id") or "semgrep")
            marker = check_id.find("mainframe.")
            rule_id = check_id[marker:] if marker >= 0 else check_id
            extra = finding.get("extra") or {}
            rows.append(
                {
                    "path": original,
                    "line": start,
                    "end": end,
                    "rule_id": rule_id,
                    "message": str(extra.get("message") or "Review this finding."),
                }
            )
        return rows, len(rows)


def _claim(rows: list[dict], payload: dict) -> list[dict]:
    accepted = []
    for row in rows:
        lines = row["path"].read_text(encoding="utf-8", errors="replace").splitlines()
        snippet = "\n".join(lines[max(0, row["line"] - 1) : row["end"]])
        signature = hashlib.sha256(snippet.encode()).hexdigest()[:20]
        topic = f"semgrep:{row['path']}:{row['rule_id']}:{signature}"
        if claim_once(topic, payload.get("session_id"), payload.get("agent_id")):
            accepted.append(row)
    return accepted


def _display(path: Path, cwd: str) -> str:
    try:
        return os.path.relpath(path, cwd or os.getcwd())
    except ValueError:
        return path.name


def main() -> None:
    payload = load_payload()
    targets = _targets(payload)
    if not targets:
        return
    try:
        rows, matched_findings = _run_semgrep(targets)
    except FileNotFoundError:
        if claim_once(
            "semgrep-unavailable", payload.get("session_id"), payload.get("agent_id")
        ):
            emit_note(
                "PostToolUse",
                "MAINFRAME Semgrep advice is unavailable because `semgrep` is not installed. Install it with `uv tool install semgrep` or `pipx install semgrep`; other checks remain active.",
            )
        return
    except Exception:
        if claim_once(
            "semgrep-failed", payload.get("session_id"), payload.get("agent_id")
        ):
            emit_note(
                "PostToolUse",
                "MAINFRAME Semgrep advice could not complete for this edit. "
                "The advisory check was skipped; other checks remain active.",
            )
        return
    rows = _claim(rows, payload)
    if not rows:
        return
    shown = rows[:MAX_ROWS]
    cwd = str(payload.get("cwd") or os.getcwd())
    lines = [
        f"  {_display(row['path'], cwd)}:{row['line']} — {row['rule_id']}: {row['message']}"
        for row in shown
    ]
    if len(rows) > MAX_ROWS:
        lines.append(f"  …and {len(rows) - MAX_ROWS} more")
    note = (
        f"Semgrep advice found {len(rows)} high-confidence issue(s) on newly edited lines:\n"
        + "\n".join(lines)
        + "\nReview the affected trust boundary before completion. This is advisory and is not a full project scan."
    )
    emit_note("PostToolUse", note)
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["rule_id"]] = counts.get(row["rule_id"], 0) + 1


if __name__ == "__main__":
    run(main)
