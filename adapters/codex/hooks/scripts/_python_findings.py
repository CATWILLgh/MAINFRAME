"""Ruff-backed, content-addressed findings for Python safety hooks."""

import hashlib
import json
import os
import shutil
import subprocess
from collections import Counter


CURATED_RULES = "S102,S307,S506,S602,S605,S501,S324"
CURATED_CODES = frozenset(CURATED_RULES.split(","))
SHELL_RULES = frozenset({"S602", "S605"})
PY_EXTS = (".py", ".pyi")


def _ruff():
    executable = shutil.which("ruff")
    if not executable:
        raise RuntimeError(
            "Python safety checks are unavailable because `ruff` is missing. "
            "Install it with `uv tool install ruff@latest` or `pipx install ruff`."
        )
    return executable


def _key(code, message, source):
    value = f"{code}\0{message}\0{source}".encode("utf-8", errors="replace")
    return hashlib.sha256(value).hexdigest()[:20]


def _source_excerpt(text, row, end_row):
    lines = text.splitlines()
    if not lines:
        return ""
    start = max(0, int(row or 1) - 1)
    end = min(len(lines), max(start + 1, int(end_row or row or 1)))
    return "\n".join(line.strip() for line in lines[start:end])[:1000]


def findings(text, file_ext, file_path=None):
    """Return stable finding rows for one complete in-memory Python file."""
    if file_ext not in PY_EXTS:
        return []
    path = os.path.realpath(file_path or f"stdin{file_ext}")
    proc = subprocess.run(
        [_ruff(), "check", "--isolated", "--select", CURATED_RULES,
         "--output-format", "json", "--no-cache", "--ignore-noqa",
         "--stdin-filename", path, "-"],
        input=text, capture_output=True, text=True, timeout=10,
        cwd=os.path.dirname(path) or ".",
    )
    if proc.returncode not in (0, 1):
        detail = (proc.stderr or proc.stdout).strip().splitlines()
        suffix = f": {detail[0][:240]}" if detail else ""
        raise RuntimeError(f"Python safety checks failed to run{suffix}")
    try:
        raw = json.loads(proc.stdout) if proc.stdout.strip() else []
    except json.JSONDecodeError as exc:
        raise RuntimeError("Python safety checks returned invalid Ruff JSON") from exc
    rows = []
    for item in raw:
        code = item.get("code")
        if code not in CURATED_CODES:
            continue
        row = int((item.get("location") or {}).get("row") or 0)
        end_row = int((item.get("end_location") or {}).get("row") or row)
        message = (item.get("message") or "").strip()
        if code in SHELL_RULES and "seems safe" in message:
            continue
        key = _key(code, message, _source_excerpt(text, row, end_row))
        rows.append({"key": key, "code": code, "row": row,
                     "end_row": end_row, "message": message})
    return rows


def finding_counts(text, file_ext, file_path=None):
    return dict(Counter(row["key"] for row in findings(text, file_ext, file_path)))


def rows_for_keys(text, file_ext, file_path, keys):
    wanted = set(keys)
    return [row for row in findings(text, file_ext, file_path)
            if row["key"] in wanted]
