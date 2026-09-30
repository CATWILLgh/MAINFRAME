import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


SOURCE = Path(__file__).resolve().parents[1]


class CredentialInstallerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="mainframe-install-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.repository = self.root / "source"
        self.component = self.repository / "shared" / "credentials"
        self.component.mkdir(parents=True)
        for name in ("install.sh", "mainframe-secret", "credentials-index.template.md"):
            shutil.copy2(SOURCE / name, self.component / name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.scratch = self.root / "scratch"
        self.scratch.mkdir()
        self.environment = {
            "HOME": str(self.home),
            "XDG_CONFIG_HOME": str(self.home / ".config"),
            "PATH": "/usr/bin:/bin",
            "TMPDIR": str(self.scratch),
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
        }

    def install(self, *arguments):
        return subprocess.run(
            ["bash", str(self.component / "install.sh"), *arguments],
            env=self.environment, stdin=subprocess.DEVNULL, capture_output=True,
            text=True, timeout=10,
        )

    def test_missing_ignore_rule_fails_before_any_installation_write(self):
        for git_checkout in (False, True):
            with self.subTest(git_checkout=git_checkout):
                if git_checkout:
                    subprocess.run(
                        ["git", "init", "-q", str(self.repository)],
                        env=self.environment, check=True, timeout=10,
                    )
                result = self.install()
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("not ignored", result.stderr)
                self.assertEqual(list(self.home.iterdir()), [])
                self.assertFalse((self.component / "credentials-index.md").exists())
                self.assertEqual(list(self.scratch.iterdir()), [])

    def test_downloaded_source_installs_idempotently_without_git_residue(self):
        (self.repository / ".gitignore").write_text(
            "/shared/credentials/credentials-index.md\n", encoding="utf-8",
        )
        result = self.install("--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(list(self.home.iterdir()), [])
        self.assertFalse((self.component / "credentials-index.md").exists())
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stderr)
        helper = self.home / ".local" / "bin" / "mainframe-secret"
        self.assertEqual(helper.read_bytes(), (SOURCE / "mainframe-secret").read_bytes())
        index = self.component / "credentials-index.md"
        index.write_text("preserved non-secret metadata\n", encoding="utf-8")
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(index.read_text(), "preserved non-secret metadata\n")
        self.assertFalse((self.repository / ".git").exists())
        self.assertEqual(list(self.scratch.iterdir()), [])

    def test_archive_preflight_ignores_user_git_template_exclusions(self):
        template = self.root / "git-template"
        (template / "info").mkdir(parents=True)
        (template / "info" / "exclude").write_text(
            "credentials-index.md\n", encoding="utf-8",
        )
        user_config = self.root / "gitconfig"
        user_config.write_text(
            f'[init]\n\ttemplateDir = "{template}"\n', encoding="utf-8",
        )
        self.environment["GIT_CONFIG_GLOBAL"] = str(user_config)
        result = self.install()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not ignored", result.stderr)
        self.assertEqual(list(self.home.iterdir()), [])
        self.assertFalse((self.component / "credentials-index.md").exists())
        self.assertEqual(list(self.scratch.iterdir()), [])

    def test_recognized_legacy_helper_is_replaced_without_a_duplicate(self):
        (self.repository / ".gitignore").write_text(
            "/shared/credentials/credentials-index.md\n", encoding="utf-8",
        )
        legacy = self.home / ".local/bin/secret"
        legacy.parent.mkdir(parents=True)
        shutil.copy2(SOURCE / "mainframe-secret", legacy)

        result = self.install()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(legacy.exists())
        current = self.home / ".local/bin/mainframe-secret"
        self.assertEqual(current.read_bytes(), (SOURCE / "mainframe-secret").read_bytes())


if __name__ == "__main__":
    unittest.main()
