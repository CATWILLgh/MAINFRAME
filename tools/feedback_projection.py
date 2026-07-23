#!/usr/bin/env python3
"""Project the optional DEV feedback skill into one adapter-local runtime."""

from pathlib import Path

from bundle_sync import sync_tree, write_text_file


FEEDBACK_DIR_TOKEN = "{{mainframe.feedback_dir}}"
DIAGNOSTICS_CONFIG_TOKEN = "{{mainframe.diagnostics_config}}"
FEEDBACK_EXPRESSION = 'os.path.expanduser("~/.claude/mainframe/feedback")'
DIAGNOSTICS_EXPRESSION = (
    'os.path.expanduser("~/.claude/mainframe/diagnostics.json")'
)
ADAPTER_PROJECTIONS = {
    "claude-code": {
        "feedback_expression": FEEDBACK_EXPRESSION,
        "diagnostics_expression": DIAGNOSTICS_EXPRESSION,
        "feedback_display": "~/.claude/mainframe/feedback",
        "diagnostics_display": "~/.claude/mainframe/diagnostics.json",
    },
    "codex": {
        "feedback_expression": (
            'os.path.join(os.environ.get("CODEX_HOME") or '
            'os.path.expanduser("~/.codex"), "mainframe", "feedback")'
        ),
        "diagnostics_expression": (
            'os.path.join(os.environ.get("CODEX_HOME") or '
            'os.path.expanduser("~/.codex"), "mainframe", "diagnostics.json")'
        ),
        "feedback_display": "${CODEX_HOME:-$HOME/.codex}/mainframe/feedback",
        "diagnostics_display": (
            "${CODEX_HOME:-$HOME/.codex}/mainframe/diagnostics.json"
        ),
    },
    "opencode": {
        "feedback_expression": (
            'os.path.join(os.environ.get("XDG_CONFIG_HOME") or '
            'os.path.expanduser("~/.config"), "opencode", "mainframe", "feedback")'
        ),
        "diagnostics_expression": (
            'os.path.join(os.environ.get("XDG_CONFIG_HOME") or '
            'os.path.expanduser("~/.config"), "opencode", "mainframe", '
            '"diagnostics.json")'
        ),
        "feedback_display": (
            "${XDG_CONFIG_HOME:-$HOME/.config}/opencode/mainframe/feedback"
        ),
        "diagnostics_display": (
            "${XDG_CONFIG_HOME:-$HOME/.config}/opencode/mainframe/diagnostics.json"
        ),
    },
    "antigravity-2": {
        "feedback_expression": (
            'os.path.expanduser("~/.gemini/antigravity/mainframe/feedback")'
        ),
        "diagnostics_expression": (
            'os.path.expanduser('
            '"~/.gemini/antigravity/mainframe/diagnostics.json")'
        ),
        "feedback_display": "~/.gemini/antigravity/mainframe/feedback",
        "diagnostics_display": (
            "~/.gemini/antigravity/mainframe/diagnostics.json"
        ),
    },
}


def project_adapter_feedback_skill(
    source: Path,
    output: Path,
    adapter: str,
) -> None:
    try:
        projection = ADAPTER_PROJECTIONS[adapter]
    except KeyError as error:
        raise ValueError(f"unknown feedback adapter: {adapter}") from error
    project_feedback_skill(source, output, **projection)


def project_feedback_skill(
    source: Path,
    output: Path,
    *,
    feedback_expression: str,
    diagnostics_expression: str,
    feedback_display: str,
    diagnostics_display: str,
) -> None:
    sync_tree(source, output)
    skill = output / "SKILL.md"
    receiver = output / "feedback.py"
    prose = (
        skill.read_text()
        .replace(FEEDBACK_DIR_TOKEN, feedback_display)
        .replace(DIAGNOSTICS_CONFIG_TOKEN, diagnostics_display)
    )
    script = _replace_once(
        receiver.read_text(),
        FEEDBACK_EXPRESSION,
        feedback_expression,
        receiver,
    )
    script = (
        _replace_once(
            script,
            DIAGNOSTICS_EXPRESSION,
            diagnostics_expression,
            receiver,
        )
        .replace(FEEDBACK_DIR_TOKEN, feedback_display)
        .replace(DIAGNOSTICS_CONFIG_TOKEN, diagnostics_display)
    )
    if "{{mainframe." in prose or "{{mainframe." in script:
        raise ValueError("projected feedback skill retains a runtime token")
    write_text_file(skill, prose)
    write_text_file(receiver, script)


def _replace_once(text: str, anchor: str, replacement: str, source: Path) -> str:
    count = text.count(anchor)
    if count != 1:
        raise ValueError(f"{source}: expected one projection anchor, found {count}")
    return text.replace(anchor, replacement)
