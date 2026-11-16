"""Reusing a tool does not grant ownership of its containing directory."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from installer import core, runtime
import test_runtime as runtime_fixtures


class RuntimeGenerationOwnershipTests(unittest.TestCase):
    def setUp(self):
        self.fixture = runtime_fixtures.RuntimeSupportTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.home = self.fixture.home
        self.root = runtime.runtime_root(self.home)

    @staticmethod
    def prepare_python(root, names):
        parent = root / "packages/python"
        parent.mkdir(parents=True, exist_ok=True)
        generation = Path(tempfile.mkdtemp(prefix="mainframe-python-", dir=parent))
        paths = {}
        for name in names:
            path = generation / "bin" / name
            path.parent.mkdir(exist_ok=True)
            path.write_text(f"#!/bin/sh\nprintf '{name} {runtime.TOOL_SPECS[name][2]}\\n'\n")
            path.chmod(0o755)
            paths[name] = path
        return paths

    def test_reused_python_path_does_not_grant_generation_ownership(self):
        foreign = self.root / "packages/python/mainframe-python-foreign1"
        executable = foreign / "bin/ruff"
        executable.parent.mkdir(parents=True)
        executable.write_text(f"#!/bin/sh\nprintf 'ruff {runtime.TOOL_SPECS['ruff'][2]}\\n'\n")
        executable.chmod(0o755)
        note = foreign / "user-note"
        note.write_text("preserve this user-owned directory")
        with mock.patch.dict(os.environ, {"PATH": str(executable.parent)}):
            self.assertTrue(runtime.ensure(self.home, ("ruff",))["ready"])
            with mock.patch.object(runtime, "_managed_python", side_effect=self.prepare_python):
                self.assertTrue(runtime.ensure(self.home, ("ruff", "yamllint"))["ready"])
        self.assertTrue(executable.is_file())
        self.assertEqual(note.read_text(), "preserve this user-owned directory")

    def test_reused_openspec_path_does_not_grant_generation_ownership(self):
        environment = self.fixture.openspec_fixture()
        foreign = self.root / "packages/openspec-foreign1"
        executable = foreign / "node_modules" / runtime.OPENSPEC_PACKAGE / "bin/openspec.js"
        executable.parent.mkdir(parents=True)
        executable.write_text(f"#!/bin/sh\nprintf '{runtime.OPENSPEC_VERSION}\\n'\n")
        executable.chmod(0o755)
        note = foreign / "user-note"
        note.write_text("preserve this user-owned directory")
        (self.fixture.external / "openspec").symlink_to(executable)
        with mock.patch.dict(os.environ, environment):
            self.assertTrue(runtime.ensure(self.home, ("openspec",))["ready"])
            executable.write_text("#!/bin/sh\nprintf '0.0.1\\n'\n")
            self.assertTrue(runtime.ensure(self.home, ("openspec",))["ready"])
        self.assertTrue(executable.is_file(), "reused foreign generation was deleted")
        self.assertEqual(executable.read_text(), "#!/bin/sh\nprintf '0.0.1\\n'\n")
        self.assertEqual(note.read_text(), "preserve this user-owned directory")

    def test_adding_a_tool_preserves_an_existing_user_edited_analyzer_shim(self):
        environment = {"PATH": str(self.fixture.root / "no-tools")}
        with (
            mock.patch.dict(os.environ, environment),
            mock.patch.object(runtime, "_managed_python", side_effect=self.prepare_python),
        ):
            self.assertTrue(runtime.ensure(self.home, ("ruff",))["ready"])
            shim = runtime.runtime_bin(self.home) / "ruff"
            custom = shim.read_bytes().replace(b"exec ", b"# User-owned customization\nexec ")
            shim.write_bytes(custom)
            manifest = (self.root / "installation.json").read_bytes()
            with self.assertRaises(core.Conflict):
                runtime.ensure(self.home, ("yamllint",))
        self.assertEqual(shim.read_bytes(), custom)
        self.assertEqual((self.root / "installation.json").read_bytes(), manifest)

    def test_next_ensure_retries_a_failed_post_commit_retirement_without_preparing_again(self):
        environment = {"PATH": str(self.fixture.root / "no-tools")}
        with (
            mock.patch.dict(os.environ, environment),
            mock.patch.object(runtime, "_managed_python", side_effect=self.prepare_python),
        ):
            runtime.ensure(self.home, ("ruff",))
            record = json.loads((self.root / "installation.json").read_text())
            old = Path(record["tools"]["ruff"]["managed_generation"])
            original = runtime._discard_generation

            def refuse_old(path, root):
                if path == old:
                    raise OSError("synthetic retirement failure")
                return original(path, root)

            with (
                mock.patch.object(runtime, "_discard_generation", side_effect=refuse_old),
                self.assertRaisesRegex(OSError, "synthetic retirement failure"),
            ):
                runtime.ensure(self.home, ("yamllint",))
            self.assertTrue(old.is_dir())
            self.assertTrue(runtime.status(self.home, ("ruff", "yamllint"))["ready"])
            with mock.patch.object(runtime, "_managed_python", side_effect=AssertionError("unnecessary preparation")):
                self.assertTrue(runtime.ensure(self.home, ("ruff", "yamllint"))["ready"])
        self.assertFalse(old.exists(), "successful retry lost the old generation's retirement receipt")


if __name__ == "__main__":
    unittest.main()
