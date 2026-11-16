from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from installer import codex_hook


class HookStateTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="mainframe-hook-state-test-")
        self.state = Path(self.temporary.name) / "state"
        self.addCleanup(self.temporary.cleanup)

    def claim(self, scope="scope", operation="operation"):
        return codex_hook.claim_event({"session_id": scope, "tool_use_id": operation}, self.state)

    def test_concurrent_duplicate_delivery_has_one_claim(self):
        self.assertTrue(self.claim(operation="initialize"))
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: self.claim(), range(16)))
        self.assertEqual(results.count(True), 1)
        self.assertTrue(self.claim(scope="another-scope"))

    def test_expired_same_key_is_reclaimed_once_and_old_rows_do_not_starve(self):
        self.assertTrue(self.claim())
        with patch.object(codex_hook.time, "time", return_value=time.time() + codex_hook.EVENT_TTL + 1):
            with ThreadPoolExecutor(max_workers=4) as pool:
                results = list(pool.map(lambda _: self.claim(), range(4)))
            self.assertEqual(results.count(True), 1)
        database = self.state / "events.sqlite3"
        with closing(sqlite3.connect(database)) as connection, connection:
            connection.executemany("INSERT INTO events VALUES (?, ?)", [(f"young-{i}", time.time() + 100) for i in range(150)])
            connection.execute("INSERT INTO events VALUES ('old-after-young', ?)", (time.time() - 1,))
        self.assertTrue(self.claim(operation="new"))
        with closing(sqlite3.connect(database)) as connection:
            self.assertIsNone(connection.execute("SELECT 1 FROM events WHERE id='old-after-young'").fetchone())

    def test_capacity_is_bounded_and_expiry_restores_capacity(self):
        with patch.object(codex_hook, "MAX_EVENTS", 2):
            self.assertTrue(self.claim(operation="one"))
            self.assertTrue(self.claim(operation="two"))
            self.assertFalse(self.claim(operation="three"))
            with patch.object(codex_hook.time, "time", return_value=time.time() + codex_hook.EVENT_TTL + 1):
                self.assertTrue(self.claim(operation="three"))
        with closing(sqlite3.connect(self.state / "events.sqlite3")) as connection:
            self.assertEqual(connection.execute("SELECT count(*) FROM events").fetchone()[0], 1)

    def test_missing_native_identity_does_not_create_state(self):
        self.assertFalse(codex_hook.claim_event({}, self.state))
        self.assertFalse(self.state.exists())

    def test_composite_guard_survives_an_advisory_state_failure(self):
        payload = {"session_id": "scope", "tool_use_id": "mixed",
                   "hook_event_name": "PreToolUse", "tool_name": "Bash",
                   "tool_input": {"command": "rg -r replacement pattern .; git reset --hard"}}
        def detector(name):
            if name == "mainframe-rg-short-replace":
                return SimpleNamespace(advisory_message=lambda command: "rg advice")
            if name == "mainframe-destructive-operations":
                return SimpleNamespace(context_free_decision_reason=lambda command: "destructive command")
            if name == "mainframe-secret-access":
                return SimpleNamespace(decision_reason=lambda command: None)
            return SimpleNamespace(check_context_free_metadata=lambda command:
                                   SimpleNamespace(block_reason=None, advisory=None))
        with (
            patch.object(codex_hook, "_load_detector", side_effect=detector),
            patch.object(codex_hook, "claim_event", side_effect=sqlite3.OperationalError("locked")),
        ):
            output = codex_hook.dispatch(codex_hook.PRE_SHELL_TRANSPORT, self.state,
                                         io.BytesIO(json.dumps(payload).encode()))
        self.assertEqual(output["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_codex_bounds_the_serialized_unicode_context(self):
        output = codex_hook._context("PostToolUse", "😀" * 10000)
        self.assertLessEqual(len(json.dumps(output, ensure_ascii=True).encode()), 8192)
        self.assertLessEqual(len(output["hookSpecificOutput"]["additionalContext"]), 1600)

    def test_post_edit_combines_channels_and_isolates_scanner_failure(self):
        data = {"hook_event_name": "PostToolUse", "tool_name": "apply_patch"}
        messages = ("Quality finding\n" + "q" * 1200,
                    "Fallow finding\n" + "f" * 1200,
                    "Commit checkpoint\n" + "c" * 1200)
        with (
            patch.object(codex_hook, "_dispatch_quality",
                         return_value=codex_hook._context("PostToolUse", messages[0])),
            patch.object(codex_hook, "_dispatch_fallow",
                         return_value=codex_hook._context("PostToolUse", messages[1])) as fallow,
            patch.object(codex_hook, "_dispatch_checkpoint",
                         return_value=codex_hook._context("PostToolUse", messages[2])),
        ):
            def invoke():
                return codex_hook.dispatch(codex_hook.POST_EDIT_TRANSPORT, self.state,
                                          io.BytesIO(json.dumps(data).encode()))
            result = invoke()
            text = result["hookSpecificOutput"]["additionalContext"]
            for message in messages:
                self.assertIn(message.splitlines()[0], text)
            self.assertLessEqual(len(text), 1600)
            self.assertNotIn("decision", result)
            fallow.side_effect = RuntimeError("unavailable")
            result = invoke()["hookSpecificOutput"]["additionalContext"]
            self.assertIn("Quality finding", result)
            self.assertIn("Commit checkpoint", result)

    def test_post_edit_keeps_unicode_and_multiline_channel_prefixes_within_wire_budget(self):
        data = {"hook_event_name": "PostToolUse", "tool_name": "apply_patch"}
        messages = [label + "\n" + "😀" * 1500 for label in ("QUALITY", "FALLOW", "CHECKPOINT")]
        with (patch.object(codex_hook, "_dispatch_quality", return_value=codex_hook._context("PostToolUse", messages[0])),
              patch.object(codex_hook, "_dispatch_fallow", return_value=codex_hook._context("PostToolUse", messages[1])),
              patch.object(codex_hook, "_dispatch_checkpoint", return_value=codex_hook._context("PostToolUse", messages[2]))):
            output = codex_hook.dispatch(codex_hook.POST_EDIT_TRANSPORT, self.state, io.BytesIO(json.dumps(data).encode()))
        context = output["hookSpecificOutput"]["additionalContext"]
        for label in ("QUALITY", "FALLOW", "CHECKPOINT"):
            self.assertIn(label + "\n😀", context)
        self.assertLessEqual(len(context), 1600)
        self.assertLessEqual(len(json.dumps(output, ensure_ascii=True, separators=(",", ":")).encode()) + 1, 8192)


if __name__ == "__main__":
    unittest.main()
