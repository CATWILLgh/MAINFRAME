#!/usr/bin/env python3
"""Install one MAINFRAME artifact as a drift-aware regular copy."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import sys
import tempfile
from typing import Any


STATE_VERSION = 1


class ManagedArtifactError(RuntimeError):
    pass


def _ignored(relative: Path) -> bool:
    return (
        "__pycache__" in relative.parts
        or relative.name == ".DS_Store"
        or relative.suffix == ".pyc"
    )


def _hash_bytes(digest: "hashlib._Hash", value: bytes) -> None:
    digest.update(len(value).to_bytes(8, "big"))
    digest.update(value)


def artifact_digest(path: Path) -> str:
    if not path.exists() and not path.is_symlink():
        raise ManagedArtifactError(f"artifact is missing: {path}")

    digest = hashlib.sha256()
    if path.is_symlink():
        _hash_bytes(digest, b"symlink")
        _hash_bytes(digest, os.readlink(path).encode())
        return digest.hexdigest()
    if path.is_file():
        _hash_bytes(digest, b"file")
        _hash_bytes(digest, b"executable" if path.stat().st_mode & stat.S_IXUSR else b"regular")
        _hash_bytes(digest, path.read_bytes())
        return digest.hexdigest()
    if not path.is_dir():
        raise ManagedArtifactError(f"unsupported artifact type: {path}")

    _hash_bytes(digest, b"directory")
    for child in sorted(path.rglob("*"), key=lambda item: item.relative_to(path).as_posix()):
        relative_path = child.relative_to(path)
        if _ignored(relative_path):
            continue
        relative = relative_path.as_posix().encode()
        _hash_bytes(digest, relative)
        if child.is_symlink():
            _hash_bytes(digest, b"symlink")
            _hash_bytes(digest, os.readlink(child).encode())
        elif child.is_dir():
            _hash_bytes(digest, b"directory")
        elif child.is_file():
            _hash_bytes(digest, b"file")
            _hash_bytes(
                digest,
                b"executable" if child.stat().st_mode & stat.S_IXUSR else b"regular",
            )
            _hash_bytes(digest, child.read_bytes())
        else:
            raise ManagedArtifactError(f"unsupported artifact type: {child}")
    return digest.hexdigest()


def _read_state(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    if path.is_symlink() or not path.is_file():
        raise ManagedArtifactError(f"managed state is not a regular file: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManagedArtifactError(f"managed state is invalid: {path}: {exc}") from exc
    if not isinstance(value, dict) or value.get("version") != STATE_VERSION:
        raise ManagedArtifactError(f"managed state has an unsupported shape: {path}")
    for key in ("source", "target", "managed_digest", "original_backup"):
        if not isinstance(value.get(key), str):
            raise ManagedArtifactError(f"managed state is missing {key}: {path}")
    return value


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _remove(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def _copy_to_temporary(source: Path, target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{target.name}.mainframe-", dir=target.parent))
    staged = temporary / "artifact"
    try:
        if source.is_dir():
            shutil.copytree(
                source,
                staged,
                symlinks=True,
                ignore=lambda directory, names: {
                    name
                    for name in names
                    if _ignored(Path(directory, name).relative_to(source))
                },
            )
        elif source.is_file():
            shutil.copy2(source, staged)
        else:
            raise ManagedArtifactError(f"source must be a regular file or directory: {source}")
        return temporary
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def _install_staged(staging_dir: Path, target: Path) -> None:
    staged = staging_dir / "artifact"
    displaced = staging_dir / "displaced"
    try:
        if target.exists() or target.is_symlink():
            os.replace(target, displaced)
        os.replace(staged, target)
    except Exception:
        if not (target.exists() or target.is_symlink()) and displaced.exists():
            os.replace(displaced, target)
        raise
    finally:
        if displaced.exists() or displaced.is_symlink():
            _remove(displaced)
        shutil.rmtree(staging_dir, ignore_errors=True)


def _unique_backup(backup_root: Path, target: Path) -> Path:
    backup_root.mkdir(parents=True, exist_ok=True)
    candidate = backup_root / target.name
    index = 2
    while candidate.exists() or candidate.is_symlink():
        candidate = backup_root / f"{target.name}-{index}"
        index += 1
    return candidate


def _move_to_backup(target: Path, backup_root: Path) -> Path:
    backup = _unique_backup(backup_root, target)
    os.replace(target, backup)
    return backup


def _legacy_owned_link(target: Path, source: Path, legacy_link_source: str = "") -> bool:
    if not target.is_symlink():
        return False
    expected = Path(legacy_link_source).resolve(strict=False) if legacy_link_source else source
    return target.resolve(strict=False) == expected.resolve(strict=False)


def _legacy_owned_target(source: Path, target: Path, args: argparse.Namespace) -> bool:
    if _legacy_owned_link(target, source, args.legacy_link_source):
        return True
    return (
        bool(args.legacy_managed_digest)
        and target.is_file()
        and not target.is_symlink()
        and artifact_digest(target) == args.legacy_managed_digest
    )


def _changed_target(target: Path, state: dict[str, Any]) -> bool:
    if not target.exists() or target.is_symlink():
        return True
    return artifact_digest(target) != state["managed_digest"]


def _needs_consent(source: Path, target: Path, state: dict[str, Any] | None, args: argparse.Namespace) -> bool:
    if state is not None:
        return _changed_target(target, state)
    if not (target.exists() or target.is_symlink()):
        return False
    if _legacy_owned_target(source, target, args):
        return False
    return True


def _confirm(message: str, *, replace_modified: bool, interactive: bool, check_only: bool) -> None:
    if replace_modified:
        return
    if check_only and interactive and sys.stdin.isatty():
        return
    if interactive and sys.stdin.isatty():
        answer = input(f"{message} [y/N] ").strip().lower()
        if answer in {"y", "yes"}:
            return
    raise ManagedArtifactError(
        f"{message} Preserved it. Confirm interactively or rerun with --replace-modified."
    )


def check_or_install(args: argparse.Namespace, *, check_only: bool) -> None:
    source = args.source.resolve()
    target = args.target.absolute()
    state_path = args.state.absolute()
    state = _read_state(state_path)
    source_digest = artifact_digest(source)

    if state is not None and Path(state["target"]) != target:
        raise ManagedArtifactError(f"managed state belongs to another target: {state_path}")

    needs_consent = _needs_consent(source, target, state, args)
    if needs_consent:
        _confirm(
            f"The installed artifact has local or pre-existing content at {target}.",
            replace_modified=args.replace_modified,
            interactive=args.interactive,
            check_only=check_only,
        )
    if check_only or args.dry_run:
        verb = "would replace managed copy after backup" if needs_consent else "would install managed copy"
        print(f"{verb}: {target}")
        return

    original_backup = state["original_backup"] if state is not None else args.legacy_backup
    if state is None and (target.exists() or target.is_symlink()):
        if _legacy_owned_target(source, target, args):
            if target.is_symlink():
                target.unlink()
        else:
            moved = _move_to_backup(target, args.backup_root.absolute())
            if args.legacy_managed_digest or args.legacy_link_source:
                print(f"backed up local changes: {moved}")
            else:
                original_backup = str(moved)
                print(f"backed up existing artifact: {original_backup}")
    elif state is not None and _changed_target(target, state):
        if target.exists() or target.is_symlink():
            local_backup = _move_to_backup(target, args.backup_root.absolute())
            print(f"backed up local changes: {local_backup}")

    if target.exists() and not target.is_symlink() and artifact_digest(target) == source_digest:
        pass
    else:
        staging = _copy_to_temporary(source, target)
        _install_staged(staging, target)

    _atomic_json(
        state_path,
        {
            "version": STATE_VERSION,
            "source": str(source),
            "target": str(target),
            "managed_digest": source_digest,
            "original_backup": original_backup,
        },
    )
    print(f"installed managed copy: {target}")


def _handle_legacy_uninstall(
    args: argparse.Namespace,
    source: Path,
    target: Path,
    *,
    check_only: bool,
) -> bool:
    legacy_known = bool(args.legacy_managed_digest or args.legacy_link_source)
    if not legacy_known or not (target.exists() or target.is_symlink()):
        return False
    changed = not _legacy_owned_target(source, target, args)
    if changed:
        _confirm(
            f"The installed artifact has local changes at {target}.",
            replace_modified=args.replace_modified,
            interactive=args.interactive,
            check_only=check_only,
        )
    if check_only or args.dry_run:
        print(f"would remove legacy managed artifact: {target}")
        return True
    if changed:
        local_backup = _move_to_backup(target, args.backup_root.absolute())
        print(f"backed up local changes: {local_backup}")
    else:
        _remove(target)
    original_backup = Path(args.legacy_backup) if args.legacy_backup else None
    if original_backup is not None and original_backup.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(original_backup, target)
        print(f"restored original artifact: {target}")
    print(f"removed legacy managed artifact: {target}")
    return True


def check_or_uninstall(args: argparse.Namespace, *, check_only: bool) -> None:
    source = args.source.resolve()
    target = args.target.absolute()
    state_path = args.state.absolute()
    state = _read_state(state_path)

    if state is None:
        if _handle_legacy_uninstall(args, source, target, check_only=check_only):
            return
        if _legacy_owned_link(target, source, args.legacy_link_source):
            if check_only or args.dry_run:
                print(f"would remove legacy link: {target}")
            else:
                target.unlink()
                print(f"removed legacy link: {target}")
        else:
            print(f"not managed: {target}")
        return
    if Path(state["target"]) != target:
        raise ManagedArtifactError(f"managed state belongs to another target: {state_path}")

    changed = _changed_target(target, state)
    if changed:
        _confirm(
            f"The installed artifact has local changes at {target}.",
            replace_modified=args.replace_modified,
            interactive=args.interactive,
            check_only=check_only,
        )
    if check_only or args.dry_run:
        print(f"would remove managed copy: {target}")
        if state["original_backup"]:
            print(f"would restore original artifact: {state['original_backup']}")
        return

    if target.exists() or target.is_symlink():
        if changed:
            local_backup = _move_to_backup(target, args.backup_root.absolute())
            print(f"backed up local changes: {local_backup}")
        else:
            _remove(target)
    original_backup = Path(state["original_backup"]) if state["original_backup"] else None
    if original_backup is not None and (original_backup.exists() or original_backup.is_symlink()):
        target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(original_backup, target)
        print(f"restored original artifact: {target}")
    state_path.unlink()
    print(f"removed managed copy: {target}")


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    result.add_argument("action", choices=("check-install", "install", "check-uninstall", "uninstall"))
    result.add_argument("--source", required=True, type=Path)
    result.add_argument("--target", required=True, type=Path)
    result.add_argument("--state", required=True, type=Path)
    result.add_argument("--backup-root", required=True, type=Path)
    result.add_argument("--dry-run", action="store_true")
    result.add_argument("--replace-modified", action="store_true")
    result.add_argument("--interactive", action="store_true")
    result.add_argument("--legacy-backup", default="")
    result.add_argument("--legacy-managed-digest", default="")
    result.add_argument("--legacy-link-source", default="")
    return result


def main() -> int:
    args = parser().parse_args()
    try:
        if args.action in {"check-install", "install"}:
            check_or_install(args, check_only=args.action == "check-install")
        else:
            check_or_uninstall(args, check_only=args.action == "check-uninstall")
    except ManagedArtifactError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
