from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import time
import unittest
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


if __name__ == "__main__":
    unittest.main()
