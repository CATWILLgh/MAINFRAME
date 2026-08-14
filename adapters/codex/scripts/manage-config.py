#!/usr/bin/env python3
"""Install and remove the bounded MAINFRAME block in Codex user config."""

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

if tomllib is None:
    class TOMLDecodeError(Exception):
        pass
else:
    TOMLDecodeError = tomllib.TOMLDecodeError


START = "# >>> MAINFRAME CODEX PERMISSIONS >>>"
END = "# <<< MAINFRAME CODEX PERMISSIONS <<<"
TOP_KEYS = {"approval_policy", "approvals_reviewer", "default_permissions", "sandbox_mode"}
TABLE_RE = re.compile(r"^\s*(\[+[^]]+\]+)\s*(?:#.*)?$")
ASSIGN_RE = re.compile(r"^\s*([A-Za-z0-9_.-]+)\s*=")


def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def managed_block(fragment: str) -> str:
    return f"{START}\n{fragment.rstrip()}\n{END}\n\n"


def split_managed(text: str) -> tuple[str | None, str]:
    start = text.find(START)
    end = text.find(END)
    if start < 0 and end < 0:
        return None, text
    if start < 0 or end < start or text.find(START, start + 1) >= 0 or text.find(END, end + 1) >= 0:
        raise ValueError("the MAINFRAME config markers are incomplete or duplicated")
    tail = end + len(END)
    if tail < len(text) and text[tail] == "\n":
        tail += 1
    if tail < len(text) and text[tail] == "\n":
        tail += 1
    return text[start:tail], text[:start] + text[tail:]


def table_name(line: str) -> str | None:
    match = TABLE_RE.match(line)
    return match.group(1) if match else None


def remove_legacy(text: str) -> tuple[str, list[dict[str, str]]]:
    lines = text.splitlines(keepends=True)
    kept: list[str] = []
    removed: list[dict[str, str]] = []
    section = ""
    index = 0
    while index < len(lines):
        line = lines[index]
        header = table_name(line)
        if header:
            section = header
            if header == "[sandbox_workspace_write]":
                chunk = [line]
                index += 1
                while index < len(lines) and not table_name(lines[index]):
                    chunk.append(lines[index])
                    index += 1
                removed.append({"kind": "table", "text": "".join(chunk)})
                section = ""
                continue
        match = ASSIGN_RE.match(line)
        key = match.group(1) if match else None
        if section == "" and key in TOP_KEYS:
            removed.append({"kind": "top", "text": line})
        elif section == "" and key == "shell_environment_policy.inherit":
            removed.append({"kind": "top", "text": line})
        elif section == "[shell_environment_policy]" and key == "inherit":
            removed.append({"kind": "shell", "text": line})
        else:
            kept.append(line)
        index += 1
    return "".join(kept), removed


def restore_legacy(text: str, removed: list[dict[str, str]]) -> str:
    top = "".join(item["text"] for item in removed if item["kind"] == "top")
    shell = "".join(item["text"] for item in removed if item["kind"] == "shell")
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
    if tables:
        text = text.rstrip() + "\n\n" + tables.lstrip("\n")
    return text


def parse_config(text: str) -> dict:
    if not text.strip():
        return {}
    if tomllib is not None:
        return tomllib.loads(text)
    data: dict = {}
    section = ""
    for line in text.splitlines():
        header = table_name(line)
        if header:
            section = header
            if header.startswith("[permissions.mainframe"):
                data.setdefault("permissions", {})["mainframe"] = {}
            elif header == "[sandbox_workspace_write]":
                data["sandbox_workspace_write"] = {}
            elif header == "[shell_environment_policy]":
                data.setdefault("shell_environment_policy", {})
            continue
        match = ASSIGN_RE.match(line)
        if not match:
            continue
        key = match.group(1)
        if section == "":
            if key in TOP_KEYS:
                data[key] = True
            elif key.startswith("permissions.mainframe."):
                data.setdefault("permissions", {})["mainframe"] = {}
            elif key == "shell_environment_policy.inherit":
                data.setdefault("shell_environment_policy", {})["inherit"] = True
        elif section == "[shell_environment_policy]" and key == "inherit":
            data.setdefault("shell_environment_policy", {})["inherit"] = True
    return data


def has_profile_collision(data: dict) -> bool:
    permissions = data.get("permissions")
    return isinstance(permissions, dict) and "mainframe" in permissions


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


