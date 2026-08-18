#!/usr/bin/env python3

import json
import hashlib
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
MANAGER = ROOT / "shared" / "managed-delivery" / "manage-artifact.py"


def _run(action, source, target, state, backup_root, *extra):
    return subprocess.run(
        [
            "python3",
            str(MANAGER),
            action,
            "--source",
            str(source),
            "--target",
            str(target),
            "--state",
            str(state),
            "--backup-root",
            str(backup_root),
            *extra,
        ],
        text=True,
        capture_output=True,
    )


def test_file_install_update_and_uninstall(tmp_path):
    source = tmp_path / "source.txt"
    target = tmp_path / "installed" / "target.txt"
    state = tmp_path / "state.json"
    backups = tmp_path / "backups"
    source.write_text("one\n", encoding="utf-8")

    installed = _run("install", source, target, state, backups)
    assert installed.returncode == 0, installed.stderr
    assert target.read_text(encoding="utf-8") == "one\n"
    assert not target.is_symlink()

    source.write_text("two\n", encoding="utf-8")
    updated = _run("install", source, target, state, backups)
    assert updated.returncode == 0, updated.stderr
    assert target.read_text(encoding="utf-8") == "two\n"

    removed = _run("uninstall", source, target, state, backups)
    assert removed.returncode == 0, removed.stderr
    assert not target.exists()
    assert not state.exists()


def test_directory_digest_blocks_local_changes_and_preserves_them(tmp_path):
    source = tmp_path / "source"
    target = tmp_path / "installed"
    state = tmp_path / "state.json"
    backups = tmp_path / "backups"
    source.mkdir()
    (source / "a.txt").write_text("managed\n", encoding="utf-8")
    assert _run("install", source, target, state, backups).returncode == 0

    (target / "a.txt").write_text("local\n", encoding="utf-8")
    refused = _run("install", source, target, state, backups)
    assert refused.returncode == 1
    assert "local" in refused.stderr.lower()
    assert (target / "a.txt").read_text(encoding="utf-8") == "local\n"

    replaced = _run("install", source, target, state, backups, "--replace-modified")
    assert replaced.returncode == 0, replaced.stderr
    assert (target / "a.txt").read_text(encoding="utf-8") == "managed\n"
    assert any(path.read_text(encoding="utf-8") == "local\n" for path in backups.rglob("a.txt"))


def test_preexisting_target_is_restored_after_uninstall(tmp_path):
    source = tmp_path / "source.txt"
    target = tmp_path / "target.txt"
    state = tmp_path / "state.json"
    backups = tmp_path / "backups"
    source.write_text("mainframe\n", encoding="utf-8")
    target.write_text("personal\n", encoding="utf-8")

    refused = _run("install", source, target, state, backups)
    assert refused.returncode == 1
    assert target.read_text(encoding="utf-8") == "personal\n"

    installed = _run("install", source, target, state, backups, "--replace-modified")
    assert installed.returncode == 0, installed.stderr
    saved_state = json.loads(state.read_text(encoding="utf-8"))
    assert saved_state["original_backup"]
    assert target.read_text(encoding="utf-8") == "mainframe\n"

    removed = _run("uninstall", source, target, state, backups)
    assert removed.returncode == 0, removed.stderr
    assert target.read_text(encoding="utf-8") == "personal\n"


def test_owned_legacy_symlink_migrates_without_confirmation(tmp_path):
    source = tmp_path / "source"
    target = tmp_path / "target"
    state = tmp_path / "state.json"
    backups = tmp_path / "backups"
    source.mkdir()
    (source / "file.txt").write_text("content\n", encoding="utf-8")
    target.symlink_to(source)

    installed = _run("install", source, target, state, backups)
    assert installed.returncode == 0, installed.stderr
    assert target.is_dir() and not target.is_symlink()
    assert (target / "file.txt").read_text(encoding="utf-8") == "content\n"
    assert not backups.exists()


