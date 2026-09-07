from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import importlib.util
from pathlib import Path
import tempfile
import unittest


SOURCE = Path(__file__).resolve().parents[1] / "destructive-operations.py"
SPEC = importlib.util.spec_from_file_location("destructive_operations", SOURCE)
assert SPEC is not None and SPEC.loader is not None
DETECTOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DETECTOR)


class DestructiveOperationsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="mainframe-path-hook-")
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name).resolve()
        self.home = root / "home"
        self.project = self.home / "project"
        self.child = self.project / "child"
        self.outside = root / "outside"
        for directory in (self.child, self.outside):
            directory.mkdir(parents=True)

    def decide(self, command: str, cwd: Path | None = None) -> str | None:
        return DETECTOR.decision_reason(
            command,
            str(cwd or self.project),
            str(self.project),
            str(self.home),
        )

    def test_blocks_only_the_three_literal_catastrophic_roots(self) -> None:
        cases = {
            "rm -rf /": "filesystem root",
            "rm -rf .": "active project root",
            f"rm -rf {self.project}": "active project root",
            "rm --recursive $HOME": "home root",
            "rm -R ~/": "home root",
        }
        for command, expected in cases.items():
            with self.subTest(command=command):
                self.assertIn(expected, self.decide(command) or "")

        self.assertIn(
            "active project root",
            self.decide("rm -rf ..", cwd=self.child) or "",
        )

    def test_leaves_narrow_and_external_cleanup_to_native_permissions(self) -> None:
        for command in (
            "rm one-file.txt",
            "rm -rf child",
            "rm -rf ../outside-project",
            f"rm -rf {self.outside}",
            "rm -rf generated/*",
            "rm -rf child && echo done",
            "rm -rf child || echo absent",
            "rm -rf child; echo done",
            "find child -exec rm -rf {} +",
        ):
            with self.subTest(command=command):
                self.assertIsNone(self.decide(command))

    def test_does_not_match_destructive_text_as_a_command(self) -> None:
        for command in (
            "printf 'rm -rf /'",
            "echo rm -rf /",
            "rg 'rm -rf' .",
        ):
            with self.subTest(command=command):
                self.assertIsNone(self.decide(command))

    def test_handles_supported_wrappers_and_nested_shells(self) -> None:
        for command in (
            "command rm -rf .",
            "/usr/bin/env MODE=test /bin/rm -R .",
            "sudo -u root rm -rf /",
            "timeout 5 rm --recursive .",
            "sh -c 'rm -rf /'",
            "bash -lc 'rm -rf $HOME'",
        ):
            with self.subTest(command=command):
                self.assertIsNotNone(self.decide(command))

    def test_blocks_relative_recursive_rm_after_directory_change(self) -> None:
        for command in (
            "cd .. && rm -rf project",
            "cd child && rm -rf .",
            "pushd child; rm -rf .",
            "cd child && sh -c 'rm -rf .'",
        ):
            with self.subTest(command=command):
                reason = self.decide(command)
                self.assertIsNotNone(reason)
                self.assertIn("working-directory change", reason or "")

    def test_directory_change_does_not_obscure_an_absolute_root(self) -> None:
        self.assertIn("filesystem root", self.decide("cd child && rm -rf /") or "")
        self.assertIsNone(self.decide(f"cd child && rm -rf {self.outside}"))

    def test_symlink_operand_matches_rm_traversal_behavior(self) -> None:
        external_link = self.project / "external-link"
        external_link.symlink_to(self.outside, target_is_directory=True)
        self.assertIsNone(self.decide("rm -rf external-link"))
        self.assertIsNone(self.decide("rm -rf external-link/"))

        project_link = self.project / "project-link"
        project_link.symlink_to(self.project, target_is_directory=True)
        self.assertIsNone(self.decide("rm -rf project-link"))
        self.assertIn(
            "active project root",
            self.decide("rm -rf project-link/") or "",
        )

    def test_blocks_git_safeguard_bypasses(self) -> None:
        cases = {
            "git commit --no-verify -m result": "verification bypass",
            "git commit -n -m result": "verification bypass",
            "git commit-tree deadbeef -m result": "commit-tree",
            "git push --force origin main": "Force or mirror push",
            "git push --force-with-lease origin main": "Force or mirror push",
            "git push --mirror origin": "Force or mirror push",
            "git push origin +main:main": "Force or mirror push",
            "git send-pack origin refs/heads/main": "send-pack",
        }
        for command, expected in cases.items():
            with self.subTest(command=command):
                self.assertIn(expected, self.decide(command) or "")

    def test_blocks_git_operations_that_destroy_recovery_paths(self) -> None:
        cases = {
            "git reset --hard HEAD": "hard reset",
            "git clean -fd": "Git clean",
            "git reflog expire --expire=now --all": "reflog recovery",
            "git reflog delete HEAD@{1}": "reflog recovery",
            "git prune": "unreachable Git objects",
            "git gc --prune=now": "recovery objects",
            "git gc --prune=all": "recovery objects",
            "git filter-branch -- --all": "history rewriting",
            "git filter-repo --force": "history rewriting",
            "git branch -D obsolete": "branch deletion",
            "git branch -d -f obsolete": "branch deletion",
            "git worktree remove --force ../old-worktree": "worktree removal",
            "git stash clear": "every Git stash",
            "git update-ref -d refs/heads/main": "ref mutation",
            "git symbolic-ref HEAD refs/heads/other": "symbolic-ref mutation",
            "git replace deadbeef cafebabe": "replacement-ref mutation",
        }
        for command, expected in cases.items():
            with self.subTest(command=command):
                self.assertIn(expected, self.decide(command) or "")

    def test_leaves_ordinary_git_work_to_instructions_and_native_permissions(
        self,
    ) -> None:
        for command in (
            "git status --short",
            "git diff --check",
            "git add src/app.py",
            "git rm src/obsolete.py",
            "git commit -m result",
            "git push origin main",
            "git push git@example.com:org/repo.git main",
            "git push ssh://git@example.com/org/repo.git main",
            "git merge feature",
            "git rebase main",
            "git branch feature",
            "git tag release",
            "git remote remove origin",
            "git config --global user.name Example",
            "git stash drop stash@{0}",
            "git worktree remove ../clean-worktree",
        ):
            with self.subTest(command=command):
                self.assertIsNone(self.decide(command))

    def test_git_dry_runs_and_read_only_forms_remain_available(self) -> None:
        for command in (
            "git push --dry-run --force origin main",
            "git clean -nfd",
            "git clean --force --dry-run",
            "git reflog show HEAD",
            "git reflog expire --dry-run --expire=now --all",
            "git prune -n",
            "git gc",
            "git filter-repo --dry-run",
            "git filter-repo --analyze",
            "git branch -d merged-branch",
            "git symbolic-ref HEAD",
            "git replace -l",
        ):
            with self.subTest(command=command):
                self.assertIsNone(self.decide(command))

    def test_git_detection_handles_wrappers_global_options_and_compounds(self) -> None:
        for command in (
            "command git reset --hard",
            "/usr/bin/env MODE=test /usr/bin/git -C ../repo reset --hard",
            "git --git-dir=.git reset --hard",
            "sudo -u root git push --force origin main",
            "sh -c 'git clean -fd'",
            "env MODE=test bash -lc 'git stash clear'",
            "git status && git reset --hard",
            "echo $(git push --force origin main)",
        ):
            with self.subTest(command=command):
                self.assertIsNotNone(self.decide(command))

    def test_does_not_treat_git_text_as_an_executed_git_command(self) -> None:
        for command in (
            "printf 'git reset --hard'",
            "echo git push --force origin main",
            "rg 'git clean -fd' .",
            "git commit -m 'do not run git push --force'",
        ):
            with self.subTest(command=command):
                self.assertIsNone(self.decide(command))

    def test_missing_binding_context_is_not_a_clean_result(self) -> None:
        with self.assertRaises(ValueError):
            DETECTOR.decision_reason("rm -rf .", "", str(self.project), str(self.home))
        with self.assertRaises(ValueError):
            DETECTOR.decision_reason("rm -rf .", str(self.project), "", str(self.home))

    def test_malformed_shell_text_defers_to_native_permissions(self) -> None:
        self.assertIsNone(self.decide("rm -rf 'unterminated"))
        self.assertIsNone(self.decide("git push --force 'unterminated"))

    def test_is_stateless_and_safe_under_concurrent_calls(self) -> None:
        commands = (
            "rm -rf /",
            "rm -rf child",
            "git reset --hard",
            "git status --short",
        )
        before = sorted(item.name for item in self.project.iterdir())
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(
                pool.map(
                    lambda index: self.decide(commands[index % len(commands)]),
                    range(64),
                )
            )
        self.assertEqual(sum(result is not None for result in results), 32)
        self.assertTrue(all(result is None or len(result) < 300 for result in results))
        self.assertEqual(before, sorted(item.name for item in self.project.iterdir()))


if __name__ == "__main__":
    unittest.main()
