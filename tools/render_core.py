#!/usr/bin/env python3
"""Render neutral-core sources into their committed render targets (ADR 0085).

`core/` + `adapters/<tool>/` are the source of truth; `plugin-dist/` (and
later `export/`) stay committed, byte-identical render outputs consumed via
the live `~/.claude` symlinks. Wave 1 covers the gates section.

`--check` is the sole mechanical drift guard: the existing test suites
exercise the RENDERED output, so they pass green on an un-rendered core edit;
only this check distinguishes source from render. CI runs it on every push.
It is bidirectional (a render file with no core source is an orphan) and
covers adapter-owned files, not only `core/`.

Check also lints core-owned sources for naked references to the render path:
a file mentioning `plugin-dist/` while never mentioning the core layout or the
render step teaches the exact edit location this scheme forbids. The allow
tokens are matched file-wide, not per line — wrapped prose splits a reference
across physical lines, so line-level matching false-positives on legitimate
"rendered to …" phrasings; the accepted residual is a false-negative when a
file mixes one naked and one render-aware reference.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# (source, target) relative to the repo root. A directory maps file-by-file
# into the target directory; a file maps 1:1. Every target directory named
# here is fully managed: files in it that no mapping produces are orphans.
GATES_MAPPINGS = [
    ("core/gates/detectors", "plugin-dist/hooks/scripts"),
    ("adapters/claude-code/gates/run-hook.sh", "plugin-dist/hooks/scripts/run-hook.sh"),
    ("core/gates/rules", "plugin-dist/hooks/rules"),
    ("adapters/claude-code/gates/hooks.json", "plugin-dist/hooks/hooks.json"),
]

EXCLUDED_NAMES = {"__pycache__", ".DS_Store"}
EXCLUDED_SUFFIXES = {".pyc"}
LINT_SUFFIXES = {".py", ".sh"}
LINT_NEEDLE = "plugin-dist/"
LINT_ALLOW = ("core/gates", "render")


def _excluded(path: Path) -> bool:
    if path.name in EXCLUDED_NAMES or path.suffix in EXCLUDED_SUFFIXES:
        return True
    return any(part in EXCLUDED_NAMES for part in path.parts)


def _dir_files(directory: Path) -> list[Path]:
    return sorted(p for p in directory.rglob("*") if p.is_file() and not _excluded(p))


def plan(root: Path, mappings) -> list[tuple[Path, Path]]:
    """Expand mappings into concrete (source_file, target_file) pairs."""
    pairs = []
    for src_rel, dst_rel in mappings:
        src = root / src_rel
        dst = root / dst_rel
        if src.is_dir():
            for f in _dir_files(src):
                pairs.append((f, dst / f.relative_to(src)))
        elif src.is_file():
            pairs.append((src, dst))
    return pairs


def _managed_target_dirs(root: Path, mappings) -> list[Path]:
    return [root / dst for src, dst in mappings if (root / src).is_dir()]


def lint(root: Path, mappings) -> list[str]:
    problems = []
    for src_rel, _ in mappings:
        if not src_rel.startswith("core/"):
            continue
        src = root / src_rel
        files = _dir_files(src) if src.is_dir() else ([src] if src.is_file() else [])
        for f in files:
            if f.suffix not in LINT_SUFFIXES:
                continue
            text = f.read_text(encoding="utf-8", errors="replace")
            if LINT_NEEDLE in text and not any(tok in text for tok in LINT_ALLOW):
                line_no = next(
                    i for i, line in enumerate(text.splitlines(), 1) if LINT_NEEDLE in line
                )
                problems.append(
                    f"naked render-path self-reference in {f.relative_to(root)}:{line_no} — "
                    f"mention the core source or the render step, or drop the reference"
                )
    return problems


def check(root: Path, mappings) -> list[str]:
    problems = []
    for src_rel, _ in mappings:
        if not (root / src_rel).exists():
            problems.append(f"source missing: {src_rel}")
    pairs = plan(root, mappings)
    expected = set()
    for src, dst in pairs:
        expected.add(dst)
        if not dst.exists():
            problems.append(f"render missing: {dst.relative_to(root)}")
        elif src.read_bytes() != dst.read_bytes():
            problems.append(f"render differs from source: {dst.relative_to(root)}")
    for managed in _managed_target_dirs(root, mappings):
        if not managed.is_dir():
            continue
        for f in _dir_files(managed):
            if f not in expected:
                problems.append(f"orphan render (no core/adapter source): {f.relative_to(root)}")
    problems.extend(lint(root, mappings))
    return problems


def write(root: Path, mappings) -> list[Path]:
    """Copy stale/missing targets; returns the list of written target paths."""
    written = []
    for src, dst in plan(root, mappings):
        if dst.exists() and src.read_bytes() == dst.read_bytes():
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        written.append(dst)
    return written


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="fail on any source↔render drift")
    mode.add_argument("--write", action="store_true", help="render sources into targets")
    args = parser.parse_args(argv)

    if args.write:
        for path in write(args.root, GATES_MAPPINGS):
            print(f"rendered {path.relative_to(args.root)}")
        return 0

    problems = check(args.root, GATES_MAPPINGS)
    for problem in problems:
        print(problem)
    if problems:
        print(f"{len(problems)} problem(s); render with: python3 tools/render_core.py --write")
        return 1
    print("render targets in sync with core/ + adapters/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
