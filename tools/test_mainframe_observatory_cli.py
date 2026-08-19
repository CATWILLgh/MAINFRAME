#!/usr/bin/env python3

import os
import plistlib
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "mainframe-observatory.sh"


def run(*args: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(SCRIPT), *args],
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def test_help_describes_foreground_and_explicit_autostart():
    result = subprocess.run(
        [str(SCRIPT)],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    assert result.returncode == 0, result.stdout
    assert "mainframe-observatory start" in result.stdout
    assert "Run in this terminal" in result.stdout
    assert "autostart install" in result.stdout
    assert "starts automatically only after" in result.stdout


def test_dev_delivery_is_quiet_and_autostart_is_explicit():
    with tempfile.TemporaryDirectory() as directory:
        base = Path(directory)
        env = os.environ.copy()
        env.update(
            {
                "HOME": str(base / "home"),
                "MAINFRAME_BIN_DIR": str(base / "bin"),
                "MAINFRAME_OBSERVATORY_RUNTIME": str(base / "runtime"),
                "MAINFRAME_LAUNCH_AGENTS_DIR": str(base / "launch-agents"),
                "MAINFRAME_SYSTEMD_USER_DIR": str(base / "systemd"),
                "MAINFRAME_OBSERVATORY_PORT": "54318",
                "MAINFRAME_OBSERVATORY_TESTING": "1",
            }
        )

        enabled = run("enable", "codex", env=env)
        assert enabled.returncode == 0, enabled.stdout
        command = base / "bin" / "mainframe-observatory"
        assert command.is_symlink()
        assert command.resolve() == SCRIPT.resolve()
        assert (base / "runtime" / "enabled" / "codex").is_file()
        assert not (base / "launch-agents" / "com.mainframe.observatory.plist").exists()
        assert not (base / "systemd" / "mainframe-observatory.service").exists()

        env["MAINFRAME_OBSERVATORY_TEST_PLATFORM"] = "Darwin"
        installed = run("autostart", "install", env=env)
        assert installed.returncode == 0, installed.stdout
        plist_path = base / "launch-agents" / "com.mainframe.observatory.plist"
        with plist_path.open("rb") as handle:
            plist = plistlib.load(handle)
        assert plist["Label"] == "com.mainframe.observatory"
        assert plist["RunAtLoad"] is True and plist["KeepAlive"] is True
        assert plist["ProgramArguments"][0] == "/usr/bin/python3"
        assert "--health-token-file" in plist["ProgramArguments"]
        assert plist["EnvironmentVariables"]["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] == "python"
        assert ".venv" in plist["EnvironmentVariables"]["PYTHONPATH"]

        removed = run("autostart", "remove", env=env)
        assert removed.returncode == 0, removed.stdout
        assert not plist_path.exists()

        env["MAINFRAME_OBSERVATORY_TEST_PLATFORM"] = "Linux"
        installed = run("autostart", "install", env=env)
        assert installed.returncode == 0, installed.stdout
        unit = (base / "systemd" / "mainframe-observatory.service").read_text(encoding="utf-8")
        assert "# Managed by MAINFRAME Observatory" in unit
        assert "WantedBy=default.target" in unit
        assert "Restart=on-failure" in unit

        disabled = run("disable", "codex", env=env)
        assert disabled.returncode == 0, disabled.stdout
        assert not command.exists()
        assert not (base / "systemd" / "mainframe-observatory.service").exists()


if __name__ == "__main__":
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
        print("  ok", test.__name__)
    print(f"OK mainframe-observatory CLI - {len(tests)} tests passed")
