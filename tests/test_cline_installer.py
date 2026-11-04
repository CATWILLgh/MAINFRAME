import json
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import tempfile
import unittest

from installer.cline import Cline, HOOK_NAMES, desktop_version, launcher
from installer.core import Conflict, transact


ROOT = Path(__file__).resolve().parents[1]


class ClineInstallerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources = tempfile.TemporaryDirectory(prefix="mainframe-cline-source-")
        cls.source = Path(cls.sources.name).resolve()
        for directory in ("instructions", "skills", "agents", "commands", "hooks", "plugins", "installer"):
            shutil.copytree(ROOT / directory, cls.source / directory, ignore=shutil.ignore_patterns("__pycache__"))
        for name in ("ADAPTATION.example.json", ".gitignore", "install.py"):
            shutil.copy2(ROOT / name, cls.source / name)
        (cls.source / "shared/credentials").mkdir(parents=True)
        for name in ("mainframe-secret", "credentials-index.template.md"):
            shutil.copy2(ROOT / "shared/credentials" / name, cls.source / "shared/credentials" / name)

    @classmethod
    def tearDownClass(cls):
        cls.sources.cleanup()

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="mainframe-cline-target-")
        self.addCleanup(self.temporary.cleanup)
        self.home = Path(self.temporary.name).resolve() / "home"
        self.home.mkdir()
        self.adapter = Cline(self.source, self.home, version="0.0.46", surface="desktop")
        for path in (self.adapter.state_path, self.adapter.index):
            path.unlink(missing_ok=True)
        self.addCleanup(self.adapter.clean_event_state)

    def install(self):
        changes, report = self.adapter.plan(instructions_reviewed=True)
        transact(changes, self.adapter.journal, self.adapter.allowed)
        self.adapter.clean_directories(self.adapter.receipt())
        return report

    def test_plan_is_read_only_apply_converges_and_modes_are_native(self):
        _, plan = self.adapter.plan(instructions_reviewed=True)
        self.assertTrue(plan["changes"])
        self.assertEqual(list(self.home.iterdir()), [])
        self.install()
        _, repeated = self.adapter.plan(instructions_reviewed=True)
        self.assertEqual(repeated["changes"], [])
        init_command = (self.adapter.workflows / "mainframe-tickets-init.md").read_text()
        self.assertIn("<!-- MAINFRAME ticket rules: begin -->", init_command)
        self.assertIn("<!-- MAINFRAME ticket entry: end -->", init_command)
        self.assertIn("execution: user-approved", init_command)
        self.assertFalse((self.home / "docs/tickets").exists())

        testing_source = ROOT / "skills/mainframe-testing"
        testing_delivered = (self.adapter.skills) / "mainframe-testing"
        for source in testing_source.rglob("*.md"):
            with self.subTest(testing_resource=str(source.relative_to(testing_source))):
                self.assertEqual(
                    (testing_delivered / source.relative_to(testing_source)).read_bytes(),
                    source.read_bytes(),
                )

        self.assertEqual(self.adapter.rules.stat().st_mode & 0o777, 0o600)
        self.assertEqual((self.adapter.hooks / "PreToolUse").stat().st_mode & 0o777, 0o755)
        self.assertEqual((self.adapter.hooks / "PostToolUse").stat().st_mode & 0o777, 0o755)
        self.assertEqual((self.adapter.hooks / "mainframe-cline-hook").stat().st_mode & 0o777, 0o700)
        self.assertIn(
            str(self.home / ".local/share/mainframe/runtime/bin"),
            (self.adapter.hooks / "PreToolUse").read_text(),
        )
        go_role = (self.adapter.agents / "mainframe-go-backend-engineer.yml").read_text()
        self.assertIn("skills: mainframe-go-backend", go_role)
        self.assertIn("server-side Go", go_role)
        state = json.loads(self.adapter.state_path.read_text())
        reminder = state["components"]["hooks"]["mainframe-skill-reminder"]
        self.assertEqual(reminder["delivery"], "installed")
        self.assertEqual(reminder["verification"], "pending")
        self.assertNotIn("reason", reminder)
        self.assertTrue((self.adapter.detectors / "mainframe-skill-reminder.py").exists())
        self.assertTrue(any("mainframe-skill-reminder" in path
                             for path in self.adapter.receipt()["files"]))
        self.assertNotIn("mainframe-skill-reminder", (self.adapter.hooks / "PreToolUse").read_text())
        self.assertNotIn("mainframe-skill-reminder", (self.adapter.hooks / "PostToolUse").read_text())
        self.assertEqual(state["target"]["version"], "0.0.46")
        self.assertEqual(
            sum(row["delivery"] == "unsupported" for row in state["components"]["hooks"].values()),
            3,
        )

    def test_launcher_is_silent_when_transport_or_python_is_unavailable(self):
        self.install()
        hook = self.adapter.hooks / "PreToolUse"
        transport = self.adapter.hooks / "mainframe-cline-hook"
        transport.unlink()
        result = subprocess.run([str(hook)], input="not json", text=True, capture_output=True)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))
        body = launcher("tool_call", "missing-transport").decode()
        self.assertIn('[ -f "$transport" ] || exit 0', body)

    def test_skill_only_delivery_ignores_unrelated_owned_edits(self):
        self.install()
        name = "mainframe-openspec"
        skill = self.adapter.skills / name / "SKILL.md"
        skill.unlink()
        self.adapter.rules.write_bytes(b"Unrelated user edit")
        changes, report = self.adapter.plan_skill(name)
        self.assertEqual({row["path"] for row in report["changes"]},
                         {str(skill), str(self.adapter.state_path)})
        transact(changes, self.adapter.journal, self.adapter.allowed)
        self.assertEqual(skill.read_bytes(), (self.source / "skills" / name / "SKILL.md").read_bytes())
        self.assertEqual(self.adapter.rules.read_bytes(), b"Unrelated user edit")
        self.assertEqual(self.adapter.plan_skill(name)[1]["changes"], [])

    def test_disable_is_per_identity_and_unknown_identity_is_rejected_first(self):
        self.install()
        changes = self.adapter.control(False, "mainframe-rg-short-replace")
        transact(changes, self.adapter.journal, self.adapter.allowed)
        self.assertTrue((self.adapter.hooks / ".disabled-mainframe-rg-short-replace").exists())
        self.assertFalse((self.adapter.hooks / ".disabled-mainframe-secret-access").exists())
        with self.assertRaisesRegex(Conflict, "Unknown maintained Cline hook"):
            self.adapter.control(True, "unknown")

    def test_uninstall_preserves_foreign_files_and_retained_index(self):
        self.install()
        foreign = self.adapter.cline / "user-owned.txt"
        foreign.write_text("keep\n")
        index = self.adapter.index.read_bytes()
        previous = self.adapter.receipt()
        owned = self.adapter.hooks / "mainframe-cline-hook"
        changes, _ = self.adapter.plan(instructions_reviewed=True, remove=True)
        transact(changes, self.adapter.journal, self.adapter.allowed)
        self.adapter.clean_directories(previous)
        self.assertEqual(foreign.read_text(), "keep\n")
        self.assertEqual(self.adapter.index.read_bytes(), index)
        self.assertFalse(owned.exists())
        self.assertFalse(self.adapter.receipt_path.exists())

    def test_owned_content_update_and_user_edit_conflict(self):
        self.install()
        source = self.source / "skills/mainframe-research/SKILL.md"
        original = source.read_bytes()
        self.addCleanup(source.write_bytes, original)
        source.write_bytes(original + b"\nFixture update.\n")
        changes, _ = self.adapter.plan(instructions_reviewed=True)
        self.assertTrue(any(change.path == self.adapter.skills / "mainframe-research/SKILL.md" for change in changes))
        target = self.adapter.skills / "mainframe-research/SKILL.md"
        target.write_bytes(target.read_bytes() + b"\nUser edit.\n")
        with self.assertRaisesRegex(Conflict, "Installed file was edited"):
            self.adapter.plan(instructions_reviewed=True)

    def test_desktop_version_reads_only_the_selected_bundle(self):
        app = Path(self.temporary.name) / "Cline.app"
        (app / "Contents").mkdir(parents=True)
        with (app / "Contents/Info.plist").open("wb") as stream:
            plistlib.dump({
                "CFBundleIdentifier": "bot.cline.app",
                "CFBundleShortVersionString": "0.0.33",
            }, stream)
        self.assertEqual(desktop_version(app), "0.0.33")
        with (app / "Contents/Info.plist").open("wb") as stream:
            plistlib.dump({"CFBundleIdentifier": "other.app", "CFBundleShortVersionString": "1"}, stream)
        with self.assertRaisesRegex(Conflict, "not Cline Desktop"):
            desktop_version(app)

    def test_desktop_refresh_rejects_older_release_but_removal_stays_available(self):
        self.install()
        self.adapter.version = "0.0.33"
        with self.assertRaisesRegex(Conflict, "Desktop 0.0.46"):
            self.adapter.plan(instructions_reviewed=True)
        self.assertTrue(self.adapter.control(False, "mainframe-todo-limits"))
        changes, _ = self.adapter.plan(instructions_reviewed=True, remove=True)
        self.assertTrue(changes)

    def test_desktop_plugin_is_private_owned_and_all_inventory_accounted(self):
        report = self.install()
        plugin = self.adapter.cline / "plugins/mainframe.js"
        self.assertTrue(plugin.is_file())
        self.assertIn('skip: true', plugin.read_text())
        self.assertIn('event=tool_call', (self.adapter.hooks / "PreToolUse").read_text())
        state = json.loads(self.adapter.state_path.read_text())
        rows = [row for group in state["components"].values() for row in group.values()]
        source = json.loads((self.source / "ADAPTATION.example.json").read_text())
        self.assertEqual(
            {category: set(entries) for category, entries in state["components"].items()},
            {category: set(entries) for category, entries in source["components"].items()},
        )
        self.assertTrue(all(row["delivery"] != "pending" for row in rows))
        self.assertEqual(state["components"]["hooks"]["mainframe-todo-limits"]["delivery"], "installed")
        selection = state["components"]["hooks"]["mainframe-subagent-selection"]
        self.assertEqual(selection["delivery"], "unsupported")
        self.assertIn("reasoning", selection["reason"])
        self.assertNotIn("mainframe-subagent-selection", report["retained_partial_bindings"])
        self.assertTrue(self.adapter.allowed(plugin))
        self.assertFalse(self.adapter.allowed(plugin.parent / "foreign.js"))
        self.assertIn(str(plugin), self.adapter.receipt()["files"])
        plugin.with_name("foreign.js").write_text("module.exports = {};\n")
        changes, _ = self.adapter.plan(instructions_reviewed=True, remove=True)
        transact(changes, self.adapter.journal, self.adapter.allowed)
        self.assertFalse(plugin.exists())
        self.assertTrue(plugin.with_name("foreign.js").exists())


if __name__ == "__main__":
    unittest.main()
