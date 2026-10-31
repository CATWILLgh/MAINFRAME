"""Scoped Codex backlog delivery and native pre-edit transport."""

import io
import json
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from installer import codex_hook
from installer.codex import Codex, _legacy_hook_command, hook_command, merge_hooks
from installer.core import Conflict, digest, encode_json, observed, transact


class TodoCodexTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="mainframe-todo-codex-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve() / "source"
        self.home = Path(temporary.name).resolve() / "home"
        self.root.mkdir()
        for directory in ("commands", "hooks"):
            (self.root / directory).mkdir()
        (self.root / "commands/todo.md").write_text("# Capture a todo\n\nUse the caller's prose.\n")
        (self.root / "hooks/mainframe-todo-limits.py").write_text("def check_patch(workspace, patch):\n    return 'bounded denial'\n")
        self.source = {"components": {
            "commands": {"todo": {"source": "commands/todo.md"}},
            "hooks": {"mainframe-todo-limits": {"source": "hooks/mainframe-todo-limits.py"}},
        }}
        self.adapter = Codex(self.root, self.home, version="0.165.0-alpha.1.2", surface="desktop")
        self.adapter.hooks.mkdir(parents=True)
        bridge = self.adapter.hooks / "bridge.py"
        bridge.write_bytes(b"# previous owned transport\n")
        foreign = {"matcher": "^Foreign$", "hooks": [{"type": "command", "command": "true"}]}
        self.hooks = {"description": "preserve metadata", "hooks": {"PreToolUse": [foreign], "Stop": []}}
        (self.adapter.codex / "hooks.json").write_bytes(encode_json(self.hooks))
        receipt = {"version": 1, "target": str(self.adapter.codex), "source": str(self.root),
                   "files": {str(bridge): {"component": "hook transport", "sha256": digest(bridge.read_bytes()),
                                          "mode": 0o644, "owned": True, "retain": False}},
                   "hook_groups": {"PreToolUse": [foreign]}, "directories": [],
                   "fingerprint": "previous fingerprint", "disabled_markers": {"unrelated": "preserve"}}
        self.adapter.receipt_path.write_bytes(encode_json(receipt))
        self.state = {"schema_version": 2, "target": {"config_home": str(self.adapter.codex),
                       "mainframe_root": str(self.root)}, "components": {"commands": {}, "hooks": {},
                       "skills": {"unrelated": {"verification": "passed"}}}, "next_actions": ["preserve"]}
        self.adapter.state_path.write_bytes(encode_json(self.state))
        self.addCleanup(self.adapter.clean_event_state)
        self.inventory = patch("installer.codex.inventory", return_value=self.source)
        self.inventory.start()
        self.addCleanup(self.inventory.stop)

    def apply_todo(self):
        changes, report = self.adapter.plan_todo()
        transact(changes, self.adapter.journal, self.adapter.allowed)
        return report

    def test_scoped_delivery_preserves_unrelated_state_and_converges(self):
        bridge_mode = (self.adapter.hooks / 'bridge.py').stat().st_mode & 0o777
        protected = {}
        for relative, content in [("config.toml", b"# user configuration\n"), ("native-trust.fixture", b"trust"),
                                  ("mainframe/hooks/.disabled-mainframe-todo-limits", b""),
                                  ("mainframe/hooks/.disabled-mainframe-code-quality", b"disable")]:
            path = self.adapter.codex / relative
            path.write_bytes(content)
            protected[path] = observed(path)
        previous = self.adapter.receipt()
        report = self.apply_todo()
        self.assertEqual({c["component"] for c in report["changes"]}, {
            "commands.todo", "hooks.mainframe-todo-limits", "hook transport", "hook registration",
            "adaptation state", "ownership receipt"})
        command = (self.adapter.skills / "todo/SKILL.md").read_text()
        self.assertIn("name: todo\n", command)
        self.assertIn("caller", command)
        self.assertNotIn("takes no arguments", command)
        self.assertEqual((self.adapter.skills / "todo/agents/openai.yaml").read_text(),
                         "policy:\n  allow_implicit_invocation: false\n")
        installed = json.loads((self.adapter.codex / "hooks.json").read_bytes())
        self.assertEqual(installed["description"], self.hooks["description"])
        self.assertEqual(installed["hooks"]["PreToolUse"][:-1], self.hooks["hooks"]["PreToolUse"])
        self.assertEqual(installed["hooks"]["Stop"], [])
        self.assertEqual(installed["hooks"]["PreToolUse"][-1]["matcher"], "^apply_patch$")
        after = self.adapter.receipt()
        self.assertEqual((self.adapter.hooks / 'bridge.py').stat().st_mode & 0o777, bridge_mode)
        for key, value in previous.items():
            if key not in {"files", "hook_groups", "directories"}:
                self.assertEqual(after[key], value, key)
        for path, snapshot in protected.items():
            self.assertEqual(observed(path), snapshot, str(path))
        state = json.loads(self.adapter.state_path.read_bytes())
        self.assertEqual(state["target"], self.state["target"])
        self.assertEqual(state["next_actions"], self.state["next_actions"])
        self.assertEqual(state["components"]["skills"], self.state["components"]["skills"])
        self.assertEqual(state["components"]["commands"]["todo"]["verification"], "pending")
        self.assertEqual(state["components"]["hooks"]["mainframe-todo-limits"]["verification"], "pending")
        self.assertFalse(any(c.needed for c in self.adapter.plan_todo()[0]))

    def test_rejects_wrong_runtime_missing_receipt_and_edited_transport(self):
        for version, surface in [("99.0", "desktop"), ("0.165.0-alpha.1.2", "cli")]:
            with self.subTest(version=version, surface=surface):
                adapter = Codex(self.root, self.home, version=version, surface=surface)
                with self.assertRaisesRegex(Conflict, "not validated"):
                    adapter.plan_todo()
        bridge = self.adapter.hooks / "bridge.py"
        bridge.write_bytes(b"# user edit\n")
        with self.assertRaisesRegex(Conflict, "Installed file was edited"):
            self.adapter.plan_todo()
        self.adapter.receipt_path.unlink()
        with self.assertRaisesRegex(Conflict, "existing same-source"):
            self.adapter.plan_todo()

    def test_foreign_command_and_modified_registration_are_preserved(self):
        target = self.adapter.skills / "todo/SKILL.md"
        target.parent.mkdir(parents=True)
        target.write_bytes(b"user command")
        with self.assertRaisesRegex(Conflict, "Existing file has no installer ownership"):
            self.adapter.plan_todo()
        self.assertEqual(target.read_bytes(), b"user command")
        target.unlink()
        self.apply_todo()
        path = self.adapter.codex / "hooks.json"
        hooks = json.loads(path.read_bytes())
        hooks["hooks"]["PreToolUse"][-1]["hooks"][0]["timeout"] = 100
        path.write_bytes(encode_json(hooks))
        before = observed(path)
        with self.assertRaisesRegex(Conflict, "registration was edited"):
            self.adapter.plan_todo()
        self.assertEqual(observed(path), before)

    def test_bridge_passes_native_patch_to_detector_and_denies_without_state(self):
        detector = SimpleNamespace(check_patch=lambda workspace, patch: "bounded denial" if patch == "bad" else None)
        payload = {"hook_event_name": "PreToolUse", "tool_name": "apply_patch", "cwd": str(self.root),
                   "tool_input": {"command": "bad"}}
        with patch.object(codex_hook, "_load_detector", return_value=detector):
            output = codex_hook.dispatch("mainframe-todo-limits", self.adapter.event_state,
                                         io.BytesIO(json.dumps(payload).encode()))
            self.assertEqual(output["hookSpecificOutput"]["permissionDecision"], "deny")
            for event, tool, command in [("PostToolUse", "apply_patch", "bad"),
                                         ("PreToolUse", "Bash", "bad"), ("PreToolUse", "apply_patch", "good")]:
                data = {**payload, "hook_event_name": event, "tool_name": tool, "tool_input": {"command": command}}
                self.assertIsNone(codex_hook.dispatch("mainframe-todo-limits", self.adapter.event_state,
                                                      io.BytesIO(json.dumps(data).encode())))
        self.assertFalse(self.adapter.event_state.exists())

    def test_missing_cwd_is_forwarded_for_safe_absolute_path_resolution(self):
        seen = []
        detector = SimpleNamespace(check_patch=lambda workspace, patch: seen.append((workspace, patch)))
        data = {"hook_event_name": "PreToolUse", "tool_name": "apply_patch", "tool_input": {"command": "patch"}}
        with patch.object(codex_hook, "_load_detector", return_value=detector):
            self.assertIsNone(codex_hook.dispatch("mainframe-todo-limits", self.adapter.event_state,
                                                  io.BytesIO(json.dumps(data).encode())))
        self.assertEqual(seen, [(None, "patch")])

    def test_other_commands_keep_their_no_argument_contract(self):
        packaged = self.adapter.command_artifacts({"components": {"commands": {
            "mainframe-command": {"source": "commands/todo.md"}}}})
        body = packaged[self.adapter.skills / "mainframe-command/SKILL.md"][0].decode()
        self.assertIn("takes no arguments", body)
        self.assertNotIn("accepts the caller's prose as arguments", body)

    def test_identical_user_registration_is_reused_without_ownership(self):
        path = self.adapter.codex / "hooks.json"
        group = self.adapter.todo_group()
        hooks = json.loads(path.read_bytes())
        hooks["hooks"]["PreToolUse"].append(group)
        path.write_bytes(encode_json(hooks))
        before = observed(path)
        self.apply_todo()
        self.assertEqual(observed(path), before)
        self.assertEqual(json.loads(path.read_bytes())["hooks"]["PreToolUse"].count(group), 1)
        self.assertNotIn(group, self.adapter.receipt()["hook_groups"]["PreToolUse"])
        self.assertFalse(any(c.needed for c in self.adapter.plan_todo()[0]))

    def test_other_apply_patch_binding_migration_retains_its_position(self):
        old = {"matcher": "^apply_patch$", "hooks": [{"type": "command", "command": _legacy_hook_command(
            self.adapter.hooks, "mainframe-code-quality", self.adapter.event_state)}]}
        new = {"matcher": "^apply_patch$", "hooks": [{"type": "command", "command": hook_command(
            self.adapter.hooks, "mainframe-code-quality", self.adapter.event_state, self.home / "runtime")} ]}
        guard = self.adapter.todo_group()
        user = {"hooks": [{"type": "command", "command": "true"}]}
        previous = {"hook_groups": {"PreToolUse": [old, guard]}}
        raw = encode_json({"hooks": {"PreToolUse": [old, guard, user]}})
        result, _ = merge_hooks(raw, {"PreToolUse": [new, guard]}, previous, self.adapter.hooks)
        self.assertEqual(json.loads(result)["hooks"]["PreToolUse"], [new, guard, user])

    def test_installed_callback_denies_canonical_violation_and_disabled_callback_is_silent(self):
        canonical = Path(__file__).resolve().parents[1] / "hooks/mainframe-todo-limits.py"
        (self.root / "hooks/mainframe-todo-limits.py").write_bytes(canonical.read_bytes())
        self.apply_todo()
        patch_text = "*** Begin Patch\n*** Add File: .docs/todos/limit.md\n+" + "x" * 5001 + "\n*** End Patch\n"
        data = {"hook_event_name": "PreToolUse", "tool_name": "apply_patch", "cwd": str(self.root),
                "tool_input": {"command": patch_text}}
        callback = hook_command(self.adapter.hooks, "mainframe-todo-limits", self.adapter.event_state)
        def invoke():
            return subprocess.run(["/bin/sh", "-c", callback], input=json.dumps(data),
                                  text=True, capture_output=True, timeout=5)
        result = invoke()
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")
        output = json.loads(result.stdout)["hookSpecificOutput"]
        self.assertEqual(output["permissionDecision"], "deny")
        self.assertIn("5000", output["permissionDecisionReason"])
        self.assertNotIn("x" * 100, result.stdout)
        self.assertFalse((self.root / ".docs/todos/limit.md").exists())
        transact(self.adapter.control(False, "mainframe-todo-limits"), self.adapter.journal, self.adapter.allowed)
        self.assertEqual(invoke().stdout, "")
        self.assertFalse(self.adapter.event_state.exists())


if __name__ == "__main__":
    unittest.main()
