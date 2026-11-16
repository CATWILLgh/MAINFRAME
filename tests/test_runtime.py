import io
import json
import os
from pathlib import Path
import signal
import shutil
import subprocess
import tarfile
import tempfile
import unittest
from unittest import mock

from installer.core import Conflict, digest
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
        if name == "modern-web-guidance":
            (path.parent / "legacy-scan.mjs").write_text(
                "export async function runAnalyzeCli(args) { return { exitCode: 0, output: JSON.stringify({targetDir: args[0], activeRuleCount: 1, guides: []}) }; }\n"
            )
            compiler = path.parent / "node_modules/svelte/compiler/index.js"
            compiler.parent.mkdir(parents=True, exist_ok=True)
            compiler.write_text("exports.parse = () => ({});\n")
            (compiler.parent.parent / "package.json").write_text(json.dumps({"version": "5.57.3"}))
        return path

    def test_web_wrapper_keeps_public_cli_and_routes_private_rules_without_shell_evaluation(self):
        source = self.tool("modern-web-guidance", runtime.TOOL_SPECS["modern-web-guidance"][2])
        with (
            mock.patch.dict(os.environ, {"PATH": str(self.external) + os.pathsep + os.environ.get("PATH", "")}),
            mock.patch.object(runtime, "_managed_node", side_effect=AssertionError("unexpected install")),
        ):
            runtime.ensure(self.home, ("modern-web-guidance",))
        shim = runtime.runtime_bin(self.home) / "modern-web-guidance"
        version = subprocess.run([str(shim), "--version"], capture_output=True, text=True, timeout=5)
        self.assertEqual(version.stdout.strip(), "modern-web-guidance 1.0.0")
        program = "console.log(JSON.stringify(process.argv.slice(1)))"
        result = subprocess.run([str(shim), "--mainframe-rules", program, "source.css", "--json"], capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), [
            "mainframe-web-check", str(source.parent / "legacy-scan.mjs"),
            str(source.parent / "node_modules/svelte/compiler/index.js"), "source.css", "--json",
        ])

    def test_old_web_wrapper_is_repaired_without_reinstalling_compatible_packages(self):
        source = self.tool("modern-web-guidance", runtime.TOOL_SPECS["modern-web-guidance"][2])
        with (
            mock.patch.dict(os.environ, {"PATH": str(self.external) + os.pathsep + os.environ.get("PATH", "")}),
            mock.patch.object(runtime, "_managed_node", side_effect=AssertionError("unexpected install")),
        ):
            runtime.ensure(self.home, ("modern-web-guidance",))
        shim = runtime.runtime_bin(self.home) / "modern-web-guidance"
        shim.write_text(f'#!/bin/sh\nexec "{source}" "$@"\n')
        self.assertFalse(runtime.status(self.home, ("modern-web-guidance",))["ready"])
        with mock.patch.object(runtime, "_managed_node", side_effect=AssertionError("unnecessary install")):
            self.assertTrue(runtime.ensure(self.home, ("modern-web-guidance",))["ready"])
        self.assertIn("--mainframe-rules", shim.read_text())

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

    def test_reuses_newer_ruff_only_when_it_reports_an_expected_finding(self):
        source = self.tool("ruff", "0.17.5")
        source.write_text("""#!/bin/sh
if [ "$1" = "--version" ]; then
    printf 'ruff 0.17.5\\n'
    exit
fi
case "$(/bin/cat)" in
    *'eval('*)
        printf '%s\\n' '[{"code":"S307","location":{"row":1}}]'
        exit 1 ;;
    *'value = )'*)
        printf '%s\\n' '[{"code":"invalid-syntax","location":{"row":1},"message":"parse error"}]'
        exit 1 ;;
    *) printf '[]\\n' ;;
esac
""")
        with (
            mock.patch.dict(os.environ, {"PATH": str(self.external)}),
            mock.patch.object(runtime, "_managed_python") as install,
        ):
            result = runtime.ensure(self.home, ("ruff",))
            self.assertEqual(result["versions"], {"ruff": "0.17.5"})
            self.assertTrue(runtime.status(self.home, ("ruff",))["ready"])
            install.assert_not_called()

    def test_newer_ruff_with_no_findings_uses_the_tested_distribution(self):
        source = self.tool("ruff", "0.17.5")
        source.write_text("""#!/bin/sh
case "$1" in
    --version) printf 'ruff 0.17.5\\n' ;;
    *) printf '[]\\n' ;;
esac
""")
        floor = runtime.TOOL_SPECS["ruff"][2]
        managed = self.tool("managed-ruff", floor)
        with (
            mock.patch.dict(os.environ, {"PATH": str(self.external)}),
            mock.patch.object(runtime, "_managed_python", return_value={"ruff": managed}) as install,
        ):
            result = runtime.ensure(self.home, ("ruff",))
        self.assertEqual(result["versions"], {"ruff": floor})
        install.assert_called_once()
        self.assertIn(str(managed), (runtime.runtime_bin(self.home) / "ruff").read_text())

    def test_runtime_rejects_versions_below_minimum_and_prereleases(self):
        for version in ("0.15.14", "0.15.15-rc.1", "0.17.5rc1"):
            with self.subTest(version=version):
                self.assertIsNone(runtime._analyzer_version("ruff", self.tool("ruff", version)))

    def test_runtime_reuses_a_compatible_executable_after_an_old_path_entry(self):
        self.tool("ruff", "0.15.14")
        floor = runtime.TOOL_SPECS["ruff"][2]
        other = self.external / "other"
        other.mkdir()
        self.tool("other/ruff", floor)
        with (
            mock.patch.dict(os.environ, {"PATH": os.pathsep.join(map(str, (self.external, other)))}),
            mock.patch.object(runtime, "_managed_python") as install,
        ):
            self.assertEqual(runtime.ensure(self.home, ("ruff",))["versions"], {"ruff": floor})
            install.assert_not_called()

    def test_analyzer_probe_timeout_terminates_the_process_group(self):
        executable = self.tool("ruff", "0.17.5")
        process = mock.MagicMock(pid=12345)
        process.wait.side_effect = subprocess.TimeoutExpired("probe", 5)
        with (
            mock.patch.object(runtime.subprocess, "Popen") as spawn,
            mock.patch.object(os, "killpg") as kill,
        ):
            spawn.return_value.__enter__.return_value = process
            self.assertFalse(runtime._check_analyzer("ruff", executable))
        self.assertTrue(spawn.call_args.kwargs["start_new_session"])
        kill.assert_called_once_with(process.pid, signal.SIGKILL)

    def test_killed_probe_removes_temporary_files_created_by_its_child(self):
        marker = self.root / "child-temp-path"
        executable = self.external / "slow-ruff"
        executable.write_text(
            "#!/usr/bin/env python3\nfrom pathlib import Path\nimport tempfile,time\n"
            "child = tempfile.mkdtemp(prefix='mainframe-child-probe-')\n"
            f"Path({str(marker)!r}).write_text(child)\n"
            "time.sleep(30)\n"
        )
        executable.chmod(0o755)
        try:
            self.assertFalse(runtime._check_analyzer("ruff", executable))
            self.assertTrue(marker.exists(), "probe never reached its child")
            self.assertFalse(Path(marker.read_text()).exists())
        finally:
            if marker.exists():
                child = Path(marker.read_text())
                if child.name.startswith("mainframe-child-probe-") and child.exists():
                    shutil.rmtree(child)

    def test_squawk_reuse_rejects_an_analyzer_missing_online_migration_checks(self):
        executable = self.external / "squawk"
        executable.write_text(
            "#!/usr/bin/env python3\n"
            "import json\n"
            "import sys\n"
            "source = sys.stdin.read()\n"
            "rows = []\n"
            "if 'DROP TABLE' in source:\n"
            "    rows.append({'rule_name': 'ban-drop-table', 'line': 0, 'line_end': 0})\n"
            "print(json.dumps(rows))\n"
        )
        executable.chmod(0o755)
        self.assertFalse(runtime._check_analyzer("squawk", executable))

    def test_squawk_reuse_rejects_an_analyzer_missing_index_review_checks(self):
        executable = self.external / "squawk"
        executable.write_text(
            "#!/usr/bin/env python3\n"
            "import json, sys\n"
            "source = sys.stdin.read()\n"
            "rules = {\n"
            "    'DROP TABLE history': 'ban-drop-table',\n"
            "    'CREATE INDEX idx': 'require-concurrent-index-creation',\n"
            "    'ALTER TABLE events ADD CONSTRAINT': 'constraint-missing-not-valid',\n"
            "    'ALTER TABLE events ADD COLUMN': 'require-lock-timeout',\n"
            "}\n"
            "print(json.dumps([{'rule_name': rule, 'line': 0, 'line_end': 0}\n"
            "                  for prefix, rule in rules.items() if source.startswith(prefix)]))\n"
        )
        executable.chmod(0o755)
        self.assertFalse(runtime._check_analyzer("squawk", executable))

    def test_modern_web_reuse_rejects_an_analyzer_that_always_reports_clean(self):
        executable = self.tool("modern-web-guidance", "1.1.0")
        executable.write_text(
            "#!/usr/bin/env python3\n"
            "import json\n"
            "import sys\n"
            "if '--version' in sys.argv:\n"
            "    print('1.1.0')\n"
            "else:\n"
            "    print(json.dumps({'targetDir': sys.argv[2], 'activeRuleCount': 1, 'guides': []}))\n"
        )
        executable.chmod(0o755)
        self.assertIsNone(runtime._analyzer_version("modern-web-guidance", executable))

    def test_web_runtime_rejects_missing_old_and_prerelease_compilers(self):
        executable = self.tool("modern-web-guidance", "1.0.0")
        manifest = self.external / "node_modules/svelte/package.json"
        for version in ("5.57.2", "5.58.0-rc.1", None):
            with self.subTest(version=version):
                manifest.write_text(json.dumps({"version": version}))
                self.assertIsNone(runtime._analyzer_version("modern-web-guidance", executable))
        manifest.unlink()
        self.assertIsNone(runtime._analyzer_version("modern-web-guidance", executable))

    def test_newer_compiler_requires_own_rule_compatibility_even_with_tested_cli(self):
        executable = self.tool("modern-web-guidance", "1.0.0")
        (self.external / "node_modules/svelte/package.json").write_text(json.dumps({"version": "5.58.0"}))
        self.assertIsNone(runtime._analyzer_version("modern-web-guidance", executable))

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

    def python_packages(self, command, **options):
        if command[1:3] == ["-m", "venv"]:
            target = Path(command[-1]) / "bin"
            target.mkdir(parents=True, exist_ok=True)
            (target / "python").write_text("synthetic venv interpreter\n")
            return
        self.assertEqual(command[1:4], ["-m", "pip", "install"])
        target = Path(command[0]).parent
        for argument in command[4:]:
            if "==" not in argument:
                continue
            name, version = argument.split("==")
            executable = target / name
            executable.write_text(f"#!/bin/sh\nprintf '{name} {version}\\n'\n")
            executable.chmod(0o755)

    def legacy_python_binding(self):
        root = runtime.runtime_root(self.home)
        executable = root / "packages/python/bin/ruff"
        executable.parent.mkdir(parents=True)
        executable.write_bytes(self.tool("ruff", runtime.TOOL_SPECS["ruff"][2]).read_bytes())
        executable.chmod(0o755)
        (self.external / "ruff").unlink()
        shim = runtime.runtime_bin(self.home) / "ruff"
        shim.parent.mkdir()
        shim.write_bytes(runtime._analyzer_shim("ruff", executable))
        shim.chmod(0o755)
        (root / "installation.json").write_text(json.dumps({
            "schema": 1, "tools": {"ruff": {
                "version": runtime.TOOL_SPECS["ruff"][2], "executable": str(executable),
            }},
        }))
        return executable

    def test_failed_python_preparation_preserves_active_legacy_binding_and_foreign_files(self):
        old = self.legacy_python_binding()
        root = runtime.runtime_root(self.home)
        note = old.parent / "unregistered-note"
        note.write_text("preserve legacy user data")
        manifest = root / "installation.json"
        shim = runtime.runtime_bin(self.home) / "ruff"
        before = manifest.read_bytes(), shim.read_bytes(), old.read_bytes()

        def install(command, **options):
            if command[1:3] == ["-m", "venv"]:
                return self.python_packages(command, **options)
            raise Conflict("synthetic pip failure")

        with (
            mock.patch.dict(os.environ, {"PATH": str(self.external)}),
            mock.patch.object(runtime, "_run", side_effect=install),
            self.assertRaisesRegex(Conflict, "synthetic pip failure"),
        ):
            runtime.ensure(self.home, ("semgrep",))
        self.assertTrue(old.is_file(), "pip failure destroyed the active environment")
        self.assertEqual((manifest.read_bytes(), shim.read_bytes(), old.read_bytes()), before)
        self.assertEqual(note.read_text(), "preserve legacy user data")
        self.assertTrue(runtime.status(self.home, ("ruff",))["ready"])
        self.assertEqual(list((root / "packages/python").glob("mainframe-python-*")), [])

    def test_python_activation_migrates_legacy_without_erasing_unregistered_contents(self):
        old = self.legacy_python_binding()
        root = runtime.runtime_root(self.home)
        note = old.parent / "user-note"
        note.write_text("preserve")
        installed = []

        def install(command, **options):
            self.assertTrue(old.is_file(), "legacy tools must work until activation")
            self.assertEqual(note.read_text(), "preserve")
            installed.extend(argument for argument in command if "==" in argument)
            return self.python_packages(command, **options)

        with mock.patch.dict(os.environ, {"PATH": str(self.external)}), mock.patch.object(runtime, "_run", side_effect=install) as run:
            self.assertTrue(runtime.ensure(self.home, ("semgrep",))["ready"])
            self.assertTrue(runtime.ensure(self.home, ("ruff", "semgrep"))["ready"])
            self.assertEqual(run.call_count, 2, "a converged environment must not reinstall")
        self.assertEqual(installed, ["ruff==0.15.15", "semgrep==1.164.0"])
        rows = json.loads((root / "installation.json").read_text())["tools"]
        for name in ("ruff", "semgrep"):
            self.assertIn("mainframe-python-", rows[name]["executable"])
            self.assertTrue(Path(rows[name]["executable"]).is_file())
        self.assertTrue(old.is_file(), "legacy ownership does not cover every directory entry")
        self.assertEqual(note.read_text(), "preserve")

    def test_python_repair_cleans_only_superseded_recorded_generations_after_activation(self):
        root = runtime.runtime_root(self.home)
        with mock.patch.dict(os.environ, {"PATH": str(self.external)}), mock.patch.object(runtime, "_run", side_effect=self.python_packages):
            runtime.ensure(self.home, ("ruff",))
        manifest = root / "installation.json"
        old = Path(json.loads(manifest.read_text())["tools"]["ruff"]["executable"])
        generation = old.parent.parent
        foreign = root / "packages/python/mainframe-python-foreign1/user-note"
        foreign.parent.mkdir(parents=True)
        foreign.write_text("preserve unregistered generation")
        manifest_before = manifest.read_bytes()
        shim = runtime.runtime_bin(self.home) / "ruff"
        shim_before = shim.read_bytes()

        def install(command, **options):
            self.assertTrue(old.is_file())
            self.assertEqual(manifest.read_bytes(), manifest_before)
            self.assertEqual(shim.read_bytes(), shim_before)
            return self.python_packages(command, **options)

        with mock.patch.dict(os.environ, {"PATH": str(self.external)}), mock.patch.object(runtime, "_run", side_effect=install):
            runtime.ensure(self.home, ("yamllint",))
        self.assertFalse(generation.exists(), "the superseded recorded generation was retained")
        self.assertEqual(foreign.read_text(), "preserve unregistered generation")
        self.assertTrue(runtime.status(self.home, ("ruff", "yamllint"))["ready"])
        self.assertEqual(len(list((root / "packages/python").glob("mainframe-python-*"))), 2)

    def test_later_ecosystem_preparation_failure_discards_only_new_python_generation(self):
        with mock.patch.dict(os.environ, {"PATH": str(self.external)}), mock.patch.object(runtime, "_run", side_effect=self.python_packages):
            runtime.ensure(self.home, ("ruff",))
        root = runtime.runtime_root(self.home)
        manifest = root / "installation.json"
        shim = runtime.runtime_bin(self.home) / "ruff"
        before = manifest.read_bytes(), shim.read_bytes()
        generation = Path(json.loads(manifest.read_text())["tools"]["ruff"]["executable"]).parent.parent
        self.tool("npm", "10.0.0")
        with (
            mock.patch.dict(os.environ, {"PATH": str(self.external)}),
            mock.patch.object(runtime, "_run", side_effect=self.python_packages),
            mock.patch.object(runtime, "_managed_node", side_effect=Conflict("synthetic npm failure")),
            self.assertRaisesRegex(Conflict, "synthetic npm failure"),
        ):
            runtime.ensure(self.home, ("semgrep", "oxlint"))
        self.assertEqual((manifest.read_bytes(), shim.read_bytes()), before)
        self.assertEqual(list((root / "packages/python").glob("mainframe-python-*")), [generation])
        self.assertTrue(runtime.status(self.home, ("ruff",))["ready"])

    def test_python_version_probe_failure_discards_staged_generation(self):
        old = self.legacy_python_binding()
        root = runtime.runtime_root(self.home)
        manifest = root / "installation.json"
        before = manifest.read_bytes()

        def install(command, **options):
            self.python_packages(command, **options)
            if command[1:4] == ["-m", "pip", "install"]:
                (Path(command[0]).parent / "semgrep").write_text("#!/bin/sh\nprintf 'semgrep 1.0.0\\n'\n")

        with (
            mock.patch.dict(os.environ, {"PATH": str(self.external)}),
            mock.patch.object(runtime, "_run", side_effect=install),
            self.assertRaisesRegex(Conflict, "failed its version probe"),
        ):
            runtime.ensure(self.home, ("semgrep",))
        self.assertEqual(manifest.read_bytes(), before)
        self.assertTrue(old.is_file())
        self.assertTrue(runtime.status(self.home, ("ruff",))["ready"])
        self.assertEqual(list((root / "packages/python").glob("mainframe-python-*")), [])

    def test_package_preparation_rejects_symlinked_ancestors_and_ecosystem_directories(self):
        for ecosystem in ("python", "node"):
            for linked in ("packages", f"packages/{ecosystem}"):
                with self.subTest(ecosystem=ecosystem, linked=linked):
                    root = self.root / ecosystem / linked.replace("/", "-")
                    outside = self.root / "foreign" / ecosystem / linked.replace("/", "-")
                    outside.mkdir(parents=True)
                    marker = outside / "user-note"
                    marker.write_text("preserve")
                    link = root / linked
                    link.parent.mkdir(parents=True)
                    link.symlink_to(outside, target_is_directory=True)
                    prepare = runtime._managed_python if ecosystem == "python" else runtime._managed_node
                    name = "ruff" if ecosystem == "python" else "oxlint"
                    with (
                        mock.patch.object(runtime.shutil, "which", return_value="/synthetic/npm"),
                        mock.patch.object(runtime, "_run", side_effect=AssertionError("followed a symlink")) as run,
                        self.assertRaises(Conflict),
                    ):
                        prepare(root, [name])
                    run.assert_not_called()
                    self.assertEqual(marker.read_text(), "preserve")
                    self.assertEqual(list(outside.iterdir()), [marker])

    def test_generation_cleanup_refuses_symlinked_parent_and_preserves_child_links(self):
        root = runtime.runtime_root(self.home)
        outside = self.root / "foreign-packages"
        candidate = outside / "node/mainframe-node-foreign1"
        candidate.mkdir(parents=True)
        marker = candidate / "user-note"
        marker.write_text("preserve")
        packages = root / "packages"
        packages.parent.mkdir(parents=True)
        packages.symlink_to(outside, target_is_directory=True)
        previous = {"oxlint": {"executable": str(packages / "node" / candidate.name / "oxlint")}}
        with self.assertRaisesRegex(Conflict, "symlink"):
            runtime._cleanup_node_generations(root, previous, {})
        self.assertEqual(marker.read_text(), "preserve")
        packages.unlink()
        parent = packages / "node"
        parent.mkdir(parents=True)
        link = parent / "mainframe-node-foreign1"
        link.symlink_to(candidate, target_is_directory=True)
        runtime._cleanup_node_generations(root, {"oxlint": {"executable": str(link / "oxlint")}}, {})
        self.assertTrue(link.is_symlink())
        self.assertEqual(marker.read_text(), "preserve")

    def test_cleanup_leaves_unregistered_symlinked_ecosystems_untouched(self):
        self.tool("ruff", runtime.TOOL_SPECS["ruff"][2])
        root = runtime.runtime_root(self.home)
        node = root / "packages/node"
        node.parent.mkdir(parents=True)
        node.symlink_to(self.external, target_is_directory=True)
        with mock.patch.dict(os.environ, {"PATH": str(self.external)}), mock.patch.object(runtime, "_run") as install:
            self.assertTrue(runtime.ensure(self.home, ("ruff",))["ready"])
        install.assert_not_called()
        self.assertTrue(node.is_symlink())
        self.assertTrue((self.external / "ruff").is_file())

    def test_semgrep_version_probe_preserves_user_logs_settings_and_credentials(self):
        user_log = self.root / "user-semgrep.log"
        user_settings = self.root / "user-settings.yml"
        user_log.write_text("preserve log")
        user_settings.write_text("preserve settings")
        executable = self.external / "semgrep"
        executable.write_text(
            "#!/usr/bin/env python3\n"
            "import os\n"
            "from pathlib import Path\n"
            "assert 'SEMGREP_APP_TOKEN' not in os.environ\n"
            "Path(os.environ['SEMGREP_LOG_FILE']).write_text('temporary probe log')\n"
            "Path(os.environ['SEMGREP_SETTINGS_FILE']).write_text('temporary settings')\n"
            "print('semgrep 1.164.0')\n"
        )
        executable.chmod(0o755)
        with mock.patch.dict(os.environ, {"SEMGREP_LOG_FILE": str(user_log), "SEMGREP_SETTINGS_FILE": str(user_settings), "SEMGREP_APP_TOKEN": "synthetic-token"}):
            self.assertEqual(runtime._analyzer_release("semgrep", executable), "1.164.0")
        self.assertEqual(user_log.read_text(), "preserve log")
        self.assertEqual(user_settings.read_text(), "preserve settings")

    def test_failed_node_preparation_preserves_previous_analyzers(self):
        root = runtime.runtime_root(self.home)
        previous = root / "packages/node/node_modules/.bin/oxlint"
        previous.parent.mkdir(parents=True)
        previous.write_bytes(b"previous usable analyzer")
        with (
            mock.patch.object(runtime.shutil, "which", return_value="/synthetic/npm"),
            mock.patch.object(runtime, "_version", return_value="22.12.0"),
            mock.patch.object(runtime, "_run", side_effect=Conflict("synthetic installation failure")),
            self.assertRaisesRegex(Conflict, "synthetic installation failure"),
        ):
            runtime._managed_node(root, ["modern-web-guidance", "oxlint"])
        self.assertEqual(previous.read_bytes(), b"previous usable analyzer")
        self.assertEqual(list((root / "packages/node").glob("mainframe-node-*")), [])

    def test_node_activation_keeps_old_tools_until_new_generation_is_ready(self):
        root = runtime.runtime_root(self.home)
        old = root / "packages/node/node_modules/.bin/oxlint"
        old.parent.mkdir(parents=True)
        old.write_text("#!/bin/sh\nprintf 'oxlint 1.67.0\\n'\n")
        old.chmod(0o755)
        (root / "installation.json").write_text(json.dumps({
            "schema": 1, "tools": {"oxlint": {"version": "1.67.0", "executable": str(old)}},
        }))
        node = self.tool("node", "22.12.0")
        node.write_text("#!/bin/sh\nprintf 'v22.12.0\\n'\n")
        self.tool("npm", "10.0.0")
        marker = root / "packages/node/user-note"
        marker.write_text("preserve")

        def install(command, **options):
            self.assertTrue(old.exists())
            target = Path(command[command.index("--prefix") + 1]) / "node_modules/.bin"
            target.mkdir(parents=True)
            for name in ("oxlint", "modern-web-guidance"):
                executable = target / name
                executable.write_text(f"#!/bin/sh\nprintf '{name} {runtime.TOOL_SPECS[name][2]}\\n'\n")
                executable.chmod(0o755)
            (target / "legacy-scan.mjs").write_text("export const parser = true;\n")
            compiler = target.parent / "svelte/compiler/index.js"
            compiler.parent.mkdir(parents=True)
            compiler.write_text("exports.parse = () => ({});\n")
            (compiler.parent.parent / "package.json").write_text(json.dumps({"version": runtime.WEB_COMPILER_VERSION}))
            self.assertIn(f"svelte@{runtime.WEB_COMPILER_VERSION}", command)

        with mock.patch.dict(os.environ, {"PATH": str(self.external)}), mock.patch.object(runtime, "_run", side_effect=install):
            self.assertTrue(runtime.ensure(self.home, ("modern-web-guidance",))["ready"])
        self.assertFalse(old.exists())
        self.assertEqual(marker.read_text(), "preserve")
        record = json.loads((root / "installation.json").read_text())["tools"]
        for name in ("oxlint", "modern-web-guidance"):
            self.assertTrue(Path(record[name]["executable"]).is_file())
        self.assertEqual(len(list((root / "packages/node").glob("mainframe-node-*"))), 1)

    def test_node_cleanup_preserves_unregistered_legacy_modules(self):
        root = runtime.runtime_root(self.home)
        unregistered = root / "packages/node/node_modules/user-file"
        unregistered.parent.mkdir(parents=True)
        unregistered.write_text("preserve")
        runtime._cleanup_node_generations(root, {}, {})
        self.assertEqual(unregistered.read_text(), "preserve")

    def test_npm_preparation_uses_disposable_cache_and_logs_on_success_and_failure(self):
        environment = self.openspec_fixture()
        cache = self.root / "user-npm-cache"
        cache_store = self.root / "existing-cache-store"
        logs = self.root / "user-npm-logs"
        cache_store.mkdir()
        cache.symlink_to(cache_store, target_is_directory=True)
        logs.mkdir()
        (cache / "user-note").write_text("preserve cache")
        (logs / "user-note").write_text("preserve logs")
        config = self.root / "user.npmrc"
        config.write_text(f"cache={cache}\nlogs-dir={logs}\n")
        environment.update(NPM_CONFIG_CACHE=str(cache), npm_config_cache=str(cache),
                           NPM_CONFIG_LOGS_DIR=str(logs), NPM_CONFIG_USERCONFIG=str(config))
        for ecosystem in ("node", "openspec"):
            for failed in (False, True):
                with self.subTest(ecosystem=ecosystem, failed=failed):
                    operation_paths = []
                    root = self.root / f"{ecosystem}-{failed}"

                    def install(command, **options):
                        def option(name, fallback):
                            return Path(command[command.index(name) + 1]) if name in command else fallback
                        operation_cache = option("--cache", cache)
                        operation_logs = option("--logs-dir", logs)
                        operation_paths.extend((operation_cache, operation_logs))
                        operation_cache.mkdir(parents=True, exist_ok=True)
                        operation_logs.mkdir(parents=True, exist_ok=True)
                        (operation_cache / "download").write_text("temporary package bytes")
                        (operation_logs / "debug.log").write_text("temporary install log")
                        self.assertEqual(options["env"]["NPM_CONFIG_USERCONFIG"], str(config))
                        self.assertEqual(options["env"]["NPM_CONFIG_CACHE"], str(operation_cache))
                        self.assertEqual(options["env"]["npm_config_cache"], str(operation_cache))
                        self.assertEqual(options["env"]["NPM_CONFIG_LOGS_DIR"], str(operation_logs))
                        self.assertEqual(options["env"]["npm_config_logs_dir"], str(operation_logs))
                        if failed:
                            raise Conflict("synthetic npm failure")
                        target = Path(command[command.index("--prefix") + 1])
                        if ecosystem == "openspec":
                            executable = target / "node_modules" / runtime.OPENSPEC_PACKAGE / "bin/openspec.js"
                            executable.parent.mkdir(parents=True)
                            executable.write_bytes(Path(environment["OPENSPEC_FIXTURE_ENTRY"]).read_bytes())
                        else:
                            executable = target / "node_modules/.bin/oxlint"
                            executable.parent.mkdir(parents=True)
                            executable.write_text(f"#!/bin/sh\nprintf 'oxlint {runtime.TOOL_SPECS['oxlint'][2]}\\n'\n")
                        executable.chmod(0o755)

                    with mock.patch.dict(os.environ, environment), mock.patch.object(runtime, "_run", side_effect=install):
                        def prepare():
                            if ecosystem == "node":
                                return runtime._managed_node(root, ["oxlint"])
                            target = root / "openspec-stage"
                            target.mkdir(parents=True)
                            return runtime._install_openspec(target, str(self.external / "npm"), self.external / "node")
                        if failed:
                            with self.assertRaisesRegex(Conflict, "synthetic npm failure"):
                                prepare()
                        else:
                            prepare()
                    self.assertEqual(len(operation_paths), 2)
                    self.assertNotEqual(operation_paths[0], cache)
                    self.assertNotEqual(operation_paths[1], logs)
                    self.assertTrue(all(not path.exists() for path in operation_paths))
                    self.assertTrue(cache.is_symlink())
                    self.assertEqual(list(cache.iterdir()), [cache / "user-note"])
                    self.assertEqual(list(logs.iterdir()), [logs / "user-note"])
                    self.assertEqual(config.read_text(), f"cache={cache}\nlogs-dir={logs}\n")

    def test_compatible_npm_tools_are_reused_without_preparing_a_cache(self):
        environment = self.openspec_fixture()
        self.tool("openspec", runtime.OPENSPEC_VERSION)
        self.tool("oxlint", runtime.TOOL_SPECS["oxlint"][2])
        with (
            mock.patch.dict(os.environ, environment),
            mock.patch.object(runtime, "_npm_install", side_effect=AssertionError("unnecessary npm preparation")) as install,
        ):
            self.assertTrue(runtime.ensure(self.home, ("openspec", "oxlint"))["ready"])
        install.assert_not_called()

    def test_native_analyzer_is_prepared_once_and_reused_without_network(self):
        binary = self.tool("actionlint", "1.7.12").read_bytes()
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
            member = tarfile.TarInfo("actionlint")
            member.size = len(binary)
            archive.addfile(member, io.BytesIO(binary))
        content = buffer.getvalue()
        release = ("example/actionlint", "v1.7.12", "standalone.tar.gz", "actionlint", digest(content))
        with (
            mock.patch.object(runtime, "_native_release", return_value=release),
            mock.patch.object(runtime, "_download_release", return_value=content) as fetch,
            mock.patch.object(runtime.shutil, "which", return_value=None),
        ):
            result = runtime.ensure(self.home, ("actionlint",))
            self.assertEqual(result["versions"], {"actionlint": "1.7.12"})
            self.assertTrue(runtime.ensure(self.home, ("actionlint",))["ready"])
            fetch.assert_called_once()
        job = subprocess.run(
            [runtime.runtime_bin(self.home) / "actionlint", "-version"],
            capture_output=True, text=True, check=True, timeout=2,
        )
        self.assertEqual(job.stdout, "actionlint 1.7.12\n")

    def test_native_analyzer_digest_mismatch_does_not_activate_it(self):
        release = ("example/actionlint", "v1.7.12", "standalone.tar.gz", "actionlint", "0" * 64)
        with (
            mock.patch.object(runtime, "_native_release", return_value=release),
            mock.patch.object(runtime, "_download_release", return_value=b"wrong archive"),
            mock.patch.object(runtime.shutil, "which", return_value=None),
            self.assertRaisesRegex(Conflict, "checksum"),
        ):
            runtime.ensure(self.home, ("actionlint",))
        self.assertFalse((runtime.runtime_bin(self.home) / "actionlint").exists())
        self.assertFalse((runtime.runtime_root(self.home) / "installation.json").exists())

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
        self.assertFalse(entrypoint.parents[4].exists())
        self.assertEqual(len(list((root / "packages").glob("openspec-*"))), 1)

    def test_openspec_replacement_cleans_previous_generation_after_commit_only(self):
        environment = self.openspec_fixture()
        root = runtime.runtime_root(self.home)
        manifest = root / "installation.json"
        with mock.patch.dict(os.environ, environment):
            runtime.ensure(self.home, ("openspec",))
        old = Path(json.loads(manifest.read_text())["tools"]["openspec"]["executable"])
        generation = old.parents[4]
        foreign = root / "packages/openspec-foreign1/user-note"
        foreign.parent.mkdir()
        foreign.write_text("preserve unregistered generation")
        old.unlink()
        transact = runtime.transact

        def activate(changes, journal, allowed):
            self.assertTrue(generation.exists())
            transact(changes, journal, allowed)
            self.assertTrue(generation.exists(), "cleanup must follow committed activation")
            active = json.loads(manifest.read_text())["tools"]["openspec"]["executable"]
            self.assertNotEqual(active, str(old))
            self.assertTrue(Path(active).is_file())
            self.assertFalse(journal.exists())

        with mock.patch.dict(os.environ, environment), mock.patch.object(runtime, "transact", side_effect=activate):
            self.assertTrue(runtime.ensure(self.home, ("openspec",))["ready"])
        self.assertFalse(generation.exists())
        self.assertEqual(foreign.read_text(), "preserve unregistered generation")

    def test_openspec_cleanup_preserves_a_generation_still_referenced_by_another_tool(self):
        environment = self.openspec_fixture()
        root = runtime.runtime_root(self.home)
        manifest = root / "installation.json"
        with mock.patch.dict(os.environ, environment):
            runtime.ensure(self.home, ("openspec",))
        record = json.loads(manifest.read_text())
        old = Path(record["tools"]["openspec"]["executable"])
        retained = old.parent / "retained-reference"
        retained.write_text("another recorded tool")
        external_alias = self.external / "retained-tool"
        external_alias.symlink_to(retained)
        record["tools"]["other-tool"] = {"executable": str(external_alias)}
        manifest.write_text(json.dumps(record))
        old.unlink()
        with mock.patch.dict(os.environ, environment):
            self.assertTrue(runtime.ensure(self.home, ("openspec",))["ready"])
        self.assertTrue(old.parents[4].is_dir())

    def test_openspec_recovery_data_keeps_both_generations_after_failed_transaction(self):
        environment = self.openspec_fixture()
        root = runtime.runtime_root(self.home)
        manifest = root / "installation.json"
        shim = runtime.runtime_bin(self.home) / "openspec"
        journal = root / ".openspec-recovery.json"
        with mock.patch.dict(os.environ, environment):
            runtime.ensure(self.home, ("openspec",))
        old = Path(json.loads(manifest.read_text())["tools"]["openspec"]["executable"])
        old.unlink()
        before = manifest.read_bytes(), shim.read_bytes()

        def interrupted(*arguments):
            journal.write_text("synthetic recovery data")
            raise Conflict("synthetic recovery needed")

        with (
            mock.patch.dict(os.environ, environment),
            mock.patch.object(runtime, "transact", side_effect=interrupted),
            self.assertRaisesRegex(Conflict, "synthetic recovery needed"),
        ):
            runtime.ensure(self.home, ("openspec",))
        self.assertEqual(journal.read_text(), "synthetic recovery data")
        self.assertEqual((manifest.read_bytes(), shim.read_bytes()), before)
        self.assertTrue(old.parents[4].exists())
        self.assertEqual(len(list((root / "packages").glob("openspec-*"))), 2)

    def test_openspec_cleanup_preserves_symlinked_previous_generation(self):
        environment = self.openspec_fixture()
        root = runtime.runtime_root(self.home)
        manifest = root / "installation.json"
        with mock.patch.dict(os.environ, environment):
            runtime.ensure(self.home, ("openspec",))
        old = Path(json.loads(manifest.read_text())["tools"]["openspec"]["executable"])
        generation = old.parents[4]
        foreign = self.root / "foreign-openspec-generation"
        generation.rename(foreign)
        generation.symlink_to(foreign, target_is_directory=True)
        old.unlink()
        marker = foreign / "user-note"
        marker.write_text("preserve")
        with mock.patch.dict(os.environ, environment):
            self.assertTrue(runtime.ensure(self.home, ("openspec",))["ready"])
        self.assertTrue(generation.is_symlink())
        self.assertEqual(marker.read_text(), "preserve")

    def test_openspec_cleanup_refusal_after_commit_keeps_the_new_active_generation(self):
        environment = self.openspec_fixture()
        root = runtime.runtime_root(self.home)
        manifest = root / "installation.json"
        with mock.patch.dict(os.environ, environment):
            runtime.ensure(self.home, ("openspec",))
        old = Path(json.loads(manifest.read_text())["tools"]["openspec"]["executable"])
        old.unlink()
        packages = root / "packages"
        relocated = self.root / "relocated-packages"
        transact = runtime.transact

        def activate(changes, journal, allowed):
            transact(changes, journal, allowed)
            packages.rename(relocated)
            packages.symlink_to(relocated, target_is_directory=True)

        with (
            mock.patch.dict(os.environ, environment),
            mock.patch.object(runtime, "transact", side_effect=activate),
            self.assertRaisesRegex(Conflict, "symlink"),
        ):
            runtime.ensure(self.home, ("openspec",))
        active = Path(json.loads(manifest.read_text())["tools"]["openspec"]["executable"])
        self.assertNotEqual(active, old)
        self.assertTrue(active.is_file())
        self.assertTrue(runtime.status(self.home, ("openspec",))["ready"])
        self.assertTrue(old.parents[4].is_dir())
        self.assertFalse((root / ".openspec-recovery.json").exists())

    def test_openspec_replacement_preserves_a_previously_reused_external_tool(self):
        environment = self.openspec_fixture()
        external = self.tool("openspec", runtime.OPENSPEC_VERSION)
        with mock.patch.dict(os.environ, environment):
            runtime.ensure(self.home, ("openspec",))
        external.write_text("#!/bin/sh\nprintf '0.0.1\\n'\n")
        with mock.patch.dict(os.environ, environment):
            self.assertTrue(runtime.ensure(self.home, ("openspec",))["ready"])
        self.assertEqual(external.read_text(), "#!/bin/sh\nprintf '0.0.1\\n'\n")

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

    def test_openspec_reuses_newer_stable_cli_with_working_list(self):
        standalone = self.tool("openspec", "1.17.0")
        standalone.write_text("""#!/bin/sh
case "$*" in
    --version) printf '1.17.0\\n' ;;
    'list --json') printf '{"changes":[]}\\n' ;;
    *) exit 2 ;;
esac
""")
        with mock.patch.dict(os.environ, {"PATH": str(self.external)}):
            result = runtime.ensure(self.home, ("openspec",))
            self.assertEqual(result["versions"], {"openspec": "1.17.0"})
            self.assertTrue(runtime.status(self.home, ("openspec",))["ready"])
            self.tool("openspec", "1.18.0")
            self.assertFalse(runtime.status(self.home, ("openspec",))["ready"])

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
