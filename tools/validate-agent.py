#!/usr/bin/env python3
"""Validate MAINFRAME Claude Code file-agent discovery metadata."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
VENV_LIB = PROJECT_ROOT / ".venv" / "lib"
if VENV_LIB.exists():
    for site_dir in VENV_LIB.glob("python*/site-packages"):
        if str(site_dir) not in sys.path:
            sys.path.insert(0, str(site_dir))

try:
    import yaml
except ImportError as error:
    print(f"validate-agent requires PyYAML: {error}", file=sys.stderr)
    raise SystemExit(2)

AGENTS_DIR = PROJECT_ROOT / "adapters" / "claude-code" / "agents"
TARGET_DESCRIPTION_CHARS = 600
MAX_DESCRIPTION_CHARS = 800
EXECUTION_PHRASES = (
    re.compile(r"\brecons? (?:the )?project stack\b", re.IGNORECASE),
    re.compile(r"\bpreloaded?\b", re.IGNORECASE),
    re.compile(r"\bnot eagerly self-dispatched\b", re.IGNORECASE),
    re.compile(r"\binvocation should be\b", re.IGNORECASE),
)
DEPRECATED_TOOLS = {"TodoWrite"}


def frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    if len(parts) < 3 or parts[0].strip():
        raise ValueError("missing YAML frontmatter")
    value = yaml.safe_load(parts[1]) or {}
    if not isinstance(value, dict):
        raise ValueError("frontmatter must be a mapping")
    return value


def validate(path: Path) -> list[tuple[str, str]]:
    issues: list[tuple[str, str]] = []
    try:
        metadata = frontmatter(path)
    except (OSError, ValueError, yaml.YAMLError) as error:
        return [("error", str(error))]

    name = metadata.get("name")
    description = metadata.get("description")
    if not isinstance(name, str) or not name:
        issues.append(("error", "missing string `name`"))
    elif name != path.stem:
        issues.append(("error", f"name `{name}` does not match filename"))
    if not isinstance(description, str) or not description.strip():
        issues.append(("error", "missing string `description`"))
        return issues
    if "when_to_use" in metadata:
        issues.append(("error", "file agents do not support `when_to_use`"))

    tools = metadata.get("tools")
    if isinstance(tools, str):
        tool_names = {part.strip() for part in tools.split(",") if part.strip()}
    elif isinstance(tools, list):
        tool_names = {str(part).strip() for part in tools if str(part).strip()}
    else:
        tool_names = set()
    for tool in sorted(tool_names & DEPRECATED_TOOLS):
        issues.append((
            "error",
            f"deprecated Claude Code tool `{tool}`; omit it or intentionally choose current Task tools",
        ))

    length = len(description)
    if length > MAX_DESCRIPTION_CHARS:
        issues.append(("error", f"description is {length} chars; MAINFRAME maximum is 800"))
    elif length > TARGET_DESCRIPTION_CHARS:
        issues.append(("warning", f"description is {length} chars; target is at most 600"))
    for pattern in EXECUTION_PHRASES:
        if pattern.search(description):
            issues.append(("error", f"execution detail in routing description: `{pattern.pattern}`"))
    return issues


def agent_paths(argument: str | None) -> list[Path]:
    if argument:
        path = Path(argument).expanduser().resolve()
        return [path]
    return sorted(AGENTS_DIR.glob("*.md"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", help="Agent file; omit to validate all agents")
    args = parser.parse_args()
    failed = False
    for path in agent_paths(args.path):
        issues = validate(path)
        if not issues:
            print(f"OK {path.relative_to(PROJECT_ROOT)}")
            continue
        for level, message in issues:
            print(f"{level.upper()} {path.relative_to(PROJECT_ROOT)}: {message}")
            failed = failed or level == "error"
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
