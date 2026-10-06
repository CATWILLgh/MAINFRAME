"""Skill payload privacy at all maintained adapter artifact boundaries."""

from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from installer.antigravity import Antigravity
from installer.cline import Cline
from installer.codex import Codex
from installer.core import Conflict
from installer.minimax import MiniMax
from installer.shared import inventory
from installer.zcode import ZCode


ROOT = Path(__file__).resolve().parents[1]
ADAPTERS = (Codex, ZCode, Antigravity, MiniMax, Cline)


class PayloadBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="mainframe-payload-boundary-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve() / "source"
        self.root.mkdir()
        for name in ("skills", "instructions", "agents", "commands", "hooks"):
            shutil.copytree(ROOT / name, self.root / name,
                            ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copy2(ROOT / "ADAPTATION.example.json", self.root)
        shutil.copy2(ROOT / ".gitignore", self.root)
        credentials = self.root / "shared/credentials"
        credentials.mkdir(parents=True)
        for name in ("mainframe-secret", "credentials-index.template.md"):
            shutil.copy2(ROOT / "shared/credentials" / name, credentials / name)
        self.skill = self.root / "skills/mainframe-research"
        self.home = Path(self.temp.name).resolve() / "home"
        self.home.mkdir()

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.root), *args], check=True,
                              capture_output=True)

    def artifacts(self, adapter_type):
        adapter = adapter_type(self.root, self.home)
        source = inventory(self.root)
        if adapter_type is Codex:
            return adapter.artifacts(source, {})
        return adapter.artifacts(source)

    def add_resource(self, name, data=b"private synthetic marker"):
        path = self.skill / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def test_archive_excludes_local_ignored_material_in_every_adapter(self):
        resources = (".env", "references/.env.production", "references/cache.pyc",
                     "scripts/__pycache__/cached.pyc", "assets/node_modules/private.txt")
        for name in resources:
            self.add_resource(name)
        self.add_resource("assets/fixture.bin", b"\0\xffportable binary")
        for adapter in ADAPTERS:
            with self.subTest(adapter=adapter.__name__):
                artifacts = self.artifacts(adapter)
                delivered = {path.as_posix(): row
                             for path, row in artifacts.items() if row[2] == "skills.mainframe-research"}
                paths = list(delivered)
                for name in resources:
                    self.assertFalse(any(path.endswith("mainframe-research/" + name)
                                         for path in paths), name)
                self.assertTrue(any(row[0] == b"\0\xffportable binary" for row in delivered.values()))
        self.assertFalse((self.root / ".git").exists())
        self.assertEqual(list(self.home.iterdir()), [])

    def test_checkout_rejects_untracked_nonignored_resource_before_delivery(self):
        self.git("init", "-q", "--template=")
        self.git("add", ".")
        self.add_resource("references/local-session.md")
        for adapter in ADAPTERS:
            with self.subTest(adapter=adapter.__name__):
                with self.assertRaisesRegex(Conflict, "[Uu]ntracked.*resource"):
                    self.artifacts(adapter)
        self.assertEqual(list(self.home.iterdir()), [])

    def test_checkout_keeps_tracked_binary_and_excludes_ignored_files(self):
        self.add_resource("assets/fixture.bin", b"\0\xffportable binary")
        self.git("init", "-q", "--template=")
        self.git("add", ".")
        self.add_resource(".env")
        for adapter in ADAPTERS:
            with self.subTest(adapter=adapter.__name__):
                files = self.artifacts(adapter)
                self.assertFalse(any(path.name == ".env" for path in files))
                self.assertTrue(any(row[0] == b"\0\xffportable binary" for row in files.values()))

    def test_symlink_resource_rejected_in_every_adapter(self):
        outside = Path(self.temp.name) / "outside.txt"
        outside.write_text("private synthetic marker")
        (self.skill / "references/escape.md").symlink_to(outside)
        for adapter in ADAPTERS:
            with self.subTest(adapter=adapter.__name__):
                with self.assertRaisesRegex(Conflict, "symlink"):
                    self.artifacts(adapter)

    def test_forcibly_tracked_ignored_resource_is_rejected(self):
        self.git("init", "-q", "--template=")
        self.git("add", ".")
        self.add_resource(".env")
        self.git("add", "-f", "skills/mainframe-research/.env")
        for adapter in ADAPTERS:
            with self.subTest(adapter=adapter.__name__):
                with self.assertRaisesRegex(Conflict, "Ignored local material"):
                    self.artifacts(adapter)

    def test_archive_obeys_nested_ignore_and_preserves_explicit_example(self):
        self.add_resource("references/.gitignore", b"local-state/\n")
        self.add_resource("references/local-state/session.md")
        self.add_resource("assets/.env.example", b"SERVICE_URL=https://example.test\n")
        for adapter in ADAPTERS:
            with self.subTest(adapter=adapter.__name__):
                files = self.artifacts(adapter)
                self.assertFalse(any(path.name in ("session.md", ".gitignore") for path in files))
                self.assertTrue(any(path.name == ".env.example" for path in files))

    def test_tracked_missing_resource_cannot_silently_disappear(self):
        resource = self.add_resource("references/required.md", b"portable guidance")
        self.git("init", "-q", "--template=")
        self.git("add", ".")
        resource.unlink()
        for adapter in ADAPTERS:
            with self.subTest(adapter=adapter.__name__):
                with self.assertRaisesRegex(Conflict, "missing.*regular file"):
                    self.artifacts(adapter)


if __name__ == "__main__":
    unittest.main()
