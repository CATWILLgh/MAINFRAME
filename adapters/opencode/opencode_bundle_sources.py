#!/usr/bin/env python3
"""Validate and return immutable OpenCode bundle sources."""

from pathlib import Path


def require_sources(
    root: Path,
    validate_agents,
) -> tuple[Path, Path, Path, Path, Path]:
    agents = root / "dist/opencode/AGENTS.md"
    gates = root / "adapters/opencode/plugins/mainframe-gates.js"
    memory = root / "adapters/opencode/plugins/mainframe-memory.js"
    rules = root / "core/permissions/rules.json"
    credentials = root / "core/resources/credentials-index.md"
    directories = (
        root / "core/skills",
        root / "core/gates/detectors",
        root / "core/gates/rules",
        root / "dev/harness-feedback-plugin/skills/harness-feedback",
    )
    if missing := next((source for source in directories if not source.is_dir()), None):
        raise FileNotFoundError(missing)
    files = (agents, gates, memory, rules, credentials)
    for source in files:
        if source.is_symlink() or not source.is_file():
            raise ValueError(f"bundle source must be a regular file: {source}")
    validate_agents(root)
    return files
