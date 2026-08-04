"""Collision-safe access to Antigravity adapter modules."""

from __future__ import annotations

import importlib.util
import plistlib
import sys
from pathlib import Path
from types import ModuleType


ADAPTER_DIR = Path(__file__).resolve().parent


def load_adapter_module(name: str, filename: str) -> ModuleType:
    path = ADAPTER_DIR / filename
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load Antigravity module {path.name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


compatibility = load_adapter_module(
    "mainframe_antigravity_compatibility", "compatibility.py"
)
runtime = load_adapter_module(
    "mainframe_antigravity_runtime", "gates/mainframe_runtime.py"
)
skill_projection = load_adapter_module(
    "mainframe_antigravity_skill_projection", "skill_projection.py"
)


def validate_native_app(app: Path) -> str:
    plist_path = app / "Contents" / "Info.plist"
    try:
        with plist_path.open("rb") as handle:
            metadata = plistlib.load(handle)
            version = str(metadata["CFBundleShortVersionString"])
            identifier = str(metadata["CFBundleIdentifier"])
    except (OSError, KeyError, plistlib.InvalidFileException) as error:
        raise ValueError(
            f"cannot read Antigravity app metadata: {plist_path}"
        ) from error
    if identifier != compatibility.BUNDLE_IDENTIFIER:
        raise ValueError(
            f"Antigravity bundle identifier {compatibility.BUNDLE_IDENTIFIER} is required; "
            f"found {identifier!r} at {app}"
        )
    if version.split(".", 1)[0] != compatibility.LEGACY_SUPPORTED_MAJOR:
        raise ValueError(
            f"Antigravity major version {compatibility.LEGACY_SUPPORTED_MAJOR} is required; "
            f"found {version} at {app}"
        )
    return version
