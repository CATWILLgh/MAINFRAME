#!/usr/bin/env python3
"""Load and apply adapter-owned runtime path profiles."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


PLAN_ROOT_TOKEN = "{{mainframe.plans_root}}"
CONFIG_ROOT_TOKEN = "{{mainframe.config_root}}"
PROFILE_PATH = Path("adapters/runtime-profiles.json")


@dataclass(frozen=True)
class AdapterProfile:
    config_root: str
    skills_root: str
    plans_root: str
    detectors_root: str


def load_profiles(root: Path) -> dict[str, AdapterProfile]:
    source = root / PROFILE_PATH
    raw = json.loads(source.read_text())
    profiles = {name: AdapterProfile(**values) for name, values in raw.items()}
    _validate_profiles(profiles, source)
    return profiles


def project_text(text: str, profile: AdapterProfile) -> str:
    return text.replace(PLAN_ROOT_TOKEN, profile.plans_root).replace(
        CONFIG_ROOT_TOKEN, profile.config_root
    )


def _validate_profiles(
    profiles: dict[str, AdapterProfile], source: Path
) -> None:
    expected = {"claude-code", "codex", "opencode"}
    if set(profiles) != expected:
        raise ValueError(f"{source}: expected profiles {sorted(expected)}")
    for name, profile in profiles.items():
        for field in ("skills_root", "plans_root", "detectors_root"):
            value = getattr(profile, field)
            if not value.startswith(f"{profile.config_root}/"):
                raise ValueError(
                    f"{source}: {name} {field} is outside config_root"
                )
            relative = value[len(profile.config_root) + 1 :]
            if any(part in {".", ".."} for part in relative.split("/")):
                raise ValueError(
                    f"{source}: {name} {field} contains a traversal segment"
                )
        if profile.plans_root != f"{profile.config_root}/plans":
            raise ValueError(f"{source}: {name} plans_root must equal config_root/plans")
