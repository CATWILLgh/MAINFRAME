import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from installer.core import Conflict
from installer import runtime


class RuntimeSupportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="mainframe-runtime-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.home = self.root / "home"
        self.external = self.root / "external"
        self.external.mkdir(parents=True)

    def tool(self, name, version):
        path = self.external / name
        path.write_text(f"#!/bin/sh\nprintf '%s\\n' '{name} {version}'\n")
        path.chmod(0o755)
        return path

    def test_reuses_compatible_tools_and_exposes_stable_shims(self):
        for name, (_, _, version) in runtime.TOOL_SPECS.items():
            self.tool(name, version)
        with mock.patch.dict(
            os.environ, {"PATH": str(self.external) + os.pathsep + os.environ.get("PATH", "")}
        ):
            result = runtime.ensure(self.home, tuple(runtime.TOOL_SPECS))
            self.assertTrue(result["ready"])
            self.assertEqual(result["missing"], [])
            self.assertTrue(runtime.status(self.home, tuple(runtime.TOOL_SPECS))["ready"])
        record = json.loads((runtime.runtime_root(self.home) / "installation.json").read_text())
        self.assertEqual(set(record["tools"]), set(runtime.TOOL_SPECS))
        for name in runtime.TOOL_SPECS:
            shim = runtime.runtime_bin(self.home) / name
            self.assertTrue(shim.is_file())
            self.assertTrue(os.access(shim, os.X_OK))

    def test_missing_node_installer_stops_before_activation_manifest(self):
        with mock.patch.object(runtime.shutil, "which", return_value=None):
            with self.assertRaisesRegex(Conflict, "npm is required"):
                runtime.ensure(self.home, ("fallow",))
        self.assertFalse((runtime.runtime_root(self.home) / "installation.json").exists())

    def test_repair_never_points_a_runtime_shim_at_itself(self):
        for name, (_, _, version) in runtime.TOOL_SPECS.items():
            self.tool(name, version)
        external_path = str(self.external) + os.pathsep + os.environ.get("PATH", "")
        with mock.patch.dict(os.environ, {"PATH": external_path}):
            runtime.ensure(self.home, tuple(runtime.TOOL_SPECS))
        broken = runtime.runtime_bin(self.home) / "semgrep"
        broken.unlink()
        with mock.patch.dict(
            os.environ,
            {"PATH": str(runtime.runtime_bin(self.home)) + os.pathsep + external_path},
        ):
            result = runtime.ensure(self.home, tuple(runtime.TOOL_SPECS))
        self.assertTrue(result["ready"])
        for name in runtime.TOOL_SPECS:
            body = (runtime.runtime_bin(self.home) / name).read_text()
            self.assertNotIn("exec " + str(runtime.runtime_bin(self.home) / name), body)

    def test_rebuilding_one_managed_ecosystem_keeps_its_other_tools(self):
        root = runtime.runtime_root(self.home)
        managed = root / "packages/python/bin"
        managed.mkdir(parents=True)
        ruff = managed / "ruff"
        ruff.write_text("#!/bin/sh\nprintf 'ruff 0.15.15\\n'\n")
        ruff.chmod(0o755)
        (root / "installation.json").write_text(json.dumps({
            "schema": 1,
            "tools": {"ruff": {"version": "0.15.15", "executable": str(ruff)}},
        }))
        installed = []

        def fake_python(_root, names):
            installed.extend(names)
            return {
                name: self.tool(name, runtime.TOOL_SPECS[name][2])
                for name in names
            }

        with mock.patch.object(runtime, "_managed_python", side_effect=fake_python), \
                mock.patch.object(runtime.shutil, "which", return_value=None):
            result = runtime.ensure(self.home, ("ruff", "semgrep"))
        self.assertTrue(result["ready"])
        self.assertEqual(installed, ["ruff", "semgrep"])

    def test_hook_dependency_selection_is_exact(self):
        all_tools = (*runtime.CODE_QUALITY_TOOLS, *runtime.FALLOW_TOOLS)
        self.assertEqual(
            runtime.tools_for_hook(all_tools, "mainframe-code-quality"),
            runtime.CODE_QUALITY_TOOLS,
        )
        self.assertEqual(
            runtime.tools_for_hook(all_tools, "mainframe-fallow-quality"),
            runtime.FALLOW_TOOLS,
        )
        self.assertEqual(runtime.tools_for_hook(all_tools, "mainframe-secret-access"), ())


if __name__ == "__main__":
    unittest.main()
