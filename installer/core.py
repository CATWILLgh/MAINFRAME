"""Small file transaction and ownership primitives used by the installer."""

from __future__ import annotations

import base64
from contextlib import contextmanager
from dataclasses import dataclass
import fcntl
import hashlib
import json
import os
from pathlib import Path
import tempfile


class Conflict(Exception):
    """An installation cannot preserve the observed boundary automatically."""


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def encode_json(value: object) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode()


def regular_bytes(path: Path) -> bytes | None:
    for candidate in (path, *path.parents):
        if candidate.is_symlink():
            raise Conflict(f"Refusing to change a symlink or its child: {path}")
    if not path.exists():
        return None
    if not path.is_file():
        raise Conflict(f"Expected a regular file: {path}")
    return path.read_bytes()


def atomic_write(path: Path, data: bytes, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            os.fchmod(stream.fileno(), mode)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def observed(path: Path):
    data = regular_bytes(path)
    return data, path.stat().st_mode & 0o777 if data is not None else None


@dataclass
class Change:
    path: Path
    before: bytes | None
    after: bytes | None
    mode: int = 0o600
    component: str = "support"
    before_mode: int | None = None

    @classmethod
    def to(cls, path: Path, after: bytes | None, mode=0o600, component="support"):
        return cls.from_snapshot(path, observed(path), after, mode, component)

    @classmethod
    def from_snapshot(cls, path: Path, snapshot, after, mode=0o600, component="support"):
        return cls(path, snapshot[0], after, mode, component, snapshot[1])

    @property
    def needed(self) -> bool:
        return self.before != self.after or (
            self.after is not None and self.before_mode != self.mode
        )

    def summary(self) -> dict:
        action = "remove" if self.after is None else "create" if self.before is None else "update"
        return {"action": action, "path": str(self.path), "component": self.component}


@contextmanager
def installation_lock(path: Path):
    regular_bytes(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with path.open("a+b") as stream:
        os.chmod(path, 0o600)
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise Conflict("Another MAINFRAME installation is active for this target.") from exc
        yield


def _pack(data: bytes | None) -> str | None:
    return None if data is None else base64.b64encode(data).decode("ascii")


def _unpack(value: str | None) -> bytes | None:
    return None if value is None else base64.b64decode(value, validate=True)


def restore(journal: Path, allowed_path) -> None:
    raw = regular_bytes(journal)
    if raw is None:
        return
    record = json.loads(raw)
    if record.get("version") != 1:
        raise Conflict("Unrecognized recovery format; preserve the recovery file.")
    changes = []
    for item in record["changes"]:
        path = Path(item["path"])
        if not path.is_absolute() or not allowed_path(path):
            raise Conflict(f"Recovery path is outside this installation: {path}")
        changes.append(Change(path, _unpack(item["before"]), _unpack(item["after"]),
                              item["mode"], before_mode=item["before_mode"]))
    # Check the whole boundary before restoring any file. Never replace a
    # concurrent edit merely because a previous transaction touched its path.
    for change in changes:
        current = observed(change.path)
        if current not in ((change.before, change.before_mode),
                           (change.after, change.mode if change.after is not None else None)):
            raise Conflict(f"Concurrent change needs manual recovery: {change.path}")
    for change in reversed(changes):
        current = observed(change.path)
        if current == (change.before, change.before_mode):
            continue
        if current != (change.after, change.mode if change.after is not None else None):
            raise Conflict(f"Concurrent change during recovery: {change.path}")
        if change.before is None:
            change.path.unlink(missing_ok=True)
        else:
            atomic_write(change.path, change.before, change.before_mode or 0o600)
    for raw_path in sorted(record.get("created_dirs", []), key=len, reverse=True):
        path = Path(raw_path)
        if allowed_path(path):
            try:
                path.rmdir()
            except OSError:
                pass  # Never remove a directory containing someone else's work.
    journal.unlink()


def transact(changes: list[Change], journal: Path, allowed_path) -> None:
    changes = [change for change in changes if change.needed]
    if not changes:
        return
    if journal.exists():
        raise Conflict(f"Recover the interrupted operation first: {journal}")
    created_dirs = set()
    for change in changes:
        if not allowed_path(change.path):
            raise Conflict(f"Change is outside this installation: {change.path}")
        if observed(change.path) != (change.before, change.before_mode):
            raise Conflict(f"The target changed after planning: {change.path}")
        parent = change.path.parent
        while not parent.exists():
            created_dirs.add(str(parent))
            parent = parent.parent
    record = {"version": 1, "created_dirs": sorted(created_dirs), "changes": [
        {"path": str(c.path), "before": _pack(c.before), "after": _pack(c.after),
         "mode": c.mode, "before_mode": c.before_mode} for c in changes
    ]}
    atomic_write(journal, encode_json(record))
    try:
        for change in changes:
            if observed(change.path) != (change.before, change.before_mode):
                raise Conflict(f"Concurrent change during installation: {change.path}")
            if change.after is None:
                change.path.unlink(missing_ok=True)
            else:
                atomic_write(change.path, change.after, change.mode)
    except Exception:
        restore(journal, allowed_path)
        raise
    journal.unlink()


def reconcile_files(artifacts: dict[Path, tuple[bytes, int, str, bool]], previous: dict,
                    allowed_path) -> tuple[list[Change], dict]:
    """Reuse foreign identical content without claiming ownership of it."""
    changes, records = [], {}
    for path, (data, mode, component, retain) in artifacts.items():
        snapshot = observed(path)
        before, before_mode = snapshot
        prior = previous.get(str(path))
        if prior and prior["owned"] and not prior.get("retain") and before is not None:
            if digest(before) != prior["sha256"] or before_mode != prior["mode"]:
                raise Conflict(f"Installed file was edited; preserve and reconcile it: {path}")
        if before is not None and retain:
            data, mode = before, before_mode
        elif before is not None and prior and not prior["owned"] and before != data:
            raise Conflict(f"Reused user-owned file differs from the new source: {path}")
        elif before is not None and prior is None and before != data:
            raise Conflict(f"Existing file has no installer ownership: {path}")
        # Reuse does not grant deletion rights, but recreating a now-missing
        # file is a new owned write. Otherwise verification could miss it.
        owned = before is None or bool(prior and prior["owned"])
        if not owned and before is not None:
            actual_mode = before_mode
            if mode & 0o111 and not actual_mode & 0o111:
                raise Conflict(f"A reused executable lacks execution permission: {path}")
            mode = actual_mode
        records[str(path)] = {"sha256": digest(data), "mode": mode,
                              "component": component, "owned": owned, "retain": retain}
        if owned:
            changes.append(Change.from_snapshot(path, snapshot, data, mode, component))
    for raw_path, prior in previous.items():
        if raw_path in records:
            continue
        if prior.get("retain"):
            continue  # User data from a former source root is never retired.
        path = Path(raw_path)
        if not allowed_path(path):
            raise Conflict(f"Receipt contains an unexpected path: {path}")
        snapshot = observed(path)
        before, before_mode = snapshot
        if prior["owned"] and not prior.get("retain") and before is not None:
            if digest(before) != prior["sha256"] or before_mode != prior["mode"]:
                raise Conflict(f"Obsolete file has user changes: {path}")
            changes.append(Change.from_snapshot(path, snapshot, None, component=prior["component"]))
    return changes, records


def migrate_disabled_markers(previous: dict, directory: Path, renames: dict[str, str],
                             component: str) -> list[Change]:
    """Carry an explicit disabled state across a maintained hook rename."""
    markers = previous.setdefault("disabled_markers", {})
    if not isinstance(markers, dict):
        raise Conflict("Hook disable-marker ownership must be an object.")
    changes = []
    for old_name, new_name in renames.items():
        if old_name not in markers:
            continue
        old_owned = markers.pop(old_name)
        if not isinstance(old_owned, bool):
            raise Conflict("Hook disable-marker ownership must be boolean.")
        old_path = directory / (".disabled-" + old_name)
        old_snapshot = observed(old_path)
        if old_owned and old_snapshot[0] is not None and old_snapshot != (b"", 0o600):
            raise Conflict(f"Owned hook disable marker was edited: {old_path}")
        if old_snapshot[0] is None:
            continue

        new_path = directory / (".disabled-" + new_name)
        new_snapshot = observed(new_path)
        if new_snapshot[0] is not None and new_snapshot != (b"", 0o600):
            raise Conflict(f"Hook disable marker has unexpected content: {new_path}")
        if new_snapshot[0] is None:
            changes.append(Change.from_snapshot(
                new_path, new_snapshot, b"", component=component
            ))
            markers[new_name] = True
        else:
            markers.setdefault(new_name, False)
        if old_owned:
            changes.append(Change.from_snapshot(
                old_path, old_snapshot, None, component=component
            ))
    return changes


def retire_recorded_legacy_file(previous: dict, path: Path, component: str) -> list[Change]:
    """Retire a renamed dependency only when the prior receipt proves its bytes."""
    record = previous.get("files", {}).get(str(path))
    if (not record or record.get("component") != component or record.get("retain")
            or record.get("owned") is not False):
        return []
    snapshot = observed(path)
    if snapshot[0] is None:
        return []
    if digest(snapshot[0]) != record.get("sha256") or snapshot[1] != record.get("mode"):
        raise Conflict(f"Recorded legacy file was edited; preserve and reconcile it: {path}")
    return [Change.from_snapshot(path, snapshot, None, component=component)]
