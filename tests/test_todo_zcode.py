import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from installer.core import Conflict, digest, encode_json, transact
from installer.shared import inventory
from installer.zcode import ZCode, command_body, hook_registration

ROOT = Path(__file__).resolve().parents[1]
TODO = "mainframe-todo-limits"


class TodoZCodeTests(unittest.TestCase):
    def test_does_not_reassign_an_unrelated_receipted_command(self):
        path = self.adapter.commands / 'todo.md'
        path.parent.mkdir(parents=True)
        path.write_bytes(b'Unrelated owned command')
        receipt = self.adapter.receipt()
        receipt['files'][str(path)] = {'sha256': digest(path.read_bytes()), 'mode': 0o644,
                                     'owned': True, 'retain': False, 'component': 'commands.keep'}
        self.adapter.receipt_path.write_bytes(encode_json(receipt))
        with self.assertRaisesRegex(Conflict, 'another.*component'):
            self.plan()
        self.assertEqual(path.read_bytes(), b'Unrelated owned command')

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="mainframe-todo-zcode-")
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name).resolve()
        self.source, self.home = base / "source", base / "home with 'quotes'"
        self.source.mkdir(); self.home.mkdir()
        self.adapter = ZCode(self.source, self.home, version="3.17.1.9553")
        self.inventory = {"components": {
            "commands": {"todo": {"source": "commands/todo.md", "delivery": "pending", "verification": "pending"}},
            "hooks": {TODO: {"source": "hooks/mainframe-todo-limits.py", "delivery": "pending", "verification": "pending"}},
        }}
        for relative, content in {
            "commands/todo.md": "# Todo\n\nRecord the following user arguments.\n",
            "hooks/mainframe-todo-limits.py": "def check_write(workspace,path,content):\n    return 'bounded todo finding' if content == 'bad' else None\n\ndef check_edit(workspace,path,old,new,replace_all=False):\n    return 'bounded edit finding' if new == 'bad' else None\n",
        }.items():
            path = self.source / relative
            path.parent.mkdir(parents=True, exist_ok=True); path.write_text(content)
        self.bridge = self.adapter.hooks / "bridge.py"
        self.bridge.parent.mkdir(parents=True)
        self.bridge.write_bytes(b"# previous receipted bridge\n"); self.bridge.chmod(0o600)
        self.foreign = self.adapter.skills / "mainframe-user/SKILL.md"
        self.foreign.parent.mkdir(parents=True); self.foreign.write_bytes(b"user skill\n")
        self.foreign.chmod(0o644)
        self.receipt = {"version": 1, "target": str(self.adapter.zcode), "source": str(self.source),
                        "files": {str(self.bridge): {"sha256": digest(self.bridge.read_bytes()), "mode": 0o600,
                                   "owned": True, "retain": False, "component": "hook transport"},
                                  str(self.foreign): {"sha256": digest(self.foreign.read_bytes()), "mode": 0o644,
                                   "owned": True, "retain": False, "component": "skills.mainframe-user"}},
                        "hook_groups": {}, "disabled_markers": {"mainframe-secret-access": False},
                        "instruction": {"user": "retain"}, "skill_overrides": {"keep": "verbatim"}}
        self.adapter.receipt_path.write_bytes(encode_json(self.receipt)); self.adapter.receipt_path.chmod(0o600)
        self.config = {"hooks": {"enabled": False, "timeoutMs": 4567, "events": {
            "PreToolUse": [{"matcher": "Read", "hooks": [{"type": "process", "command": "user-tool", "enabled": False}]}],
            "Stop": [{"hooks": [{"type": "command", "command": "user-stop"}]}]}},
            "trust": {"unchanged": True}, "skills": {"local": {"enable": False}}, "model": "user-choice"}
        self.adapter.config.parent.mkdir(); self.adapter.config.write_bytes(encode_json(self.config)); self.adapter.config.chmod(0o600)
        self.state = {"schema_version": 2, "target": {"product": "zcode", "config_home": str(self.adapter.zcode), "version": "old"},
                      "components": {"commands": {"user": {"source": "user", "delivery": "installed", "verification": "passed"}},
                                     "hooks": {"old": {"source": "old", "delivery": "installed", "verification": "passed"}}},
                      "next_actions": ["retain user action"], "user": {"retain": True}}
        self.adapter.state_path.write_bytes(encode_json(self.state)); self.adapter.state_path.chmod(0o600)

    def plan(self):
        with patch("installer.zcode.inventory", return_value=self.inventory):
            return self.adapter.plan_todo()

    def apply(self):
        changes, report = self.plan()
        transact(changes, self.adapter.journal, self.adapter.allowed)
        return changes, report

    def test_narrow_delivery_preserves_unrelated_state_and_converges(self):
        changes, report = self.apply()
        destinations = {self.adapter.commands / "todo.md", self.adapter.hooks / "detectors/mainframe-todo-limits.py",
                        self.bridge, self.adapter.config, self.adapter.state_path, self.adapter.receipt_path}
        self.assertEqual({c.path for c in changes}, destinations)
        self.assertEqual((self.adapter.commands / "todo.md").read_bytes(), command_body((self.source / "commands/todo.md").read_text()))
        config = json.loads(self.adapter.config.read_bytes())
        expected = json.loads(json.dumps(self.config))
        expected["hooks"]["events"]["PreToolUse"].append(config["hooks"]["events"]["PreToolUse"][-1])
        self.assertEqual(config, expected)
        self.assertEqual(config["hooks"]["events"]["PreToolUse"][-1]["matcher"], "Write|Edit")
        self.assertFalse(config["hooks"]["enabled"])
        receipt = self.adapter.receipt()
        for key in ("instruction", "skill_overrides", "disabled_markers"):
            self.assertEqual(receipt[key], self.receipt[key])
        self.assertEqual(receipt["files"][str(self.foreign)], self.receipt["files"][str(self.foreign)])
        state = json.loads(self.adapter.state_path.read_bytes())
        self.assertEqual(state["target"], self.state["target"])
        self.assertEqual(state["user"], self.state["user"])
        self.assertEqual(state["components"]["hooks"]["old"], self.state["components"]["hooks"]["old"])
        self.assertEqual(state["components"]["hooks"][TODO]["verification"], "pending")
        self.assertEqual(self.plan()[0], [])
        self.assertIn("Primary", report["hook_scope"])

    def test_requires_existing_same_source_and_reviewed_build(self):
        for version, surface in (("unknown", "desktop"), ("3.17.1.9553", "cli")):
            self.adapter.version, self.adapter.surface = version, surface
            with self.assertRaises(Conflict): self.plan()
        self.adapter.version, self.adapter.surface = "3.17.1.9553", "desktop"
        receipt = self.receipt.copy(); receipt["source"] = str(self.source / "other")
        self.adapter.receipt_path.write_bytes(encode_json(receipt))
        with self.assertRaises(Conflict): self.plan()
        self.adapter.receipt_path.unlink()
        with self.assertRaises(Conflict): self.plan()

    def test_foreign_command_and_edited_bridge_conflict(self):
        self.adapter.commands.mkdir()
        command = self.adapter.commands / "todo.md"; command.write_text("user command")
        with self.assertRaises(Conflict): self.plan()
        command.unlink(); self.bridge.write_text("edited bridge")
        with self.assertRaises(Conflict): self.plan()

    def test_unowned_identical_command_is_reused(self):
        self.adapter.commands.mkdir()
        path = self.adapter.commands / "todo.md"
        path.write_bytes(command_body((self.source / "commands/todo.md").read_text())); path.chmod(0o644)
        self.apply()
        self.assertFalse(self.adapter.receipt()["files"][str(path)]["owned"])
        self.assertEqual(path.stat().st_mode & 0o777, 0o644)
        self.assertEqual(self.plan()[0], [])

    def test_edited_or_duplicate_todo_registration_conflicts(self):
        self.apply()
        raw = self.adapter.config.read_bytes()
        for duplicate in (False, True):
            config = json.loads(raw); group = config["hooks"]["events"]["PreToolUse"][-1]
            if duplicate: config["hooks"]["events"]["PreToolUse"].append(group)
            else: group["matcher"] = "Read"
            self.adapter.config.write_bytes(encode_json(config))
            with self.assertRaises(Conflict): self.plan()
        self.adapter.config.write_bytes(raw)

    def test_native_toggle_and_disable_marker_preserved(self):
        self.apply()
        config = json.loads(self.adapter.config.read_bytes())
        config["hooks"]["events"]["PreToolUse"][-1]["hooks"][0]["enabled"] = False
        self.adapter.config.write_bytes(encode_json(config))
        self.apply()
        self.assertFalse(json.loads(self.adapter.config.read_bytes())["hooks"]["events"]["PreToolUse"][-1]["hooks"][0]["enabled"])
        transact(self.adapter.control(False, TODO), self.adapter.journal, self.adapter.allowed)
        self.assertTrue((self.adapter.hooks / (".disabled-" + TODO)).exists())
        self.apply()
        self.assertTrue((self.adapter.hooks / (".disabled-" + TODO)).exists())

    def run_callback(self, payload):
        callback = hook_registration(self.adapter.hooks, TODO, self.adapter.event_state)
        return subprocess.run([callback["command"], *callback["args"]], input=json.dumps(payload).encode(), capture_output=True)

    def test_callback_denies_write_edit_and_is_neutral_when_disabled_or_absent(self):
        self.apply()
        payload = {"hook_event_name": "PreToolUse", "cwd": str(self.home), "tool_name": "Write", "tool_input": {"file_path": str(self.home / ".docs/todo"), "content": "bad"}}
        process = self.run_callback(payload)
        self.assertEqual(process.returncode, 0)
        self.assertEqual(json.loads(process.stdout)["hookSpecificOutput"]["permissionDecision"], "deny")
        payload["tool_name"] = "Edit"; payload["tool_input"] = {"file_path": str(self.home / ".docs/todo"), "old_string": "old", "new_string": "bad", "replace_all": True}
        self.assertEqual(json.loads(self.run_callback(payload).stdout)["hookSpecificOutput"]["permissionDecision"], "deny")
        marker = self.adapter.hooks / (".disabled-" + TODO); marker.write_bytes(b"")
        self.assertEqual(self.run_callback(payload).stdout, b""); marker.unlink()
        detector = self.adapter.hooks / "detectors/mainframe-todo-limits.py"; detector.unlink()
        self.assertEqual(self.run_callback(payload).stdout, b"")
        self.bridge.unlink()
        self.assertEqual(self.run_callback(payload).stdout, b"")

    def test_invalid_native_payload_stays_neutral(self):
        self.apply()
        payload = {"hook_event_name": "PreToolUse", "cwd": str(self.home), "tool_name": "Edit", "tool_input": {"file_path": "x", "old_string": "old", "new_string": "bad", "replace_all": "false"}}
        self.assertEqual(self.run_callback(payload).stdout, b"")
        payload["toolInput"] = {"conflict": True}
        self.assertEqual(self.run_callback(payload).stdout, b"")
        payload["hook_event_name"] = "PostToolUse"
        self.assertEqual(self.run_callback(payload).stdout, b"")

    def test_real_detector_checks_addressed_write_and_edit_without_state(self):
        (self.source / "hooks/mainframe-todo-limits.py").write_bytes((ROOT / "hooks/mainframe-todo-limits.py").read_bytes())
        self.apply()
        docs = self.home / ".docs"; notes = docs / "todos"; notes.mkdir(parents=True)
        note = notes / "new-idea.md"
        valid = "# Idea\n\n## Суть\nCapture.\n\n## Ожидаемый результат\nSaved.\n\n## Ограничения\nUnknown.\n"
        payload = {"hook_event_name": "PreToolUse", "cwd": str(self.home), "tool_name": "Write",
                   "tool_input": {"file_path": str(note), "content": valid + "x" * 5000}}
        self.assertIn("5000", json.loads(self.run_callback(payload).stdout)["hookSpecificOutput"]["permissionDecisionReason"])
        payload["tool_input"]["content"] = valid
        self.assertEqual(self.run_callback(payload).stdout, b"")
        note.write_text(valid)
        index = docs / "todo"
        template = "# TODO\n\n## Запланировано\n{row}\n\n## На рассмотрении\n\n## Отложено\n\n## Отказались\n"
        payload["tool_input"] = {"file_path": str(index), "content": template.format(row="- " + "x" * 501 + " [Подробнее](todos/new-idea.md)")}
        self.assertIn("500", json.loads(self.run_callback(payload).stdout)["hookSpecificOutput"]["permissionDecisionReason"])
        payload["tool_input"]["content"] = template.format(row="- Save this idea [Подробнее](todos/new-idea.md)")
        self.assertEqual(self.run_callback(payload).stdout, b"")
        payload["tool_name"] = "Edit"
        payload["tool_input"] = {"file_path": str(note), "old_string": "Capture.", "new_string": "x" * 5000}
        self.assertIn("5000", json.loads(self.run_callback(payload).stdout)["hookSpecificOutput"]["permissionDecisionReason"])
        self.assertFalse(self.adapter.event_state.exists())

    def test_full_mapping_packages_todo_with_exact_reviewed_build_allowance(self):
        from installer.zcode import FULL_MAPPING_RUNTIMES
        adapter = ZCode(ROOT, self.home, version="3.14.4.7912")
        artifacts = adapter.artifacts(inventory(ROOT, "zcode"))
        self.assertIn(adapter.commands / "todo.md", artifacts)
        self.assertEqual(artifacts[adapter.hooks / "detectors/mainframe-todo-limits.py"][0], (ROOT / "hooks/mainframe-todo-limits.py").read_bytes())
        merged = json.loads(adapter.merge_config(None, {}, False)[0])
        callbacks = [hook for group in merged["hooks"]["events"]["PreToolUse"]
                     if group["matcher"] == "Write|Edit" for hook in group["hooks"]]
        self.assertEqual(sum(hook["args"][-2] == TODO for hook in callbacks), 1)
        self.assertIn("3.17.1.9553", FULL_MAPPING_RUNTIMES)
        self.assertNotIn("unknown", FULL_MAPPING_RUNTIMES)


if __name__ == "__main__":
    unittest.main()
