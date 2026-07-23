#!/usr/bin/env python3
"""Tier-1 isolation contracts for the Antigravity 2.x adapter builder."""

from __future__ import annotations

import sys
from importlib import import_module
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ADAPTER = REPO / "adapters" / "antigravity-2"
TOOLS = REPO / "tools"
sys.path.insert(0, str(ADAPTER))
sys.path.insert(0, str(TOOLS))

build = import_module("build_antigravity")
fixtures = import_module("test_build_antigravity")

ANTIGRAVITY_FEEDBACK = (
    'os.path.expanduser("~/.gemini/config/skills/'
    'harness-feedback")'
)
ANTIGRAVITY_TELEMETRY = (
    'os.path.expanduser("~/.gemini/antigravity/mainframe-telemetry/'
    'telemetry.db")'
)
ANTIGRAVITY_DIAGNOSTICS = (
    'os.path.expanduser("~/.gemini/antigravity/mainframe/diagnostics.json")'
)
ANTIGRAVITY_CREDENTIALS_INDEX = (
    "~/.gemini/antigravity/credentials-index.md"
)


def test_real_runtime_artifacts_are_antigravity_owned() -> None:
    files = build.render_plugin(REPO)
    hooklib = files[Path("scripts/detectors/_hooklib.py")].decode()
    secrets = files[Path("skills/secrets-handling/SKILL.md")].decode()
    skills = "\n".join(
        content.decode()
        for path, content in files.items()
        if path.parts[:1] == ("skills",) and path.suffix == ".md"
    )

    assert ANTIGRAVITY_FEEDBACK in hooklib
    assert ANTIGRAVITY_TELEMETRY in hooklib
    assert ANTIGRAVITY_DIAGNOSTICS in hooklib
    assert ANTIGRAVITY_CREDENTIALS_INDEX in secrets
    assert "~/.claude/" not in hooklib
    assert "~/.claude/" not in skills


def test_runtime_projection_rejects_unmapped_claude_path() -> None:
    root = fixtures.fixture_root()
    hooklib = root / "core/gates/detectors/_hooklib.py"
    hooklib.write_text(
        'FEEDBACK = os.path.expanduser('
        '"~/.claude/skills/mainframe-dev/skills/harness-feedback")\n'
        'TELEMETRY = os.path.expanduser('
        '"~/.claude/mainframe/telemetry/telemetry.db")\n'
        'DIAGNOSTICS = os.path.expanduser('
        '"~/.claude/mainframe/diagnostics.json")\n'
        'OTHER = "~/.claude/unmapped"\n'
    )

    try:
        build.render_plugin(root)
    except ValueError as error:
        assert "scripts/detectors/_hooklib.py" in str(error)
    else:
        raise AssertionError("unmapped Claude runtime path was accepted")


if __name__ == "__main__":
    tests = sorted(name for name in globals() if name.startswith("test_"))
    for name in tests:
        globals()[name]()
        print(f"PASS {name}")
    print(f"{len(tests)} tests passed")
