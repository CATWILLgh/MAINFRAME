from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import importlib.util
from pathlib import Path
import unittest


SOURCE = Path(__file__).resolve().parents[1] / "rg-short-replace.py"
SPEC = importlib.util.spec_from_file_location("rg_short_replace", SOURCE)
assert SPEC is not None and SPEC.loader is not None
DETECTOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DETECTOR)


class RgShortReplaceTests(unittest.TestCase):
    def test_detects_actual_short_replace_options(self) -> None:
        for command in (
            "rg -r replacement needle .",
            "rg -rn needle .",
            "rg -nr replacement needle .",
            "rg -rreplacement needle .",
            "/usr/local/bin/rg needle . -r replacement",
            "MODE=test command rg -r replacement needle .",
            "cd src && rg -r replacement needle .",
            "bash -lc 'rg -r replacement needle .'",
        ):
            with self.subTest(command=command):
                self.assertTrue(DETECTOR.short_replace_options(command))
                note = DETECTOR.advisory_message(command)
                self.assertIn("recursion is already the default", note or "")
                self.assertIn("was not blocked", note or "")

    def test_preserves_explicit_replace_and_other_option_values(self) -> None:
        for command in (
            "rg --replace replacement needle .",
            "rg --replace=replacement needle .",
            "rg -g -r needle .",
            "rg --glob -r needle .",
            "rg -e -r .",
            "rg --regexp -r .",
            "rg -- -r",
            "rg -g'*.py' needle .",
        ):
            with self.subTest(command=command):
                self.assertIsNone(DETECTOR.advisory_message(command))

    def test_ignores_text_and_other_executables(self) -> None:
        for command in (
            "echo 'rg -r replacement needle .'",
            "printf '%s' 'rg -r replacement needle .'",
            "grep -r needle .",
            "my-rg -r replacement needle .",
            "python -c 'print(\"rg -r\")'",
        ):
            with self.subTest(command=command):
                self.assertIsNone(DETECTOR.advisory_message(command))

    def test_malformed_or_missing_input_is_silent(self) -> None:
        for command in ("", "rg 'unterminated", "rg", "rg needle ."):
            with self.subTest(command=command):
                self.assertIsNone(DETECTOR.advisory_message(command))
        self.assertIsNone(DETECTOR.advisory_message(None))  # type: ignore[arg-type]

    def test_repeated_and_parallel_calls_are_stateless(self) -> None:
        command = "rg -rn needle ."
        expected = DETECTOR.advisory_message(command)
        self.assertIsNotNone(expected)
        self.assertEqual(DETECTOR.advisory_message(command), expected)
        with ThreadPoolExecutor(max_workers=16) as executor:
            results = list(executor.map(DETECTOR.advisory_message, [command] * 128))
        self.assertEqual(results, [expected] * 128)


if __name__ == "__main__":
    unittest.main()
