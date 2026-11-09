import json
import os
from pathlib import Path
import subprocess
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
        all_tools = (*runtime.CODE_QUALITY_TOOLS, *runtime.FALLOW_TOOLS, "openspec")
        self.assertEqual(
            runtime.tools_for_hook(all_tools, "mainframe-code-quality"),
            runtime.CODE_QUALITY_TOOLS,
        )
        self.assertEqual(
            runtime.tools_for_hook(all_tools, "mainframe-fallow-quality"),
            runtime.FALLOW_TOOLS,
        )
        self.assertEqual(runtime.tools_for_hook(all_tools, "mainframe-secret-access"), ())

    def openspec_fixture(self, node_version="22.12.0"):
        node = self.external / "node"
        node.write_text(f"""#!/bin/sh
if [ "$1" = --version ]; then
    printf 'v%s\\n' '{node_version}'
    exit 0
fi
exec /bin/sh "$@"
""")
        node.chmod(0o755)
        entry = self.root / "openspec.js"
        entry.write_text("""#!/usr/bin/env node
[ "$OPENSPEC_TELEMETRY" = 0 ] && [ "$OPENSPEC_NO_UPDATE_CHECK" = 1 ] || exit 3
[ "$1" = --version ] && printf '1.16.1\\n'
""")
        entry.chmod(0o755)
        npm = self.external / "npm"
        npm.write_text("""#!/bin/sh
[ "$(node --version)" = v22.12.0 ] || exit 4
[ "$1" = install ] && [ "$2" = --prefix ] && [ "$3" = "$PWD" ] || exit 5
prefix=$3
shift 3
case " $* " in *' --ignore-scripts '*) ;; *) exit 6 ;; esac
case " $* " in *' --global=false '*) ;; *) exit 7 ;; esac
case " $* " in *' @fission-ai/openspec@1.16.1 '*) ;; *) exit 8 ;; esac
bin="$prefix/node_modules/@fission-ai/openspec/bin"
/bin/mkdir -p "$bin"
/bin/cp "$OPENSPEC_FIXTURE_ENTRY" "$bin/openspec.js"
printf 'attempt\\n' >> "$OPENSPEC_FIXTURE_ATTEMPTS"
[ "$OPENSPEC_FIXTURE_FAIL" != 1 ]
""")
        npm.chmod(0o755)
        return {
            "PATH": str(self.external),
            "OPENSPEC_FIXTURE_ENTRY": str(entry),
            "OPENSPEC_FIXTURE_ATTEMPTS": str(self.root / "npm-attempts"),
            "OPENSPEC_TELEMETRY": "1",
            "OPENSPEC_NO_UPDATE_CHECK": "0",
        }

    def test_openspec_install_and_retry_keep_existing_analyzer_state(self):
        root = runtime.runtime_root(self.home)
        manifest = root / "installation.json"
        shims = runtime.runtime_bin(self.home)
        fallow = root / "packages/node/node_modules/fallow/bin/fallow"
        fallow.parent.mkdir(parents=True)
        fallow.write_text("existing managed package\n")
        self.tool("oxlint", "1.67.0")
        env = self.openspec_fixture()
        with mock.patch.dict(os.environ, env):
            runtime.ensure(self.home, ("oxlint",))
        previous = json.loads(manifest.read_text())
        previous["tools"]["fallow"] = {"version": "2.92.1", "executable": str(fallow)}
        manifest.write_text(json.dumps(previous))
        previous_manifest = manifest.read_bytes()
        oxlint_before = (shims / "oxlint").stat().st_ino
        with mock.patch.dict(os.environ, {**env, "OPENSPEC_FIXTURE_FAIL": "1"}):
            self.assertEqual(runtime.status(self.home, ("openspec",))["missing"], ["openspec"])
            with self.assertRaisesRegex(Conflict, "installation failed"):
                runtime.ensure(self.home, ("openspec",))
        self.assertEqual(manifest.read_bytes(), previous_manifest)
        self.assertFalse((shims / "openspec").exists())
        self.assertEqual(list((root / "packages").glob("openspec-*")), [])
        with mock.patch.dict(os.environ, env):
            installed = runtime.ensure(self.home, ("openspec",))
        self.assertEqual(installed["versions"], {"openspec": "1.16.1"})
        self.assertEqual(installed["bin"], str(shims))
        new_rows = json.loads(manifest.read_text())["tools"]
        for name, row in previous["tools"].items():
            self.assertEqual(new_rows[name], row)
        self.assertEqual(fallow.read_text(), "existing managed package\n")
        self.assertFalse((shims / "fallow").exists())
        self.assertEqual((shims / "oxlint").stat().st_ino, oxlint_before)

        minimal_env = {"PATH": str(shims), "OPENSPEC_TELEMETRY": "1", "OPENSPEC_NO_UPDATE_CHECK": "0"}
        project = self.root / "project"
        project.mkdir()
        launch = subprocess.run([str(shims / "openspec"), "--version"], cwd=project,
                                env=minimal_env, capture_output=True, text=True, check=True)
        self.assertEqual(launch.stdout.strip(), "1.16.1")
        self.assertEqual(list(project.iterdir()), [])
        (shims / "openspec").unlink()
        with mock.patch.dict(os.environ, minimal_env):
            self.assertTrue(runtime.ensure(self.home, ("openspec",))["ready"])
        self.assertEqual(Path(env["OPENSPEC_FIXTURE_ATTEMPTS"]).read_text(), "attempt\nattempt\n")

    def test_openspec_failed_repair_keeps_previous_binding(self):
        env = self.openspec_fixture()
        root = runtime.runtime_root(self.home)
        manifest = root / "installation.json"
        shim = runtime.runtime_bin(self.home) / "openspec"
        with mock.patch.dict(os.environ, env):
            runtime.ensure(self.home, ("openspec",))
        before = manifest.read_bytes()
        shim_before = shim.read_bytes()
        entrypoint = Path(json.loads(before)["tools"]["openspec"]["executable"])
        entrypoint.unlink()
        with mock.patch.dict(os.environ, {**env, "OPENSPEC_FIXTURE_FAIL": "1"}):
            with self.assertRaisesRegex(Conflict, "installation failed"):
                runtime.ensure(self.home, ("openspec",))
        self.assertEqual(manifest.read_bytes(), before)
        self.assertEqual(shim.read_bytes(), shim_before)
        self.assertEqual(len(list((root / "packages").glob("openspec-*"))), 1)
        with mock.patch.dict(os.environ, env):
            self.assertTrue(runtime.ensure(self.home, ("openspec",))["ready"])
        self.assertNotEqual(shim.read_bytes(), shim_before)

    def test_openspec_reuses_compatible_npm_link_after_managed_bin(self):
        env = self.openspec_fixture()
        (self.external / "npm").unlink()
        npm_bin = self.root / "lib/node_modules/@fission-ai/openspec/bin"
        npm_bin.mkdir(parents=True)
        entry = Path(env["OPENSPEC_FIXTURE_ENTRY"]).rename(npm_bin / "openspec.js")
        (self.external / "openspec").symlink_to(entry)
        shims = runtime.runtime_bin(self.home)
        with mock.patch.dict(os.environ, {**env, "PATH": os.pathsep.join(map(str, (shims, self.external)))}):
            self.assertTrue(runtime.ensure(self.home, ("openspec",))["ready"])
        self.assertIn(str(entry), (shims / "openspec").read_text())
        with mock.patch.dict(os.environ, {"PATH": str(shims)}):
            self.assertTrue(runtime.status(self.home, ("openspec",))["ready"])

    def test_openspec_requires_compatible_node_before_npm(self):
        for version in ("22.11.0", "22.12.0-rc.1"):
            with self.subTest(version=version):
                env = self.openspec_fixture(node_version=version)
                with mock.patch.dict(os.environ, env):
                    with self.assertRaisesRegex(Conflict, "Node.js 22.12.0 or newer"):
                        runtime.ensure(self.home, ("openspec",))
                self.assertFalse(Path(env["OPENSPEC_FIXTURE_ATTEMPTS"]).exists())

    def test_openspec_does_not_reuse_a_prerelease(self):
        env = self.openspec_fixture()
        self.tool("openspec", "1.16.1-rc.1")
        with mock.patch.dict(os.environ, env):
            self.assertTrue(runtime.ensure(self.home, ("openspec",))["ready"])
        self.assertTrue(Path(env["OPENSPEC_FIXTURE_ATTEMPTS"]).is_file())

    def test_openspec_reuses_standalone_and_survives_analyzer_repair(self):
        standalone = self.tool("openspec", "1.16.1")
        self.tool("oxlint", "1.67.0")
        shims = runtime.runtime_bin(self.home)
        manifest = runtime.runtime_root(self.home) / "installation.json"
        with mock.patch.dict(os.environ, {"PATH": str(self.external)}):
            self.assertTrue(runtime.ensure(self.home, ("openspec",))["ready"])
            prior = json.loads(manifest.read_text())["tools"]["openspec"]
            self.assertTrue(runtime.ensure(self.home, ("oxlint",))["ready"])
        self.assertEqual(prior["executable"], str(standalone))
        self.assertEqual(json.loads(manifest.read_text())["tools"]["openspec"], prior)
        with mock.patch.dict(os.environ, {"PATH": str(shims)}):
            self.assertTrue(runtime.status(self.home, ("openspec",))["ready"])

    def test_openspec_preserves_foreign_shim(self):
        env = self.openspec_fixture()
        shim = runtime.runtime_bin(self.home) / "openspec"
        shim.parent.mkdir(parents=True)
        shim.write_text("foreign contents\n")
        shim.chmod(0o755)
        with mock.patch.dict(os.environ, env):
            with self.assertRaisesRegex(Conflict, "Existing file has no installer ownership"):
                runtime.ensure(self.home, ("openspec",))
        self.assertEqual(shim.read_text(), "foreign contents\n")
        self.assertFalse(Path(env["OPENSPEC_FIXTURE_ATTEMPTS"]).exists())


if __name__ == "__main__":
    unittest.main()
