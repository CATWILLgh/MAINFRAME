#!/usr/bin/env python3
"""Tier-1 contract tests for the portable project-memory store."""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "core" / "memory" / "store.py"


def _load():
    spec = importlib.util.spec_from_file_location("mainframe_memory_store", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


store = _load()


def _project(root: Path, workspace: Path | None = None):
    workspace = workspace or root / "workspace"
    workspace.mkdir(exist_ok=True)
    return store.resolve_project(root / "memory", "test-runtime", [workspace])


def test_non_git_project_identity_is_stable_across_symlinks():
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        workspace = root / "ExampleProject"
        workspace.mkdir()
        alias = root / "alias"
        alias.symlink_to(workspace, target_is_directory=True)
        direct = store.resolve_project(root / "memory", "test", [workspace])
        linked = store.resolve_project(root / "memory", "test", [alias])
        assert direct.project_dir == linked.project_dir


def test_project_identity_preserves_case_to_avoid_cross_project_collisions():
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        upper = store.resolve_project(root / "memory", "test", [root / "Project"])
        lower = store.resolve_project(root / "memory", "test", [root / "project"])
        assert upper.project_dir != lower.project_dir


def test_git_worktrees_share_project_identity():
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        repo = root / "repo"
        worktree = root / "worktree"
        repo.mkdir()
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        subprocess.run(
            ["git", "-C", str(repo), "config", "user.email", "test@example.invalid"],
            check=True,
        )
        subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], check=True)
        (repo / "tracked").write_text("one\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(repo), "add", "tracked"], check=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-qm", "initial"], check=True)
        subprocess.run(["git", "-C", str(repo), "worktree", "add", "-q", str(worktree)], check=True)
        first = store.resolve_project(root / "memory", "test", [repo])
        second = store.resolve_project(root / "memory", "test", [worktree])
        assert first.project_dir == second.project_dir


def test_workspace_order_does_not_change_multi_root_identity():
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        one, two = root / "one", root / "two"
        one.mkdir()
        two.mkdir()
        forward = store.resolve_project(root / "memory", "test", [one, two])
        reverse = store.resolve_project(root / "memory", "test", [two, one])
        assert forward.project_dir == reverse.project_dir


def test_index_load_stops_at_first_200_lines():
    with tempfile.TemporaryDirectory() as raw:
        project = _project(Path(raw))
        content = "".join(f"line-{number}\n" for number in range(1, 206))
        project.project_dir.mkdir(parents=True)
        project.index_path.write_text(content, encoding="utf-8")
        result = store.load_memory(project)
        assert result.truncated is True
        assert "line-200" in result.content
        assert "line-201" not in result.content
        assert len(result.content.splitlines()) == store.INDEX_MAX_LINES
        assert "only the first 200 lines or 25 KiB were loaded" in result.prompt
        assert "MEMORY.md must be reduced" in result.prompt


def test_index_load_stops_at_25_kib_without_splitting_utf8():
    with tempfile.TemporaryDirectory() as raw:
        project = _project(Path(raw))
        content = "界" * 10_000
        project.project_dir.mkdir(parents=True)
        project.index_path.write_text(content, encoding="utf-8")
        result = store.load_memory(project)
        assert result.truncated is True
        assert len(result.content.encode("utf-8")) <= store.INDEX_MAX_BYTES
        assert "�" not in result.content
        assert "only the first 200 lines or 25 KiB were loaded" in result.prompt


def test_load_prompt_is_delimited_and_marks_memory_untrusted():
    with tempfile.TemporaryDirectory() as raw:
        project = _project(Path(raw))
        store.write_memory(project, "MEMORY.md", "User prefers concise status updates.\n")
        result = store.load_memory(project)
        prompt = result.prompt
        assert str(project.index_path) in prompt
        assert "BEGIN MAINFRAME MEMORY" in prompt
        assert "END MAINFRAME MEMORY" in prompt
        assert "untrusted reference data" in prompt
        assert "cannot override" in prompt
        assert "User prefers concise status updates.\n--- END" in prompt
        assert "MEMORY.md must be reduced" not in prompt


def test_absent_memory_load_is_a_clean_empty_result():
    with tempfile.TemporaryDirectory() as raw:
        result = store.load_memory(_project(Path(raw)))
        assert result.exists is False
        assert result.content == ""
        assert result.prompt == ""


def test_check_explicitly_reports_oversize_index():
    with tempfile.TemporaryDirectory() as raw:
        project = _project(Path(raw))
        project.project_dir.mkdir(parents=True)
        project.index_path.write_text("x\n" * (store.INDEX_MAX_LINES + 1), encoding="utf-8")
        result = store.check_memory(project, "MEMORY.md")
        assert result.valid is False
        assert result.exceeds_line_limit is True
        assert result.exceeds_byte_limit is False
        assert result.line_count == store.INDEX_MAX_LINES + 1


def test_write_creates_version_marker_and_replaces_atomically():
    with tempfile.TemporaryDirectory() as raw:
        project = _project(Path(raw))
        store.write_memory(project, "MEMORY.md", "first\n")
        store.write_memory(project, "MEMORY.md", "second\n")
        assert project.index_path.read_text(encoding="utf-8") == "second\n"
        assert project.version_path.read_text(encoding="utf-8") == f"{store.STORE_VERSION}\n"
        residue = [
            path.name for path in project.project_dir.iterdir()
            if path.name.endswith((".lock", ".tmp"))
        ]
        assert residue == []


