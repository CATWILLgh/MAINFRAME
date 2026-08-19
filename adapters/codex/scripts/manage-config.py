#!/usr/bin/env python3
"""Retire legacy MAINFRAME permissions and manage dev-only Codex telemetry."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
try:
    import tomllib
except ModuleNotFoundError:  # macOS can still ship Python 3.9.
    tomllib = None

TOMLDecodeError = ValueError if tomllib is None else tomllib.TOMLDecodeError


LEGACY_START = "# >>> MAINFRAME CODEX PERMISSIONS >>>"
LEGACY_END = "# <<< MAINFRAME CODEX PERMISSIONS <<<"
LEGACY_FEATURE_START = "# >>> MAINFRAME CODEX NETWORK PROXY >>>"
LEGACY_FEATURE_END = "# <<< MAINFRAME CODEX NETWORK PROXY <<<"
TELEMETRY_START = "# >>> MAINFRAME CODEX DEV TELEMETRY >>>"
TELEMETRY_END = "# <<< MAINFRAME CODEX DEV TELEMETRY <<<"
MUTABLE_KEYS = {"model", "model_reasoning_effort", "notify"}
TABLE_RE = re.compile(r"^\s*(\[+[^]]+\]+)\s*(?:#.*)?$")
ASSIGN_RE = re.compile(r"^\s*([A-Za-z0-9_.-]+)\s*=")


def digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def table_name(line: str) -> str | None:
    match = TABLE_RE.match(line)
    return match.group(1) if match else None


def split_marked(text: str, start_marker: str, end_marker: str) -> tuple[str | None, str]:
    start = text.find(start_marker)
    end = text.find(end_marker)
    if start < 0 and end < 0:
        return None, text
    if (
        start < 0
        or end < start
        or text.find(start_marker, start + 1) >= 0
        or text.find(end_marker, end + 1) >= 0
    ):
        raise ValueError(f"markers are incomplete or duplicated: {start_marker}")
    tail = end + len(end_marker)
    newline_count = 0
    while tail < len(text) and text[tail] == "\n" and newline_count < 2:
        tail += 1
        newline_count += 1
    return text[start:tail], text[:start] + text[tail:]


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def root_keys(text: str) -> set[str]:
    keys: set[str] = set()
    for line in text.splitlines():
        if table_name(line):
            break
        match = ASSIGN_RE.match(line)
        if match:
            keys.add(match.group(1))
    return keys


def parse_config(text: str) -> dict:
    if not text.strip():
        return {}
    if tomllib is not None:
        return tomllib.loads(text)
    result: dict = {}
    for line in text.splitlines():
        header = table_name(line)
        if header == "[otel]" or (header and header.startswith("[otel.")):
            result["otel"] = {}
        match = ASSIGN_RE.match(line)
        if match and match.group(1).startswith("otel."):
            result["otel"] = {}
    return result


def mutable_preferences(block: str) -> list[str]:
    result: list[str] = []
    for line in block.splitlines(keepends=True):
        match = ASSIGN_RE.match(line)
        if match and match.group(1) in MUTABLE_KEYS:
            result.append(line)
    return result


def insert_missing_root_preferences(text: str, preferences: list[str]) -> str:
    existing = root_keys(text)
    missing: list[str] = []
    for line in preferences:
        match = ASSIGN_RE.match(line)
        if match and match.group(1) not in existing:
            missing.append(line)
    return "".join(missing) + text


def insert_in_table(text: str, table: str, content: str) -> tuple[str, bool]:
    lines = text.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if table_name(line) == table:
            lines.insert(index + 1, content)
            return "".join(lines), False
    separator = "" if not text or text.endswith("\n\n") else "\n"
    return f"{text}{separator}{table}\n{content}", True


def remove_empty_features_table(text: str) -> str:
    lines = text.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if table_name(line) != "[features]":
            continue
        end = index + 1
        while end < len(lines) and table_name(lines[end]) is None:
            if lines[end].strip():
                return text
            end += 1
        del lines[index:end]
        return "".join(lines)
    return text


def restore_displaced(text: str, removed: list[dict[str, str]]) -> str:
    top = "".join(item["text"] for item in removed if item["kind"] in {"top", "feature_top"})
    shell = "".join(item["text"] for item in removed if item["kind"] == "shell")
    feature = "".join(item["text"] for item in removed if item["kind"] == "feature")
    tables = "".join(item["text"] for item in removed if item["kind"] == "table")
    if shell:
        lines = text.splitlines(keepends=True)
        for index, line in enumerate(lines):
            if table_name(line) == "[shell_environment_policy]":
                lines.insert(index + 1, shell)
                text = "".join(lines)
                break
        else:
            top += "shell_environment_policy.inherit = " + shell.split("=", 1)[1]
    if top:
        text = top + ("\n" if text and not top.endswith("\n\n") else "") + text
    if feature:
        text, _ = insert_in_table(text, "[features]", feature)
    if tables:
        text = text.rstrip() + "\n\n" + tables.lstrip("\n")
    return text


def retire_legacy(text: str, state: dict) -> str:
    block, remainder = split_marked(text, LEGACY_START, LEGACY_END)
    if block is None:
        raise ValueError("legacy MAINFRAME permissions changed after installation")
    preferences = mutable_preferences(block)
    retained: list[str] = []
    for line in block.splitlines(keepends=True):
        match = ASSIGN_RE.match(line)
        if not (match and match.group(1) in MUTABLE_KEYS):
            retained.append(line)
    without_preferences = "".join(retained)
    normalized = re.sub(r"\n{3,}", "\n\n", without_preferences) if preferences else without_preferences
    if state.get("managed_sha") not in {digest(without_preferences), digest(normalized)}:
        raise ValueError("legacy MAINFRAME permissions changed after installation")
    if "feature_managed_sha" in state:
        feature, remainder = split_marked(
            remainder, LEGACY_FEATURE_START, LEGACY_FEATURE_END
        )
        if feature is None or digest(feature) != state["feature_managed_sha"]:
            raise ValueError("legacy MAINFRAME network proxy changed after installation")
        if state.get("feature_table_created"):
            remainder = remove_empty_features_table(remainder)
    restored = restore_displaced(remainder, state.get("removed", []))
    restored = insert_missing_root_preferences(restored, preferences)
    parse_config(restored)
    return restored


def telemetry_block(endpoint: str) -> str:
    escaped = endpoint.replace("\\", "\\\\").replace('"', '\\"')
    return (
        f"{TELEMETRY_START}\n"
        'otel.environment = "mainframe-dev"\n'
        f'otel.exporter = {{ otlp-http = {{ endpoint = "{escaped}", protocol = "binary" }} }}\n'
        "otel.log_user_prompt = false\n"
        f"{TELEMETRY_END}\n\n"
    )


def sync(
    action: str,
    config: Path,
    state_path: Path,
    backup: Path,
    dry_run: bool,
    endpoint: str | None,
) -> str:
    existed = config.exists()
    original = config.read_text(encoding="utf-8") if existed else ""
    text = original
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else None
    messages: list[str] = []

    if state and state.get("schema_version") != 2:
        text = retire_legacy(text, state)
        state = None
        messages.append("retired legacy MAINFRAME permissions")

    current, remainder = split_marked(text, TELEMETRY_START, TELEMETRY_END)
    if state and state.get("schema_version") == 2:
        if current is None or digest(current) != state.get("managed_sha"):
            raise ValueError("MAINFRAME dev telemetry config changed after installation")
    elif current is not None:
        raise ValueError("MAINFRAME dev telemetry markers exist without installation state")

    desired = telemetry_block(endpoint) if action == "install" and endpoint else None
    if desired:
        if current is None:
            parsed = parse_config(remainder)
            if "otel" in parsed:
                raise ValueError("existing Codex otel configuration is user-owned; MAINFRAME preserved it")
        text = desired + remainder
        state = {"schema_version": 2, "managed_sha": digest(desired)}
        messages.append("enabled MAINFRAME dev telemetry config")
    else:
        text = remainder
        state = None
        if current is not None:
            messages.append("removed MAINFRAME dev telemetry config")

    parse_config(text)
    changed = text != original
    if dry_run:
        return "; ".join(messages) if messages else "Codex config already untouched"
    if changed and existed and not backup.exists():
        atomic_write(backup, original)
    if changed:
        if text.strip():
            atomic_write(config, text)
        elif config.exists():
            config.unlink()
    if state:
        atomic_write(state_path, json.dumps(state, indent=2) + "\n")
    elif state_path.exists():
        state_path.unlink()
    return "; ".join(messages) if messages else "Codex config left untouched"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("install", "uninstall"))
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--backup", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--dev-telemetry-endpoint")
    args = parser.parse_args()

    try:
        if args.dry_run:
            message = sync(
                args.action, args.config, args.state, args.backup, True,
                args.dev_telemetry_endpoint,
            )
        else:
            lock = args.state.with_suffix(".lock")
            lock.parent.mkdir(parents=True, exist_ok=True)
            with lock.open("a+", encoding="utf-8") as handle:
                fcntl.flock(handle, fcntl.LOCK_EX)
                message = sync(
                    args.action, args.config, args.state, args.backup, False,
                    args.dev_telemetry_endpoint,
                )
            if not args.state.exists() and lock.exists():
                lock.unlink()
    except (OSError, ValueError, TOMLDecodeError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Error: {exc}") from exc
    print(message)


if __name__ == "__main__":
    main()
