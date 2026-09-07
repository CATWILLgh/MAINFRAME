from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest


SOURCE = Path(__file__).resolve().parents[1] / "secret"


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


if __name__ == "__main__":
    unittest.main()
