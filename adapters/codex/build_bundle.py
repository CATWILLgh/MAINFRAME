#!/usr/bin/env python3
"""Build the unlinked, self-contained Codex bundle-v2 gate projection."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import asdict
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[2] / "tools"
sys.path.insert(0, str(TOOLS))

from adapter_profiles import load_profiles


def _source_files(source: Path) -> dict[Path, Path]:
    files = {}
    for path in sorted(source.rglob("*")):
        if "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        if path.is_symlink():
            raise ValueError(f"bundle source must not be a symlink: {path}")
        if path.is_file() and path.name != ".DS_Store":
            files[path.relative_to(source)] = path
    return files


def _remove(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        for child in path.iterdir():
            _remove(child)
        path.rmdir()
    else:
        path.unlink(missing_ok=True)


def _sync_tree(source: Path, destination: Path) -> None:
    expected = _source_files(source)
    if destination.is_symlink() or (destination.exists() and not destination.is_dir()):
        _remove(destination)
    destination.mkdir(parents=True, exist_ok=True)
    for path in sorted(destination.rglob("*"), reverse=True):
        relative = path.relative_to(destination)
        if path.is_symlink() and relative not in expected:
            path.unlink()
        elif path.is_file() and relative not in expected:
            path.unlink()
        elif path.is_dir() and not any(path.iterdir()):
            path.rmdir()
    for relative, source_path in expected.items():
        target = destination / relative
        if target.is_symlink() or (target.exists() and not target.is_file()):
            _remove(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target)


def build(root: Path, output: Path) -> None:
    """Materialize one authoritative Codex gate bundle without user-state I/O."""
    if output.is_symlink() or (output.exists() and not output.is_dir()):
        raise ValueError(f"bundle output must be a real directory: {output}")
    detectors = root / "core/gates/detectors"
    rules = root / "core/gates/rules"
    launcher = root / "adapters/codex/gates/bundle-hook.sh"
    for source in (detectors, rules):
        if not source.is_dir():
            raise FileNotFoundError(source)
    if not launcher.is_file():
        raise FileNotFoundError(launcher)

    output.mkdir(parents=True, exist_ok=True)
    for child in output.iterdir():
        if child.name not in {"gates", "mainframe-hook.sh", "bundle.json"}:
            _remove(child)
    gates = output / "gates"
    if gates.is_symlink() or (gates.exists() and not gates.is_dir()):
        _remove(gates)

    _sync_tree(detectors, gates / "detectors")
    _sync_tree(rules, gates / "rules")
    target = output / "mainframe-hook.sh"
    if target.is_symlink() or (target.exists() and not target.is_file()):
        _remove(target)
    shutil.copy2(launcher, target)
    target.chmod(0o755)
    profile = load_profiles(root)["codex"]
    manifest = {"adapter": "codex", **asdict(profile)}
    manifest_path = output / "bundle.json"
    if manifest_path.is_symlink() or (
        manifest_path.exists() and not manifest_path.is_file()
    ):
        _remove(manifest_path)
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    output = args.output or root / "dist/codex/bundle-v2"
    build(root, output)
    print(f"wrote Codex bundle to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
