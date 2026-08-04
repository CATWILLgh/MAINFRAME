"""Canonical dormant diagnostics resource for adapter release bundles."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from bundle_sync import copy_regular_file


DIAGNOSTICS_SOURCE = Path("core/resources/diagnostics.json")
DIAGNOSTICS_BUNDLE_PATH = Path("diagnostics.json")
DIAGNOSTICS_TARGET_PATH = "mainframe/diagnostics.json"
_TARGET_ROOTS = {
    "antigravity-2": "antigravity-data",
    "claude-code": "claude-config",
    "codex": "codex-config",
    "opencode": "opencode-config",
    "zcode-desktop": "zcode-config",
}


def diagnostics_target(component: str) -> dict[str, str] | None:
    root = _TARGET_ROOTS.get(component)
    if root is None:
        return None
    return {"root": root, "path": DIAGNOSTICS_TARGET_PATH}


def diagnostics_resource(component: str) -> dict[str, Any]:
    target = diagnostics_target(component)
    if target is None:
        raise ValueError(f"unsupported diagnostics component: {component}")
    return {
        "id": f"{component}.diagnostics",
        "strategy": "exact-json-document",
        "source": DIAGNOSTICS_BUNDLE_PATH.as_posix(),
        "target": target,
        "observation": "supported",
        "apply": "supported",
    }


def copy_diagnostics(root: Path, output: Path) -> None:
    copy_regular_file(
        root / DIAGNOSTICS_SOURCE,
        output / DIAGNOSTICS_BUNDLE_PATH,
    )
