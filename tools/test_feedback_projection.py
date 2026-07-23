#!/usr/bin/env python3
"""Tier-1 contracts for adapter-local feedback skill projection."""

from pathlib import Path
from tempfile import TemporaryDirectory

from feedback_projection import project_feedback_skill


def _write_skill(root: Path, receiver: str) -> Path:
    source = root / "source"
    source.mkdir()
    (source / "SKILL.md").write_text(
        "Feedback: {{mainframe.feedback_dir}}\n"
        "Config: {{mainframe.diagnostics_config}}\n"
    )
    (source / "feedback.py").write_text(receiver)
    return source


def test_projection_rejects_missing_python_anchor() -> None:
    with TemporaryDirectory() as temp:
        root = Path(temp)
        source = _write_skill(root, "print('receiver without defaults')\n")
        try:
            project_feedback_skill(
                source,
                root / "output",
                feedback_expression="'feedback'",
                diagnostics_expression="'diagnostics'",
                feedback_display="/feedback",
                diagnostics_display="/diagnostics",
            )
        except ValueError as error:
            assert "feedback.py" in str(error)
        else:
            raise AssertionError("missing projection anchors were accepted")


if __name__ == "__main__":
    test_projection_rejects_missing_python_anchor()
    print("1/1 passed")
