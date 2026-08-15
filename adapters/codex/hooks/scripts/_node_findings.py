"""Oxlint-backed, content-addressed findings for Node.js safety hooks."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
import os
import shutil
import subprocess
import tempfile


CURATED_RULES = ("no-eval", "no-new-func", "no-script-url")
JS_EXTS = (".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx")


def _oxlint() -> str:
    executable = shutil.which("oxlint")
    if not executable:
        raise RuntimeError(
            "Node safety checks are unavailable because `oxlint` is missing. "
            "Install it with `npm install -g oxlint`."
        )
    return executable


def _normalized_code(value) -> str:
    code = str(value or "")
    if "(" in code and code.endswith(")"):
        code = code.split("(", 1)[1][:-1]
    return code


def _key(code: str, message: str, source: str) -> str:
    value = f"{code}\0{message}\0{source}".encode("utf-8", errors="replace")
    return hashlib.sha256(value).hexdigest()[:20]


def _source_excerpt(text: str, row, end_row) -> str:
    lines = text.splitlines()
    if not lines:
        return ""
    start = max(0, int(row or 1) - 1)
    end = min(len(lines), max(start + 1, int(end_row or row or 1)))
    return "\n".join(line.strip() for line in lines[start:end])[:1000]


def findings(text: str, file_ext: str, file_path=None) -> list[dict]:
    """Return stable high-confidence findings for one complete JS/TS file."""
    if file_ext not in JS_EXTS:
        return []
    with tempfile.TemporaryDirectory(prefix="mainframe-node-") as directory:
        probe = os.path.join(directory, "source" + file_ext)
        with open(probe, "w", encoding="utf-8") as handle:
            handle.write(text)
        args = [
            _oxlint(), "-A", "all", "--disable-nested-config", "--no-ignore",
            "--format=json",
        ]
        for rule in CURATED_RULES:
            args.extend(["-D", rule])
        args.append(probe)
        try:
            proc = subprocess.run(
                args, capture_output=True, text=True, timeout=15, cwd=directory
            )
        except Exception as exc:
            raise RuntimeError("Node safety checks failed to run Oxlint") from exc
    if proc.returncode not in (0, 1):
        detail = (proc.stderr or proc.stdout).strip().splitlines()
        suffix = f": {detail[0][:240]}" if detail else ""
        raise RuntimeError(f"Node safety checks failed to run{suffix}")
    try:
        data = json.loads(proc.stdout) if proc.stdout.strip() else {}
    except json.JSONDecodeError as exc:
        raise RuntimeError("Node safety checks returned invalid Oxlint JSON") from exc

    rows = []
    diagnostics = data.get("diagnostics", []) if isinstance(data, dict) else []
    for item in diagnostics:
        code = _normalized_code(item.get("code"))
        if code not in CURATED_RULES:
            continue
        labels = item.get("labels") or []
        span = labels[0].get("span", {}) if labels else {}
        row = int(span.get("line") or 0)
        end_row = int(span.get("line_end") or row)
        message = (item.get("message") or "").strip()
        key = _key(code, message, _source_excerpt(text, row, end_row))
        rows.append({
            "key": key,
            "code": code,
            "row": row,
            "end_row": end_row,
            "message": message,
        })
    return rows


def finding_counts(text: str, file_ext: str, file_path=None) -> dict[str, int]:
    return dict(Counter(row["key"] for row in findings(text, file_ext, file_path)))
