#!/usr/bin/env python3
"""Merge and remove MAINFRAME-owned Claude Code user settings safely."""

from __future__ import annotations

import argparse
import copy
import json
import os
import pathlib
import shutil
import stat
import tempfile
from typing import Any


STATE_VERSION = 1
ARRAY_PATHS = (
    ("permissions", "allow"),
    ("permissions", "ask"),
    ("permissions", "deny"),
)
MANAGED_VALUE_PATHS = (
    ("permissions", "defaultMode"),
    ("permissions", "disableBypassPermissionsMode"),
    ("enabledPlugins", "context7@claude-plugins-official"),
)
MISSING = object()


class SettingsError(RuntimeError):
    """A settings input is unsafe to mutate."""


def _load_object(path: pathlib.Path, *, required: bool) -> dict[str, Any]:
    if not path.exists() and not path.is_symlink():
        if required:
            raise SettingsError(f"required JSON file does not exist: {path}")
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SettingsError(f"cannot read valid JSON from {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise SettingsError(f"JSON root must be an object: {path}")
    return value


def _path_key(path: tuple[str, ...]) -> str:
    return "/".join(path)


def _get(root: dict[str, Any], path: tuple[str, ...]) -> Any:
    current: Any = root
    for part in path:
        if not isinstance(current, dict) or part not in current:
            return MISSING
        current = current[part]
    return current


def _set(root: dict[str, Any], path: tuple[str, ...], value: Any) -> None:
    current = root
    for part in path[:-1]:
        if part not in current:
            child = {}
            current[part] = child
        else:
            child = current[part]
        if not isinstance(child, dict):
            raise SettingsError(
                f"user setting {'/'.join(path[:-1])} must be an object"
            )
        current = child
    current[path[-1]] = copy.deepcopy(value)


def _delete(root: dict[str, Any], path: tuple[str, ...]) -> None:
    parents: list[tuple[dict[str, Any], str]] = []
    current: Any = root
    for part in path[:-1]:
        if not isinstance(current, dict) or part not in current:
            return
        parents.append((current, part))
        current = current[part]
    if not isinstance(current, dict):
        return
    current.pop(path[-1], None)
    for parent, key in reversed(parents):
        child = parent.get(key)
        if isinstance(child, dict) and not child:
            parent.pop(key, None)
        else:
            break


def _leaf_paths(root: dict[str, Any]) -> list[tuple[str, ...]]:
    result: list[tuple[str, ...]] = []

    def visit(value: Any, prefix: tuple[str, ...]) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                visit(child, (*prefix, key))
        else:
            result.append(prefix)

    visit(root, ())
    return result


def _validate_template(template: dict[str, Any]) -> None:
    for path in ARRAY_PATHS:
        value = _get(template, path)
        if not isinstance(value, list) or not all(
            isinstance(item, str) for item in value
        ):
            raise SettingsError(
                f"template {_path_key(path)} must be an array of strings"
            )


def _empty_state(*, target_existed: bool) -> dict[str, Any]:
    return {
        "version": STATE_VERSION,
        "targetExistedBeforeInstall": target_existed,
        "arrays": {},
        "values": {},
    }


def _load_state(path: pathlib.Path) -> dict[str, Any] | None:
    if path.is_symlink():
        raise SettingsError(f"refusing to use symlinked MAINFRAME state: {path}")
    if not path.exists():
        return None
    state = _load_object(path, required=True)
    if state.get("version") != STATE_VERSION:
        raise SettingsError(
            f"unsupported MAINFRAME settings state version in {path}"
        )
    if not isinstance(state.get("arrays"), dict) or not isinstance(
        state.get("values"), dict
    ) or not isinstance(state.get("targetExistedBeforeInstall"), bool):
        raise SettingsError(f"invalid MAINFRAME settings state: {path}")
    return state


def _is_legacy_link(target: pathlib.Path, source: pathlib.Path) -> bool:
    return target.is_symlink() and target.resolve(strict=False) == source.resolve()


def _merge(
    template: dict[str, Any],
    current: dict[str, Any],
    state: dict[str, Any],
    *,
    legacy_link: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    merged = copy.deepcopy(current)
    next_state = copy.deepcopy(state)
    arrays = next_state["arrays"]
    values = next_state["values"]

    for path in ARRAY_PATHS:
        key = _path_key(path)
        template_items = list(dict.fromkeys(_get(template, path)))
        current_value = _get(merged, path)
        if current_value is MISSING:
            current_items: list[str] = []
        elif isinstance(current_value, list) and all(
            isinstance(item, str) for item in current_value
        ):
            current_items = list(current_value)
        else:
            raise SettingsError(f"user setting {key} must be an array of strings")

        array_record = arrays.get(key)
        if array_record is None:
            array_record = {
                "owned": [],
                "originalPresent": current_value is not MISSING and not legacy_link,
            }
        if not isinstance(array_record, dict):
            raise SettingsError(f"invalid owned array state for {key}")
        previous_owned = array_record.get("owned")
        if not isinstance(previous_owned, list) or not all(
            isinstance(item, str) for item in previous_owned
        ) or not isinstance(array_record.get("originalPresent"), bool):
            raise SettingsError(f"invalid owned array state for {key}")

        stale = set(previous_owned) - set(template_items)
        current_items = [item for item in current_items if item not in stale]
        owned = [item for item in previous_owned if item in template_items]
        for item in template_items:
            if item not in current_items:
                current_items.append(item)
                if item not in owned:
                    owned.append(item)
            elif legacy_link and item not in owned:
                owned.append(item)
        if current_items or array_record["originalPresent"]:
            _set(merged, path, current_items)
        else:
            _delete(merged, path)
        if owned:
            array_record["owned"] = owned
            arrays[key] = array_record
        else:
            arrays.pop(key, None)

    special_paths = set(ARRAY_PATHS) | set(MANAGED_VALUE_PATHS)
    default_paths = [
        path for path in _leaf_paths(template) if path not in special_paths
    ]
    template_value_keys = {
        _path_key(path) for path in (*MANAGED_VALUE_PATHS, *default_paths)
        if _get(template, path) is not MISSING
    }

    for key in list(values):
        if key in template_value_keys:
            continue
        record = values[key]
        if not isinstance(record, dict):
            raise SettingsError(f"invalid value state for {key}")
        path = tuple(key.split("/"))
        current_value = _get(merged, path)
        if current_value == record.get("applied", MISSING):
            if record.get("originalPresent"):
                _set(merged, path, record.get("original"))
            else:
                _delete(merged, path)
        values.pop(key, None)

    for path in MANAGED_VALUE_PATHS:
        source_value = _get(template, path)
        if source_value is MISSING:
            continue
        key = _path_key(path)
        record = values.get(key)
        if record is None:
            old_value = _get(current, path)
            record = {
                "mode": "managed",
                "originalPresent": old_value is not MISSING and not legacy_link,
                "applied": copy.deepcopy(source_value),
            }
            if old_value is not MISSING and not legacy_link:
                record["original"] = copy.deepcopy(old_value)
        elif not isinstance(record, dict) or record.get("mode") != "managed":
            raise SettingsError(f"invalid managed value state for {key}")
        record["applied"] = copy.deepcopy(source_value)
        values[key] = record
        _set(merged, path, source_value)

    for path in default_paths:
        source_value = _get(template, path)
        key = _path_key(path)
        record = values.get(key)
        current_value = _get(merged, path)
        if record is not None:
            if not isinstance(record, dict) or record.get("mode") != "default":
                raise SettingsError(f"invalid default value state for {key}")
            if current_value == record.get("applied", MISSING):
                _set(merged, path, source_value)
                record["applied"] = copy.deepcopy(source_value)
                values[key] = record
            else:
                values.pop(key, None)
            continue
        if legacy_link:
            values[key] = {
                "mode": "default",
                "originalPresent": False,
                "applied": copy.deepcopy(current_value),
            }
        elif current_value is MISSING:
            _set(merged, path, source_value)
            values[key] = {
                "mode": "default",
                "originalPresent": False,
                "applied": copy.deepcopy(source_value),
            }

    return merged, next_state


def _remove_owned(
    current: dict[str, Any], state: dict[str, Any]
) -> dict[str, Any]:
    result = copy.deepcopy(current)
    for key, record in state["arrays"].items():
        if not isinstance(record, dict):
            raise SettingsError(f"invalid owned array state for {key}")
        owned = record.get("owned")
        if not isinstance(owned, list):
            raise SettingsError(f"invalid owned array state for {key}")
        path = tuple(key.split("/"))
        value = _get(result, path)
        if isinstance(value, list):
            owned_set = set(owned)
            remaining = [item for item in value if item not in owned_set]
            if remaining or record.get("originalPresent"):
                _set(result, path, remaining)
            else:
                _delete(result, path)

    for key, record in state["values"].items():
        if not isinstance(record, dict):
            continue
        path = tuple(key.split("/"))
        current_value = _get(result, path)
        if current_value != record.get("applied", MISSING):
            continue
        if record.get("originalPresent"):
            _set(result, path, record.get("original"))
        else:
            _delete(result, path)
    return result


def _write_json_atomic(path: pathlib.Path, value: dict[str, Any], mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = pathlib.Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _backup(target: pathlib.Path, backup: pathlib.Path) -> None:
    if backup.exists() or backup.is_symlink():
        raise SettingsError(f"backup target already exists: {backup}")
    shutil.copy2(target, backup, follow_symlinks=True)


def check(source: pathlib.Path, target: pathlib.Path, state_path: pathlib.Path) -> None:
    template = _load_object(source, required=True)
    _validate_template(template)
    legacy_link = _is_legacy_link(target, source)
    if target.is_symlink() and not legacy_link:
        raise SettingsError(
            f"refusing to replace unrelated settings symlink: {target}"
        )
    current = _load_object(target, required=False)
    state = _load_state(state_path)
    if state is None:
        state = _empty_state(
            target_existed=(target.exists() and not legacy_link)
        )
    _merge(template, current, state, legacy_link=legacy_link)


def install(
    source: pathlib.Path,
    target: pathlib.Path,
    state_path: pathlib.Path,
    backup: pathlib.Path,
    *,
    dry_run: bool,
) -> bool:
    template = _load_object(source, required=True)
    _validate_template(template)
    legacy_link = _is_legacy_link(target, source)
    if target.is_symlink() and not legacy_link:
        raise SettingsError(
            f"refusing to replace unrelated settings symlink: {target}"
        )
    current = _load_object(target, required=False)
    state = _load_state(state_path)
    if state is not None and not target.exists() and not target.is_symlink():
        state = None
    if state is None:
        state = _empty_state(
            target_existed=(target.exists() and not legacy_link)
        )
    merged, next_state = _merge(
        template, current, state, legacy_link=legacy_link
    )
    changed = legacy_link or merged != current or next_state != state
    if dry_run:
        if changed:
            print("would merge MAINFRAME settings into user settings")
        else:
            print("MAINFRAME settings already merged")
        return changed
    if not changed:
        print("MAINFRAME settings already merged")
        return False
    backed_up = target.exists() or target.is_symlink()
    target_mode = 0o600
    if target.exists() and not target.is_symlink():
        target_mode = stat.S_IMODE(target.stat().st_mode)
    if backed_up:
        _backup(target, backup)
        if not legacy_link and _load_object(target, required=True) != current:
            raise SettingsError(
                "user settings changed during install; no settings were overwritten"
            )
        if legacy_link:
            target.unlink()
    try:
        _write_json_atomic(target, merged, target_mode)
        _write_json_atomic(state_path, next_state, 0o600)
    except OSError as exc:
        try:
            target.unlink(missing_ok=True)
            if legacy_link:
                target.symlink_to(source)
            elif backed_up:
                _write_json_atomic(target, current, target_mode)
        except OSError:
            pass
        raise SettingsError(
            f"cannot write settings transaction; previous target was restored: {exc}"
        ) from exc
    if backed_up:
        print(f"merged MAINFRAME settings; backup: {backup}")
    else:
        print("merged MAINFRAME settings")
    return True


def uninstall(
    source: pathlib.Path,
    target: pathlib.Path,
    state_path: pathlib.Path,
    backup: pathlib.Path,
    *,
    dry_run: bool,
) -> bool:
    if _is_legacy_link(target, source) and not state_path.exists():
        if dry_run:
            print("would remove legacy MAINFRAME settings symlink")
            return True
        target.unlink()
        print("removed legacy MAINFRAME settings symlink")
        return True
    state = _load_state(state_path)
    if state is None:
        print("no MAINFRAME settings state to remove")
        return False
    if not target.exists() and not target.is_symlink():
        if dry_run:
            print("would remove stale MAINFRAME settings state")
            return True
        state_path.unlink(missing_ok=True)
        print("removed stale MAINFRAME settings state")
        return True
    current = _load_object(target, required=False)
    result = _remove_owned(current, state)
    remove_target = (
        not state.get("targetExistedBeforeInstall", True) and not result
    )
    if dry_run:
        print("would remove MAINFRAME-owned user settings")
        return True
    backed_up = target.exists() or target.is_symlink()
    if backed_up:
        _backup(target, backup)
        if _load_object(target, required=True) != current:
            raise SettingsError(
                "user settings changed during uninstall; no settings were overwritten"
            )
    if remove_target:
        target.unlink(missing_ok=True)
    else:
        target_mode = 0o600
        if target.exists() and not target.is_symlink():
            target_mode = stat.S_IMODE(target.stat().st_mode)
        _write_json_atomic(target, result, target_mode)
    state_path.unlink(missing_ok=True)
    if backed_up:
        print(f"removed MAINFRAME-owned settings; backup: {backup}")
    else:
        print("removed MAINFRAME-owned settings")
    return True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("check", "install", "uninstall"))
    parser.add_argument("--source", type=pathlib.Path, required=True)
    parser.add_argument("--target", type=pathlib.Path, required=True)
    parser.add_argument("--state", type=pathlib.Path, required=True)
    parser.add_argument("--backup", type=pathlib.Path)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.action == "check":
            check(args.source, args.target, args.state)
        elif args.action == "install":
            if args.backup is None:
                raise SettingsError("--backup is required for install")
            install(
                args.source,
                args.target,
                args.state,
                args.backup,
                dry_run=args.dry_run,
            )
        else:
            if args.backup is None:
                raise SettingsError("--backup is required for uninstall")
            uninstall(
                args.source,
                args.target,
                args.state,
                args.backup,
                dry_run=args.dry_run,
            )
    except (SettingsError, OSError) as exc:
        print(f"settings error: {exc}", file=os.sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
