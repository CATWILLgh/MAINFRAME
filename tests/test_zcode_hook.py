from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import json
import os
from pathlib import Path
import shutil
import signal
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from installer import zcode_hook


SOURCE = Path(__file__).resolve().parents[1]


class ZCodeHookFixture(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="mainframe-zcode-hook-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "hooks" / "mainframe"
        self.detectors = self.root / "detectors"
        self.detectors.mkdir(parents=True)
        self.bridge = self.root / "bridge.py"
        shutil.copyfile(SOURCE / "installer" / "zcode_hook.py", self.bridge)
        for name in zcode_hook.SUPPORTED_HOOKS - {zcode_hook.PRE_SHELL_TRANSPORT}:
            shutil.copyfile(SOURCE / "hooks" / (name + ".py"), self.detectors / (name + ".py"))
        self.state = Path(self.temporary.name) / "state"

    def payload(self, command="pwd", operation="operation"):
        return {
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": command},
            "session_id": "session",
            "tool_use_id": operation,
        }

    def invoke(self, name, payload=None, *, raw=None):
        environment = os.environ.copy()
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        return subprocess.run(
            [sys.executable, "-B", str(self.bridge), name, str(self.state)],
            input=raw if raw is not None else json.dumps(payload or self.payload()),
            text=True,
            capture_output=True,
            timeout=5,
            env=environment,
        )

    def test_clean_shell_command_is_silent_and_creates_no_state(self):
        for name in sorted(zcode_hook.SUPPORTED_HOOKS):
            with self.subTest(name=name):
                result = self.invoke(name)
                self.assertEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "")
                self.assertEqual(result.stderr, "")
        self.assertFalse(self.state.exists())
        self.assertFalse(any(self.root.rglob("__pycache__")))

    def test_combined_pre_shell_transport_is_silent_and_preserves_mixed_results(self):
        neutral = self.invoke(zcode_hook.PRE_SHELL_TRANSPORT, self.payload("pwd", "combined-neutral"))
        self.assertEqual((neutral.returncode, neutral.stdout, neutral.stderr), (0, "", ""))

        (self.detectors / "mainframe-secret-access.py").write_text(
            "def decision_reason(command): return 'synthetic denial'\n"
        )
        (self.detectors / "mainframe-rg-short-replace.py").write_text(
            "def advisory_message(command): return 'synthetic advice'\n"
        )
        mixed = self.invoke(
            zcode_hook.PRE_SHELL_TRANSPORT,
            self.payload("synthetic", "combined-mixed"),
        )
        specific = json.loads(mixed.stdout)["hookSpecificOutput"]
        self.assertEqual(specific["permissionDecision"], "deny")
        self.assertEqual(specific["permissionDecisionReason"], "synthetic denial")
        self.assertEqual(specific["additionalContext"], "synthetic advice")

    def test_combined_pre_shell_transport_honors_individual_disable_markers(self):
        (self.root / ".disabled-mainframe-rg-short-replace").touch()
        result = self.invoke(
            zcode_hook.PRE_SHELL_TRANSPORT,
            self.payload("rg -r replacement pattern .", "combined-disabled"),
        )
        self.assertEqual(result.stdout, "")
        secret = self.invoke(
            zcode_hook.PRE_SHELL_TRANSPORT,
            self.payload("mainframe-secret get synthetic", "combined-secret"),
        )
        self.assertEqual(
            json.loads(secret.stdout)["hookSpecificOutput"]["permissionDecision"], "deny"
        )

    def test_secret_finding_is_a_native_denial_without_cwd_or_identity(self):
        payload = self.payload("mainframe-secret get synthetic")
        payload.pop("session_id")
        payload.pop("tool_use_id")
        result = self.invoke("mainframe-secret-access", payload)
        output = json.loads(result.stdout)
        specific = output["hookSpecificOutput"]
        self.assertEqual(specific["hookEventName"], "PreToolUse")
        self.assertEqual(specific["permissionDecision"], "deny")
        self.assertIn("mainframe-secret run NAME", specific["permissionDecisionReason"])
        self.assertFalse(self.state.exists())

    def test_rg_finding_is_nonblocking_context_and_supports_camel_case_input(self):
        payload = {
            "hookEventName": "PreToolUse",
            "toolName": "Bash",
            "toolInput": {"command": "rg -r replacement pattern ."},
            "sessionId": "session",
            "toolUseId": "camel-operation",
        }
        result = self.invoke("mainframe-rg-short-replace", payload)
        specific = json.loads(result.stdout)["hookSpecificOutput"]
        self.assertEqual(specific["hookEventName"], "PreToolUse")
        self.assertIn("additionalContext", specific)
        self.assertNotIn("permissionDecision", specific)
        self.assertIn("command was not blocked", specific["additionalContext"])

    def test_advisory_duplicate_delivery_is_silent_but_new_event_is_delivered(self):
        payload = self.payload("rg -r replacement pattern .")
        first = self.invoke("mainframe-rg-short-replace", payload)
        duplicate = self.invoke("mainframe-rg-short-replace", payload)
        later = self.invoke(
            "mainframe-rg-short-replace", self.payload("rg -r replacement pattern .", "later")
        )
        self.assertTrue(first.stdout)
        self.assertEqual(duplicate.stdout, "")
        self.assertTrue(later.stdout)
        self.assertEqual(self.state.stat().st_mode & 0o777, 0o700)
        self.assertEqual((self.state / "events.sqlite3").stat().st_mode & 0o777, 0o600)

    def test_advisory_without_real_native_identity_is_neutral(self):
        payload = self.payload("rg -r replacement pattern .")
        payload.pop("tool_use_id")
        result = self.invoke("mainframe-rg-short-replace", payload)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "")
        self.assertFalse(self.state.exists())

    def test_unicode_message_is_bounded_before_serialization_and_valid_json(self):
        (self.detectors / "mainframe-rg-short-replace.py").write_text(
            "def advisory_message(command):\n"
            '    return ("Привет 😀 \\"quoted\\"\\n" * 1000)\n',
            encoding="utf-8",
        )
        result = self.invoke(
            "mainframe-rg-short-replace", self.payload("rg -r replacement pattern .", "unicode")
        )
        output = json.loads(result.stdout)
        message = output["hookSpecificOutput"]["additionalContext"]
        self.assertLessEqual(len(message), zcode_hook.MAX_MESSAGE_CHARS)
        self.assertIn("Привет 😀", message)
        self.assertLessEqual(len(result.stdout.encode()), zcode_hook.MAX_OUTPUT_BYTES)

    def test_disabled_cached_bridge_is_neutral_before_loading_input_or_detector(self):
        (self.root / ".disabled-mainframe-secret-access").touch()
        (self.detectors / "mainframe-secret-access.py").unlink()
        result = self.invoke("mainframe-secret-access", raw="not JSON")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "")
        self.assertFalse(self.state.exists())

    def test_missing_or_broken_detector_and_unsupported_names_are_neutral(self):
        (self.detectors / "mainframe-secret-access.py").unlink()
        missing = self.invoke("mainframe-secret-access", self.payload("mainframe-secret get synthetic"))
        (self.detectors / "mainframe-rg-short-replace.py").write_text(
            "raise RuntimeError('dependency unavailable')\n", encoding="utf-8"
        )
        broken = self.invoke(
            "mainframe-rg-short-replace", self.payload("rg -r replacement pattern .", "broken")
        )
        unsupported = self.invoke("not-a-hook", self.payload("rm -rf /"))
        for result in (missing, broken, unsupported):
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout, "")
            self.assertEqual(result.stderr, "")
        self.assertFalse(self.state.exists())

    def test_malformed_oversized_wrong_event_and_conflicting_aliases_are_neutral(self):
        malformed = self.invoke("mainframe-secret-access", raw="{")
        oversized = self.invoke(
            "mainframe-secret-access", raw=" " * (zcode_hook.MAX_INPUT_BYTES + 1)
        )
        wrong = self.payload("mainframe-secret get synthetic")
        wrong["hook_event_name"] = "PostToolUse"
        wrong_event = self.invoke("mainframe-secret-access", wrong)
        conflict = self.payload("mainframe-secret get synthetic")
        conflict["hookEventName"] = "Stop"
        conflicting = self.invoke("mainframe-secret-access", conflict)
        for result in (malformed, oversized, wrong_event, conflicting):
            self.assertEqual(result.stdout, "")
            self.assertEqual(result.stderr, "")

    def test_emoji_output_obeys_full_wire_byte_budget(self):
        (self.detectors / "mainframe-rg-short-replace.py").write_text(
            "def advisory_message(command): return '😀' * 100000\n"
        )
        result = self.invoke("mainframe-rg-short-replace", self.payload("rg -r x y"))
        self.assertTrue(json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"])
        self.assertLessEqual(len(result.stdout.encode()), 32768)

    def test_code_quality_tracks_introduction_blocks_stop_and_releases_after_repair(self):
        project = Path(self.temporary.name) / "quality-project"
        project.mkdir()
        source = project / "sample.go"
        source.write_text("package sample\n", encoding="utf-8")

        def event(name, operation):
            return {
                "hook_event_name": name,
                "tool_name": "Write",
                "tool_input": {"file_path": str(source)},
                "session_id": "quality-session",
                "tool_use_id": operation,
                "cwd": str(project),
            }

        self.assertEqual(self.invoke("mainframe-code-quality", event("PreToolUse", "introduce")).stdout, "")
        source.write_text("package sample\n// TODO: finish behavior\n", encoding="utf-8")
        after = self.invoke("mainframe-code-quality", event("PostToolUse", "introduce"))
        self.assertIn("TODO/FIXME/HACK/XXX", json.loads(after.stdout)["hookSpecificOutput"]["additionalContext"])
        stop = event("Stop", "stop-one")
        stop.pop("tool_name")
        stop.pop("tool_input")
        blocked = json.loads(self.invoke("mainframe-code-quality", stop).stdout)
        self.assertEqual(blocked["decision"], "block")

        self.assertEqual(self.invoke("mainframe-code-quality", event("PreToolUse", "repair")).stdout, "")
        source.write_text("package sample\n", encoding="utf-8")
        repaired = self.invoke("mainframe-code-quality", event("PostToolUse", "repair"))
        self.assertEqual(repaired.stdout, "")
        self.assertEqual(self.invoke("mainframe-code-quality", stop).stdout, "")

    def git(self, root, *args):
        return subprocess.run(["git", "-C", str(root), *args], check=True,
                              capture_output=True, timeout=5)

    def repository(self, name):
        root = Path(self.temporary.name) / name
        root.mkdir()
        self.git(root, "init", "-q")
        return root

    def test_commit_inspects_actual_cwd_and_redacts_staged_fixture(self):
        dirty = self.repository("dirty")
        clean = self.repository("clean")
        synthetic = "ghp_" + ("0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ" * 2)[:36]
        (dirty / "fixture.txt").write_text("TOKEN=" + synthetic + "\n")
        self.git(dirty, "add", "fixture.txt")
        (clean / "fixture.txt").write_text("ordinary content\n")
        self.git(clean, "add", "fixture.txt")
        payload = self.payload("git commit -m test")
        payload["cwd"] = str(dirty)
        specific = json.loads(self.invoke("mainframe-commit-secrets", payload).stdout)["hookSpecificOutput"]
        self.assertEqual(specific["permissionDecision"], "deny")
        self.assertNotIn(synthetic, json.dumps(specific))
        disabled = self.root / ".disabled-mainframe-commit-secrets"
        disabled.touch()
        self.assertEqual(self.invoke("mainframe-commit-secrets", payload).stdout, "")
        disabled.unlink()
        payload["cwd"] = str(clean)
        self.assertEqual(self.invoke("mainframe-commit-secrets", payload).stdout, "")
        self.assertFalse(self.state.exists())
        for invalid in (None, "relative", str(clean / "missing")):
            payload["cwd"] = invalid
            self.assertEqual(self.invoke("mainframe-commit-secrets", payload).stdout, "")

    def test_commit_unavailable_advisory_is_deduplicated_by_native_tool_call(self):
        payload = self.payload("git commit -F -")
        payload["cwd"] = str(self.repository("advisory"))
        payload["toolCallId"] = payload.pop("tool_use_id")
        specific = json.loads(self.invoke("mainframe-commit-secrets", payload).stdout)["hookSpecificOutput"]
        self.assertIn("additionalContext", specific)
        self.assertNotIn("permissionDecision", specific)
        self.assertEqual(self.invoke("mainframe-commit-secrets", payload).stdout, "")
        payload["tool_use_id"] = "conflict"
        self.assertEqual(self.invoke("mainframe-commit-secrets", payload).stdout, "")

    def test_commit_time_budget_returns_advisory_and_kills_git_child(self):
        root = self.repository("slow")
        tools = Path(self.temporary.name) / "bin"
        tools.mkdir()
        marker = Path(self.temporary.name) / "child-pid"
        fake = tools / "git"
        fake.write_text("#!" + sys.executable + "\nimport os, time\n"
                        + "open(" + repr(str(marker)) + ", 'w').write(str(os.getpid()))\n"
                        + "time.sleep(30)\n")
        fake.chmod(0o700)
        payload = self.payload("git commit -m test")
        payload["cwd"] = str(root)
        started = time.monotonic()
        with patch.dict(os.environ, {"PATH": str(tools) + os.pathsep + os.environ["PATH"]}):
            result = self.invoke("mainframe-commit-secrets", payload)
        self.assertLess(time.monotonic() - started, 4.5)
        specific = json.loads(result.stdout)["hookSpecificOutput"]
        self.assertIn("native_time_budget", specific["additionalContext"])
        self.assertNotIn("permissionDecision", specific)
        with self.assertRaises(ProcessLookupError):
            os.kill(int(marker.read_text()), 0)

    def capture(self, root, session="session", source="startup"):
        return self.invoke("mainframe-destructive-operations", {
            "hook_event_name": "SessionStart", "session_id": session,
            "cwd": str(root), "source": source,
        })

    def test_captured_root_survives_cwd_change_and_isolated_sessions(self):
        root = Path(self.temporary.name) / "project"
        root.mkdir()
        child = root / "child"
        child.mkdir()
        payload = self.payload("rm -rf ..")
        payload["cwd"] = str(child)
        self.assertEqual(self.invoke("mainframe-destructive-operations", payload).stdout, "")
        self.assertFalse(self.state.exists())
        self.assertEqual(self.capture(root).stdout, "")
        specific = json.loads(self.invoke("mainframe-destructive-operations", payload).stdout)["hookSpecificOutput"]
        self.assertEqual(specific["permissionDecision"], "deny")
        self.assertIn("active project root", specific["permissionDecisionReason"])
        payload["session_id"] = "other"
        self.assertEqual(self.invoke("mainframe-destructive-operations", payload).stdout, "")
        payload["session_id"] = "session"
        payload["tool_input"]["command"] = "rm -rf ordinary-subdir"
        self.assertEqual(self.invoke("mainframe-destructive-operations", payload).stdout, "")
        (self.root / ".disabled-mainframe-destructive-operations").touch()
        payload["tool_input"]["command"] = "rm -rf .."
        self.assertEqual(self.invoke("mainframe-destructive-operations", payload).stdout, "")
        self.capture(root, session="disabled")
        self.assertIsNone(zcode_hook.session_root({"session_id": "disabled"}, self.state))

    def test_only_verified_session_start_sources_capture(self):
        for source in ("other", None):
            self.assertEqual(
                self.capture(self.temporary.name, source=source, session="rejected").stdout,
                "",
            )
        self.assertFalse(self.state.exists())
        for source in ("startup", "clear", "compact", "resume"):
            session = "session-" + source
            self.assertEqual(
                self.capture(self.temporary.name, source=source, session=session).stdout,
                "",
            )
            self.assertEqual(
                zcode_hook.session_root({"session_id": session}, self.state),
                str(Path(self.temporary.name).resolve()),
            )


class ZCodeEventStateTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="mainframe-zcode-state-")
        self.addCleanup(self.temporary.cleanup)
        self.state = Path(self.temporary.name) / "state"

    def claim(self, scope="scope", operation="operation", kind="mainframe-rg-short-replace"):
        return zcode_hook.claim_event(
            {"session_id": scope, "tool_use_id": operation}, self.state, kind
        )

    def test_concurrent_duplicate_has_one_claim_and_hook_kinds_are_independent(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: self.claim(), range(16)))
        self.assertEqual(results.count(True), 1)
        self.assertTrue(self.claim(kind="another-advisory"))
        self.assertTrue(self.claim(scope="another-session"))

    def test_expiry_reclaims_once_and_capacity_is_bounded(self):
        with patch.object(zcode_hook, "MAX_EVENTS", 2):
            self.assertTrue(self.claim(operation="one"))
            self.assertTrue(self.claim(operation="two"))
            self.assertFalse(self.claim(operation="three"))
            with patch.object(
                zcode_hook.time,
                "time",
                return_value=time.time() + zcode_hook.EVENT_TTL + 1,
            ):
                with ThreadPoolExecutor(max_workers=4) as pool:
                    results = list(
                        pool.map(lambda _: self.claim(operation="three"), range(4))
                    )
                self.assertEqual(results.count(True), 1)
        with closing(sqlite3.connect(self.state / "events.sqlite3")) as connection:
            self.assertEqual(
                connection.execute("SELECT count(*) FROM events").fetchone()[0], 1
            )

    def test_missing_or_synthetic_identity_does_not_create_state(self):
        self.assertFalse(zcode_hook.claim_event({}, self.state, "mainframe-rg-short-replace"))
        self.assertFalse(
            zcode_hook.claim_event(
                {"session_id": "session", "cwd": "/tmp"},
                self.state,
                "mainframe-rg-short-replace",
            )
        )
        self.assertFalse(self.state.exists())

    def test_roots_expiry_capacity_concurrency_and_private_hashes(self):
        def capture(scope):
            return zcode_hook.session_root({"session_id": scope, "cwd": self.temporary.name,
                                           "source": "startup"}, self.state, capture=True)
        with patch.object(zcode_hook, "MAX_ROOTS", 2):
            with ThreadPoolExecutor(max_workers=8) as pool:
                results = list(pool.map(capture, ["private-session"] * 16))
            self.assertEqual(results, [str(Path(self.temporary.name).resolve())] * 16)
            self.assertEqual(capture("second"), str(Path(self.temporary.name).resolve()))
            self.assertIsNone(capture("third"))
            with patch.object(zcode_hook.time, "time", return_value=time.time() + zcode_hook.EVENT_TTL + 1):
                self.assertIsNone(zcode_hook.session_root({"session_id": "private-session"}, self.state))
                self.assertEqual(capture("third"), str(Path(self.temporary.name).resolve()))
        with closing(sqlite3.connect(self.state / "events.sqlite3")) as connection:
            rows = connection.execute("SELECT id, root FROM roots").fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0][0]), 64)
        self.assertEqual((self.state / "events.sqlite3").stat().st_mode & 0o777, 0o600)
        self.assertNotIn(b"private-session", (self.state / "events.sqlite3").read_bytes())

    def test_active_root_retention_refreshes_without_changing_root(self):
        data = {"session_id": "active", "source": "startup", "cwd": self.temporary.name}
        now = time.time()
        root = zcode_hook.session_root(data, self.state, capture=True)
        with patch.object(zcode_hook.time, "time", return_value=now + zcode_hook.EVENT_TTL - 10):
            self.assertEqual(zcode_hook.session_root(data, self.state), root)
        with patch.object(zcode_hook.time, "time", return_value=now + zcode_hook.EVENT_TTL + 10):
            self.assertEqual(zcode_hook.session_root(data, self.state), root)

    def test_resume_replaces_root_only_through_capture(self):
        data = {"session_id": "session", "source": "startup", "cwd": self.temporary.name}
        original = zcode_hook.session_root(data, self.state, capture=True)
        child = Path(self.temporary.name) / "resumed"
        child.mkdir()
        data.update(cwd=str(child), source="resume")
        self.assertEqual(zcode_hook.session_root(data, self.state), original)
        self.assertEqual(zcode_hook.session_root(data, self.state, capture=True), str(child.resolve()))

    def test_commit_budget_restores_existing_alarm_after_exception(self):
        previous_handler = signal.getsignal(signal.SIGALRM)
        previous_timer = signal.getitimer(signal.ITIMER_REAL)
        def handler(signum, frame):
            pass
        try:
            signal.signal(signal.SIGALRM, handler)
            signal.setitimer(signal.ITIMER_REAL, 30, 2)
            with self.assertRaises(ValueError):
                with zcode_hook._commit_budget(None):
                    raise ValueError("fixture")
            self.assertIs(signal.getsignal(signal.SIGALRM), handler)
            remaining, interval = signal.getitimer(signal.ITIMER_REAL)
            self.assertGreater(remaining, 29)
            self.assertLessEqual(remaining, 30)
            self.assertEqual(interval, 2)
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, previous_handler)
            signal.setitimer(signal.ITIMER_REAL, *previous_timer)

    def test_roots_reject_unprivate_or_symlink_state(self):
        self.state.mkdir(mode=0o755)
        data = {"session_id": "session", "source": "startup", "cwd": self.temporary.name}
        self.assertIsNone(zcode_hook.session_root(data, self.state, capture=True))
        self.assertFalse((self.state / "events.sqlite3").exists())
        self.state.rmdir()
        self.state.symlink_to(self.temporary.name)
        self.assertIsNone(zcode_hook.session_root(data, self.state, capture=True))


if __name__ == "__main__":
    unittest.main()
