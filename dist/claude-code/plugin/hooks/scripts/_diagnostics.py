"""Secure activation and SQLite filesystem handling for diagnostics events."""

import json
import os
import sqlite3
import stat


PRIVATE_DIRECTORY_MODE = 0o700
PRIVATE_FILE_MODE = 0o600
_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
_DIRECTORY = getattr(os, "O_DIRECTORY", 0)


def _is_owned_regular(info):
    return stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid()


def _is_owned_directory(info):
    return stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid()


def events_enabled(config_path):
    if not _NOFOLLOW:
        return False
    try:
        fd = os.open(config_path, os.O_RDONLY | _NOFOLLOW)
        with os.fdopen(fd, encoding="utf-8") as config_file:
            if not _is_owned_regular(os.fstat(config_file.fileno())):
                return False
            config = json.load(config_file)
        return (
            type(config) is dict
            and type(config.get("schema_version")) is int
            and config["schema_version"] == 1
            and type(config.get("events")) is bool
            and type(config.get("feedback")) is bool
            and config["events"]
        )
    except Exception:
        return False


def _open_owned_directory(path):
    fd = os.open(path, os.O_RDONLY | _DIRECTORY | _NOFOLLOW)
    if not _is_owned_directory(os.fstat(fd)):
        os.close(fd)
        raise PermissionError(path)
    return fd


def _open_or_create_leaf_parent(database_path):
    parent = os.path.dirname(database_path)
    if not parent or parent == database_path:
        raise ValueError(database_path)
    try:
        parent_fd = _open_owned_directory(parent)
    except FileNotFoundError:
        ancestor, leaf = os.path.split(parent)
        if not ancestor or not leaf:
            raise ValueError(parent)
        ancestor_fd = _open_owned_directory(ancestor)
        try:
            os.mkdir(leaf, PRIVATE_DIRECTORY_MODE, dir_fd=ancestor_fd)
            parent_fd = os.open(
                leaf, os.O_RDONLY | _DIRECTORY | _NOFOLLOW, dir_fd=ancestor_fd
            )
        finally:
            os.close(ancestor_fd)
        if not _is_owned_directory(os.fstat(parent_fd)):
            os.close(parent_fd)
            raise PermissionError(parent)
    os.fchmod(parent_fd, PRIVATE_DIRECTORY_MODE)
    return parent_fd


def _open_owned_file(parent_fd, name, create):
    flags = os.O_RDWR | _NOFOLLOW
    if create:
        flags |= os.O_CREAT | os.O_EXCL
    fd = os.open(name, flags, PRIVATE_FILE_MODE, dir_fd=parent_fd)
    if not _is_owned_regular(os.fstat(fd)):
        os.close(fd)
        raise PermissionError(name)
    os.fchmod(fd, PRIVATE_FILE_MODE)
    return fd


def _secure_existing_artifact(parent_fd, name):
    try:
        fd = _open_owned_file(parent_fd, name, False)
    except FileNotFoundError:
        return
    os.close(fd)


def _secure_database_file(parent_fd, name):
    try:
        fd = _open_owned_file(parent_fd, name, False)
    except FileNotFoundError:
        fd = _open_owned_file(parent_fd, name, True)
    identity = os.fstat(fd).st_dev, os.fstat(fd).st_ino
    os.close(fd)
    return identity


def _verify_database_identity(database_path, identity):
    info = os.stat(database_path, follow_symlinks=False)
    if not _is_owned_regular(info) or (info.st_dev, info.st_ino) != identity:
        raise PermissionError(database_path)


def connect_event_database(config_path, database_path, timeout):
    if not events_enabled(config_path) or not os.path.isabs(database_path):
        return None
    parent_fd = _open_or_create_leaf_parent(database_path)
    try:
        name = os.path.basename(database_path)
        if not name:
            raise ValueError(database_path)
        for suffix in ("-wal", "-shm"):
            _secure_existing_artifact(parent_fd, name + suffix)
        identity = _secure_database_file(parent_fd, name)
        connection = sqlite3.connect(database_path, timeout=timeout)
        try:
            _verify_database_identity(database_path, identity)
        except Exception:
            connection.close()
            raise
        return connection
    finally:
        os.close(parent_fd)


def write_event(config_path, database_path, row):
    old_umask = os.umask(0o077)
    try:
        connection = connect_event_database(config_path, database_path, 0.05)
        if connection is None:
            return
        try:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA busy_timeout=50")
            connection.execute(
                "CREATE TABLE IF NOT EXISTS events ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, session_id TEXT, "
                "agent_type TEXT, project TEXT, event TEXT, payload TEXT, "
                "source TEXT DEFAULT 'claude-code')")
            try:
                connection.execute(
                    "ALTER TABLE events ADD COLUMN source TEXT "
                    "DEFAULT 'claude-code'")
            except sqlite3.OperationalError:
                pass
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_events_event_ts "
                "ON events(event, ts)")
            connection.execute(
                "INSERT INTO events(ts, session_id, agent_type, project, event, "
                "payload, source) VALUES (?,?,?,?,?,?,?)", row)
            connection.commit()
        finally:
            connection.close()
    finally:
        os.umask(old_umask)
