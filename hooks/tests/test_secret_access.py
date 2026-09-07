from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import importlib.util
from pathlib import Path
import unittest


SOURCE = Path(__file__).resolve().parents[1] / "secret-access.py"
SPEC = importlib.util.spec_from_file_location("secret_access", SOURCE)
assert SPEC is not None and SPEC.loader is not None
DETECTOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DETECTOR)


class SecretAccessTests(unittest.TestCase):
    def test_blocks_only_standalone_get(self) -> None:
        for command in (
            "secret get API_TOKEN",
            "command secret get API_TOKEN",
            "/usr/local/bin/secret get API_TOKEN",
            "MODE=test exec secret get API_TOKEN",
        ):
            with self.subTest(command=command):
                reason = DETECTOR.decision_reason(command)
                self.assertIn("secret copy NAME", reason or "")
                self.assertNotIn("API_TOKEN", reason or "")

        for command in (
            "secret copy API_TOKEN",
            "secret run API_TOKEN -- consumer",
            'consumer --token "$(secret get API_TOKEN)"',
            "secret get API_TOKEN | pbcopy",
            "echo secret get API_TOKEN",
            "printf 'secret get API_TOKEN'",
        ):
            with self.subTest(command=command):
                self.assertIsNone(DETECTOR.decision_reason(command))

    def test_blocks_value_bearing_set_and_allows_protected_modes(self) -> None:
        for command in (
            "secret set API_TOKEN literal-value",
            "secret set API_TOKEN 'literal value'",
            'secret set API_TOKEN "$(pbpaste)"',
            "command secret set API_TOKEN literal-value extra",
        ):
            with self.subTest(command=command):
                reason = DETECTOR.decision_reason(command)
                self.assertIn("--clipboard", reason or "")
                self.assertNotIn("literal-value", reason or "")

        for command in (
            "secret set API_TOKEN --clipboard",
            "secret set API_TOKEN --prompt",
            "secret set API_TOKEN",
            "secret del API_TOKEN",
            "secret list",
        ):
            with self.subTest(command=command):
                self.assertIsNone(DETECTOR.decision_reason(command))

    def test_malformed_or_unrelated_input_is_silent(self) -> None:
        for command in (
            "",
            "secret",
            "secret get",
            "secret get API_TOKEN extra",
            "secret 'unterminated",
            "other-secret get API_TOKEN",
            "echo ok && secret get API_TOKEN",
        ):
            with self.subTest(command=command):
                self.assertIsNone(DETECTOR.decision_reason(command))

        self.assertIsNone(DETECTOR.decision_reason(None))  # type: ignore[arg-type]

    def test_parallel_calls_are_stateless(self) -> None:
        commands = ["secret get API_TOKEN", "secret copy API_TOKEN"] * 64
        with ThreadPoolExecutor(max_workers=16) as executor:
            results = list(executor.map(DETECTOR.decision_reason, commands))
        self.assertEqual(sum(result is not None for result in results), 64)


if __name__ == "__main__":
    unittest.main()
