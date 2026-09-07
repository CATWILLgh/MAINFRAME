from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


SOURCE = Path(__file__).resolve().parents[1] / "commit-secrets.py"
SPEC = importlib.util.spec_from_file_location("commit_secrets", SOURCE)
assert SPEC is not None and SPEC.loader is not None
DETECTOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = DETECTOR
SPEC.loader.exec_module(DETECTOR)

ALNUM = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"


def _token() -> str:
    return "ghp_" + (ALNUM * 2)[:36]


class CommitSecretsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="mainframe-commit-secrets-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.git("init", "-q")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "user.name", "Test")
        (self.root / "base.txt").write_text("base\n", encoding="utf-8")
        self.git("add", "base.txt")
        self.git("commit", "-qm", "base")

    def git(self, *args: str) -> subprocess.CompletedProcess[bytes]:
        return subprocess.run(
            ["git", *args],
            cwd=self.root,
            check=True,
            capture_output=True,
            timeout=10,
        )

    def check(self, command: str, cwd: Path | None = None):
        return DETECTOR.check_command(command, str(cwd or self.root))

    def test_clean_and_non_commit_commands_are_silent(self) -> None:
        (self.root / "clean.txt").write_text("clean\n", encoding="utf-8")
        self.git("add", "clean.txt")
        for command in (
            "git status --short",
            "echo git commit -m example",
            "git commit --dry-run",
            "git commit -m clean",
        ):
            with self.subTest(command=command):
                self.assertEqual(self.check(command), DETECTOR.CheckResult())

    def test_staged_secret_blocks_without_exposing_value(self) -> None:
        token = _token()
        (self.root / ".env").write_text(f"TOKEN={token}\n", encoding="utf-8")
        self.git("add", ".env")
        result = self.check("git commit -m secret")
        self.assertIsNotNone(result.block_reason)
        self.assertIsNone(result.advisory)
        self.assertIn("github_pat in .env:1", result.block_reason or "")
        self.assertNotIn(token, result.block_reason or "")

    def test_initial_commit_is_checked(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="mainframe-initial-commit-"))
        self.addCleanup(shutil.rmtree, root)
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        (root / ".env").write_text(f"TOKEN={_token()}\n", encoding="utf-8")
        subprocess.run(["git", "add", ".env"], cwd=root, check=True)
        result = DETECTOR.check_command("git commit -m initial", str(root))
        self.assertIsNotNone(result.block_reason)

    def test_unusual_repository_relative_path_is_reported_safely(self) -> None:
        target = self.root / "space name.env"
        target.write_text(f"TOKEN={_token()}\n", encoding="utf-8")
        self.git("add", target.name)
        result = self.check("git commit -m path")
        self.assertIn("github_pat in space name.env:1", result.block_reason or "")

    def test_secret_shaped_filename_is_redacted_from_output(self) -> None:
        token = _token()
        target = self.root / f"{token}.env"
        target.write_text(f"TOKEN={_token()}z\n", encoding="utf-8")
        self.git("add", target.name)
        result = self.check("git commit -m path")
        self.assertIsNotNone(result.block_reason)
        self.assertNotIn(token, result.block_reason or "")
        self.assertIn("<redacted>.env", result.block_reason or "")

    def test_partial_staging_uses_the_index_not_dirty_worktree(self) -> None:
        target = self.root / "partial.txt"
        target.write_text("clean\n", encoding="utf-8")
        self.git("add", "partial.txt")
        target.write_text(f"TOKEN={_token()}\n", encoding="utf-8")
        self.assertEqual(self.check("git commit -m partial"), DETECTOR.CheckResult())

    def test_commit_all_and_named_path_use_worktree_content(self) -> None:
        for command in ("git commit -am update", "git commit base.txt -m update"):
            with self.subTest(command=command):
                (self.root / "base.txt").write_text(f"TOKEN={_token()}\n", encoding="utf-8")
                result = self.check(command)
                self.assertIsNotNone(result.block_reason)
                (self.root / "base.txt").write_text("base\n", encoding="utf-8")

    def test_commit_all_matches_git_for_staged_new_file_changed_after_add(self) -> None:
        token = _token()
        target = self.root / "new.env"
        target.write_text(f"TOKEN={token}\n", encoding="utf-8")
        self.git("add", "new.env")
        target.write_text("clean\n", encoding="utf-8")
        result = self.check("git commit -am update")
        self.git("commit", "-qam", "update")
        committed = self.git("show", "HEAD:new.env").stdout
        self.assertEqual(token.encode() in committed, result.block_reason is not None)

    def test_include_checks_index_and_named_worktree_paths(self) -> None:
        (self.root / "staged.txt").write_text(f"TOKEN={_token()}\n", encoding="utf-8")
        self.git("add", "staged.txt")
        (self.root / "base.txt").write_text("changed\n", encoding="utf-8")
        result = self.check("git commit --include base.txt -m update")
        self.assertIsNotNone(result.block_reason)

    def test_only_ignores_unrelated_staged_secret(self) -> None:
        (self.root / "staged.txt").write_text(f"TOKEN={_token()}\n", encoding="utf-8")
        self.git("add", "staged.txt")
        (self.root / "base.txt").write_text("changed\n", encoding="utf-8")
        result = self.check("git commit --only base.txt -m update")
        self.assertEqual(result, DETECTOR.CheckResult())

    def test_literal_metadata_is_checked(self) -> None:
        token = _token()
        result = self.check(f"git commit -m token-{token}")
        self.assertIn("github_pat in message", result.block_reason or "")
        self.assertNotIn(token, result.block_reason or "")

        message = self.root / "message.txt"
        message.write_text(f"release {token}\n", encoding="utf-8")
        result = self.check("git commit -F message.txt")
        self.assertIn("github_pat in commit-message-file", result.block_reason or "")

    def test_existing_secret_and_unchanged_rename_do_not_create_a_new_finding(self) -> None:
        token = _token()
        source = self.root / "tracked.env"
        source.write_text(f"TOKEN={token}\n", encoding="utf-8")
        self.git("add", "tracked.env")
        self.git("commit", "-qm", "fixture")
        self.git("mv", "tracked.env", "renamed.env")
        self.assertEqual(self.check("git commit -m rename"), DETECTOR.CheckResult())

    def test_binary_staged_content_is_checked(self) -> None:
        token = _token()
        (self.root / "blob.bin").write_bytes(b"\x00\x01" + token.encode() + b"\xff")
        self.git("add", "blob.bin")
        result = self.check("git commit -m binary")
        self.assertIn("github_pat in blob.bin:1", result.block_reason or "")

    def test_encrypted_repository_marker_does_not_disable_other_paths(self) -> None:
        (self.root / ".sops.yaml").write_text("creation_rules: []\n", encoding="utf-8")
        (self.root / "plain.env").write_text(f"TOKEN={_token()}\n", encoding="utf-8")
        self.git("add", ".sops.yaml", "plain.env")
        self.assertIsNotNone(self.check("git commit -m secret").block_reason)

    def test_filtered_staged_blob_passes_naturally(self) -> None:
        token = _token()
        self.git(
            "config",
            "filter.redact.clean",
            "sed 's/ghp_[0-9A-Za-z]*/CIPHERTEXT/g'",
        )
        self.git("config", "filter.redact.smudge", "cat")
        (self.root / ".gitattributes").write_text(
            "encrypted.env filter=redact\n",
            encoding="utf-8",
        )
        (self.root / "encrypted.env").write_text(f"TOKEN={token}\n", encoding="utf-8")
        self.git("add", ".gitattributes", "encrypted.env")
        staged = self.git("show", ":encrypted.env").stdout
        self.assertNotIn(token.encode(), staged)
        self.assertEqual(self.check("git commit -m encrypted"), DETECTOR.CheckResult())

    def test_git_c_cd_nested_shell_and_heredoc_are_parsed(self) -> None:
        token = _token()
        (self.root / ".env").write_text(f"TOKEN={token}\n", encoding="utf-8")
        self.git("add", ".env")
        parent = self.root.parent
        commands = (
            f"git -C {self.root.name} commit -m secret",
            f"cd {self.root.name} && git commit -m secret",
            f"sh -c 'cd {self.root.name} && git commit -m secret'",
            (
                "cat <<'TEXT'\ngit commit -m not-executed\nTEXT\n"
                f"git -C {self.root.name} commit -m secret"
            ),
        )
        for command in commands:
            with self.subTest(command=command):
                self.assertIsNotNone(self.check(command, parent).block_reason)

    def test_unavailable_inspection_warns_without_blocking(self) -> None:
        for command in (
            "git commit --pathspec-from-file=paths.txt -m update",
            "git commit -F -",
            "cd $TARGET && git commit -m update",
            "git commit -m '$DYNAMIC_MESSAGE'",
            "xargs git commit -m update",
            "git commit -m 'unterminated",
        ):
            with self.subTest(command=command):
                result = self.check(command)
                self.assertIsNone(result.block_reason)
                self.assertIn("was not blocked", result.advisory or "")

    def test_runtime_failure_warns_without_blocking(self) -> None:
        with mock.patch.object(DETECTOR, "_git", side_effect=DETECTOR.InspectionUnavailable("git_timeout")):
            result = self.check("git commit -m update")
        self.assertIsNone(result.block_reason)
        self.assertIn("git_timeout", result.advisory or "")

        with mock.patch.object(DETECTOR, "parse_commit_invocations", side_effect=RuntimeError("boom")):
            result = self.check("git commit -m update")
        self.assertIsNone(result.block_reason)
        self.assertIn("detector_failure", result.advisory or "")

    def test_filtered_worktree_is_not_misreported_as_committed_plaintext(self) -> None:
        self.git("config", "filter.test-clean.clean", "cat")
        (self.root / ".gitattributes").write_text("filtered.txt filter=test-clean\n", encoding="utf-8")
        (self.root / "filtered.txt").write_text("clean\n", encoding="utf-8")
        self.git("add", ".gitattributes", "filtered.txt")
        self.git("commit", "-qm", "filtered")
        (self.root / "filtered.txt").write_text(f"TOKEN={_token()}\n", encoding="utf-8")
        result = self.check("git commit -am update")
        self.assertIsNone(result.block_reason)
        self.assertIn("filtered_worktree_content", result.advisory or "")

    def test_parallel_calls_are_read_only_and_independent(self) -> None:
        (self.root / ".env").write_text(f"TOKEN={_token()}\n", encoding="utf-8")
        self.git("add", ".env")
        before = self.git("status", "--porcelain=v1", "-z").stdout
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: self.check("git commit -m secret"), range(64)))
        after = self.git("status", "--porcelain=v1", "-z").stdout
        self.assertTrue(all(result.block_reason for result in results))
        self.assertTrue(all(result.advisory is None for result in results))
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
