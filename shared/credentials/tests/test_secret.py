from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import time
import unittest


SOURCE = Path(__file__).resolve().parents[1] / "mainframe-secret"


class SecretCommandTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="mainframe-secret-command-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.config = self.root / "config"
        self.fake_bin = self.root / "bin"
        self.clipboard = self.root / "clipboard"
        self.fake_bin.mkdir()
        self._write_executable(
            "pbpaste",
            '#!/bin/sh\ncat "$FAKE_CLIPBOARD"\n',
        )
        self._write_executable(
            "pbcopy",
            '#!/bin/sh\ncat > "$FAKE_CLIPBOARD"\n',
        )
        self.environment = os.environ.copy()
        self.environment.update(
            {
                "XDG_CONFIG_HOME": str(self.config),
                "FAKE_CLIPBOARD": str(self.clipboard),
                "PATH": f"{self.fake_bin}:/usr/bin:/bin",
            }
        )

    def _write_executable(self, name: str, body: str) -> None:
        target = self.fake_bin / name
        target.write_text(body, encoding="utf-8")
        target.chmod(0o755)

    def _wait_for(self, condition: Callable[[], bool], description: str) -> None:
        deadline = time.monotonic() + 3
        while not condition() and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertTrue(condition(), description)

    def run_secret(
        self,
        *arguments: str,
        environment: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(SOURCE), *arguments],
            check=False,
            capture_output=True,
            text=True,
            env=environment or self.environment,
            stdin=subprocess.DEVNULL,
            timeout=10,
        )

    def test_registers_from_clipboard_without_printing_the_value(self) -> None:
        value = "synthetic-api-key-'-$-value"
        self.clipboard.write_text(value, encoding="utf-8")

        result = self.run_secret("set", "API_TOKEN", "--clipboard")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("registered 'API_TOKEN'", result.stdout)
        self.assertNotIn(value, result.stdout + result.stderr)
        store = self.config / "credentials" / "secrets.env"
        self.assertEqual(stat.S_IMODE(store.stat().st_mode), 0o600)
        copied = self.run_secret("copy", "API_TOKEN")
        self.assertEqual(copied.returncode, 0, copied.stderr)
        self.assertEqual(self.clipboard.read_text(encoding="utf-8"), value)
        self.assertNotIn(value, copied.stdout + copied.stderr)

    def test_run_delivers_only_the_named_value_to_the_consumer(self) -> None:
        value = "synthetic-process-value"
        self.clipboard.write_text(value, encoding="utf-8")
        self.assertEqual(
            self.run_secret("set", "API_TOKEN", "--clipboard").returncode,
            0,
        )
        environment = self.environment | {"EXPECTED_SYNTHETIC": value}

        result = self.run_secret(
            "run",
            "API_TOKEN",
            "--",
            "sh",
            "-c",
            'test "$API_TOKEN" = "$EXPECTED_SYNTHETIC"',
            environment=environment,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn(value, result.stdout + result.stderr)

    def test_rejects_command_argument_empty_and_multiline_values(self) -> None:
        result = self.run_secret("set", "API_TOKEN", "literal-value")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("cannot be passed as command arguments", result.stderr)

        self.clipboard.write_text("", encoding="utf-8")
        result = self.run_secret("set", "API_TOKEN", "--clipboard")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("empty value", result.stderr)

        self.clipboard.write_text("first\nsecond", encoding="utf-8")
        result = self.run_secret("set", "API_TOKEN", "--clipboard")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("multiline values", result.stderr)

    def test_prompt_fails_cleanly_without_an_interactive_terminal(self) -> None:
        result = self.run_secret("set", "API_TOKEN", "--prompt")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("requires an interactive terminal", result.stderr)

    def test_clipboard_failure_does_not_register_a_value(self) -> None:
        self._write_executable("pbpaste", "#!/bin/sh\nexit 1\n")
        result = self.run_secret("set", "API_TOKEN", "--clipboard")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn(
            "API_TOKEN=",
            (self.config / "credentials" / "secrets.env").read_text(encoding="utf-8")
            if (self.config / "credentials" / "secrets.env").exists()
            else "",
        )

    def test_parallel_registration_converges_without_lost_entries(self) -> None:
        value = "synthetic-parallel-value"
        self.clipboard.write_text(value, encoding="utf-8")
        names = [f"TOKEN_{index}" for index in range(24)]
        with ThreadPoolExecutor(max_workers=12) as executor:
            results = list(
                executor.map(
                    lambda name: self.run_secret("set", name, "--clipboard"),
                    names,
                )
            )
        self.assertTrue(all(result.returncode == 0 for result in results))
        listed = self.run_secret("list")
        self.assertEqual(listed.returncode, 0, listed.stderr)
        self.assertEqual(set(listed.stdout.splitlines()), set(names))

    def test_delayed_first_use_does_not_clear_a_registered_entry(self) -> None:
        self.clipboard.write_text("synthetic-first-use-value", encoding="utf-8")
        waiting = self.root / "initialization-waiting"
        resume = self.root / "initialization-resume"
        bash_env = self.root / "pause-initialization.sh"
        bash_env.write_text(
            'umask() {\n'
            '    : > "$INITIALIZATION_WAITING"\n'
            '    while [[ ! -e "$INITIALIZATION_RESUME" ]]; do sleep 0.01; done\n'
            '    builtin umask "$@"\n'
            '}\n',
            encoding="utf-8",
        )
        delayed_environment = self.environment | {
            "BASH_ENV": str(bash_env),
            "INITIALIZATION_WAITING": str(waiting),
            "INITIALIZATION_RESUME": str(resume),
        }
        with ThreadPoolExecutor(max_workers=1) as executor:
            delayed = executor.submit(
                self.run_secret, "set", "DELAYED", "--clipboard",
                environment=delayed_environment,
            )
            try:
                # Pause after the helper observes the missing store, before it creates it.
                self._wait_for(waiting.exists, "initializer never reached the barrier")
                first = self.run_secret("set", "FIRST", "--clipboard")
                self.assertEqual(first.returncode, 0, first.stderr)
            finally:
                resume.touch()
            completed = delayed.result()
        self.assertEqual(completed.returncode, 0, completed.stderr)
        listed = self.run_secret("list")
        self.assertEqual(listed.returncode, 0, listed.stderr)
        self.assertEqual(set(listed.stdout.splitlines()), {"FIRST", "DELAYED"})

    def test_waiter_with_old_pid_cannot_remove_the_successors_lock(self) -> None:
        self.clipboard.write_text("synthetic-lock-value", encoding="utf-8")
        bash_env = self.root / "pause-lock-stages.sh"
        bash_env.write_text(
            '''checkpoint() {
    : > "$LOCK_TEST_DIR/$LOCK_TEST_STAGE-waiting"
    while [[ ! -e "$LOCK_TEST_DIR/$LOCK_TEST_STAGE-resume" ]]; do command sleep 0.01; done
}
case "$LOCK_TEST_STAGE" in
    holder) grep() { checkpoint; command grep "$@"; } ;;
    waiter)
        kill() {
            if [[ ! -e "$LOCK_TEST_DIR/waiter-waiting" ]]; then checkpoint; fi
            builtin kill "$@"
        }
        sleep() { : > "$LOCK_TEST_DIR/waiter-retrying"; command sleep "$@"; }
        ;;
    successor) cp() { checkpoint; command cp "$@"; } ;;
esac
''',
            encoding="utf-8",
        )

        def register(stage: str) -> subprocess.CompletedProcess[str]:
            environment = self.environment | {
                "BASH_ENV": str(bash_env),
                "LOCK_TEST_DIR": str(self.root),
                "LOCK_TEST_STAGE": stage,
            }
            return self.run_secret("set", stage.upper(), "--clipboard", environment=environment)

        with ThreadPoolExecutor(max_workers=3) as executor:
            try:
                holder = executor.submit(register, "holder")
                self._wait_for((self.root / "holder-waiting").exists, "holder never acquired lock")
                waiter = executor.submit(register, "waiter")
                self._wait_for((self.root / "waiter-waiting").exists, "waiter never read holder PID")
                (self.root / "holder-resume").touch()
                held = holder.result()
                self.assertEqual(held.returncode, 0, held.stderr)

                # The successor snapshots the store before the waiter checks the old PID.
                successor = executor.submit(register, "successor")
                self._wait_for(
                    (self.root / "successor-waiting").exists, "successor never reached its write"
                )
                (self.root / "waiter-resume").touch()
                retrying = self.root / "waiter-retrying"
                self._wait_for(
                    lambda: retrying.exists() or waiter.done(), "waiter never checked the old PID"
                )
            finally:
                for stage in ("holder", "waiter", "successor"):
                    (self.root / f"{stage}-resume").touch()
            for future in (waiter, successor):
                result = future.result()
                self.assertEqual(result.returncode, 0, result.stderr)
        listed = self.run_secret("list")
        self.assertEqual(listed.returncode, 0, listed.stderr)
        self.assertEqual(set(listed.stdout.splitlines()), {"HOLDER", "WAITER", "SUCCESSOR"})

    def test_registration_recovers_a_lock_from_an_exited_owner(self) -> None:
        self.clipboard.write_text("synthetic-recovery-value", encoding="utf-8")
        lock = self.config / "credentials" / ".lock"
        lock.mkdir(parents=True)
        with subprocess.Popen(["/bin/sh", "-c", "exit 0"]) as owner:
            self.assertEqual(owner.wait(timeout=3), 0)
        (lock / "pid").write_text(f"{owner.pid}\n", encoding="utf-8")

        registered = self.run_secret("set", "RECOVERED", "--clipboard")

        self.assertEqual(registered.returncode, 0, registered.stderr)
        self.assertFalse(lock.exists())
        listed = self.run_secret("list")
        self.assertEqual(listed.returncode, 0, listed.stderr)
        self.assertEqual(listed.stdout.splitlines(), ["RECOVERED"])

    def test_termination_after_reading_store_does_not_commit(self) -> None:
        self.clipboard.write_text("synthetic-signal-value", encoding="utf-8")
        first = self.run_secret("set", "FIRST", "--clipboard")
        self.assertEqual(first.returncode, 0, first.stderr)
        bash_env = self.root / "interrupt-registration.sh"
        bash_env.write_text(
            'sed() { command sed "$@"; builtin kill -TERM "$$"; }\n',
            encoding="utf-8",
        )

        interrupted = self.run_secret(
            "set", "INTERRUPTED", "--clipboard",
            environment=self.environment | {"BASH_ENV": str(bash_env)},
        )

        self.assertEqual(interrupted.returncode, 143, interrupted.stderr)
        successor = self.run_secret("set", "SUCCESSOR", "--clipboard")
        self.assertEqual(successor.returncode, 0, successor.stderr)
        self.assertEqual(self.run_secret("list").stdout.splitlines(), ["FIRST", "SUCCESSOR"])

    def test_incomplete_pid_marker_does_not_authorize_recovery(self) -> None:
        self.clipboard.write_text("synthetic-marker-value", encoding="utf-8")
        lock = self.config / "credentials" / ".lock"
        lock.mkdir(parents=True)
        with subprocess.Popen(["/bin/sh", "-c", "exit 0"]) as owner:
            self.assertEqual(owner.wait(timeout=3), 0)
        marker = lock / "pid"
        marker.write_text(str(owner.pid), encoding="utf-8")
        bash_env = self.root / "skip-lock-retry-delay.sh"
        bash_env.write_text("sleep() { :; }\n", encoding="utf-8")

        result = self.run_secret(
            "set", "BLOCKED", "--clipboard",
            environment=self.environment | {"BASH_ENV": str(bash_env)},
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("another instance holds the lock", result.stderr)
        self.assertEqual(marker.read_text(encoding="utf-8"), str(owner.pid))
        self.assertEqual(self.run_secret("list").stdout, "")

    def test_mutations_preserve_entries_on_store_read_error(self) -> None:
        self.clipboard.write_text("synthetic-read-error-value", encoding="utf-8")
        for name in ("FIRST", "SECOND"):
            result = self.run_secret("set", name, "--clipboard")
            self.assertEqual(result.returncode, 0, result.stderr)
        bash_env = self.root / "fail-store-read.sh"
        bash_env.write_text(
            'grep() { if [[ "$1" = "-v" ]]; then return 2; fi; command grep "$@"; }\n',
            encoding="utf-8",
        )

        for arguments in (("set", "THIRD", "--clipboard"), ("del", "FIRST")):
            with self.subTest(operation=arguments[0]):
                result = self.run_secret(
                    *arguments, environment=self.environment | {"BASH_ENV": str(bash_env)},
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(self.run_secret("list").stdout.splitlines(), ["FIRST", "SECOND"])


if __name__ == "__main__":
    unittest.main()
