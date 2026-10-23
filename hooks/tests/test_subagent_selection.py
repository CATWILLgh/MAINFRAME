from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


SOURCE = Path(__file__).resolve().parents[1] / "mainframe-subagent-selection.py"
SPEC = importlib.util.spec_from_file_location("subagent_selection", SOURCE)
assert SPEC is not None and SPEC.loader is not None
DETECTOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DETECTOR)


class SubagentSelectionTests(unittest.TestCase):
    def test_accepts_explicit_choices_without_a_model_or_effort_catalog(self) -> None:
        for model, effort in (
            ("available-model", "high"),
            ("future-model", "future-supported-effort"),
            (" available-model ", " low "),
            ("available-model", "none"),
            ("available-model", " NONE "),
        ):
            with self.subTest(model=model, effort=effort):
                self.assertIsNone(DETECTOR.decision_reason(model, effort))

    def test_requires_both_choices_for_recognized_creation(self) -> None:
        # Adapters extract absent argument fields as None, including from {}.
        for model, effort in (
            (None, None),
            (None, "high"),
            ("available-model", None),
            ("", "high"),
            ("available-model", " \t\n "),
        ):
            with self.subTest(model=model, effort=effort):
                self.assertIsInstance(DETECTOR.decision_reason(model, effort), str)

    def test_rejects_implicit_selections_with_case_and_space_variations(self) -> None:
        for implicit in ("inherit", " DEFAULT ", "AuTo", "\tInHeRiT\n"):
            with self.subTest(implicit=implicit):
                self.assertIsInstance(
                    DETECTOR.decision_reason(implicit, "high"), str
                )
                self.assertIsInstance(
                    DETECTOR.decision_reason("available-model", implicit), str
                )

    def test_rejects_nonstring_values_in_either_control(self) -> None:
        for value in (False, True, 0, 1, [], {}, ["high"], {"value": "high"}):
            with self.subTest(value=value):
                self.assertIsInstance(DETECTOR.decision_reason(value, "high"), str)
                self.assertIsInstance(
                    DETECTOR.decision_reason("available-model", value), str
                )

    def test_denial_gives_an_actionable_explicit_retry(self) -> None:
        reason = DETECTOR.decision_reason(None, None)
        self.assertIsInstance(reason, str)
        for guidance in (
            "available model", "supported reasoning effort", "complexity",
            "importance", "cost of error", "budget", "retry", "explicit",
        ):
            with self.subTest(guidance=guidance):
                self.assertIn(guidance, reason or "")


if __name__ == "__main__":
    unittest.main()
