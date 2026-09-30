import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from installer import minimax_hook


ROOT = Path(__file__).resolve().parents[1]


class MiniMaxHookTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="mainframe-minimax-hook-")
        self.addCleanup(self.temporary.cleanup)
        base = Path(self.temporary.name).resolve()
        self.plugin = base / "plugin"
        (self.plugin / "hooks/detectors").mkdir(parents=True)
        (self.plugin / "instructions").mkdir()
        for name in minimax_hook.HOOK_NAMES:
            shutil.copyfile(ROOT / "hooks" / (name + ".py"), self.plugin / "hooks/detectors" / (name + ".py"))
        shutil.copyfile(ROOT / "instructions/global.md", self.plugin / "instructions/global.md")
        self.state = base / "data/mainframe"
        self.state.mkdir(parents=True, mode=0o700)
        self.old = (minimax_hook.PLUGIN_ROOT, minimax_hook.DETECTORS, minimax_hook.HOOKS)
        minimax_hook.PLUGIN_ROOT = self.plugin
        minimax_hook.DETECTORS = self.plugin / "hooks/detectors"
        minimax_hook.HOOKS = self.plugin / "hooks"
        self.addCleanup(self.restore)
        self.workspace = base / "workspace"
        self.workspace.mkdir()

    def restore(self):
        minimax_hook.PLUGIN_ROOT, minimax_hook.DETECTORS, minimax_hook.HOOKS = self.old

    def payload(self, event, **extra):
        return {"hook_event_name": event, "session_id": "session", "cwd": str(self.workspace), **extra}

    def test_session_start_injects_canonical_global_instruction(self):
        result = minimax_hook.dispatch(self.payload("SessionStart", source="startup"), self.state)
        self.assertEqual(result["hookSpecificOutput"]["hookEventName"], "SessionStart")
        context = result["hookSpecificOutput"]["additionalContext"]
        self.assertIn("actively match available skill descriptions", context)
        self.assertTrue(context.rstrip().endswith("alternate syntax to bypass the restriction."))
        child = minimax_hook.dispatch(self.payload(
            "SubagentStart", agent_id="child", agent_type="worker",
        ), self.state)
        self.assertEqual(child["hookSpecificOutput"]["hookEventName"], "SubagentStart")
        self.assertEqual(child["hookSpecificOutput"]["additionalContext"], context)

    def test_pre_tool_denies_secret_read_and_advises_rg_without_duplicate_processes(self):
        denied = minimax_hook.dispatch(self.payload(
            "PreToolUse", tool_use_id="one", tool_name="bash",
            tool_input={"command": "mainframe-secret get API_TOKEN"},
        ), self.state)
        specific = denied["hookSpecificOutput"]
        self.assertEqual(specific["permissionDecision"], "deny")
        self.assertNotIn("API_TOKEN", specific["permissionDecisionReason"])
        advised = minimax_hook.dispatch(self.payload(
            "PreToolUse", tool_use_id="two", tool_name="bash",
            tool_input={"command": "rg -r replacement needle ."},
        ), self.state)
        self.assertIn("was not blocked", advised["hookSpecificOutput"]["additionalContext"])
        self.assertNotIn("permissionDecision", advised["hookSpecificOutput"])

    def test_exact_edit_is_checked_post_tool_and_stop_guard_is_one_shot(self):
        path = self.workspace / "unsafe.py"
        path.write_text("def ok():\n    return 1\n")
        pre = self.payload("PreToolUse", tool_use_id="edit-1", tool_name="write", tool_input={"path": str(path)})
        minimax_hook.dispatch(pre, self.state)
        path.write_text("import subprocess\ndef bad(value):\n    return subprocess.run(value, shell=True)\n")
        post = self.payload("PostToolUse", tool_use_id="edit-1", tool_name="write",
                            tool_input={"path": str(path)}, tool_response={"ok": True})
        result = minimax_hook.dispatch(post, self.state)
        self.assertIsNotNone(result)
        self.assertEqual(result["hookSpecificOutput"]["hookEventName"], "PostToolUse")
        stop = self.payload("Stop", turn_id="turn-1", stop_hook_active=False, last_assistant_message="done")
        blocked = minimax_hook.dispatch(stop, self.state)
        self.assertEqual(blocked["decision"], "block")
        self.assertIsNone(minimax_hook.dispatch({**stop, "stop_hook_active": True}, self.state))
        self.assertIsNone(minimax_hook.dispatch(stop, self.state))
        child_stop = self.payload(
            "SubagentStop", turn_id="turn-1", agent_id="child", agent_type="worker",
            stop_hook_active=False, last_assistant_message="done",
        )
        self.assertEqual(minimax_hook.dispatch(child_stop, self.state)["decision"], "block")
        self.assertIsNone(minimax_hook.dispatch({**child_stop, "stop_hook_active": True}, self.state))
        self.assertIsNone(minimax_hook.dispatch(child_stop, self.state))

    def test_invalid_and_oversized_input_are_silent(self):
        self.assertIsNone(minimax_hook._read_payload(io.BytesIO(b"not json")))
        self.assertIsNone(minimax_hook._read_payload(io.BytesIO(b" " * (minimax_hook.MAX_INPUT_BYTES + 1))))
        self.assertIsNone(minimax_hook.dispatch(self.payload("PreToolUse", tool_name="read", tool_input={}), self.state))

    def test_disabled_fallow_does_not_capture_edit_bytes(self):
        (self.plugin / "hooks/.disabled-mainframe-fallow-quality").write_text("")
        path = self.workspace / "file.ts"
        path.write_text("export const value = 1;\n")
        minimax_hook.dispatch(self.payload(
            "PreToolUse", tool_use_id="disabled-edit", tool_name="edit",
            tool_input={"path": str(path)},
        ), self.state)
        database = self.state / "events.sqlite3"
        if database.exists():
            import sqlite3
            with sqlite3.connect(database) as connection:
                self.assertEqual(connection.execute("SELECT count(*) FROM snapshots").fetchone()[0], 0)


if __name__ == "__main__": unittest.main()
