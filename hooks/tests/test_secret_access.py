from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import importlib.util
from pathlib import Path
import unittest


SOURCE = Path(__file__).resolve().parents[1] / "mainframe-secret-access.py"
SPEC = importlib.util.spec_from_file_location("secret_access", SOURCE)
assert SPEC is not None and SPEC.loader is not None
DETECTOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DETECTOR)


class SecretAccessTests(unittest.TestCase):
    def test_blocks_only_standalone_get(self) -> None:
        for command in (
            "mainframe-secret get API_TOKEN",
            "command mainframe-secret get API_TOKEN",
            "/usr/local/bin/mainframe-secret get API_TOKEN",
            "MODE=test exec mainframe-secret get API_TOKEN",
        ):
            with self.subTest(command=command):
                reason = DETECTOR.decision_reason(command)
                self.assertIn("mainframe-secret copy NAME", reason or "")
                self.assertNotIn("API_TOKEN", reason or "")

        for command in (
            "mainframe-secret copy API_TOKEN",
            "mainframe-secret run API_TOKEN -- consumer",
            'consumer --token "$(mainframe-secret get API_TOKEN)"',
            "mainframe-secret get API_TOKEN | pbcopy",
            "echo mainframe-secret get API_TOKEN",
            "printf 'mainframe-secret get API_TOKEN'",
        ):
            with self.subTest(command=command):
                self.assertIsNone(DETECTOR.decision_reason(command))

    def test_blocks_value_bearing_set_and_allows_protected_modes(self) -> None:
        for command in (
            "mainframe-secret set API_TOKEN literal-value",
            "mainframe-secret set API_TOKEN 'literal value'",
            'mainframe-secret set API_TOKEN "$(pbpaste)"',
            "command mainframe-secret set API_TOKEN literal-value extra",
        ):
            with self.subTest(command=command):
                reason = DETECTOR.decision_reason(command)
                self.assertIn("--clipboard", reason or "")
                self.assertNotIn("literal-value", reason or "")

        for command in (
            "mainframe-secret set API_TOKEN --clipboard",
            "mainframe-secret set API_TOKEN --prompt",
            "mainframe-secret set API_TOKEN",
            "mainframe-secret del API_TOKEN",
            "mainframe-secret list",
        ):
            with self.subTest(command=command):
                self.assertIsNone(DETECTOR.decision_reason(command))

    def test_malformed_or_unrelated_input_is_silent(self) -> None:
        for command in (
            "",
            "secret",
            "mainframe-secret get",
            "mainframe-secret get API_TOKEN extra",
            "secret 'unterminated",
            "other-secret get API_TOKEN",
            "echo ok && mainframe-secret get API_TOKEN",
        ):
            with self.subTest(command=command):
                self.assertIsNone(DETECTOR.decision_reason(command))

        self.assertIsNone(DETECTOR.decision_reason(None))  # type: ignore[arg-type]

    def test_protected_set_ignores_following_shell_commands_but_not_quoted_arguments(self) -> None:
        for command in (
            "mainframe-secret set API_TOKEN --clipboard && echo done",
            "mainframe-secret set API_TOKEN --prompt; echo done",
            'mainframe-secret set API_TOKEN --clip"board"; echo done',
            "mainframe-secret set API_TOKEN --clipboard\necho done",
        ):
            with self.subTest(command=command):
                self.assertIsNone(DETECTOR.decision_reason(command))
        for command in (
            "mainframe-secret set API_TOKEN literal-value && echo done",
            "mainframe-secret set API_TOKEN --clipboard extra-value && echo done",
            'mainframe-secret set API_TOKEN --clipboard ";"',
            "mainframe-secret set API_TOKEN --clipboard \\;",
            'mainframe-secret set API_TOKEN --clipboard "&&"',
        ):
            with self.subTest(command=command):
                self.assertIsNotNone(DETECTOR.decision_reason(command))

    def test_parallel_calls_are_stateless(self) -> None:
        commands = ["mainframe-secret get API_TOKEN", "mainframe-secret copy API_TOKEN"] * 64
        with ThreadPoolExecutor(max_workers=16) as executor:
            results = list(executor.map(DETECTOR.decision_reason, commands))
        self.assertEqual(sum(result is not None for result in results), 64)


if __name__ == "__main__":
    unittest.main()