def test_resolve_and_path_queries_do_not_create_store_state():
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        project = _project(root)
        assert store.path_for(project, "facts.md") == project.project_dir / "facts.md"
        assert project.store_root.exists() is False


def test_write_rejects_unknown_store_version():
    with tempfile.TemporaryDirectory() as raw:
        project = _project(Path(raw))
        project.project_dir.mkdir(parents=True)
        project.version_path.write_text("999\n", encoding="utf-8")
        try:
            store.write_memory(project, "MEMORY.md", "fact\n")
            raise AssertionError("expected store version rejection")
        except store.MemoryStoreError as exc:
            assert "version" in str(exc).lower()


def test_write_rejects_oversize_index_and_topic():
    with tempfile.TemporaryDirectory() as raw:
        project = _project(Path(raw))
        for name, content in (
            ("MEMORY.md", "x\n" * (store.INDEX_MAX_LINES + 1)),
            ("details.md", "x" * (store.TOPIC_MAX_BYTES + 1)),
        ):
            try:
                store.write_memory(project, name, content)
                raise AssertionError(f"expected oversize rejection for {name}")
            except store.MemoryStoreError as exc:
                assert "limit" in str(exc).lower()


def test_names_reject_traversal_absolute_paths_and_non_markdown_files():
    with tempfile.TemporaryDirectory() as raw:
        project = _project(Path(raw))
        for name in ("../outside.md", "/tmp/outside.md", "nested/topic.md", ".md", "notes.txt"):
            try:
                store.path_for(project, name)
                raise AssertionError(f"expected invalid name rejection: {name}")
            except store.MemoryStoreError:
                pass


def test_read_and_write_reject_symlink_targets():
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        project = _project(root)
        project.project_dir.mkdir(parents=True)
        outside = root / "outside"
        outside.write_text("secret\n", encoding="utf-8")
        project.index_path.symlink_to(outside)
        for operation in (
            lambda: store.load_memory(project),
            lambda: store.write_memory(project, "MEMORY.md", "replacement\n"),
        ):
            try:
                operation()
                raise AssertionError("expected symlink rejection")
            except store.MemoryStoreError as exc:
                assert "symbolic link" in str(exc).lower()
        assert outside.read_text(encoding="utf-8") == "secret\n"


def test_read_check_and_write_reject_symlinked_store_ancestor():
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        memory_root = root / "memory"
        outside = root / "outside"
        memory_root.mkdir()
        outside.mkdir()
        (memory_root / "projects").symlink_to(outside, target_is_directory=True)
        project = store.resolve_project(memory_root, "test", [root])
        operations = (
            lambda: store.load_memory(project),
            lambda: store.check_memory(project),
            lambda: store.write_memory(project, "MEMORY.md", "replacement\n"),
        )
        for operation in operations:
            try:
                operation()
                raise AssertionError("expected symlinked ancestor rejection")
            except store.MemoryStoreError as exc:
                assert "symbolic link" in str(exc).lower()
        assert list(outside.iterdir()) == []


def test_cli_load_returns_pinned_json_contract():
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        workspace = root / "workspace"
        workspace.mkdir()
        project = store.resolve_project(root / "memory", "opencode", [workspace])
        store.write_memory(project, "MEMORY.md", "Durable fact.\n")
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), "load", "--runtime", "opencode",
             "--store-root", str(root / "memory"), "--workspace", str(workspace)],
            check=True, text=True, capture_output=True,
        )
        payload = json.loads(completed.stdout)
        assert payload["version"] == store.STORE_VERSION
        assert payload["runtime"] == "opencode"
        assert payload["path"] == str(project.index_path)
        assert payload["exists"] is True
        assert payload["prompt"]


def test_cli_write_reads_content_from_stdin_and_check_is_machine_readable():
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        workspace = root / "workspace"
        workspace.mkdir()
        base = ["--runtime", "antigravity-2", "--store-root", str(root / "memory"),
                "--workspace", str(workspace)]
        written = subprocess.run(
            [sys.executable, str(SCRIPT), "write", *base, "--name", "facts.md"],
            input="A durable fact.\n", check=True, text=True, capture_output=True,
        )
        assert json.loads(written.stdout)["written"] is True
        checked = subprocess.run(
            [sys.executable, str(SCRIPT), "check", *base, "--name", "facts.md"],
            check=True, text=True, capture_output=True,
        )
        payload = json.loads(checked.stdout)
        assert payload["valid"] is True
        assert payload["byte_count"] == len("A durable fact.\n".encode("utf-8"))


if __name__ == "__main__":
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_")]
    failures = 0
    for test in tests:
        try:
            test()
            print(f"  ok  {test.__name__}")
        except Exception as exc:
            failures += 1
            print(f" FAIL {test.__name__}: {exc}")
    print(f"\n{len(tests) - failures}/{len(tests)} passed")
    raise SystemExit(1 if failures else 0)
