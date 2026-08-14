#!/usr/bin/env python3
"""Install and remove MAINFRAME's Codex permission-profile allowlist."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
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


START = "# >>> MAINFRAME CODEX PROFILE ALLOWLIST >>>"
END = "# <<< MAINFRAME CODEX PROFILE ALLOWLIST <<<"
EXPECTED_PROFILES = {
    ":read-only": True,
    ":workspace": True,
    ":danger-full-access": True,
    "mainframe": True,
}
TABLE_RE = re.compile(r"^\s*\[([^]]+)]\s*(?:#.*)?$")
ASSIGN_RE = re.compile(r'^\s*(?:"([^"]+)"|([A-Za-z0-9_.:-]+))\s*=\s*(.*?)\s*(?:#.*)?$')


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
        raise ValueError("the MAINFRAME profile allowlist markers are incomplete or duplicated")
    tail = end + len(END)
    if tail < len(text) and text[tail] == "\n":
        tail += 1
    if tail < len(text) and text[tail] == "\n":
        tail += 1
    return text[start:tail], text[:start] + text[tail:]


def parse_toml(text: str) -> dict:
    if not text.strip():
        return {}
    if tomllib is not None:
        return tomllib.loads(text)
    data: dict = {}
    section = ""
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        table_match = TABLE_RE.match(line)
        if table_match:
            section = table_match.group(1)
            if section == "allowed_permission_profiles":
                if "allowed_permission_profiles" in data:
                    raise ValueError("allowed_permission_profiles is defined more than once")
                data["allowed_permission_profiles"] = {}
            continue
        assign_match = ASSIGN_RE.match(line)
        if not assign_match:
            continue
        key = assign_match.group(1) or assign_match.group(2)
        value = assign_match.group(3)
        if section == "allowed_permission_profiles":
            if value not in {"true", "false"}:
                raise ValueError("allowed_permission_profiles values must be booleans")
            profiles = data["allowed_permission_profiles"]
            if key in profiles:
                raise ValueError(f"duplicate allowed permission profile: {key}")
            profiles[key] = value == "true"
        elif section == "" and key == "allowed_permission_profiles":
            data["allowed_permission_profiles"] = value
        elif section == "" and key.startswith("allowed_permission_profiles."):
            data["allowed_permission_profiles"] = value
        elif section == "":
            data[key] = value
    return data


def validate_fragment(fragment: str) -> None:
    data = parse_toml(fragment)
    if data != {"allowed_permission_profiles": EXPECTED_PROFILES}:
        raise ValueError("the MAINFRAME requirements source must allow exactly three built-ins and mainframe")


def atomic_write(path: Path, text: str, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, mode)
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
        raise ValueError("the MAINFRAME profile allowlist changed after installation")
    return current, remainder


def target_mode(path: Path) -> int:
    if not path.exists():
        return 0o644
    return stat.S_IMODE(path.stat().st_mode)


def install(requirements: Path, source: Path, state_path: Path, backup: Path, dry_run: bool) -> str:
    fragment = source.read_text(encoding="utf-8")
    validate_fragment(fragment)
    current = requirements.read_text(encoding="utf-8") if requirements.exists() else ""
    state = read_state(state_path)
    expected = managed_block(fragment)
    if state:
        current_block, remainder = verify_managed(current, state)
        candidate = current.replace(current_block, expected, 1)
        parse_toml(candidate)
        if current_block == expected:
            return "profile allowlist already installed" if not dry_run else "would keep existing profile allowlist"
        if dry_run:
            return "would update the owned MAINFRAME profile allowlist"
        state["managed_sha"] = sha(expected)
        atomic_write(requirements, candidate, target_mode(requirements))
        atomic_write(state_path, json.dumps(state, ensure_ascii=True, indent=2) + "\n", 0o644)
        return "updated MAINFRAME profile allowlist"

    block, _ = split_managed(current)
    if block is not None:
        raise ValueError("MAINFRAME profile allowlist markers exist without installation state")
    data = parse_toml(current)
    if "allowed_permission_profiles" in data:
        raise ValueError("an unmanaged allowed_permission_profiles table already exists")
    if not current or current.endswith("\n\n"):
        separator = ""
    elif current.endswith("\n"):
        separator = "\n"
    else:
        separator = "\n\n"
    candidate = current + separator + expected
    parse_toml(candidate)
    if dry_run:
        return "would back up and merge the MAINFRAME profile allowlist"

    was_missing = not requirements.exists()
    original_mode = target_mode(requirements)
    requirements.parent.mkdir(parents=True, exist_ok=True)
    if requirements.exists():
        atomic_write(backup, current, 0o600)
    state_data = {
        "backup_path": str(backup) if requirements.exists() else "-",
        "managed_sha": sha(expected),
        "original_mode": original_mode,
        "requirements_was_missing": was_missing,
        "separator": separator,
    }
    atomic_write(requirements, candidate, original_mode)
    atomic_write(state_path, json.dumps(state_data, ensure_ascii=True, indent=2) + "\n", 0o644)
    return "installed MAINFRAME profile allowlist"


def uninstall(requirements: Path, state_path: Path, dry_run: bool) -> str:
    state = read_state(state_path)
    if state is None:
        return "profile allowlist is not managed by MAINFRAME"
    if not requirements.exists():
        raise ValueError("the managed Codex requirements file is missing")
    current = requirements.read_text(encoding="utf-8")
    _, remainder = verify_managed(current, state)
    separator = state.get("separator", "")
    if separator:
        if not remainder.endswith(separator):
            raise ValueError("content immediately before the MAINFRAME profile allowlist changed")
        remainder = remainder[: -len(separator)]
    parse_toml(remainder)
    if dry_run:
        return "would remove the MAINFRAME profile allowlist"
    if state.get("requirements_was_missing") and not remainder.strip():
        requirements.unlink()
    else:
        atomic_write(requirements, remainder, int(state.get("original_mode", 0o644)))
    state_path.unlink()
    return "removed MAINFRAME profile allowlist"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("install", "uninstall"))
    parser.add_argument("--requirements", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--backup", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    def run() -> str:
        if args.action == "install":
            return install(args.requirements, args.source, args.state, args.backup, args.dry_run)
        return uninstall(args.requirements, args.state, args.dry_run)

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
