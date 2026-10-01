import json
from pathlib import Path
import plistlib
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest

from installer.antigravity import Antigravity, COMMAND_REASON, PARTIAL_HOOKS, desktop_version
from installer.core import Conflict, transact


ROOT = Path(__file__).resolve().parents[1]


class AntigravityInstallationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="mainframe-antigravity-install-")
        self.addCleanup(self.temporary.cleanup)
        base = Path(self.temporary.name).resolve()
        self.source = base / "source"
        self.source.mkdir()
        for name in ("instructions", "skills", "agents", "commands", "hooks", "installer"):
            shutil.copytree(ROOT / name, self.source / name, ignore=shutil.ignore_patterns("__pycache__"))
        for name in ("ADAPTATION.example.json", ".gitignore", "install.py"):
            shutil.copyfile(ROOT / name, self.source / name)
        credentials = self.source / "shared/credentials"
        credentials.mkdir(parents=True)
        for name in ("mainframe-secret", "credentials-index.template.md"):
            shutil.copyfile(ROOT / "shared/credentials" / name, credentials / name)
        self.home = base / "home with 'quotes'"
        self.home.mkdir()
        self.adapter = Antigravity(self.source, self.home, version="2.13.0")
        self.addCleanup(self.adapter.clean_event_state)

    def apply(self, reviewed=False):
        changes, report = self.adapter.plan(reviewed)
        self.assertIsNone(report["instruction_review"])
        transact(changes, self.adapter.journal, self.adapter.allowed)
        self.adapter.clean_directories(self.adapter.receipt())
        return report

    def test_fresh_delivery_converges_and_records_exact_limits(self):
        self.apply()
        _, report = self.adapter.plan()
        self.assertEqual(report["changes"], [])
        self.assertFalse(report["retiring_hooks"])
        state = json.loads(self.adapter.state_path.read_text())
        self.assertEqual(report["planned_delivery"], {"installed": 26, "pending": 0, "unsupported": 12})
        self.assertEqual(set(report["retained_partial_bindings"]), {
            "mainframe-init", "mainframe-project-skill", "mainframe-tickets-find", "mainframe-tickets-refine", "mainframe-tickets-implement",
            "mainframe-tickets-verify",
            *PARTIAL_HOOKS,
        })
        self.assertEqual(state["components"]["commands"]["mainframe-project-skill"]["reason"], COMMAND_REASON)
        self.assertEqual(state["components"]["hooks"]["mainframe-code-quality"]["delivery"], "unsupported")
        self.assertEqual(state["components"]["hooks"]["mainframe-secret-access"]["delivery"], "unsupported")
        command = (self.adapter.skills / "mainframe-project-skill/SKILL.md").read_text()
        self.assertIn("never select it autonomously", command)
        self.assertIn("Execute it only because the current invocation explicitly selected it", command)
        self.assertFalse((self.home / ".agents").exists())

    def test_native_layout_role_schema_and_post_event_hook_registration(self):
        self.apply()
        role = (self.adapter.agents / "mainframe-researcher.md").read_text()
        self.assertIn("mainAgent: false", role)
        self.assertIn("model: pro", role)
        self.assertIn("  - search_web", role)
        self.assertNotIn("write_to_file", role)
        backend = (self.adapter.agents / "mainframe-typescript-backend-engineer.md").read_text()
        self.assertIn("  - manage_task", backend)
        self.assertNotIn("list_permissions", backend)
        self.assertNotIn("ask_permission", backend)
        go_backend = (self.adapter.agents / "mainframe-go-backend-engineer.md").read_text()
        self.assertIn("mainframe-go-backend", go_backend)
        self.assertIn("  - manage_task", go_backend)
        hooks = self.adapter.desired_hooks()
        self.assertEqual(set(hooks), {"mainframe-adaptation"})
        self.assertEqual(set(hooks["mainframe-adaptation"]), {"PostInvocation", "Stop"})
        self.assertNotIn("PreToolUse", hooks["mainframe-adaptation"])
        analyzer_path = str((self.home / ".local/share/mainframe/runtime/bin").resolve())
        self.assertTrue(all(
            any(token == f"PATH={analyzer_path}:$PATH" for token in shlex.split(row["command"]))
            for rows in hooks["mainframe-adaptation"].values() for row in rows
        ))
        self.assertTrue(self.adapter.hooks_config.exists())
        self.assertEqual(set(json.loads(self.adapter.hooks_config.read_text())), {"mainframe-adaptation"})
        self.assertIn("pre-tool timing is unavailable",
                      self.adapter.plan()[1]["retained_partial_bindings"]["mainframe-rg-short-replace"])
        state = json.loads(self.adapter.state_path.read_text())
        self.assertEqual(state["components"]["hooks"]["mainframe-commit-checkpoint"]["delivery"], "installed")
        self.assertTrue(all(row["delivery"] == "unsupported" for name, row in state["components"]["hooks"].items()
                            if name != "mainframe-commit-checkpoint"))

    def test_user_instruction_and_foreign_hook_are_preserved_and_restored(self):
        self.adapter.instruction.parent.mkdir(parents=True)
        self.adapter.instruction.write_text("User instruction.\n")
        self.adapter.hooks_config.parent.mkdir(parents=True, exist_ok=True)
        foreign = {"foreign": {"enabled": False, "Stop": [{"command": "true"}]}}
        self.adapter.hooks_config.write_text(json.dumps(foreign))
        _, report = self.adapter.plan()
        self.assertIsNotNone(report["instruction_review"])
        self.apply(reviewed=True)
        self.assertLessEqual(len(self.adapter.instruction.read_text()), 12_000)
        self.assertTrue(self.adapter.instruction.read_text().startswith("User instruction.\n"))
        self.assertEqual(json.loads(self.adapter.hooks_config.read_text())["foreign"], foreign["foreign"])
        changes, _ = self.adapter.plan(remove=True)
        transact(changes, self.adapter.journal, self.adapter.allowed)
        self.assertEqual(self.adapter.instruction.read_text(), "User instruction.\n")
        self.assertEqual(json.loads(self.adapter.hooks_config.read_text()), foreign)

    def test_owned_edits_and_oversized_instruction_are_refused(self):
        self.apply()
        target = self.adapter.skills / "mainframe-research/SKILL.md"
        target.write_text(target.read_text() + "user edit\n")
        with self.assertRaisesRegex(Conflict, "was edited"):
            self.adapter.plan()
        target.write_bytes((self.source / "skills/mainframe-research/SKILL.md").read_bytes())
        receipt = json.loads(self.adapter.receipt_path.read_text())
        receipt["files"][str(target)]["sha256"] = __import__("hashlib").sha256(target.read_bytes()).hexdigest()
        self.adapter.receipt_path.write_text(json.dumps(receipt))
        self.adapter.instruction.write_text("x" * 12_001)
        with self.assertRaises(Conflict):
            self.adapter.plan()

    def test_hook_control_uses_component_disable_markers(self):
        self.apply()
        changes = self.adapter.control(False, "mainframe-secret-access")
        transact(changes, self.adapter.journal, self.adapter.allowed)
        self.assertTrue((self.adapter.hooks / ".disabled-mainframe-secret-access").exists())
        changes = self.adapter.control(True, "mainframe-secret-access")
        transact(changes, self.adapter.journal, self.adapter.allowed)
        self.assertFalse((self.adapter.hooks / ".disabled-mainframe-secret-access").exists())

    def test_update_preserves_disabled_state_across_hook_prefix_migration(self):
        self.apply()
        transact(
            self.adapter.control(False, "mainframe-secret-access"),
            self.adapter.journal,
            self.adapter.allowed,
        )
        current = self.adapter.hooks / ".disabled-mainframe-secret-access"
        legacy = self.adapter.hooks / ".disabled-secret-access"
        current.rename(legacy)
        receipt = json.loads(self.adapter.receipt_path.read_text())
        receipt["disabled_markers"] = {"secret-access": True}
        self.adapter.receipt_path.write_text(json.dumps(receipt))

        self.apply()
        self.assertFalse(legacy.exists())
        self.assertTrue(current.exists())
        self.assertEqual(
            self.adapter.receipt()["disabled_markers"],
            {"mainframe-secret-access": True},
        )

    def test_entrypoint_is_desktop_only_and_rejects_stale_runtime(self):
        result = subprocess.run([
            sys.executable, "-B", str(self.source / "install.py"), "antigravity", "apply",
            "--home", str(self.home), "--surface", "desktop", "--runtime-version", "2.12.2",
        ], cwd=self.source, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 2)
        self.assertIn("supported release is 2.13.0", result.stderr)
        result = subprocess.run([
            sys.executable, "-B", str(self.source / "install.py"), "antigravity", "plan",
            "--home", str(self.home), "--surface", "cli", "--runtime-version", "2.13.0",
        ], cwd=self.source, capture_output=True, text=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("applies only to Desktop", result.stderr)


class AntigravityVersionTests(unittest.TestCase):
    def test_bundle_identity_and_version(self):
        with tempfile.TemporaryDirectory() as temporary:
            app = Path(temporary) / "Antigravity.app"
            (app / "Contents").mkdir(parents=True)
            with (app / "Contents/Info.plist").open("wb") as stream:
                plistlib.dump({"CFBundleIdentifier": "com.google.antigravity",
                               "CFBundleShortVersionString": "2.13.0"}, stream)
            self.assertEqual(desktop_version(app), "2.13.0")
            with (app / "Contents/Info.plist").open("wb") as stream:
                plistlib.dump({"CFBundleIdentifier": "other", "CFBundleShortVersionString": "2.13.0"}, stream)
            with self.assertRaises(Conflict):
                desktop_version(app)


if __name__ == "__main__":
    unittest.main()
