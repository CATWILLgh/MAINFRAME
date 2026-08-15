#!/usr/bin/env python3
"""Merge and remove only the hook groups owned by the Codex adapter."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shlex
import tempfile


def _atomic_write(path: Path, text: str) -> None:
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
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def _load_document(path: Path) -> dict:
    if not path.exists():
        return {"hooks": {}}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Codex hooks file is not valid JSON: {path}") from exc
    if not isinstance(value, dict):
        raise ValueError("Codex hooks file must contain a JSON object")
    hooks = value.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise ValueError("Codex hooks field must contain an object")
    for event, groups in hooks.items():
        if not isinstance(event, str) or not isinstance(groups, list):
            raise ValueError("every Codex hook event must contain an array")
        if not all(isinstance(group, dict) for group in groups):
            raise ValueError("every Codex hook matcher group must be an object")
    return value


def _render_source(source: Path, script: Path) -> dict[str, list[dict]]:
    marker = "@MAINFRAME_HOOK_SCRIPT@"
    body = source.read_text(encoding="utf-8")
    if marker not in body:
        raise ValueError("MAINFRAME hook source has no script marker")
    rendered = body.replace(marker, shlex.quote(str(script.resolve())))
    document = json.loads(rendered)
    hooks = document.get("hooks")
    if not isinstance(hooks, dict) or not hooks:
        raise ValueError("MAINFRAME hook source has no hook groups")
    for groups in hooks.values():
        if not isinstance(groups, list) or not groups:
            raise ValueError("MAINFRAME hook source contains an empty event")
    return hooks


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical(value).encode()).hexdigest()


def _read_state(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("MAINFRAME hook installation state is invalid") from exc
    if not isinstance(value, dict) or not isinstance(value.get("managed"), dict):
        raise ValueError("MAINFRAME hook installation state is incomplete")
    if value.get("managed_sha") != _digest(value["managed"]):
        raise ValueError("MAINFRAME hook installation state was modified")
    return value


def _remove_exact(document: dict, managed: dict[str, list[dict]]) -> None:
    hooks = document["hooks"]
    for event, owned_groups in managed.items():
        groups = hooks.get(event)
        if not isinstance(groups, list):
            raise ValueError(f"managed MAINFRAME hook event is missing: {event}")
        for owned in owned_groups:
            matches = [index for index, group in enumerate(groups) if group == owned]
            if len(matches) != 1:
                raise ValueError(
                    f"managed MAINFRAME hook group changed or is duplicated: {event}"
                )
            groups.pop(matches[0])
        if not groups:
            hooks.pop(event)


def _contains_mainframe_script(document: dict) -> bool:
    for groups in document["hooks"].values():
        for group in groups:
            for handler in group.get("hooks", []):
                command = handler.get("command") if isinstance(handler, dict) else None
                if isinstance(command, str) and "mainframe-hook.py" in command:
                    return True
    return False


def _merge(document: dict, managed: dict[str, list[dict]]) -> None:
    for event, groups in managed.items():
        document["hooks"].setdefault(event, []).extend(groups)


def _render_document(document: dict) -> str:
    return json.dumps(document, ensure_ascii=False, indent=2) + "\n"


def install(target: Path, source: Path, script: Path, state_path: Path, dry_run: bool) -> str:
    existed = target.exists()
    document = _load_document(target)
    state = _read_state(state_path)
    if state is not None:
        _remove_exact(document, state["managed"])
    elif _contains_mainframe_script(document):
        raise ValueError("MAINFRAME hook command exists without installation state")
    managed = _render_source(source, script)
    _merge(document, managed)
    rendered = _render_document(document)
    if state is not None and state["managed"] == managed:
        current = target.read_text(encoding="utf-8") if target.exists() else ""
        if current == rendered:
            return "hooks already installed" if not dry_run else "would keep existing hook groups"
    if dry_run:
        return "would merge MAINFRAME hook groups into Codex hooks.json"
    _atomic_write(target, rendered)
    state_value = {
        "target_was_missing": not existed if state is None else state.get("target_was_missing", False),
        "managed": managed,
        "managed_sha": _digest(managed),
    }
    _atomic_write(state_path, json.dumps(state_value, ensure_ascii=True, indent=2) + "\n")
    return "installed MAINFRAME Codex hooks"


def uninstall(target: Path, state_path: Path, dry_run: bool) -> str:
    state = _read_state(state_path)
    if state is None:
        return "hooks are not managed by MAINFRAME"
    if not target.exists():
        raise ValueError("managed Codex hooks.json is missing")
    document = _load_document(target)
    _remove_exact(document, state["managed"])
    should_remove = bool(state.get("target_was_missing")) and document == {"hooks": {}}
    if dry_run:
        return "would remove only MAINFRAME hook groups"
    if should_remove:
        target.unlink()
    else:
        _atomic_write(target, _render_document(document))
    state_path.unlink()
    return "removed MAINFRAME Codex hooks"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("install", "uninstall"))
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--script", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.dry_run:
        if args.action == "install":
            result = install(
                args.target, args.source, args.script, args.state, args.dry_run
            )
        else:
            result = uninstall(args.target, args.state, args.dry_run)
        print(result)
        return

    lock_path = args.state.with_suffix(args.state.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        if args.action == "install":
            result = install(
                args.target, args.source, args.script, args.state, False
            )
        else:
            result = uninstall(args.target, args.state, False)
    if not args.dry_run:
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass
    print(result)


if __name__ == "__main__":
    main()
