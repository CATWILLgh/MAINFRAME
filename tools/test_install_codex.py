#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
INSTALLER = ROOT / "install.sh"


def _fake_codex(path: Path, decisions: dict[str, str]) -> None:
    encoded = json.dumps(decisions, separators=(",", ":"))
    path.write_text(
        "#!/usr/bin/env python3\n"
        "import json, sys\n"
        f"decisions = {encoded!r}\n"
        "command = sys.argv[sys.argv.index('--') + 1:]\n"
        "print(json.dumps({'decision': json.loads(decisions).get(command[0])}))\n"
    )
    path.chmod(0o755)


def _run_install(decisions: dict[str, str]) -> subprocess.CompletedProcess[str]:
    with tempfile.TemporaryDirectory() as temp:
        home = Path(temp) / "home"
        fake_bin = Path(temp) / "bin"
        (home / ".claude").mkdir(parents=True)
        fake_bin.mkdir()
        _fake_codex(fake_bin / "codex", decisions)
        env = os.environ.copy()
        env["HOME"] = str(home)
        env["PATH"] = f"{fake_bin}{os.pathsep}{env['PATH']}"
        return subprocess.run(
            [str(INSTALLER), "--codex", "--dry-run"],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )


def test_failed_codex_validation_is_a_failed_install() -> None:
    result = _run_install({"git": "allow", "sudo": "allow", "rm": "forbidden"})
    output = result.stdout + result.stderr
    assert result.returncode != 0, output
    assert "failed Codex layer" in output
    assert "Install complete" not in output


def test_valid_codex_validation_preserves_success() -> None:
    result = _run_install({"git": "allow", "sudo": "prompt", "rm": "forbidden"})
    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    assert "Install complete" in output
    assert "failed Codex layer" not in output


def main() -> int:
    test_failed_codex_validation_is_a_failed_install()
    test_valid_codex_validation_preserves_success()
    print("OK install Codex validation — 2 tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
