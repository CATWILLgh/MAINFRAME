#!/usr/bin/env python3
"""Read-only layout preflight for local Claude Code and Codex surfaces."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path


ADAPTER = Path(__file__).resolve().parents[1] / "adapters/codex"
sys.path.insert(0, str(ADAPTER))

import build_codex


PRIVATE_METHODS_DIR = "mainframe-agent-methods"
VERSION_TIMEOUT_SECONDS = 10


def _frontmatter(text: str) -> str:
    if not text.startswith("---\n"):
        return ""
    end = text.find("\n---\n", 4)
    return "" if end < 0 else text[4:end]


def _restricted_skills(root: Path) -> set[str]:
    restricted = set()
    for source in (root / "core/skills").glob("*/SKILL.md"):
        if "\ndisable-model-invocation: true\n" in f"\n{_frontmatter(source.read_text())}\n":
            restricted.add(source.parent.name)
    return restricted


def _agent_methods(source: Path) -> list[str]:
    lines = _frontmatter(source.read_text()).splitlines()
    methods = []
    inside = False
    for line in lines:
        if line == "method-skills:":
            inside = True
            continue
        if inside and line.startswith("  - "):
            methods.append(line[4:].strip())
            continue
        if inside and line and not line.startswith(" "):
            break
    return methods


def _check_file(path: Path, label: str, failures: list[str]) -> None:
    if not path.is_file():
        failures.append(f"{label}: missing {path}")


def _check_binaries(failures: list[str]) -> None:
    for binary in ("claude", "codex"):
        resolved = shutil.which(binary)
        if not resolved:
            failures.append(f"binary: {binary} is not on PATH")
            continue
        result = subprocess.run(
            [resolved, "--version"],
            capture_output=True,
            text=True,
            timeout=VERSION_TIMEOUT_SECONDS,
            check=False,
        )
        if result.returncode != 0:
            failures.append(f"binary: {binary} --version failed")


def check_layout(
    root: Path,
    claude_home: Path,
    codex_home: Path,
    *,
    check_binaries: bool,
) -> list[str]:
    failures: list[str] = []
    skill_sources = sorted((root / "core/skills").glob("*/SKILL.md"))
    restricted = _restricted_skills(root)
    public = (
        {source.parent.name for source in skill_sources}
        - restricted
        - set(build_codex.UNPROJECTABLE_SKILLS)
    )

    for source in skill_sources:
        name = source.parent.name
        _check_file(
            claude_home / "skills/mainframe/skills" / name / "SKILL.md",
            f"claude skill {name}",
            failures,
        )
    for name in sorted(public):
        _check_file(
            codex_home / "skills" / name / "SKILL.md",
            f"codex public skill {name}",
            failures,
        )
    for name in sorted(restricted):
        global_path = codex_home / "skills" / name
        if global_path.exists() or global_path.is_symlink():
            failures.append(f"codex restricted skill is globally visible: {name}")
        _check_file(
            codex_home / PRIVATE_METHODS_DIR / name / "SKILL.md",
            f"codex private method {name}",
            failures,
        )

    for source in sorted((root / "core/agents").glob("*.md")):
        target = codex_home / "agents" / f"{source.stem}.toml"
        _check_file(target, f"codex agent {source.stem}", failures)
        if not target.is_file():
            continue
        try:
            instructions = tomllib.loads(target.read_text()).get(
                "developer_instructions", ""
            )
        except (OSError, UnicodeError, tomllib.TOMLDecodeError):
            failures.append(f"codex agent {source.stem} has invalid TOML")
            continue
        for method in set(_agent_methods(source)) & restricted:
            if f"Private method: {method}" not in instructions:
                failures.append(
                    f"codex agent {source.stem} lacks private method {method}"
                )

    if check_binaries:
        _check_binaries(failures)
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).parents[1])
    parser.add_argument("--claude-home", type=Path, default=Path.home() / ".claude")
    parser.add_argument("--codex-home", type=Path, default=Path.home() / ".codex")
    parser.add_argument("--skip-binaries", action="store_true")
    args = parser.parse_args(argv)
    failures = check_layout(
        args.root.resolve(),
        args.claude_home.expanduser(),
        args.codex_home.expanduser(),
        check_binaries=not args.skip_binaries,
    )
    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        return 1
    print("PASS: local Claude Code and Codex filesystem contracts are ready")
    return 0


if __name__ == "__main__":
    sys.exit(main())
