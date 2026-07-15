#!/usr/bin/env python3
"""Build the unlinked, self-contained Codex bundle-v2 gate projection."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[2] / "tools"
sys.path.insert(0, str(TOOLS))

from adapter_profiles import load_profiles
from bundle_sync import (
    copy_regular_file,
    prepare_output_root,
    remove_path,
    sync_tree,
)
import build_codex


def build(root: Path, output: Path) -> None:
    """Materialize one authoritative Codex gate bundle without user-state I/O."""
    detectors = root / "core/gates/detectors"
    rules = root / "core/gates/rules"
    launcher = root / "adapters/codex/gates/bundle-hook.sh"
    for source in (detectors, rules):
        if not source.is_dir():
            raise FileNotFoundError(source)
    if not launcher.is_file():
        raise FileNotFoundError(launcher)

    prepare_output_root(
        output, {"gates", "skills", "mainframe-hook.sh", "bundle.json"}
    )
    gates = output / "gates"
    if gates.is_symlink() or (gates.exists() and not gates.is_dir()):
        remove_path(gates)

    sync_tree(detectors, gates / "detectors")
    sync_tree(rules, gates / "rules")
    profile = load_profiles(root)["codex"]
    skills, _ = build_codex.collect_skills(root, profile)
    with tempfile.TemporaryDirectory() as temporary:
        staged_skills = Path(temporary) / "skills"
        build_codex.write_skills(staged_skills, skills)
        sync_tree(staged_skills, output / "skills")
    copy_regular_file(launcher, output / "mainframe-hook.sh", executable=True)
    manifest = {"adapter": "codex", **asdict(profile)}
    manifest_path = output / "bundle.json"
    if manifest_path.is_symlink() or (
        manifest_path.exists() and not manifest_path.is_file()
    ):
        remove_path(manifest_path)
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