def test_changed_managed_target_blocks_uninstall(tmp_path):
    source = tmp_path / "source.txt"
    target = tmp_path / "target.txt"
    state = tmp_path / "state.json"
    backups = tmp_path / "backups"
    source.write_text("managed\n", encoding="utf-8")
    assert _run("install", source, target, state, backups).returncode == 0
    target.write_text("changed\n", encoding="utf-8")

    refused = _run("uninstall", source, target, state, backups)
    assert refused.returncode == 1
    assert target.read_text(encoding="utf-8") == "changed\n"
    assert state.exists()

    removed = _run("uninstall", source, target, state, backups, "--replace-modified")
    assert removed.returncode == 0, removed.stderr
    assert not target.exists()
    assert any(path.read_text(encoding="utf-8") == "changed\n" for path in backups.rglob("target.txt"))


def test_runtime_python_cache_is_not_delivered_or_counted_as_drift(tmp_path):
    source = tmp_path / "source"
    target = tmp_path / "target"
    state = tmp_path / "state.json"
    backups = tmp_path / "backups"
    source.mkdir()
    (source / "hook.py").write_text("pass\n", encoding="utf-8")
    cache = source / "__pycache__"
    cache.mkdir()
    (cache / "hook.pyc").write_bytes(b"source cache")

    assert _run("install", source, target, state, backups).returncode == 0
    assert not (target / "__pycache__").exists()

    installed_cache = target / "__pycache__"
    installed_cache.mkdir()
    (installed_cache / "hook.pyc").write_bytes(b"runtime cache")
    checked = _run("check-uninstall", source, target, state, backups)
    assert checked.returncode == 0, checked.stderr


def test_legacy_managed_copy_migrates_without_treating_it_as_user_content(tmp_path):
    old_source = tmp_path / "old.txt"
    source = tmp_path / "source.txt"
    target = tmp_path / "target.txt"
    state = tmp_path / "state.json"
    backups = tmp_path / "backups"
    old_source.write_text("old managed\n", encoding="utf-8")
    source.write_text("new managed\n", encoding="utf-8")
    target.write_bytes(old_source.read_bytes())
    digest_proc = subprocess.run(
        [
            "python3",
            "-c",
            (
                "import importlib.util,sys;"
                "s=importlib.util.spec_from_file_location('m',sys.argv[1]);"
                "m=importlib.util.module_from_spec(s);s.loader.exec_module(m);"
                "print(m.artifact_digest(m.Path(sys.argv[2])))"
            ),
            str(MANAGER),
            str(target),
        ],
        text=True,
        capture_output=True,
        check=True,
    )
    installed = _run(
        "install",
        source,
        target,
        state,
        backups,
        "--legacy-managed-digest",
        digest_proc.stdout.strip(),
    )
    assert installed.returncode == 0, installed.stderr
    assert target.read_text(encoding="utf-8") == "new managed\n"
    assert not backups.exists()


def test_legacy_plain_sha256_migrates_without_confirmation(tmp_path):
    source = tmp_path / "source.txt"
    target = tmp_path / "target.txt"
    state = tmp_path / "state.json"
    backups = tmp_path / "backups"
    source.write_text("new managed\n", encoding="utf-8")
    target.write_text("old managed\n", encoding="utf-8")
    legacy_digest = hashlib.sha256(target.read_bytes()).hexdigest()

    installed = _run(
        "install",
        source,
        target,
        state,
        backups,
        "--legacy-managed-digest",
        legacy_digest,
    )
    assert installed.returncode == 0, installed.stderr
    assert target.read_text(encoding="utf-8") == "new managed\n"
    assert not backups.exists()


if __name__ == "__main__":
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_")]
    import tempfile

    for test in tests:
        with tempfile.TemporaryDirectory() as directory:
            test(Path(directory))
    print(f"ok: {len(tests)} managed delivery tests")
