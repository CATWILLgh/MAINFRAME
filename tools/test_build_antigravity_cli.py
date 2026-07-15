#!/usr/bin/env python3
"""CLI and native-application checks for the Antigravity 2.x builder."""

from __future__ import annotations

import plistlib
import subprocess
import sys
import tempfile
from pathlib import Path

from test_build_antigravity import ADAPTER, REPO, build, fixture_root


def test_native_validation_requires_antigravity_major_two() -> None:
    root = fixture_root()
    app = root / "Antigravity.app"
    plist = app / "Contents/Info.plist"
    plist.parent.mkdir(parents=True)
    with plist.open("wb") as handle:
        plistlib.dump({"CFBundleIdentifier": build.BUNDLE_IDENTIFIER, "CFBundleShortVersionString": "2.2.1"}, handle)
    assert build.validate_native_app(app) == "2.2.1"
    with plist.open("wb") as handle:
        plistlib.dump({"CFBundleIdentifier": build.BUNDLE_IDENTIFIER, "CFBundleShortVersionString": "3.0.0"}, handle)
    try:
        build.validate_native_app(app)
    except ValueError as error:
        assert "major version 2" in str(error)
    else:
        raise AssertionError("Antigravity 3.x was accepted")
    with plist.open("wb") as handle:
        plistlib.dump({"CFBundleIdentifier": "com.example.unrelated", "CFBundleShortVersionString": "2.2.1"}, handle)
    try:
        build.validate_native_app(app)
    except ValueError as error:
        assert build.BUNDLE_IDENTIFIER in str(error)
    else:
        raise AssertionError("an unrelated 2.x application was accepted")


def test_real_builder_cli_check_and_default_output() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "plugin"
        subprocess.run([sys.executable, str(ADAPTER / "build_antigravity.py"), "--root", str(REPO), "--out", str(out)], check=True)
        subprocess.run([sys.executable, str(ADAPTER / "build_antigravity.py"), "--root", str(REPO), "--out", str(out), "--check"], check=True)
        meta, body = build.parse_frontmatter((out / "skills/delegate-web-search/SKILL.md").read_text())
        assert meta["name"] == "delegate-web-search"
        assert "define_subagent" in body
        for path in out.glob("skills/delegate-*/SKILL.md"):
            projected = path.read_text()
            assert "dist/claude-code" not in projected
            assert "`skills:` frontmatter" not in projected
            assert "preloaded" not in projected.lower()
            assert "~/.claude/" not in projected
            assert "CLAUDE.md" not in projected
            assert "MAINFRAME plugin rules rules" not in projected


if __name__ == "__main__":
    tests = sorted(name for name in globals() if name.startswith("test_"))
    for name in tests:
        globals()[name]()
        print(f"PASS {name}")
    print(f"{len(tests)} tests passed")
