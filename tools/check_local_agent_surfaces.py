#!/usr/bin/env python3
"""Read-only layout preflight for local Claude Code, Codex, and ZCode surfaces."""

from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path


ADAPTER = Path(__file__).resolve().parents[1] / "adapters/codex"
ZCODE_ADAPTER = Path(__file__).resolve().parents[1] / "adapters/zcode-desktop"
sys.path.insert(0, str(ADAPTER))

import build_codex


def _load_zcode_builder():
    path = ZCODE_ADAPTER / "build_zcode.py"
    spec = importlib.util.spec_from_file_location("mainframe_surface_zcode", path)
    if spec is None or spec.loader is None:
        raise ValueError(f"cannot load ZCode builder: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


build_zcode = _load_zcode_builder()


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


def _zcode_host() -> tuple[Path, str]:
    contract = json.loads((ZCODE_ADAPTER / "capabilities.json").read_text())
    host = contract["host"]
    return Path(host["cli_path"]), host["cli_version"]


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
    zcode_cli, expected_version = _zcode_host()
    if not zcode_cli.is_file():
        failures.append(f"binary: ZCode CLI is missing at {zcode_cli}")
        return
    result = subprocess.run(
        [zcode_cli, "--version"],
        capture_output=True,
        text=True,
        timeout=VERSION_TIMEOUT_SECONDS,
        check=False,
    )
    if result.returncode != 0:
        failures.append("binary: ZCode CLI --version failed")
    elif result.stdout.strip() != expected_version:
        failures.append(
            f"binary: ZCode CLI version is {result.stdout.strip()}, expected {expected_version}"
        )


def _check_codex_agents(
    root: Path, codex_home: Path, restricted: set[str], failures: list[str]
) -> None:
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


def _check_zcode_agents(
    root: Path, zcode_home: Path, restricted: set[str], failures: list[str]
) -> None:
    for source in sorted((root / "core/agents").glob("*.md")):
        target = zcode_home / "agents" / source.name
        _check_file(target, f"zcode agent {source.stem}", failures)
        if not target.is_file():
            continue
        try:
            instructions = target.read_text()
        except (OSError, UnicodeError):
            failures.append(f"zcode agent {source.stem} is unreadable")
            continue
        for method in set(_agent_methods(source)) & restricted:
            if f"Private method: {method}" not in instructions:
                failures.append(
                    f"zcode agent {source.stem} lacks private method {method}"
                )


def check_layout(
    root: Path,
    claude_home: Path,
    codex_home: Path,
    zcode_home: Path,
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
    zcode_public = (
        {source.parent.name for source in skill_sources}
        - restricted
        - set(build_zcode.UNPROJECTABLE_SKILLS)
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

    _check_file(zcode_home / "AGENTS.md", "zcode global instructions", failures)
    for name in sorted(zcode_public):
        _check_file(
            zcode_home / "skills" / name / "SKILL.md",
            f"zcode public skill {name}",
            failures,
        )
    for name in sorted(restricted):
        global_path = zcode_home / "skills" / name
        if global_path.exists() or global_path.is_symlink():
            failures.append(f"zcode restricted skill is globally visible: {name}")

    _check_codex_agents(root, codex_home, restricted, failures)
    _check_zcode_agents(root, zcode_home, restricted, failures)

    if check_binaries:
        _check_binaries(failures)
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).parents[1])
    parser.add_argument("--claude-home", type=Path, default=Path.home() / ".claude")
    parser.add_argument("--codex-home", type=Path, default=Path.home() / ".codex")
    parser.add_argument("--zcode-home", type=Path, default=Path.home() / ".zcode")
    parser.add_argument("--skip-binaries", action="store_true")
    args = parser.parse_args(argv)
    failures = check_layout(
        args.root.resolve(),
        args.claude_home.expanduser(),
        args.codex_home.expanduser(),
        args.zcode_home.expanduser(),
        check_binaries=not args.skip_binaries,
    )
    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        return 1
    print("PASS: local Claude Code, Codex, and ZCode filesystem contracts are ready")
    return 0


if __name__ == "__main__":
    sys.exit(main())