def read_state(path: Path) -> dict | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def verify_managed(text: str, state: dict) -> tuple[str, str]:
    current, remainder = split_managed(text)
    if current is None or state.get("managed_sha") != sha(current):
        raise ValueError("the MAINFRAME permissions block changed after installation")
    return current, remainder


def render_fragment(source: Path, repo_root: Path) -> str:
    escaped_root = str(repo_root.resolve()).replace("\\", "\\\\").replace('"', '\\"')
    return source.read_text(encoding="utf-8").replace("@MAINFRAME_REPO@", escaped_root)


def install(config: Path, source: Path, repo_root: Path, state_path: Path, backup: Path, dry_run: bool) -> str:
    fragment = render_fragment(source, repo_root)
    parse_config(fragment)
    current = config.read_text(encoding="utf-8") if config.exists() else ""
    state = read_state(state_path)
    if state:
        current_block, remainder = verify_managed(current, state)
        expected = managed_block(fragment)
        candidate = expected + remainder
        parse_config(candidate)
        if current_block == expected:
            return "permissions already installed" if not dry_run else "would keep existing permissions block"
        if dry_run:
            return "would update the owned MAINFRAME permissions block"
        state["managed_sha"] = sha(expected)
        atomic_write(config, candidate)
        atomic_write(state_path, json.dumps(state, ensure_ascii=True, indent=2) + "\n")
        return "updated MAINFRAME permissions"
    block, _ = split_managed(current)
    if block is not None:
        raise ValueError("MAINFRAME config markers exist without installation state")
    data = parse_config(current)
    if has_profile_collision(data):
        raise ValueError("an unmanaged permissions.mainframe profile already exists")
    cleaned, removed = remove_legacy(current)
    candidate = managed_block(fragment) + cleaned.lstrip("\n")
    parse_config(candidate)
    if dry_run:
        return "would back up and merge the MAINFRAME permissions block"
    was_missing = not config.exists()
    config.parent.mkdir(parents=True, exist_ok=True)
    if config.exists():
        atomic_write(backup, current)
    state_data = {
        "backup_path": str(backup) if config.exists() else "-",
        "config_was_missing": was_missing,
        "managed_sha": sha(managed_block(fragment)),
        "removed": removed,
    }
    atomic_write(config, candidate)
    atomic_write(state_path, json.dumps(state_data, ensure_ascii=True, indent=2) + "\n")
    return "installed MAINFRAME permissions"


def uninstall(config: Path, source: Path, repo_root: Path, state_path: Path, dry_run: bool) -> str:
    state = read_state(state_path)
    if state is None:
        return "permissions are not managed by MAINFRAME"
    if not config.exists():
        raise ValueError("the managed Codex config is missing")
    _ = source, repo_root
    current = config.read_text(encoding="utf-8")
    _, remainder = verify_managed(current, state)
    data = parse_config(remainder)
    if any(key in data for key in TOP_KEYS):
        raise ValueError("a restored top-level permission key now conflicts with user configuration")
    shell = data.get("shell_environment_policy")
    if isinstance(shell, dict) and "inherit" in shell and any(i["kind"] == "shell" for i in state["removed"]):
        raise ValueError("shell_environment_policy.inherit now conflicts with user configuration")
    if "sandbox_workspace_write" in data and any(i["kind"] == "table" for i in state["removed"]):
        raise ValueError("sandbox_workspace_write now conflicts with user configuration")
    restored = restore_legacy(remainder, state["removed"])
    parse_config(restored)
    if dry_run:
        return "would remove MAINFRAME permissions and restore displaced settings"
    if state.get("config_was_missing") and not restored.strip():
        config.unlink()
    else:
        atomic_write(config, restored)
    state_path.unlink()
    return "removed MAINFRAME permissions"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("install", "uninstall"))
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--backup", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    def run() -> str:
        if args.action == "install":
            return install(args.config, args.source, args.repo_root, args.state, args.backup, args.dry_run)
        return uninstall(args.config, args.source, args.repo_root, args.state, args.dry_run)

    try:
        if args.dry_run:
            message = run()
        else:
            lock = args.state.with_suffix(".lock")
            lock.parent.mkdir(parents=True, exist_ok=True)
            with lock.open("a+", encoding="utf-8") as handle:
                fcntl.flock(handle, fcntl.LOCK_EX)
                message = run()
            if not args.state.exists() and lock.exists():
                lock.unlink()
    except (OSError, ValueError, TOMLDecodeError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Error: {exc}") from exc
    print(message)


if __name__ == "__main__":
    main()
