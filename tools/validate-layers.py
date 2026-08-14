#!/usr/bin/env python3
"""Validate structural boundaries between shipped Claude agents and skills."""

from __future__ import annotations

import sys
from pathlib import Path

try:
    import yaml
except ImportError as error:
    print(f"validate-layers requires PyYAML: {error}", file=sys.stderr)
    raise SystemExit(2)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
AGENTS_DIR = PROJECT_ROOT / "adapters" / "claude-code" / "agents"
SKILLS_DIR = PROJECT_ROOT / "adapters" / "claude-code" / "plugin" / "skills"
PLUGIN_NAMESPACE = "mainframe:"


def frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    if len(parts) < 3 or parts[0].strip():
        raise ValueError("missing YAML frontmatter")
    value = yaml.safe_load(parts[1]) or {}
    if not isinstance(value, dict):
        raise ValueError("frontmatter must be a mapping")
    return value


def validate(
    agents_dir: Path = AGENTS_DIR,
    skills_dir: Path = SKILLS_DIR,
) -> list[tuple[str, str]]:
    issues: list[tuple[str, str]] = []
    skill_metadata: dict[str, dict] = {}

    for path in sorted(skills_dir.glob("*/SKILL.md")):
        try:
            metadata = frontmatter(path)
        except (OSError, ValueError, yaml.YAMLError) as error:
            issues.append(("error", f"{path}: {error}"))
            continue
        name = metadata.get("name")
        if not isinstance(name, str) or not name:
            continue  # validate-skill owns required-field diagnostics
        if name in skill_metadata:
            issues.append(("error", f"duplicate shipped skill name `{name}`"))
            continue
        skill_metadata[name] = metadata

    for path in sorted(agents_dir.glob("*.md")):
        try:
            metadata = frontmatter(path)
        except (OSError, ValueError, yaml.YAMLError) as error:
            issues.append(("error", f"{path}: {error}"))
            continue

        declared = metadata.get("skills", [])
        if not isinstance(declared, list):
            issues.append(("error", f"{path.name}: `skills` must be a YAML list"))
            continue

        seen: set[str] = set()
        for reference in declared:
            if not isinstance(reference, str) or not reference:
                issues.append(("error", f"{path.name}: every `skills` entry must be a non-empty string"))
                continue
            if not reference.startswith(PLUGIN_NAMESPACE):
                issues.append((
                    "error",
                    f"{path.name}: shipped skill `{reference}` must use the `{PLUGIN_NAMESPACE}` namespace",
                ))
                continue
            name = reference.removeprefix(PLUGIN_NAMESPACE)
            if name in seen:
                issues.append(("error", f"{path.name}: duplicate preloaded skill `{reference}`"))
                continue
            seen.add(name)

            target = skill_metadata.get(name)
            if target is None:
                issues.append(("error", f"{path.name}: preloaded skill `{reference}` does not exist"))
                continue
            if target.get("disable-model-invocation") is True:
                issues.append((
                    "error",
                    f"{path.name}: `{reference}` cannot be preloaded because it disables model invocation",
                ))

    return issues


def main() -> int:
    issues = validate()
    if not issues:
        print("OK agent-skill layer boundaries")
        return 0
    for level, message in issues:
        print(f"{level.upper()} {message}")
    return 1 if any(level == "error" for level, _ in issues) else 0


if __name__ == "__main__":
    raise SystemExit(main())
