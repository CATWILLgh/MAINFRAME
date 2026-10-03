import importlib.util
import json
import os
from pathlib import Path
import shutil
import shlex
import sqlite3
import subprocess
import sys
import tempfile
import tomllib
import unittest
from unittest.mock import patch

from installer.codex import (
    Codex,
    HOOK_NAMES,
    PRE_SHELL_TRANSPORT,
    SHELL_HOOK_NAMES,
    hook_command,
    merge_permission,
)
from installer.core import Change, Conflict, installation_lock, observed, restore, transact
from installer import core
from installer import codex
from installer.codex_native import summarize
from installer.runtime import runtime_bin

ROOT = Path(__file__).resolve().parents[1]


class InstallationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources = tempfile.TemporaryDirectory(prefix="mainframe-installer-source-")
        cls.source = Path(cls.sources.name).resolve()
        for directory in ("instructions", "skills", "agents", "commands", "hooks", "installer"):
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
        self.temporary = tempfile.TemporaryDirectory(prefix="mainframe-installer-target-")
        self.home = Path(self.temporary.name).resolve() / "home with 'quotes'"
        self.home.mkdir()
        self.adapter = Codex(self.source, self.home, version="0.153.4")
        for path in (self.adapter.state_path, self.adapter.index):
            path.unlink(missing_ok=True)
        self.addCleanup(self.temporary.cleanup)
        self.addCleanup(self.adapter.clean_event_state)

    def install(self):
        changes, report = self.adapter.plan(instructions_reviewed=True)
        transact(changes, self.adapter.journal, self.adapter.allowed)
        self.adapter.clean_directories(self.adapter.receipt())
        return report

    def invoke(self, name, command="pwd", event="PreToolUse", operation="operation", cached=None):
        data = {"hook_event_name": event, "tool_name": "Bash", "tool_input": {"command": command},
                "session_id": "synthetic-scope", "tool_use_id": operation}
        callback = cached or hook_command(self.adapter.hooks, name, self.adapter.event_state)
        return subprocess.run(["/bin/sh", "-c", callback], input=json.dumps(data),
                              text=True, capture_output=True, timeout=5)

    def invoke_payload(self, name, data, cached=None, timeout=10):
        callback = cached or hook_command(self.adapter.hooks, name, self.adapter.event_state)
        return subprocess.run(["/bin/sh", "-c", callback], input=json.dumps(data),
                              text=True, capture_output=True, timeout=timeout)

    def test_receipted_reminder_pilot_retires_without_foreign_loss(self):
        self.install()
        pilot = self.adapter.support / "experiments/skill-reminder"
        pilot.mkdir(parents=True)
        group = {"matcher": "^Bash$", "hooks": [{"type": "command", "command": str(pilot / "codex.py")}]}
        hook_path = self.adapter.codex / "hooks.json"
        hooks = json.loads(hook_path.read_text())
        foreign = {"matcher": "^Other$", "hooks": [{"type": "command", "command": "true"}]}
        hooks["hooks"]["PostToolUse"].extend([group, foreign])
        hook_path.write_text(json.dumps(hooks))
        (pilot / "receipt.json").write_text(json.dumps({"registration": group}))
        (pilot / "config.json").write_text(json.dumps({"disabled": False, "profiles": []}))
        (pilot / "codex.py").write_text("# preserve late-callback executable")
        self.install()
        after = json.loads(hook_path.read_text())["hooks"]["PostToolUse"]
        self.assertNotIn(group, after)
        self.assertIn(foreign, after)
        self.assertTrue(json.loads((pilot / "config.json").read_text())["disabled"])
        self.assertTrue((pilot / "codex.py").exists())
        self.assertEqual(self.adapter.plan()[1]["changes"], [])

    def test_skill_reminder_delivery_dispatch_disable_and_repeat(self):
        self.install()
        (self.home / "server").mkdir()
        path = self.home / "server/app.py"
        path.write_text("fixture")
        payload = {"hook_event_name": "PostToolUse", "tool_name": "Bash",
                   "session_id": "reminder-scope", "tool_use_id": "read",
                   "cwd": str(self.home), "tool_input": {"command": "cat " + shlex.quote(str(path))},
                   "tool_response": {"exit_code": 0}}
        result = self.invoke_payload("mainframe-skill-reminder", payload)
        self.assertEqual(result.returncode, 0)
        self.assertIn("mainframe-python-backend", result.stdout)
        self.assertNotIn("permissionDecision", result.stdout)
        self.assertEqual(self.invoke_payload("mainframe-skill-reminder", payload).stdout, "")
        (self.adapter.hooks / ".disabled-mainframe-skill-reminder").write_text("")
        payload["agent_id"] = "child"
        self.assertEqual(self.invoke_payload("mainframe-skill-reminder", payload).stdout, "")

    def test_plan_is_read_only_and_repeat_install_converges(self):
        _, report = self.adapter.plan()
        self.assertTrue(report["changes"])
        self.assertEqual(list(self.home.iterdir()), [])
        self.assertFalse(self.adapter.index.exists())
        self.install()
        _, repeated = self.adapter.plan()
        self.assertEqual(repeated["changes"], [])
        self.assertFalse(self.adapter.journal.exists())
        init_command = (self.adapter.skills / "mainframe-tickets-init/SKILL.md").read_text()
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

        state = json.loads(self.adapter.state_path.read_bytes())
        hooks = state["components"]["hooks"]
        self.assertEqual(sum(e["delivery"] == "unsupported" for e in hooks.values()), 4)
        self.assertTrue(all("verification" not in e for e in hooks.values() if e["delivery"] == "unsupported"))
        supported = [e for group in state["components"].values() for e in group.values()
                     if e["delivery"] != "unsupported"]
        self.assertTrue(all(e["delivery"] == "installed" for e in supported))
        self.assertTrue(all(e["verification"] == "pending" for e in supported))
        self.assertEqual(len(state["next_actions"]), 2)
        self.assertTrue(any("fresh Codex" in action for action in state["next_actions"]))
        self.assertIn(codex.READ_ONLY_ROLE_ACTION, state["next_actions"])
        self.assertEqual(self.adapter.receipt_path.stat().st_mode & 0o777, 0o600)
        native_hooks = json.loads((self.adapter.codex / "hooks.json").read_bytes())["hooks"]
        bash = [group for group in native_hooks["PreToolUse"] if group.get("matcher") == "^Bash$"]
        self.assertEqual(len(bash), 1)
        self.assertIn(PRE_SHELL_TRANSPORT, bash[0]["hooks"][0]["command"])
        self.assertEqual(
            shlex.split(bash[0]["hooks"][0]["command"])[-1], str(runtime_bin(self.home))
        )
        self.assertNotIn("additionalContextLimit", native_hooks["Stop"][0]["hooks"][0])
        self.assertEqual(native_hooks["PostToolUse"][0]["hooks"][0]["additionalContextLimit"], 6000)

    def test_resolved_fresh_session_handoff_stays_resolved_until_delivery_changes(self):
        self.install()
        state = json.loads(self.adapter.state_path.read_bytes())
        state["next_actions"] = [codex.READ_ONLY_ROLE_ACTION]
        state["components"]["instructions"]["global"]["verification"] = "passed"
        self.adapter.state_path.write_text(json.dumps(state, indent=2) + "\n")
        changes, report = self.adapter.plan(instructions_reviewed=True)
        self.assertEqual([change for change in changes if change.needed], [])
        self.assertEqual(report["changes"], [])

        body = self.source / "skills/mainframe-research/SKILL.md"
        original = body.read_bytes()
        try:
            body.write_bytes(original + b"\nA source update.\n")
            changes, _ = self.adapter.plan(instructions_reviewed=True)
            state_change = next(change for change in changes if change.path == self.adapter.state_path)
            changed_state = json.loads(state_change.after)
            self.assertTrue(any("fresh Codex" in action for action in changed_state["next_actions"]))
            self.assertEqual(
                changed_state["components"]["instructions"]["global"]["verification"],
                "pending",
            )
        finally:
            body.write_bytes(original)

    def test_updates_follow_canonical_content_and_keep_resources_binary(self):
        skill = self.source / "skills/mainframe-research"
        binary = skill / "fixture.bin"
        body = skill / "SKILL.md"
        original = body.read_bytes()
        binary.write_bytes(b"\x00\xffbinary\xfe")
        try:
            self.install()
            target = self.adapter.skills / "mainframe-research"
            self.assertEqual((target / "fixture.bin").read_bytes(), binary.read_bytes())
            body.write_bytes(original + b"\nA source update.\n")
            self.install()
            self.assertTrue((target / "SKILL.md").read_bytes().endswith(b"A source update.\n"))
            binary.unlink()
            self.install()
            self.assertFalse((target / "fixture.bin").exists())
        finally:
            body.write_bytes(original)
            binary.unlink(missing_ok=True)

    def test_shared_skills_migrate_to_private_home_and_converge(self):
        private = self.adapter.skills
        self.assertEqual(private, self.adapter.codex / "skills")
        legacy = self.home / ".agents/skills"
        self.adapter.skills = legacy
        self.install()
        foreign = legacy / "mainframe-research/user-note.txt"
        foreign.write_text("Preserve user material.")
        system = private / ".system/fixture/SKILL.md"
        system.parent.mkdir(parents=True)
        system.write_text("Preserve bundled skills.")
        old_hooks = (self.adapter.codex / "hooks.json").read_bytes()
        self.adapter.skills = private
        self.install()
        self.assertFalse((legacy / "mainframe-research/SKILL.md").exists())
        self.assertFalse((legacy / "mainframe-project-skill/SKILL.md").exists())
        self.assertFalse((legacy / "mainframe-project-skill").exists())
        self.assertTrue((private / "mainframe-project-skill/agents/openai.yaml").is_file())
        self.assertTrue((private / "mainframe-research/SKILL.md").is_file())
        self.assertEqual(foreign.read_text(), "Preserve user material.")
        self.assertEqual(system.read_text(), "Preserve bundled skills.")
        self.assertEqual((self.adapter.codex / "hooks.json").read_bytes(), old_hooks)
        role = (self.adapter.codex / "agents/mainframe-researcher.toml").read_text()
        self.assertIn(str(private / "mainframe-research/SKILL.md"), role)
        go_role = tomllib.loads(
            (self.adapter.codex / "agents/mainframe-go-backend-engineer.toml").read_text()
        )
        self.assertIn(str(private / "mainframe-go-backend/SKILL.md"), go_role["developer_instructions"])
        self.assertNotIn("sandbox_mode", go_role)
        _, report = self.adapter.plan()
        self.assertEqual(report["changes"], [])
        changes, _ = self.adapter.plan(remove=True)
        transact(changes, self.adapter.journal, self.adapter.allowed)
        self.assertFalse((private / "mainframe-project-skill/SKILL.md").exists())
        self.assertTrue(system.exists())
        self.assertTrue(foreign.exists())

    def test_cli_migration_prunes_only_empty_owned_shared_directories(self):
        private = self.adapter.skills
        legacy = self.home / ".agents/skills"
        self.adapter.skills = legacy
        self.install()
        foreign = legacy / "mainframe-research/user-note.txt"
        foreign.write_text("Preserve user material.")
        executable = self.home / "fake-codex"
        executable.write_text('#!/bin/sh\nprintf "codex-cli 0.153.4\\n"\n')
        executable.chmod(0o755)
        command = [sys.executable, "-B", str(self.source / "install.py"), "codex", "apply",
                   "--surface", "cli", "--home", str(self.home), "--executable", str(executable),
                   "--instructions-reviewed"]
        result = subprocess.run(command, cwd=self.source, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((legacy / "mainframe-project-skill").exists())
        self.assertTrue(foreign.exists())
        self.assertTrue((private / "mainframe-project-skill/SKILL.md").is_file())

    def test_shared_skill_customization_blocks_migration_before_writes(self):
        private = self.adapter.skills
        self.adapter.skills = self.home / ".agents/skills"
        self.install()
        old = self.adapter.skills / "mainframe-project-skill/SKILL.md"
        old.write_bytes(old.read_bytes() + b"\nUser customization.\n")
        receipt = self.adapter.receipt_path.read_bytes()
        self.adapter.skills = private
        with self.assertRaisesRegex(Conflict, "user changes"):
            self.install()
        self.assertFalse((private / "mainframe-project-skill/SKILL.md").exists())
        self.assertTrue(old.read_bytes().endswith(b"User customization.\n"))
        self.assertEqual(self.adapter.receipt_path.read_bytes(), receipt)

    def test_user_changes_block_before_other_files_change(self):
        self.install()
        target = self.adapter.skills / "mainframe-research/SKILL.md"
        target.write_bytes(target.read_bytes() + b"\nUser customization.\n")
        before = self.adapter.receipt_path.read_bytes()
        with self.assertRaisesRegex(Conflict, "was edited"):
            self.install()
        self.assertEqual(self.adapter.receipt_path.read_bytes(), before)
        self.assertTrue(target.read_bytes().endswith(b"User customization.\n"))

    def test_foreign_identical_file_is_reused_and_preserved_on_uninstall(self):
        target = self.adapter.skills / "mainframe-research/SKILL.md"
        target.parent.mkdir(parents=True)
        target.write_bytes((self.source / "skills/mainframe-research/SKILL.md").read_bytes())
        self.install()
        self.assertFalse(self.adapter.receipt()["files"][str(target)]["owned"])
        changes, _ = self.adapter.plan(remove=True)
        transact(changes, self.adapter.journal, self.adapter.allowed)
        self.assertTrue(target.exists())

    def test_missing_previously_reused_file_is_recreated_and_owned(self):
        target = self.adapter.skills / "mainframe-research/SKILL.md"
        target.parent.mkdir(parents=True)
        target.write_bytes((self.source / "skills/mainframe-research/SKILL.md").read_bytes())
        self.install()
        target.unlink()
        _, report = self.adapter.plan()
        self.assertIn({"action": "create", "path": str(target), "component": "skills.mainframe-research"}, report["changes"])
        self.install()
        self.assertEqual(target.read_bytes(), (self.source / "skills/mainframe-research/SKILL.md").read_bytes())
        self.assertTrue(self.adapter.receipt()["files"][str(target)]["owned"])
        self.assertEqual(self.adapter.plan()[1]["changes"], [])

    def test_global_settings_and_user_text_survive_update_and_uninstall(self):
        self.adapter.codex.mkdir(parents=True)
        instruction = self.adapter.codex / "AGENTS.md"
        config = self.adapter.codex / "config.toml"
        hook_path = self.adapter.codex / "hooks.json"
        instruction.write_bytes(b"User rule without a trailing newline")
        config.write_text('# User settings\nmodel = "chosen-model"\n[sandbox_workspace_write]\nwritable_roots = ["/user/project"]\n[features]\napps = true\n')
        user_hook = {"matcher": "^Bash$", "hooks": [{"type": "command", "command": "printf ''"}]}
        hook_path.write_text(json.dumps({"description": "User hooks", "hooks": {"PreToolUse": [user_hook]}}))
        _, report = self.adapter.plan()
        self.assertIsNotNone(report["instruction_review"])
        self.install()
        instruction.write_text("Additional user rule\n" + instruction.read_text())
        self.assertIsNotNone(self.adapter.plan()[1]["instruction_review"])
        self.install()
        state = tomllib.loads(config.read_text())
        self.assertEqual(state["sandbox_workspace_write"]["writable_roots"], ["/user/project", str(self.source / "docs/tickets/open/observations")])
        self.assertFalse((self.source / "docs/tickets/open/observations").exists())
        changes, _ = self.adapter.plan(remove=True)
        transact(changes, self.adapter.journal, self.adapter.allowed)
        self.assertEqual(instruction.read_bytes(), b"Additional user rule\nUser rule without a trailing newline")
        self.assertEqual(tomllib.loads(config.read_text())["sandbox_workspace_write"]["writable_roots"], ["/user/project"])
        self.assertIn("# User settings", config.read_text())
        self.assertEqual(json.loads(hook_path.read_bytes()), {"description": "User hooks", "hooks": {"PreToolUse": [user_hook]}})
        self.assertTrue(self.adapter.index.exists())
        self.assertFalse(self.adapter.receipt_path.exists())

    def test_missing_instruction_boundary_stops_before_other_writes(self):
        self.install()
        instruction = self.adapter.codex / "AGENTS.md"
        instruction.write_bytes((self.source / "instructions/global.md").read_bytes())
        receipt = self.adapter.receipt_path.read_bytes()
        skill = self.adapter.skills / "mainframe-research/SKILL.md"
        installed_skill = skill.read_bytes()
        with self.assertRaisesRegex(Conflict, "reconcile its ownership"):
            self.adapter.plan(instructions_reviewed=True)
        self.assertEqual(self.adapter.receipt_path.read_bytes(), receipt)
        self.assertEqual(skill.read_bytes(), installed_skill)

    def test_unchanged_hook_positions_survive_a_later_user_registration(self):
        self.install()
        path = self.adapter.codex / "hooks.json"
        hooks = json.loads(path.read_bytes())
        hooks["hooks"]["PreToolUse"].append({"hooks": [{"type": "command", "command": "printf ''"}]})
        path.write_text(json.dumps(hooks, indent=3))
        original = path.read_bytes()
        self.install()
        self.assertEqual(path.read_bytes(), original)
        self.assertEqual(len(self.adapter.receipt()["hook_groups"]["PreToolUse"]), 2)
        self.assertEqual(self.adapter.plan()[1]["changes"], [])
        changes, _ = self.adapter.plan(remove=True)
        transact(changes, self.adapter.journal, self.adapter.allowed)
        self.assertEqual(json.loads(path.read_bytes())["hooks"]["PreToolUse"], hooks["hooks"]["PreToolUse"][-1:])

    def test_global_override_is_the_only_instruction_target(self):
        self.adapter.codex.mkdir(parents=True)
        fallback = self.adapter.codex / "AGENTS.md"
        override = self.adapter.codex / "AGENTS.override.md"
        fallback.write_text("Shadowed user file\n")
        override.write_text("Effective user file\n")
        self.install()
        self.assertEqual(fallback.read_text(), "Shadowed user file\n")
        self.assertIn("MAINFRAME managed instructions", override.read_text())

    def test_symlink_and_foreign_content_are_not_replaced(self):
        destination = self.adapter.skills / "mainframe-research"
        destination.parent.mkdir(parents=True)
        outside = self.home / "user-directory"
        outside.mkdir()
        destination.symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(Conflict, "symlink"):
            self.install()
        self.assertEqual(list(outside.iterdir()), [])

    def test_hook_lifecycle_remains_neutral_after_all_owned_files_are_gone(self):
        self.install()
        cached = hook_command(self.adapter.hooks, "mainframe-secret-access", self.adapter.event_state)
        finding = self.invoke("mainframe-secret-access", "mainframe-secret get synthetic")
        self.assertEqual(finding.returncode, 0)
        self.assertEqual(json.loads(finding.stdout)["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertEqual(self.invoke("mainframe-secret-access").stdout, "")
        transact(self.adapter.control(False, None), self.adapter.journal, self.adapter.allowed)
        self.assertEqual(self.invoke("mainframe-secret-access", "mainframe-secret get synthetic").stdout, "")
        self.install()  # An update must preserve a deliberate disable.
        self.assertEqual(self.invoke("mainframe-secret-access", "mainframe-secret get synthetic").stdout, "")
        changes, _ = self.adapter.plan(remove=True)
        transact(changes, self.adapter.journal, self.adapter.allowed)
        for event in ("PreToolUse", "Stop"):
            for _ in range(2):
                result = self.invoke("mainframe-secret-access", "mainframe-secret get synthetic", event, cached=cached)
                self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))

    def test_update_preserves_disabled_state_across_hook_prefix_migration(self):
        self.install()
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

        changes, _ = self.adapter.plan()
        transact(changes, self.adapter.journal, self.adapter.allowed)
        self.assertFalse(legacy.exists())
        self.assertTrue(current.exists())
        self.assertEqual(
            self.adapter.receipt()["disabled_markers"],
            {"mainframe-secret-access": True},
        )

    def test_missing_implementation_and_interpreter_exit_two_are_neutral(self):
        self.install()
        bridge = self.adapter.hooks / "bridge.py"
        bridge.unlink()
        result = self.invoke("mainframe-secret-access", "mainframe-secret get synthetic")
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))
        bridge.write_text("raise SystemExit(2)\n")
        result = self.invoke("mainframe-secret-access", "mainframe-secret get synthetic", "Stop")
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))

    def test_rg_advisory_deduplicates_one_event_and_allows_a_new_event(self):
        self.install()
        first = self.invoke("mainframe-rg-short-replace", "rg -r beta alpha")
        self.assertIn("additionalContext", json.loads(first.stdout)["hookSpecificOutput"])
        self.assertEqual(self.invoke("mainframe-rg-short-replace", "rg -r beta alpha").stdout, "")
        self.assertTrue(self.invoke("mainframe-rg-short-replace", "rg -r beta alpha", operation="another").stdout)

    def test_composite_pre_shell_is_silent_and_retains_each_safe_effect(self):
        self.install()
        self.assertEqual(self.invoke(PRE_SHELL_TRANSPORT, "printf clean").stdout, "")

        denied = json.loads(
            self.invoke(PRE_SHELL_TRANSPORT, "mainframe-secret get synthetic").stdout
        )["hookSpecificOutput"]
        self.assertEqual(denied["permissionDecision"], "deny")

        destructive = json.loads(
            self.invoke(PRE_SHELL_TRANSPORT, "git reset --hard", operation="destructive").stdout
        )["hookSpecificOutput"]
        self.assertEqual(destructive["permissionDecision"], "deny")

        # The session cwd is not the Bash tool's actual workdir, so an ordinary
        # relative target must remain neutral rather than being misclassified.
        self.assertEqual(
            self.invoke(PRE_SHELL_TRANSPORT, "rm -rf .", operation="relative").stdout,
            "",
        )

        token = "ghp_0123456789abcdefghijklmnopqrstuvwxyz"
        commit = json.loads(
            self.invoke(
                PRE_SHELL_TRANSPORT,
                f"git commit -m {token}",
                operation="commit-metadata",
            ).stdout
        )["hookSpecificOutput"]
        self.assertEqual(commit["permissionDecision"], "deny")
        self.assertNotIn(token, commit["permissionDecisionReason"])

        advice = json.loads(
            self.invoke(
                PRE_SHELL_TRANSPORT,
                "rg -r replacement pattern .",
                operation="rg-advice",
            ).stdout
        )["hookSpecificOutput"]
        self.assertIn("additionalContext", advice)
        self.assertNotIn("permissionDecision", advice)

        mixed = json.loads(
            self.invoke(
                PRE_SHELL_TRANSPORT,
                "git reset --hard; rg -r replacement pattern .",
                operation="mixed",
            ).stdout
        )["hookSpecificOutput"]
        self.assertEqual(mixed["permissionDecision"], "deny")
        self.assertIn("additionalContext", mixed)

    def test_composite_pre_shell_honors_individual_disable_markers(self):
        self.install()
        (self.adapter.hooks / ".disabled-mainframe-rg-short-replace").touch()
        self.assertEqual(
            self.invoke(
                PRE_SHELL_TRANSPORT,
                "rg -r replacement pattern .",
                operation="disabled-rg",
            ).stdout,
            "",
        )
        secret = json.loads(
            self.invoke(
                PRE_SHELL_TRANSPORT,
                "mainframe-secret get synthetic",
                operation="enabled-secret",
            ).stdout
        )["hookSpecificOutput"]
        self.assertEqual(secret["permissionDecision"], "deny")

        for name in SHELL_HOOK_NAMES:
            (self.adapter.hooks / (".disabled-" + name)).touch(exist_ok=True)
        self.assertEqual(
            self.invoke(
                PRE_SHELL_TRANSPORT,
                "mainframe-secret get synthetic; rg -r replacement pattern .",
                operation="all-disabled",
            ).stdout,
            "",
        )

    def test_code_quality_tracks_patch_introduction_blocks_stop_and_releases(self):
        self.install()
        workspace = Path(self.temporary.name) / "quality-workspace"
        workspace.mkdir()
        source = workspace / "sample.go"
        source.write_text("package sample\n", encoding="utf-8")
        patch_text = "*** Begin Patch\n*** Update File: sample.go\n*** End Patch\n"

        def event(name, operation):
            return {
                "hook_event_name": name,
                "tool_name": "apply_patch",
                "tool_input": {"command": patch_text},
                "session_id": "quality-session",
                "tool_use_id": operation,
                "cwd": str(workspace),
            }

        self.assertEqual(self.invoke_payload("mainframe-code-quality", event("PreToolUse", "introduce")).stdout, "")
        source.write_text("package sample\n// TODO: finish behavior\n", encoding="utf-8")
        after = self.invoke_payload("mainframe-code-quality", event("PostToolUse", "introduce"))
        self.assertIn("TODO/FIXME/HACK/XXX", json.loads(after.stdout)["hookSpecificOutput"]["additionalContext"])
        stop = event("Stop", "stop-one")
        stop.pop("tool_name")
        stop.pop("tool_input")
        blocked = json.loads(self.invoke_payload("mainframe-code-quality", stop).stdout)
        self.assertEqual(blocked["decision"], "block")
        continued = {**stop, "stop_hook_active": True}
        self.assertEqual(self.invoke_payload("mainframe-code-quality", continued).stdout, "")

        self.assertEqual(self.invoke_payload("mainframe-code-quality", event("PreToolUse", "repair")).stdout, "")
        source.write_text("package sample\n", encoding="utf-8")
        self.assertEqual(self.invoke_payload("mainframe-code-quality", event("PostToolUse", "repair")).stdout, "")
        self.assertEqual(self.invoke_payload("mainframe-code-quality", stop).stdout, "")

    def test_permission_comments_are_preserved_for_a_bounded_handoff(self):
        raw = b'[sandbox_workspace_write]\nwritable_roots = [\n  "/user", # important user annotation\n]\n'
        result, _, note = merge_permission(raw, "/feedback", {})
        self.assertEqual(result, raw)
        self.assertIsNotNone(note)

    def test_failure_rolls_back_and_crash_can_be_recovered(self):
        changes, _ = self.adapter.plan()
        real_write = core.atomic_write
        calls = 0
        def fail_once(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 4:
                raise OSError("Synthetic disk failure")
            return real_write(*args, **kwargs)
        with patch.object(core, "atomic_write", side_effect=fail_once):
            with self.assertRaisesRegex(OSError, "Synthetic"):
                transact(changes, self.adapter.journal, self.adapter.allowed)
        self.assertFalse(self.adapter.receipt_path.exists())
        self.assertFalse(self.adapter.journal.exists())
        self.assertFalse(any(self.adapter.skills.rglob("SKILL.md")))
        calls = 0
        def interrupt_once(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 4:
                raise KeyboardInterrupt()
            return real_write(*args, **kwargs)
        with patch.object(core, "atomic_write", side_effect=interrupt_once):
            with self.assertRaises(KeyboardInterrupt):
                transact(changes, self.adapter.journal, self.adapter.allowed)
        self.assertTrue(self.adapter.journal.exists())
        restore(self.adapter.journal, self.adapter.allowed)
        self.assertFalse(self.adapter.journal.exists())
        self.assertFalse(any(self.adapter.skills.rglob("SKILL.md")))

    def test_target_changes_after_plan_are_preserved(self):
        changes, _ = self.adapter.plan()
        target = next(change.path for change in changes if change.component.startswith("skills."))
        target.parent.mkdir(parents=True)
        target.write_text("A concurrent user edit")
        with self.assertRaisesRegex(Conflict, "changed after planning"):
            transact(changes, self.adapter.journal, self.adapter.allowed)
        self.assertEqual(target.read_text(), "A concurrent user edit")
        self.assertFalse(self.adapter.receipt_path.exists())

    def test_merge_uses_the_snapshot_it_read_and_does_not_adopt_a_later_edit(self):
        self.adapter.codex.mkdir(parents=True)
        config = self.adapter.codex / "config.toml"
        config.write_text('model = "chosen-model"\n')
        real_merge = codex.merge_permission
        def edit_during_merge(*args):
            result = real_merge(*args)
            config.write_text(config.read_text() + '\n# A concurrent user change\n')
            return result
        with patch.object(codex, "merge_permission", side_effect=edit_during_merge):
            changes, _ = self.adapter.plan()
        with self.assertRaisesRegex(Conflict, "changed after planning"):
            transact(changes, self.adapter.journal, self.adapter.allowed)
        self.assertIn("# A concurrent user change", config.read_text())
        self.assertFalse(self.adapter.receipt_path.exists())

    def test_switching_source_roots_preserves_credential_metadata_and_rebinds_feedback(self):
        self.install()
        self.adapter.index.write_text("Synthetic credential description; no value.\n")
        moved = self.home.parent / "new-source"
        shutil.copytree(self.source, moved, ignore=shutil.ignore_patterns("ADAPTATION.codex.json", "credentials-index.md"))
        replacement = Codex(moved, self.home, version="0.153.4")
        changes, _ = replacement.plan(instructions_reviewed=True)
        transact(changes, replacement.journal, replacement.allowed)
        self.assertEqual(replacement.index.read_bytes(), self.adapter.index.read_bytes())
        roots = tomllib.loads((replacement.codex / "config.toml").read_text())["sandbox_workspace_write"]["writable_roots"]
        self.assertEqual(roots, [str(moved / "docs/tickets/open/observations")])
        self.assertEqual(replacement.plan()[1]["changes"], [])
        changes, _ = replacement.plan(remove=True)
        transact(changes, replacement.journal, replacement.allowed)
        self.assertTrue(self.adapter.index.exists())
        self.assertTrue(replacement.index.exists())

    def test_installation_lock_rejects_a_second_writer(self):
        with installation_lock(self.adapter.lock_path):
            with self.assertRaisesRegex(Conflict, "Another"):
                with installation_lock(self.adapter.lock_path):
                    self.fail("Second writer entered")

    def test_mode_change_after_planning_is_a_preserved_concurrent_edit(self):
        self.install()
        path = self.adapter.hooks / "bridge.py"
        change = Change.to(path, b"a proposed replacement")
        path.chmod(0o400)
        with self.assertRaisesRegex(Conflict, "changed after planning"):
            transact([change], self.adapter.journal, self.adapter.allowed)
        self.assertEqual(path.stat().st_mode & 0o777, 0o400)

    def test_recovery_preserves_concurrent_edits_and_the_recovery_pointer(self):
        path = self.adapter.hooks / "bridge.py"
        original = core.atomic_write
        def interrupt_receipt(target, *args, **kwargs):
            if target == self.adapter.receipt_path:
                raise KeyboardInterrupt()
            return original(target, *args, **kwargs)
        changes = [Change.to(path, b"owned implementation"), Change.to(self.adapter.receipt_path, b"{}")]
        with patch.object(core, "atomic_write", side_effect=interrupt_receipt):
            with self.assertRaises(KeyboardInterrupt):
                transact(changes, self.adapter.journal, self.adapter.allowed)
        path.write_bytes(b"concurrent user correction")
        with self.assertRaisesRegex(Conflict, "Concurrent change"):
            restore(self.adapter.journal, self.adapter.allowed)
        self.assertEqual(path.read_bytes(), b"concurrent user correction")
        self.assertTrue(self.adapter.journal.exists())

    def test_native_discovery_rejects_the_wrong_scope_and_an_empty_catalog(self):
        source = json.loads((self.source / "ADAPTATION.example.json").read_bytes())
        cwd = self.home / "isolated"
        skills = {"data": [{"cwd": str(cwd), "skills": []}]}
        hooks = {"data": [{"cwd": str(cwd), "hooks": []}]}
        result = summarize(self.adapter, source, skills, hooks, cwd)
        self.assertTrue(all(not row["discovered"] for group in ("skills", "commands", "hooks") for row in result[group].values()))
        hooks["data"][0]["cwd"] = str(self.source)
        with self.assertRaisesRegex(Conflict, "requested isolated scope"):
            summarize(self.adapter, source, skills, hooks, cwd)

    def test_native_discovery_rejects_a_wrong_source_or_duplicate_identity(self):
        source = json.loads((self.source / "ADAPTATION.example.json").read_bytes())
        cwd = self.home / "isolated"
        skill = {"name": "mainframe-research", "enabled": True, "path": str(self.adapter.skills / "mainframe-research/SKILL.md")}
        skills = {"data": [{"cwd": str(cwd), "skills": [skill, skill]}]}
        hook = {"command": hook_command(self.adapter.hooks, "mainframe-secret-access", self.adapter.event_state),
                "eventName": "preToolUse", "matcher": "^Bash$", "enabled": True, "trustStatus": "trusted",
                "sourcePath": "/unrelated/hooks.json", "source": "project", "handlerType": "command",
                "timeoutSec": 5, "additionalContextLimit": 6000}
        hooks = {"data": [{"cwd": str(cwd), "hooks": [hook]}]}
        result = summarize(self.adapter, source, skills, hooks, cwd)
        self.assertFalse(result["skills"]["mainframe-research"]["discovered"])
        self.assertFalse(result["hooks"]["mainframe-secret-access"]["discovered"])

    def test_native_discovery_recognizes_post_tool_advisories(self):
        source = json.loads((self.source / "ADAPTATION.example.json").read_bytes())
        cwd = self.home / "isolated"
        hooks = []
        for name, matcher, timeout, limit in (
            ("mainframe-skill-reminder", "^Bash$", 2, 300),
            ("mainframe-commit-checkpoint", "^apply_patch$", 5, 1000),
        ):
            hooks.append({"command": hook_command(self.adapter.hooks, name, self.adapter.event_state),
                          "eventName": "postToolUse", "matcher": matcher,
                          "timeoutSec": timeout, "additionalContextLimit": limit,
                          "enabled": True, "trustStatus": "trusted", "handlerType": "command",
                          "source": "user", "sourcePath": str(self.adapter.codex / "hooks.json")})
        result = summarize(self.adapter, source, {"data": [{"cwd": str(cwd), "skills": []}]},
                           {"data": [{"cwd": str(cwd), "hooks": hooks}]}, cwd)
        for name in ("mainframe-skill-reminder", "mainframe-commit-checkpoint"):
            self.assertTrue(result["hooks"][name]["discovered"], name)
            self.assertTrue(result["hooks"][name]["trusted"], name)

    def test_cli_requires_instruction_review_before_applying(self):
        self.adapter.codex.mkdir(parents=True)
        (self.adapter.codex / "AGENTS.md").write_text("User instruction")
        executable = self.home / "fake-codex"
        executable.write_text('#!/bin/sh\nprintf "codex-cli 0.153.4\\n"\n')
        executable.chmod(0o755)
        command = [sys.executable, "-B", str(self.source / "install.py"), "codex", "apply", "--surface", "cli", "--home", str(self.home), "--executable", str(executable)]
        result = subprocess.run(command, cwd=self.source, text=True, capture_output=True)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("instructions-reviewed", result.stderr)
        self.assertFalse(self.adapter.receipt_path.exists())
        result = subprocess.run(command + ["--instructions-reviewed"], cwd=self.source, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(self.adapter.receipt_path.exists())
        verify = command.copy()
        verify[verify.index("apply")] = "verify"
        result = subprocess.run(verify, cwd=self.source, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["file_change_count"], 0)

    def test_desktop_installs_without_invoking_a_codex_executable(self):
        executable = self.home / "codex"
        executable.write_text('#!/bin/sh\nprintf called > "$0.called"\nprintf "codex-cli 0.147.0\\n"\n')
        executable.chmod(0o755)
        environment = dict(os.environ, PATH=str(self.home) + os.pathsep + os.environ.get("PATH", ""))
        base = [sys.executable, "-B", str(self.source / "install.py"), "codex"]
        options = ["--surface", "desktop", "--runtime-version", "0.153.4", "--home", str(self.home)]
        for action in ("plan", "apply", "verify"):
            with self.subTest(action=action):
                result = subprocess.run(base + [action] + options + ["--instructions-reviewed"],
                    cwd=self.source, env=environment, text=True, capture_output=True, timeout=15)
                self.assertEqual(result.returncode, 0, result.stderr)
                report = json.loads(result.stdout)
                self.assertEqual(report["surface"], "desktop")
                self.assertEqual(report["runtime_version"], "0.153.4")
                if action == "plan":
                    self.assertFalse(self.adapter.receipt_path.exists())
                elif action == "verify":
                    self.assertTrue(report["structure_matches"])
                    self.assertEqual(report["file_change_count"], 0)
        self.assertFalse(Path(str(executable) + ".called").exists())
        self.assertEqual(json.loads(self.adapter.state_path.read_bytes())["target"]["surface"], "desktop")

    def test_surface_errors_and_unknown_desktop_runtime_fail_before_writes(self):
        base = [sys.executable, "-B", str(self.source / "install.py"), "codex"]
        cases = [
            ("apply", [], "--surface"),
            ("apply", ["--surface", "desktop"], "--runtime-version"),
            ("verify", ["--surface", "desktop", "--native"], "does not launch"),
            ("apply", ["--surface", "desktop", "--executable", "/nonexistent/codex"], "does not launch"),
            ("apply", ["--surface", "cli", "--runtime-version", "0.153.4"], "applies only to Desktop"),
            ("apply", ["--surface", "desktop", "--runtime-version", "0.147.0"], "inspected Codex mapping"),
            ("apply", ["--surface", "desktop", "--runtime-version", "0.159.3"], "inspected Codex mapping"),
        ]
        for action, options, error in cases:
            with self.subTest(action=action, options=options):
                result = subprocess.run(base + [action, "--home", str(self.home)] + options,
                    cwd=self.source, text=True, capture_output=True, timeout=15)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn(error, result.stderr)
                self.assertFalse(self.adapter.receipt_path.exists())
                self.assertFalse(self.adapter.state_path.exists())
                self.assertEqual(list(self.home.iterdir()), [])

    def test_current_desktop_mapping_delivers_complete_skills_and_converges(self):
        executable = self.home / "codex"
        executable.write_text('#!/bin/sh\nprintf called > "$0.called"\n')
        executable.chmod(0o755)
        environment = dict(os.environ, PATH=str(self.home) + os.pathsep + os.environ.get("PATH", ""))
        base = [sys.executable, "-B", str(self.source / "install.py"), "codex"]
        options = ["--surface", "desktop", "--runtime-version", "0.159.2",
                   "--home", str(self.home), "--instructions-reviewed"]
        for action in ("plan", "apply", "verify"):
            result = subprocess.run(base + [action] + options, cwd=self.source,
                env=environment, text=True, capture_output=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["runtime_version"], "0.159.2")
            if action == "verify":
                self.assertTrue(report["structure_matches"])
                self.assertEqual(report["file_change_count"], 0)
        for source in (self.source / "skills/mainframe-clickhouse").rglob("*"):
            if source.is_file():
                installed = self.adapter.skills / "mainframe-clickhouse" / source.relative_to(self.source / "skills/mainframe-clickhouse")
                self.assertEqual(installed.read_bytes(), source.read_bytes())
        state = json.loads(self.adapter.state_path.read_bytes())
        self.assertEqual(state["components"]["skills"]["mainframe-clickhouse"]["delivery"], "installed")
        self.assertEqual(state["components"]["skills"]["mainframe-clickhouse"]["verification"], "pending")
        self.assertTrue(all(state["components"]["hooks"][name]["delivery"] == "unsupported"
                            for name in codex.LIMITATIONS))
        self.assertFalse(Path(str(executable) + ".called").exists())

    def test_current_mapping_does_not_authorize_an_uninspected_cli(self):
        executable = self.home / "fake-codex"
        executable.write_text('#!/bin/sh\nprintf "codex-cli 0.159.2\\n"\n')
        executable.chmod(0o755)
        result = subprocess.run([sys.executable, "-B", str(self.source / "install.py"),
            "codex", "apply", "--surface", "cli", "--home", str(self.home),
            "--executable", str(executable), "--instructions-reviewed"],
            cwd=self.source, text=True, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 2)
        self.assertIn("inspected Codex mapping", result.stderr)
        self.assertFalse(self.adapter.receipt_path.exists())
        self.assertFalse(self.adapter.state_path.exists())

    def test_desktop_reads_only_current_task_version_and_rejects_a_conflicting_override(self):
        self.assertIsNone(codex.desktop_version(self.adapter.codex, "current-task"))
        self.assertFalse(self.adapter.codex.exists())
        self.adapter.codex.mkdir()
        database = self.adapter.codex / "state_5.sqlite"
        connection = sqlite3.connect(database)
        connection.execute('CREATE TABLE threads (id TEXT PRIMARY KEY, cli_version TEXT)')
        connection.executemany('INSERT INTO threads VALUES (?, ?)', [("current-task", "0.153.4"), ("unrelated-task", "9.9.9")])
        connection.commit()
        connection.close()
        before = database.read_bytes()
        self.assertEqual(codex.desktop_version(self.adapter.codex, "current-task"), "0.153.4")
        self.assertIsNone(codex.desktop_version(self.adapter.codex, "missing-task"))
        self.assertIsNone(codex.desktop_version(self.adapter.codex, None))
        environment = dict(os.environ, CODEX_THREAD_ID="current-task")
        command = [sys.executable, "-B", str(self.source / "install.py"), "codex", "plan",
                   "--surface", "desktop", "--home", str(self.home)]
        result = subprocess.run(command, cwd=self.source, env=environment, text=True, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["runtime_version"], "0.153.4")
        result = subprocess.run(command + ["--runtime-version", "0.147.0"], cwd=self.source,
                                env=environment, text=True, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("conflicts with", result.stderr)
        self.assertFalse(self.adapter.receipt_path.exists())
        self.assertEqual(database.read_bytes(), before)

    def test_desktop_prerelease_metadata_preserves_identity_and_override_guard(self):
        self.adapter.codex.mkdir()
        database = self.adapter.codex / "state_5.sqlite"
        with sqlite3.connect(database) as connection:
            connection.execute('CREATE TABLE threads (id TEXT PRIMARY KEY, cli_version TEXT)')
            connection.execute('INSERT INTO threads VALUES (?, ?)', ("current-task", "0.154.0-alpha.6.2"))
        connection.close()
        self.assertEqual(codex.desktop_version(self.adapter.codex, "current-task"), "0.154.0-alpha.6.2")
        result = subprocess.run([sys.executable, "-B", str(self.source / "install.py"), "codex", "apply",
            "--surface", "desktop", "--runtime-version", "0.153.4", "--home", str(self.home)],
            cwd=self.source, env=dict(os.environ, CODEX_THREAD_ID="current-task"),
            text=True, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 2)
        self.assertIn("conflicts with", result.stderr)
        self.assertFalse(self.adapter.receipt_path.exists())

    def test_prerelease_content_update_converges_without_touching_native_bindings(self):
        self.adapter.surface = "desktop"
        self.install()
        protected = [self.adapter.codex / "hooks.json", self.adapter.codex / "config.toml",
                     self.adapter.hooks / "bridge.py", self.home / ".local/bin/mainframe-secret"]
        before = {path: observed(path) for path in protected}
        updated_sources = [
            "instructions/global.md",
            "skills/mainframe-research/SKILL.md",
            "skills/mainframe-research/references/software-documentation.md",
            "commands/mainframe-tickets-verify.md",
            "agents/mainframe-researcher.md",
        ]
        marker = b"\nA fixture-only content update.\n"
        for relative in updated_sources:
            source = self.source / relative
            original = source.read_bytes()
            self.addCleanup(source.write_bytes, original)
            source.write_bytes(original + marker)
        options = ["--surface", "desktop", "--runtime-version", "0.154.0-alpha.6.2",
                   "--home", str(self.home), "--instructions-reviewed"]
        for action in ("plan", "apply", "verify"):
            result = subprocess.run([sys.executable, "-B", str(self.source / "install.py"), "codex", action] + options,
                cwd=self.source, text=True, capture_output=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertIn("bounded update", report["delivery_mode"])
            if action == "verify":
                self.assertEqual(report["file_change_count"], 0)
                self.assertTrue(report["structure_matches"])
        self.assertEqual(before, {path: observed(path) for path in protected})
        for path in (self.adapter.codex / "AGENTS.md", self.adapter.skills / "mainframe-research/SKILL.md",
                     self.adapter.skills / "mainframe-research/references/software-documentation.md",
                     self.adapter.skills / "mainframe-tickets-verify/SKILL.md"):
            self.assertIn(marker.strip(), path.read_bytes())
        role = tomllib.loads((self.adapter.codex / "agents/mainframe-researcher.toml").read_text())
        self.assertIn(marker.decode().strip(), role["developer_instructions"])
        self.assertEqual(role["sandbox_mode"], "read-only")
        state = json.loads(self.adapter.state_path.read_bytes())
        self.assertEqual(state["target"]["version"], "0.154.0-alpha.6.2")
        for name in codex.LIMITATIONS:
            row = state["components"]["hooks"][name]
            self.assertEqual((row["delivery"], row["verification"]), ("pending", "pending"))

    def test_prerelease_repairs_only_the_owned_stop_context_limit(self):
        self.adapter.surface = "desktop"
        self.install()
        hook_path = self.adapter.codex / "hooks.json"
        hooks = json.loads(hook_path.read_bytes())
        hooks["hooks"]["Stop"][0]["hooks"][0]["additionalContextLimit"] = 6000
        hook_path.write_bytes(json.dumps(hooks, indent=2).encode() + b"\n")
        receipt = self.adapter.receipt()
        receipt["hook_groups"]["Stop"][0]["hooks"][0]["additionalContextLimit"] = 6000
        self.adapter.receipt_path.write_bytes(json.dumps(receipt, indent=2).encode() + b"\n")
        self.adapter.version = "0.154.0-alpha.6.2"

        changes, _ = self.adapter.plan(instructions_reviewed=True)
        registration = next(change for change in changes if change.component == "hook registration")
        self.assertTrue(registration.needed)
        self.adapter.validate_content_update(changes, receipt)
        repaired = json.loads(registration.after)
        self.assertNotIn("additionalContextLimit", repaired["hooks"]["Stop"][0]["hooks"][0])

        unrelated = json.loads(registration.after)
        unrelated["hooks"]["Stop"][0]["hooks"][0]["timeout"] = 181
        bad = Change.from_snapshot(
            hook_path, observed(hook_path), json.dumps(unrelated).encode() + b"\n",
            mode=hook_path.stat().st_mode & 0o777, component="hook registration",
        )
        with self.assertRaises(Conflict):
            self.adapter.validate_content_update([bad], receipt)

    def test_prerelease_upgrades_only_owned_hook_commands_to_managed_runtime(self):
        self.adapter.surface = "desktop"
        self.install()
        hook_path = self.adapter.codex / "hooks.json"
        hooks = json.loads(hook_path.read_bytes())
        receipt = self.adapter.receipt()
        replacements = {
            codex.hook_command(
                self.adapter.hooks, transport, self.adapter.event_state,
                runtime_bin(self.home),
            ): codex._legacy_hook_command(
                self.adapter.hooks, transport, self.adapter.event_state,
            )
            for transport in (codex.PRE_SHELL_TRANSPORT, "mainframe-code-quality")
        }
        for source in (hooks["hooks"], receipt["hook_groups"]):
            for groups in source.values():
                for group in groups:
                    for handler in group["hooks"]:
                        if handler.get("command") in replacements:
                            handler["command"] = replacements[handler["command"]]
        hook_path.write_bytes(json.dumps(hooks, indent=2).encode() + b"\n")
        self.adapter.receipt_path.write_bytes(json.dumps(receipt, indent=2).encode() + b"\n")
        self.adapter.version = "0.154.0-alpha.6.2"

        changes, _ = self.adapter.plan(instructions_reviewed=True)
        registration = next(change for change in changes if change.component == "hook registration")
        self.adapter.validate_content_update(changes, receipt)
        upgraded = json.loads(registration.after)
        commands = {
            handler["command"]
            for groups in upgraded["hooks"].values()
            for group in groups for handler in group["hooks"]
        }
        self.assertTrue(commands.isdisjoint(replacements.values()))
        self.assertTrue(set(replacements).issubset(commands))

    def test_content_update_rejects_packaging_and_permission_changes(self):
        self.adapter.surface = "desktop"
        self.install()
        self.adapter.version = "0.154.0-alpha.6.2"
        previous = self.adapter.receipt()
        skill = self.adapter.skills / "mainframe-research/SKILL.md"
        original = skill.read_bytes()
        description_edit = original.replace(b"description:", b"description: Revised", 1)
        def update(path, data, component):
            return Change.to(path, data, mode=path.stat().st_mode & 0o777, component=component)
        allowed = update(skill, description_edit, "skills.mainframe-research")
        self.adapter.validate_content_update([allowed], previous)
        candidates = [
            update(skill, original.replace(b"name: mainframe-research", b"name: different"), "skills.mainframe-research"),
            update(skill, None, "skills.mainframe-research"),
            Change.to(skill, description_edit, mode=0o755, component="skills.mainframe-research"),
            Change.to(skill.parent / "new.md", b"new", component="skills.mainframe-research"),
            update(self.adapter.hooks / "bridge.py", b"changed", "hook transport"),
            update(self.adapter.codex / "config.toml", b"changed", "feedback permission"),
            update(self.adapter.skills / "mainframe-tickets-verify/agents/openai.yaml", b"policy: changed", "commands.mainframe-tickets-verify"),
        ]
        role = self.adapter.codex / "agents/mainframe-researcher.toml"
        candidates.append(update(role, role.read_bytes().replace(b'read-only', b'danger-full-access'), "agents.mainframe-researcher"))
        for change in candidates:
            with self.subTest(path=change.path, mode=change.mode):
                with self.assertRaises(Conflict):
                    self.adapter.validate_content_update([change], previous)
        self.assertEqual(skill.read_bytes(), original)
        for receipt in ({}, dict(previous, source="/different-source")):
            with self.assertRaises(Conflict):
                self.adapter.validate_content_update([allowed], receipt)
        self.adapter.surface = "cli"
        with self.assertRaises(Conflict):
            self.adapter.validate_content_update([allowed], previous)

    def test_prerelease_fresh_install_is_refused_before_writes(self):
        result = subprocess.run([sys.executable, "-B", str(self.source / "install.py"), "codex", "apply",
            "--surface", "desktop", "--runtime-version", "0.154.0-alpha.6.2", "--home", str(self.home),
            "--instructions-reviewed"], cwd=self.source, text=True, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 2)
        self.assertIn("existing same-source", result.stderr)
        self.assertFalse(self.adapter.receipt_path.exists())
        self.assertFalse(self.adapter.state_path.exists())
        self.assertFalse((self.adapter.codex / "hooks.json").exists())

    def test_changing_surface_does_not_reuse_the_other_surfaces_acceptance(self):
        self.adapter.surface = "cli"
        self.install()
        state = json.loads(self.adapter.state_path.read_bytes())
        state["components"]["skills"]["mainframe-research"].update(
            delivery="installed", verification="passed", reason="Synthetic CLI-only proof"
        )
        self.adapter.state_path.write_text(json.dumps(state))
        desktop = Codex(self.source, self.home, version="0.153.4", surface="desktop")
        changes, _ = desktop.plan(instructions_reviewed=True)
        self.assertEqual([change.component for change in changes if change.needed], ["adaptation state"])
        transact(changes, desktop.journal, desktop.allowed)
        state = json.loads(desktop.state_path.read_bytes())
        self.assertEqual(state["target"]["surface"], "desktop")
        row = state["components"]["skills"]["mainframe-research"]
        self.assertEqual(row["delivery"], "installed")
        self.assertEqual(row["verification"], "pending")
        self.assertNotIn("reason", row)

    def test_schema_one_state_migrates_without_trusting_old_delivery(self):
        self.adapter.surface = "cli"
        self.install()
        state = json.loads(self.adapter.state_path.read_bytes())
        old = {
            "schema_version": 1,
            "status_values": ["pending", "installed", "unsupported"],
            "target": state["target"],
            "components": {},
        }
        shared_note = "Packaging prepared; record current-surface discovery and reusable adapter evidence."
        for category, group in state["components"].items():
            old["components"][category] = {}
            for name, row in group.items():
                status = "unsupported" if row["delivery"] == "unsupported" else "pending"
                note = row.get("reason", shared_note)
                old["components"][category][name] = {
                    "source": row["source"], "status": status, "note": note,
                }
        old["components"]["skills"]["mainframe-research"].update(
            status="installed", note="Exact skill loaded on this CLI surface."
        )
        self.adapter.state_path.write_text(json.dumps(old))

        changes, _ = self.adapter.plan(instructions_reviewed=True)
        self.assertEqual([change.component for change in changes if change.needed], ["adaptation state"])
        transact(changes, self.adapter.journal, self.adapter.allowed)
        migrated = json.loads(self.adapter.state_path.read_bytes())
        row = migrated["components"]["skills"]["mainframe-research"]
        self.assertEqual((row["delivery"], row["verification"]), ("installed", "passed"))
        self.assertNotIn("reason", row)
        self.assertNotIn("status_values", migrated)
        self.assertFalse(any(
            "status" in row or "note" in row
            for group in migrated["components"].values() for row in group.values()
        ))
        unsupported = migrated["components"]["hooks"]["mainframe-code-quality"]
        self.assertEqual(unsupported["delivery"], "unsupported")
        self.assertNotIn("verification", unsupported)

    def test_cli_uninstall_needs_no_runtime_and_cached_callbacks_stay_neutral(self):
        self.install()
        cached = hook_command(self.adapter.hooks, "mainframe-secret-access", self.adapter.event_state)
        result = subprocess.run([sys.executable, "-B", str(self.source / "install.py"), "codex", "uninstall",
            "--home", str(self.home), "--executable", "/nonexistent/codex"], cwd=self.source,
            text=True, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.adapter.receipt_path.exists())
        result = self.invoke("mainframe-secret-access", "mainframe-secret get synthetic", "Stop", cached=cached)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))


if __name__ == "__main__":
    unittest.main()
