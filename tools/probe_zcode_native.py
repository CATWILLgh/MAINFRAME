#!/usr/bin/env python3
"""Run value-free, temporary-home probes against a ZCode CLI executable."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any


PINNED_VERSION = "0.16.1"
DEFAULT_CLI = Path("/Applications/ZCode.app/Contents/Resources/glm/zcode.cjs")
TIMEOUT_SECONDS = 20


def _command(cli: Path, *arguments: str) -> list[str]:
    prefix = ["node", str(cli)] if cli.suffix == ".cjs" else [str(cli)]
    return [*prefix, *arguments]


def _run(cli: Path, arguments: list[str], home: Path, repo: Path) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["HOME"] = str(home)
    return subprocess.run(
        _command(cli, *arguments),
        cwd=repo,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=TIMEOUT_SECONDS,
    )


def _version(cli: Path, home: Path, repo: Path) -> tuple[str | None, str | None]:
    result = _run(cli, ["--version"], home, repo)
    if result.returncode != 0:
        return None, f"version probe exited {result.returncode}"
    tokens = result.stdout.strip().split()
    if not tokens:
        return None, "version probe returned empty output"
    return tokens[-1], None


def _write_fixture(home: Path, outside: Path) -> None:
    visible_skill = home / ".zcode" / "skills" / "phase-zero-visible"
    hidden_skill = outside / "skills" / "phase-zero-hidden"
    visible_command = home / ".zcode" / "commands" / "phase-zero-visible.md"
    hidden_command = outside / "commands" / "phase-zero-hidden.md"
    visible_skill.mkdir(parents=True)
    hidden_skill.mkdir(parents=True)
    visible_command.parent.mkdir(parents=True)
    hidden_command.parent.mkdir(parents=True)
    visible_skill.joinpath("SKILL.md").write_text(
        "---\nname: phase-zero-visible\ndescription: Hermetic discovery probe.\n---\n\n# Probe\n",
        encoding="utf-8",
    )
    hidden_skill.joinpath("SKILL.md").write_text(
        "---\nname: phase-zero-hidden\ndescription: Must stay invisible.\n---\n\n# Probe\n",
        encoding="utf-8",
    )
    visible_command.write_text("Visible command.\n", encoding="utf-8")
    hidden_command.write_text("Hidden command.\n", encoding="utf-8")


def _discover(cli: Path, kind: str, home: Path, repo: Path) -> tuple[set[str], str | None]:
    result = _run(cli, [kind, "list", "--json", "--cwd", str(repo)], home, repo)
    if result.returncode != 0:
        return set(), f"{kind} probe exited {result.returncode}"
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return set(), f"{kind} probe returned invalid JSON"
    items = payload.get(kind)
    if not isinstance(items, list):
        return set(), f"{kind} probe omitted the {kind} list"
    names = {item.get("name") for item in items if isinstance(item, dict)}
    return {name for name in names if isinstance(name, str)}, None


def probe(cli: Path = DEFAULT_CLI) -> dict[str, Any]:
    if not cli.is_file():
        return {"status": "unavailable", "reason": "ZCode CLI file is absent"}
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        home, repo, outside = root / "home", root / "repo", root / "outside"
        home.mkdir()
        repo.mkdir()
        _write_fixture(home, outside)
        version, failure = _version(cli, home, repo)
        if failure:
            return {"status": "incompatible", "reason": failure}
        if version != PINNED_VERSION:
            return {"status": "incompatible", "version": version, "expected": PINNED_VERSION}
        skills, skills_failure = _discover(cli, "skills", home, repo)
        commands, commands_failure = _discover(cli, "commands", home, repo)
        failures = [item for item in (skills_failure, commands_failure) if item]
        if failures:
            return {"status": "incompatible", "version": version, "reason": "; ".join(failures)}
        return {
            "status": "success",
            "version": version,
            "skills": {
                "visible": "phase-zero-visible" in skills,
                "hidden": "phase-zero-hidden" in skills,
            },
            "commands": {
                "visible": "phase-zero-visible" in commands,
                "hidden": "phase-zero-hidden" in commands,
            },
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cli", type=Path, default=DEFAULT_CLI)
    arguments = parser.parse_args()
    result = probe(arguments.cli)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("status") == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
