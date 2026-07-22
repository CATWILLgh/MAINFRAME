#!/usr/bin/env python3
"""Tier-1 contracts for explicit, secure event-diagnostics activation."""

from __future__ import annotations

import importlib
import json
import os
from pathlib import Path
import sqlite3
import stat
import sys
import tempfile
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
DETECTORS = REPO / "core/gates/detectors"
sys.path.insert(0, str(DETECTORS))
hooklib = importlib.import_module("_hooklib")
diagnostics = importlib.import_module("_diagnostics")


def _sandbox() -> Path:
    return Path(tempfile.mkdtemp(prefix="mainframe-diagnostics-"))


def _configure(root: Path, data: object | None = None) -> Path:
    config = root / "diagnostics.json"
    config.write_text(json.dumps(
        data if data is not None else {
            "schema_version": 1, "events": True, "feedback": False}
    ), encoding="utf-8")
    os.environ["MAINFRAME_DIAGNOSTICS_CONFIG"] = str(config)
    return config


def _db_path(root: Path, leaf: str = "telemetry") -> Path:
    db = root / leaf / "telemetry.db"
    os.environ["MAINFRAME_TELEMETRY_DB"] = str(db)
    return db


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def _event_count(db: Path) -> int:
    with sqlite3.connect(db) as connection:
        return connection.execute("SELECT count(*) FROM events").fetchone()[0]


def test_missing_config_blocks_existing_telemetry_directory() -> None:
    root = _sandbox()
    db = _db_path(root)
    db.parent.mkdir()
    os.environ["MAINFRAME_DIAGNOSTICS_CONFIG"] = str(root / "missing.json")
    hooklib.log_event("must_not_write")
    assert not db.exists()


def test_database_override_is_only_a_locator() -> None:
    root = _sandbox()
    db = _db_path(root)
    os.environ["MAINFRAME_DIAGNOSTICS_CONFIG"] = str(root / "missing.json")
    hooklib.log_event("must_not_write")
    assert not db.parent.exists()


def test_events_false_blocks_writes() -> None:
    root = _sandbox()
    db = _db_path(root)
    _configure(root, {"schema_version": 1, "events": False})
    hooklib.log_event("must_not_write")
    assert not db.parent.exists()


def test_invalid_documents_fail_closed() -> None:
    invalid = (
        [], {}, {"schema_version": True, "events": True},
        {"schema_version": 1, "events": 1},
        {"schema_version": 1, "events": True},
        {"schema_version": 1, "events": True, "feedback": 0},
        {"schema_version": 2, "events": True},
    )
    for document in invalid:
        root = _sandbox()
        db = _db_path(root)
        _configure(root, document)
        hooklib.log_event("must_not_write")
        assert not db.parent.exists(), document


def test_valid_config_creates_only_leaf_parent_with_private_modes() -> None:
    root = _sandbox()
    db = _db_path(root)
    _configure(root)
    hooklib.log_event("created")
    assert _event_count(db) == 1
    assert _mode(db.parent) == 0o700
    assert _mode(db) == 0o600


def test_missing_ancestor_is_not_created_recursively() -> None:
    root = _sandbox()
    db = _db_path(root, "missing/telemetry")
    _configure(root)
    hooklib.log_event("must_not_write")
    assert not (root / "missing").exists()


def test_existing_permissions_tighten_without_data_loss() -> None:
    root = _sandbox()
    db = _db_path(root)
    db.parent.mkdir(mode=0o777)
    os.chmod(db.parent, 0o777)
    with sqlite3.connect(db) as connection:
        connection.execute("CREATE TABLE preserved (value TEXT)")
        connection.execute("INSERT INTO preserved VALUES ('keep-me')")
    os.chmod(db, 0o666)
    _configure(root)
    hooklib.log_event("appended")
    with sqlite3.connect(db) as connection:
        preserved = connection.execute("SELECT value FROM preserved").fetchone()[0]
    assert preserved == "keep-me"
    assert _event_count(db) == 1
    assert _mode(db.parent) == 0o700
    assert _mode(db) == 0o600


def test_symlink_config_fails_closed() -> None:
    root = _sandbox()
    real = _configure(root)
    link = root / "diagnostics-link.json"
    link.symlink_to(real)
    os.environ["MAINFRAME_DIAGNOSTICS_CONFIG"] = str(link)
    db = _db_path(root)
    hooklib.log_event("must_not_write")
    assert not db.parent.exists()


def test_foreign_owned_config_fails_closed() -> None:
    root = _sandbox()
    config = _configure(root)
    with mock.patch.object(
            diagnostics.os, "getuid", return_value=os.getuid() + 1):
        assert not diagnostics.events_enabled(config)


def test_symlink_database_and_parent_fail_closed() -> None:
    for link_parent in (False, True):
        root = _sandbox()
        _configure(root)
        target = root / "target"
        target.mkdir()
        if link_parent:
            (root / "telemetry").symlink_to(target, target_is_directory=True)
            db = _db_path(root)
            forbidden = target / "telemetry.db"
        else:
            db = _db_path(root)
            db.parent.mkdir()
            forbidden = root / "target.db"
            db.symlink_to(forbidden)
        hooklib.log_event("must_not_write")
        assert not forbidden.exists()


def test_symlink_sidecar_blocks_write() -> None:
    root = _sandbox()
    db = _db_path(root)
    db.parent.mkdir()
    with sqlite3.connect(db) as connection:
        connection.execute("CREATE TABLE preserved (value TEXT)")
    forbidden = root / "outside-wal"
    Path(f"{db}-wal").symlink_to(forbidden)
    _configure(root)
    hooklib.log_event("must_not_write")
    with sqlite3.connect(db) as connection:
        tables = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='events'"
        ).fetchall()
    assert tables == []
    assert not forbidden.exists()


def test_existing_sidecars_tighten_to_private_mode() -> None:
    root = _sandbox()
    db = _db_path(root)
    db.parent.mkdir()
    _configure(root)
    connection = sqlite3.connect(db)
    try:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("CREATE TABLE preserved (value TEXT)")
        connection.commit()
        sidecars = (Path(f"{db}-wal"), Path(f"{db}-shm"))
        assert all(path.exists() for path in sidecars)
        for path in sidecars:
            os.chmod(path, 0o666)
        hooklib.log_event("appended")
        assert all(_mode(path) == 0o600 for path in sidecars)
    finally:
        connection.close()


def test_unreadable_config_fails_closed_when_enforced_by_os() -> None:
    root = _sandbox()
    config = _configure(root)
    db = _db_path(root)
    os.chmod(config, 0)
    if os.access(config, os.R_OK):
        return
    hooklib.log_event("must_not_write")
    assert not db.parent.exists()


if __name__ == "__main__":
    tests = sorted(name for name in globals() if name.startswith("test_"))
    for name in tests:
        globals()[name]()
        print(f"PASS {name}")
    print(f"{len(tests)} tests passed")
