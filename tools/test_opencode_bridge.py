#!/usr/bin/env python3
"""Contract tests for the Codex-to-OpenCode CLI bridge."""

import json
import os
import pathlib
import subprocess
import sys
import tempfile


ROOT = pathlib.Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "adapters" / "codex" / "bin" / "mainframe-opencode"


def _fixture(exit_code=0):
    root = pathlib.Path(tempfile.mkdtemp(prefix="mainframe-opencode-test-"))
    bin_dir = root / "bin"
    bin_dir.mkdir()
    capture = root / "capture.json"
    fake = bin_dir / "opencode"
    fake.write_text(
        """#!/usr/bin/env python3
import json, os, pathlib, sys
pathlib.Path(os.environ["BRIDGE_CAPTURE"]).write_text(json.dumps({
    "argv": sys.argv[1:],
    "xdg_config_home": os.environ.get("XDG_CONFIG_HOME"),
    "config": json.loads(os.environ["OPENCODE_CONFIG_CONTENT"]),
}))
print("forwarded stdout")
print("forwarded stderr", file=sys.stderr)
raise SystemExit(int(os.environ["FAKE_EXIT_CODE"]))
""",
        encoding="utf-8",
    )
    fake.chmod(0o755)
    environment = dict(os.environ)
    environment["PATH"] = f"{bin_dir}{os.pathsep}{environment.get('PATH', '')}"
    environment["BRIDGE_CAPTURE"] = str(capture)
    environment["FAKE_EXIT_CODE"] = str(exit_code)
    return capture, environment


def test_forwards_cli_arguments_without_assigning_a_role():
    capture, environment = _fixture()
    result = subprocess.run(
        [sys.executable, str(BRIDGE), "run", "--model", "provider/model", "Inspect this"],
        text=True,
        capture_output=True,
        env=environment,
    )
    assert result.returncode == 0
    assert result.stdout == "forwarded stdout\n"
    assert result.stderr == "forwarded stderr\n"
    payload = json.loads(capture.read_text(encoding="utf-8"))
    assert payload["argv"] == ["run", "--model", "provider/model", "Inspect this"]
    assert payload["xdg_config_home"]
    config = payload["config"]
    assert config["share"] == "disabled"
    assert config["plugin"] == []
    assert config["instructions"] == []
    assert "agent" not in config
    assert "tools" not in config
    assert "permission" not in config


def test_preserves_opencode_exit_code():
    _, environment = _fixture(exit_code=23)
    result = subprocess.run(
        [sys.executable, str(BRIDGE), "models"],
        text=True,
        capture_output=True,
        env=environment,
    )
    assert result.returncode == 23


def test_missing_opencode_is_reported_without_fallback():
    environment = dict(os.environ)
    environment["PATH"] = ""
    result = subprocess.run(
        [sys.executable, str(BRIDGE), "--version"],
        text=True,
        capture_output=True,
        env=environment,
    )
    assert result.returncode == 127
    assert "OpenCode CLI is not installed" in result.stderr


def main():
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
        print(f"  ok {test.__name__}")
    print(f"OK OpenCode bridge — {len(tests)} tests passed")


if __name__ == "__main__":
    main()
