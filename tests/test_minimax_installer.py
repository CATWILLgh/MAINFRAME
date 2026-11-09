import json
import os
from pathlib import Path
import plistlib
import shutil
import shlex
import subprocess
import sys
import tempfile
import unittest

from installer.core import Conflict, digest, encode_json, observed, transact
from installer.runtime import OPENSPEC_VERSION, TOOL_SPECS
from installer.minimax import COMMAND_REASON, MiniMax, desktop_version


ROOT = Path(__file__).resolve().parents[1]


class MiniMaxInstallationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="mainframe-minimax-install-")
        self.addCleanup(self.temporary.cleanup)
        base = Path(self.temporary.name).resolve()
        self.source = base / "source"
        self.source.mkdir()
        for name in ("instructions", "skills", "agents", "commands", "hooks", "plugins", "installer"):
            shutil.copytree(ROOT / name, self.source / name, ignore=shutil.ignore_patterns("__pycache__"))
        for name in ("ADAPTATION.example.json", ".gitignore", "install.py"):
            shutil.copyfile(ROOT / name, self.source / name)
        credentials = self.source / "shared/credentials"
        credentials.mkdir(parents=True)
        for name in ("mainframe-secret", "credentials-index.template.md"):
            shutil.copyfile(ROOT / "shared/credentials" / name, credentials / name)
        self.home = base / "home with 'quotes'"
        self.home.mkdir()
        self.adapter = MiniMax(self.source, self.home, version="3.0.73")

    def apply(self):
        changes, report = self.adapter.plan()
        transact(changes, self.adapter.journal, self.adapter.allowed)
        self.adapter.clean_directories(self.adapter.receipt())
        return report

    def test_skill_only_delivery_registers_one_private_package(self):
        self.apply()
        transact(self.adapter.control(False, "mainframe-secret-access"), self.adapter.journal, self.adapter.allowed)
        name = "mainframe-k3s"
        destination = self.adapter.plugin / "skills" / name
        manifest_path = self.adapter.plugin / ".minimax-plugin/plugin.json"
        manifest = json.loads(manifest_path.read_bytes())
        manifest["description"] = "Existing Plugin metadata"
        original_manifest = encode_json(manifest)
        manifest["skills"].remove(f"skills/{name}/SKILL.md")
        manifest_path.write_bytes(encode_json(manifest))
        shutil.rmtree(destination)
        receipt = self.adapter.receipt()
        receipt["files"] = {path: record for path, record in receipt["files"].items()
                            if not Path(path).is_relative_to(destination)}
        receipt["files"][str(manifest_path)]["sha256"] = digest(manifest_path.read_bytes())
        self.adapter.receipt_path.write_bytes(encode_json(receipt))
        state = json.loads(self.adapter.state_path.read_bytes())
        del state["components"]["skills"][name]
        self.adapter.state_path.write_bytes(encode_json(state))

        edited_command = self.adapter.plugin / "skills/mainframe-project-skill/SKILL.md"
        edited_command.write_text(edited_command.read_text() + "\nUnrelated edit\n")
        shared = self.home / ".agents/skills" / name / "SKILL.md"
        shared.parent.mkdir(parents=True)
        shared.write_text("unrelated shared skill\n")
        protected = {path: observed(path) for path in self.home.rglob("*")
                     if path.is_file() and path not in {manifest_path, self.adapter.receipt_path}}

        def run(action):
            return subprocess.run([
                sys.executable, "-B", str(self.source / "install.py"), "minimax", action,
                "--home", str(self.home), "--surface", "desktop", "--runtime-version", "3.0.73",
                "--skill", name,
            ], cwd=self.source, capture_output=True, text=True, timeout=10)

        result = run("plan")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(set(json.loads(result.stdout)["components_changed"]),
                         {"skills." + name, "plugin package", "adaptation state", "ownership receipt"})
        self.assertFalse(destination.exists())
        result = run("apply")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(manifest_path.read_bytes(), original_manifest)
        for source in (self.source / "skills" / name).rglob("*"):
            if source.is_file():
                self.assertEqual(observed(destination / source.relative_to(self.source / "skills" / name)),
                                 observed(source))
        for path, snapshot in protected.items():
            self.assertEqual(observed(path), snapshot, str(path))
        new_files = {path for path in self.home.rglob("*") if path.is_file()} - protected.keys()
        self.assertTrue(all(path.is_relative_to(destination) or path in {
            manifest_path, self.adapter.receipt_path, self.adapter.lock_path,
        } for path in new_files))
        after_receipt = self.adapter.receipt()
        self.assertEqual(after_receipt["disabled_markers"], receipt["disabled_markers"])
        for path, record in receipt["files"].items():
            if path != str(manifest_path):
                self.assertEqual(after_receipt["files"][path], record)
        after_state = json.loads(self.adapter.state_path.read_bytes())
        self.assertEqual(after_state["components"]["skills"].pop(name)["verification"], "pending")
        self.assertEqual(after_state, state)
        result = run("verify")
        self.assertEqual(result.returncode, 0, result.stderr)
        verified = json.loads(result.stdout)
        self.assertTrue(verified["scoped_update_matches"])
        self.assertEqual(verified["file_change_count"], 0)
        self.assertNotIn("runtime_support", verified)

    def test_skill_only_requires_an_unedited_owned_manifest_and_known_release(self):
        self.apply()
        name = "mainframe-k3s"
        manifest = self.adapter.plugin / ".minimax-plugin/plugin.json"
        data = manifest.read_bytes()
        manifest.write_bytes(data + b"\n")
        with self.assertRaisesRegex(Conflict, "manifest is missing or was edited"):
            self.adapter.plan_skill(name)
        manifest.write_bytes(data)
        receipt = self.adapter.receipt()
        receipt["files"][str(manifest)]["owned"] = False
        self.adapter.receipt_path.write_bytes(encode_json(receipt))
        with self.assertRaisesRegex(Conflict, "requires the installer-owned MiniMax Plugin manifest"):
            self.adapter.plan_skill(name)
        adapter = MiniMax(self.source, self.home, version="3.0.74")
        with self.assertRaisesRegex(Conflict, "requires the inspected Desktop release 3.0.73"):
            adapter.plan_skill(name)

    def test_skill_only_rejects_duplicate_selected_registration(self):
        self.apply()
        name = "mainframe-k3s"
        path = self.adapter.plugin / ".minimax-plugin/plugin.json"
        manifest = json.loads(path.read_bytes())
        manifest["skills"].append(f"skills/{name}/SKILL.md")
        data = encode_json(manifest)
        path.write_bytes(data)
        receipt = self.adapter.receipt()
        receipt["files"][str(path)]["sha256"] = digest(data)
        self.adapter.receipt_path.write_bytes(encode_json(receipt))
        with self.assertRaisesRegex(Conflict, "registers the selected skill more than once"):
            self.adapter.plan_skill(name)

    def test_fresh_delivery_converges_as_one_native_plugin(self):
        report = self.apply()
        _, converged = self.adapter.plan()
        self.assertEqual(converged["changes"], [])
        init_command = (self.adapter.plugin / "skills/mainframe-tickets-init/SKILL.md").read_text()
        self.assertIn("<!-- MAINFRAME ticket rules: begin -->", init_command)
        self.assertIn("<!-- MAINFRAME ticket entry: end -->", init_command)
        self.assertIn("execution: user-approved", init_command)
        self.assertFalse((self.home / "docs/tickets").exists())

        testing_source = ROOT / "skills/mainframe-testing"
        testing_delivered = (self.adapter.plugin / "skills") / "mainframe-testing"
        for source in testing_source.rglob("*.md"):
            with self.subTest(testing_resource=str(source.relative_to(testing_source))):
                self.assertEqual(
                    (testing_delivered / source.relative_to(testing_source)).read_bytes(),
                    source.read_bytes(),
                )

        self.assertEqual(report["planned_delivery"], {"installed": 42, "pending": 0, "unsupported": 13})
        manifest = json.loads((self.adapter.plugin / ".minimax-plugin/plugin.json").read_text())
        self.assertEqual(manifest["name"], "mainframe")
        source = json.loads((self.source / "ADAPTATION.example.json").read_text())
        expected_skills = [f"skills/{name}/SKILL.md" for category in ("skills", "commands")
                           for name in source["components"][category]]
        self.assertCountEqual(manifest["skills"], expected_skills)
        self.assertEqual(manifest["hooks"], ["hooks/hooks.json"])
        hooks = json.loads((self.adapter.plugin / "hooks/hooks.json").read_text())["hooks"]
        self.assertEqual(set(hooks), {
            "SessionStart", "SubagentStart", "PreToolUse", "PostToolUse", "Stop", "SubagentStop",
        })
        self.assertEqual(hooks["PreToolUse"][0]["matcher"], "bash|write|edit|task")
        self.assertEqual(hooks["PostToolUse"][0]["matcher"], "bash|read|write|edit")
        self.assertTrue(all(
            "MAINFRAME_RUNTIME_BIN=" in handler["command"]
            for groups in hooks.values() for group in groups for handler in group["hooks"]
        ))
        state = json.loads(self.adapter.state_path.read_text())
        reminder = state["components"]["hooks"]["mainframe-skill-reminder"]
        self.assertEqual(reminder["delivery"], "installed")
        self.assertEqual(reminder["verification"], "pending")
        self.assertNotIn("reason", reminder)
        self.assertTrue((self.adapter.plugin / "hooks/detectors" / "mainframe-skill-reminder.py").exists())
        self.assertTrue(any("mainframe-skill-reminder" in path
                             for path in self.adapter.receipt()["files"]))
        self.assertNotIn("mainframe-skill-reminder", (self.adapter.plugin / "hooks/hooks.json").read_text())
        self.assertEqual(state["components"]["agents"]["mainframe-researcher"]["delivery"], "installed")
        self.assertEqual(state["components"]["agents"]["mainframe-go-backend-engineer"]["delivery"], "installed")
        self.assertEqual(state["components"]["commands"]["mainframe-project-skill"]["reason"], COMMAND_REASON)
        self.assertEqual(state["components"]["hooks"]["mainframe-fallow-quality"]["delivery"], "installed")
        command = (self.adapter.plugin / "skills/mainframe-project-skill/SKILL.md").read_text()
        self.assertIn("Never select this Skill autonomously", command)

    def test_native_role_material_preserves_canonical_body_and_method_links(self):
        report = self.apply()
        for source in (self.source / "agents").glob("*.md"):
            role = self.adapter.minimax / "agents" / source.stem / "agent.md"
            text = role.read_text()
            self.assertIn(str(self.adapter.plugin / "skills"), text)
            for line in source.read_text().splitlines():
                if line and not line.startswith("Required method:"):
                    self.assertIn(line, text)
            self.assertNotIn(source.stem, report["retained_partial_bindings"])

    def test_role_skill_migration_preserves_disables_and_unrelated_native_state(self):
        self.apply()
        role_name = "mainframe-researcher"
        native = self.adapter.minimax / "agents" / role_name / "agent.md"
        native.unlink()
        old = self.adapter.plugin / "skills" / role_name / "SKILL.md"
        old.parent.mkdir()
        old.write_text("previous receipted role guidance\n")
        old.chmod(0o600)
        from installer.core import digest
        receipt = self.adapter.receipt()
        del receipt["files"][str(native)]
        receipt["directories"].append(str(old.parent))
        receipt["files"][str(old)] = {"sha256": digest(old.read_bytes()), "mode": 0o600,
                                     "component": "agents." + role_name, "owned": True, "retain": False}
        self.adapter.receipt_path.write_text(json.dumps(receipt))
        settings = self.adapter.minimax / "settings.json"
        settings.write_text('{"theme":"user","plugins":{"mainframe":{"enabled":false}}}')
        foreign = self.adapter.minimax / "agents/user-owned/agent.md"
        foreign.parent.mkdir()
        foreign.write_text("user role settings")
        transact(self.adapter.control(False, "mainframe-secret-access"), self.adapter.journal, self.adapter.allowed)
        self.apply()
        self.assertTrue(native.is_file())
        self.assertFalse(old.exists())
        self.assertTrue((self.adapter.plugin / "hooks/.disabled-mainframe-secret-access").exists())
        self.assertEqual(settings.read_text(), '{"theme":"user","plugins":{"mainframe":{"enabled":false}}}')
        self.assertEqual(foreign.read_text(), "user role settings")
        self.assertEqual(self.adapter.plan()[1]["changes"], [])
        native.write_text(native.read_text().replace("description:", 'model: user/selected\neffort: high\ndescription:', 1))
        before = native.read_bytes()
        with self.assertRaisesRegex(Conflict, "was edited"):
            self.adapter.plan()
        self.assertEqual(native.read_bytes(), before)

    def test_native_roles_and_new_guards_account_for_all_components(self):
        report = self.apply()
        self.assertEqual(report["planned_delivery"], {"installed": 42, "pending": 0, "unsupported": 13})
        for name in ("mainframe-subagent-selection", "mainframe-todo-limits"):
            self.assertTrue((self.adapter.plugin / "hooks/detectors" / (name + ".py")).is_file())
        for source in (self.source / "agents").glob("*.md"):
            role = self.adapter.minimax / "agents" / source.stem / "agent.md"
            self.assertTrue(role.is_file(), source.stem)
            self.assertIn("description:", role.read_text())
            self.assertNotIn("model:", role.read_text())
            self.assertNotIn("effort:", role.read_text())
            self.assertFalse((self.adapter.plugin / "skills" / source.stem / "SKILL.md").exists())
        for name in ("mainframe-consequential-reviewer", "mainframe-test-auditor", "mainframe-researcher"):
            role = self.adapter.minimax / "agents" / name / "agent.md"
            self.assertIn('tools: ["read", "glob", "grep", "skill", "web_fetch", "web_search", "ask_user"]', role.read_text())
            self.assertNotIn("bash", role.read_text().split("---")[1])

    def test_full_mapping_requires_verified_native_generation_but_removal_remains_available(self):
        self.adapter.version = "3.0.71"
        with self.assertRaisesRegex(Conflict, "3.0.73"):
            self.adapter.plan()
        self.assertFalse(self.adapter.plugin.exists())
        self.adapter.version = "3.0.73"
        self.apply()
        self.adapter.version = "3.0.71"
        self.assertTrue(self.adapter.plan(remove=True)[0])

    def test_package_obeys_v1_portable_path_and_size_limits(self):
        self.apply()
        manifest = json.loads((self.adapter.plugin / ".minimax-plugin/plugin.json").read_text())
        self.assertEqual(set(manifest), {
            "schemaVersion", "name", "displayName", "version", "description", "author",
            "icon", "category", "exampleQueries", "apps", "mcpServers", "skills", "hooks",
        })
        files = [p for p in self.adapter.plugin.rglob("*") if p.is_file()]
        entries = list(self.adapter.plugin.rglob("*"))
        self.assertLessEqual(len(entries), 2048)
        self.assertLessEqual(len(files), 1024)
        self.assertLessEqual(sum(p.stat().st_size for p in files), 64 * 1024 * 1024)
        for path in entries:
            relative = path.relative_to(self.adapter.plugin)
            self.assertLessEqual(len(relative.parts), 16)
            self.assertFalse(path.is_symlink())
            for part in relative.parts:
                self.assertRegex(part, r"^[A-Za-z0-9._-]+$")
                self.assertLessEqual(len(part.encode("ascii")), 128)
            self.assertLessEqual(len(relative.as_posix().encode("ascii")), 512)
        self.assertTrue((self.adapter.plugin / "icon.png").read_bytes().startswith(b"\x89PNG\r\n\x1a\n"))
        for relative in manifest["skills"]:
            path = self.adapter.plugin / relative
            self.assertTrue(path.is_file())
            name = path.parent.name
            self.assertRegex(path.read_text(), rf"(?m)^name: {name}$")
        hook_document = json.loads((self.adapter.plugin / manifest["hooks"][0]).read_text())
        handlers = [handler for groups in hook_document["hooks"].values()
                    for group in groups for handler in group["hooks"]]
        self.assertEqual(len(handlers), 6)
        self.assertTrue(all(set(handler) <= {"type", "command", "timeout", "commandWindows"}
                            for handler in handlers))
        self.assertTrue(all(handler["type"] == "command" and 1 <= handler["timeout"] <= 10
                            for handler in handlers))

    def test_installed_hook_command_runs_with_native_environment(self):
        self.apply()
        hooks = json.loads((self.adapter.plugin / "hooks/hooks.json").read_text())["hooks"]
        command = hooks["SessionStart"][0]["hooks"][0]["command"]
        plugin_data = self.home / ".minimax/plugin-data/mainframe"
        command = command.replace("${PLUGIN_ROOT}", str(self.adapter.plugin)).replace(
            "${PLUGIN_DATA}", str(plugin_data)
        )
        result = subprocess.run(
            shlex.split(command), input=json.dumps({
                "hook_event_name": "SessionStart", "session_id": "session",
                "cwd": str(self.source), "source": "startup",
            }), capture_output=True, text=True, timeout=10,
            env={**os.environ, "PLUGIN_ROOT": str(self.adapter.plugin),
                 "PLUGIN_DATA": str(plugin_data)},
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["hookSpecificOutput"]["hookEventName"], "SessionStart")
        self.assertIn("actively match available skill descriptions",
                      payload["hookSpecificOutput"]["additionalContext"])

    def test_existing_foreign_plugin_and_owned_edits_are_refused(self):
        target = self.adapter.plugin / ".minimax-plugin/plugin.json"
        target.parent.mkdir(parents=True)
        target.write_text('{"name":"foreign"}\n')
        with self.assertRaisesRegex(Conflict, "no installer ownership"):
            self.adapter.plan()
        target.unlink()
        self.apply()
        skill = self.adapter.plugin / "skills/mainframe-research/SKILL.md"
        skill.write_text(skill.read_text() + "user edit\n")
        with self.assertRaisesRegex(Conflict, "was edited"):
            self.adapter.plan()

    def test_unexpected_plugin_entry_is_refused(self):
        extra = self.adapter.plugin / "foreign.txt"
        extra.parent.mkdir(parents=True)
        extra.write_text("foreign\n")
        with self.assertRaisesRegex(Conflict, "Unexpected entry"):
            self.adapter.plan()

    def test_hook_control_preserves_markers(self):
        self.apply()
        transact(self.adapter.control(False, "mainframe-secret-access"), self.adapter.journal, self.adapter.allowed)
        marker = self.adapter.plugin / "hooks/.disabled-mainframe-secret-access"
        self.assertTrue(marker.exists())
        transact(self.adapter.control(True, "mainframe-secret-access"), self.adapter.journal, self.adapter.allowed)
        self.assertFalse(marker.exists())

    def test_uninstall_removes_owned_plugin_and_retains_index(self):
        self.apply()
        transact(self.adapter.control(False), self.adapter.journal, self.adapter.allowed)
        changes, _ = self.adapter.plan(remove=True)
        transact(changes, self.adapter.journal, self.adapter.allowed)
        self.adapter.clean_directories(self.adapter.receipt())
        self.assertFalse((self.adapter.plugin / ".minimax-plugin/plugin.json").exists())
        self.assertFalse(any((self.adapter.minimax / "agents").glob("mainframe-*/agent.md")))
        self.assertFalse(any(self.adapter.plugin.glob("hooks/.disabled-*")))
        self.assertTrue(self.adapter.index.exists())

    def test_entrypoint_is_desktop_only_without_a_runtime_pin(self):
        # This test owns entrypoint/version routing, not network provisioning.
        tools = self.home / "fixture-version-tools"
        tools.mkdir()
        versions = {name: spec[2] for name, spec in TOOL_SPECS.items()}
        versions["openspec"] = OPENSPEC_VERSION
        for name, version in versions.items():
            executable = tools / name
            executable.write_text(f"#!/bin/sh\nprintf '%s\\n' '{name} {version}'\n")
            executable.chmod(0o755)
        environment = {**os.environ, "PATH": str(tools) + os.pathsep + os.environ.get("PATH", "")}
        result = subprocess.run([
            sys.executable, "-B", str(self.source / "install.py"), "minimax", "apply",
            "--home", str(self.home), "--surface", "desktop", "--runtime-version", "4.2.0",
        ], cwd=self.source, env=environment, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        state = json.loads((self.source / "ADAPTATION.minimax.json").read_text())
        self.assertEqual(state["target"]["version"], "4.2.0")
        result = subprocess.run([
            sys.executable, "-B", str(self.source / "install.py"), "minimax", "plan",
            "--home", str(self.home), "--surface", "cli",
        ], cwd=self.source, env=environment, capture_output=True, text=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("targets Desktop only", result.stderr)


class MiniMaxVersionTests(unittest.TestCase):
    def test_bundle_identity_and_version(self):
        with tempfile.TemporaryDirectory() as temporary:
            app = Path(temporary) / "MiniMax Code.app"
            (app / "Contents").mkdir(parents=True)
            with (app / "Contents/Info.plist").open("wb") as stream:
                plistlib.dump({"CFBundleIdentifier": "com.minimax.agent", "CFBundleShortVersionString": "3.0.71"}, stream)
            self.assertEqual(desktop_version(app), "3.0.71")
            with (app / "Contents/Info.plist").open("wb") as stream:
                plistlib.dump({"CFBundleIdentifier": "other", "CFBundleShortVersionString": "3.0.71"}, stream)
            with self.assertRaises(Conflict): desktop_version(app)


if __name__ == "__main__": unittest.main()
