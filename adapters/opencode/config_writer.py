"""Secure atomic publication for the local OpenCode configuration."""

from dataclasses import dataclass
import errno
import json
import os
import stat
import tempfile


class ConfigWriteError(RuntimeError):
    """Raised when a configuration cannot be published safely."""


@dataclass(frozen=True)
class ConfigWriteResult:
    """Observable permission-mode outcome of a configuration write."""

    previous_mode: int | None
    mode: int
    tightened: bool
    cleanup_warning: str | None = None


@dataclass(frozen=True)
class _ExistingFile:
    mode: int
    identity: tuple[int, int]
    raw: bytes


def _serialize(data):
    return (json.dumps(data, indent=2, allow_nan=False) + "\n").encode()


def _ensure_parent(path):
    parent = os.path.abspath(os.path.dirname(path) or ".")
    missing = []
    cursor = parent
    while not os.path.exists(cursor):
        missing.append(cursor)
        next_cursor = os.path.dirname(cursor)
        if next_cursor == cursor:
            break
        cursor = next_cursor
    for directory in reversed(missing):
        try:
            os.mkdir(directory, 0o700)
        except FileExistsError:
            continue
        os.chmod(directory, 0o700)
    return parent


def _lstat_regular(path, label, required=False):
    try:
        metadata = os.lstat(path)
    except FileNotFoundError:
        if required:
            raise ConfigWriteError(f"{label} disappeared during publication")
        return None
    if not stat.S_ISREG(metadata.st_mode):
        raise ConfigWriteError(f"{label} is not a regular file: {path}")
    return metadata


def _read_existing(path, metadata):
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise ConfigWriteError(f"cannot safely open existing config: {exc}") from exc
    try:
        opened = os.fstat(descriptor)
        if ((opened.st_dev, opened.st_ino) !=
                (metadata.st_dev, metadata.st_ino) or
                not stat.S_ISREG(opened.st_mode)):
            raise ConfigWriteError("config changed while it was being opened")
        chunks = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
    except OSError as exc:
        raise ConfigWriteError(f"cannot read existing config: {exc}") from exc
    finally:
        os.close(descriptor)
    return b"".join(chunks)


def _inspect_existing(path):
    metadata = _lstat_regular(path, "config")
    if metadata is None:
        return None
    mode = stat.S_IMODE(metadata.st_mode)
    if not mode & stat.S_IRUSR:
        raise ConfigWriteError("existing config is not readable by its owner")
    raw = _read_existing(path, metadata)
    return _ExistingFile(mode, (metadata.st_dev, metadata.st_ino), raw)


def _validate_backup(path):
    _lstat_regular(path + ".backup", "config backup")


def _stage(directory, basename, raw, mode):
    descriptor, path = tempfile.mkstemp(prefix=f".{basename}.", dir=directory)
    try:
        os.fchmod(descriptor, mode)
        with os.fdopen(descriptor, "wb") as handle:
            descriptor = -1
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        return path
    except Exception:
        if descriptor >= 0:
            os.close(descriptor)
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass
        raise


def _same_live(path, existing):
    if existing is None:
        try:
            os.lstat(path)
        except FileNotFoundError:
            return
        raise ConfigWriteError("config appeared during publication")
    metadata = _lstat_regular(path, "config", required=True)
    if (metadata.st_dev, metadata.st_ino) != existing.identity:
        raise ConfigWriteError("config changed during publication")


def _publish_fresh(staged, path):
    try:
        os.link(staged, path, follow_symlinks=False)
    except FileExistsError as exc:
        raise ConfigWriteError("config appeared during publication") from exc
    except OSError as exc:
        if exc.errno == errno.EEXIST:
            raise ConfigWriteError("config appeared during publication") from exc
        raise
    try:
        os.unlink(staged)
    except OSError as exc:
        return f"staged config remains at {staged}: {exc}"
    return None


def _fsync_directory(directory):
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    descriptor = os.open(directory, flags)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _remove(path):
    if path is None:
        return
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass


def _publish(path, directory, live_stage, backup_stage, existing):
    cleanup_warning = None
    try:
        _same_live(path, existing)
        if backup_stage is not None:
            os.replace(backup_stage, path + ".backup")
            backup_stage = None
        if existing is None:
            cleanup_warning = _publish_fresh(live_stage, path)
        else:
            _same_live(path, existing)
            os.replace(live_stage, path)
        live_stage = None
    finally:
        _remove(live_stage)
        _remove(backup_stage)
    try:
        _fsync_directory(directory)
    except OSError as exc:
        raise ConfigWriteError(
            f"config published but durability unconfirmed: {exc}") from exc
    return cleanup_warning


def write_config(path, data):
    """Publish JSON without following targets or exposing weak file modes."""
    raw = _serialize(data)
    path = os.path.abspath(os.fspath(path))
    try:
        directory = _ensure_parent(path)
        existing = _inspect_existing(path)
        _validate_backup(path)
        mode = 0o600 if existing is None else existing.mode & 0o600
        basename = os.path.basename(path)
        live_stage = _stage(directory, basename, raw, mode)
        try:
            backup_stage = None
            if existing is not None:
                backup_stage = _stage(
                    directory, basename + ".backup", existing.raw, mode)
            cleanup_warning = _publish(
                path, directory, live_stage, backup_stage, existing)
        except Exception:
            _remove(live_stage)
            raise
    except ConfigWriteError:
        raise
    except OSError as exc:
        raise ConfigWriteError(f"cannot publish config: {exc}") from exc
    previous = None if existing is None else existing.mode
    tightened = previous is not None and mode != previous
    return ConfigWriteResult(previous, mode, tightened, cleanup_warning)
