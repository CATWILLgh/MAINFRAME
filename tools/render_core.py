#!/usr/bin/env python3
"""Render neutral-core sources into their committed render targets (ADR 0085).

`core/` + `adapters/<tool>/` are the source of truth; `dist/<tool>/` holds
the committed render outputs consumed via the live `~/.claude` symlinks.
Wave 1 sections: gates (byte-copy) and agents
(capability contract → deterministic Claude Code frontmatter + verbatim body,
with optional per-agent overrides in `adapters/claude-code/agents/*.yml`).
Requires pyyaml for the agents section (`.venv` locally, installed in CI);
a missing pyyaml fails LOUDLY (exit 2) — a silent skip would hole the guard.

`--check` is the sole mechanical drift guard: the existing test suites
exercise the RENDERED output, so they pass green on an un-rendered core edit;
only this check distinguishes source from render. CI runs it on every push.
It is bidirectional (a render file with no core source is an orphan) and
covers adapter-owned files, not only `core/`.

Check also lints core-owned sources for naked references to the render path:
a file mentioning `dist/claude-code/plugin/` while never mentioning the core
layout or the render step teaches the exact edit location this scheme forbids. Allow tokens
are matched within a ±2-line window around each reference — wrapped prose
splits a reference across physical lines (same-line matching would
false-positive on legitimate "rendered to …" phrasings), while a window keeps
a naked reference elsewhere in the same file flaggable.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# (source, target) relative to the repo root. A directory maps file-by-file
# into the target directory; a file maps 1:1. Every target directory named
# here is fully managed: files in it that no mapping produces are orphans.
GATES_MAPPINGS = [
    ("core/gates/detectors", "dist/claude-code/plugin/hooks/scripts"),
    ("adapters/claude-code/gates/run-hook.sh", "dist/claude-code/plugin/hooks/scripts/run-hook.sh"),
    ("core/gates/rules", "dist/claude-code/plugin/hooks/rules"),
    ("adapters/claude-code/gates/hooks.json", "dist/claude-code/plugin/hooks/hooks.json"),
]

# Skills render as byte-copies: SKILL.md is a cross-tool standard and foreign
# parsers tolerate the hub's extra frontmatter keys (verified empirically on
# OpenCode). If a future render TRANSFORMS skills, validating core/ stops
# being equivalent to validating the render — revisit validate-skill.py
# targeting then.
SKILLS_MAPPINGS = [
    ("core/skills", "dist/claude-code/plugin/skills"),
]

FILES_MAPPINGS = [
    ("adapters/claude-code/files/output-styles", "dist/claude-code/output-styles"),
    ("adapters/claude-code/files/scripts", "dist/claude-code/scripts"),
    ("adapters/claude-code/files/templates", "dist/claude-code/templates"),
]

PLUGIN_MAPPINGS = [
    ("adapters/claude-code/plugin.json",
     "dist/claude-code/plugin/.claude-plugin/plugin.json"),
]

MAPPINGS = GATES_MAPPINGS + SKILLS_MAPPINGS + FILES_MAPPINGS + PLUGIN_MAPPINGS
EXECUTABLE_MAPPINGS = {
    ("adapters/claude-code/files/scripts/secret", "dist/claude-code/scripts/secret"),
}

# Instructions render by ordered concatenation: core sections + per-tool
# wrapper/mechanics fragments, one shared ordering namespace (the numeric
# prefixes). Both targets are committed renders guarded by --check.
_CORE_SECTIONS = [
    "core/instructions/05-title.md",
    "core/instructions/10-partnership.md",
    "core/instructions/15-communication.md",
    "core/instructions/20-honesty.md",
    "core/instructions/25-no-flattery.md",
    "core/instructions/30-thinking-decisions.md",
    "core/instructions/35-evidence-sources.md",
    "core/instructions/40-verification.md",
    "core/instructions/45-output-format.md",
    "core/instructions/50-engineering-practices.md",
    "core/instructions/55-problem-solving.md",
    "core/instructions/60-orchestration.md",
]
_CORE_TAIL = [
    "core/instructions/80-git-commits.md",
    "core/instructions/85-destructive-actions.md",
]
COMPOSE_MAPPINGS = [
    ("dist/claude-code/CLAUDE.md",
     ["adapters/claude-code/instructions/00-preamble.md"]
     + _CORE_SECTIONS
     + ["adapters/claude-code/instructions/62-orchestration-claude-code.md",
        "adapters/claude-code/instructions/70-memory.md",
        "adapters/claude-code/instructions/75-advisor.md"]
     + _CORE_TAIL),
    ("dist/opencode/AGENTS.md",
     ["adapters/opencode/instructions/00-preamble.md"]
     + _CORE_SECTIONS
     + _CORE_TAIL
     + ["adapters/opencode/instructions/90-runtime-opencode.md"]),
    ("dist/codex/AGENTS.md",
     ["adapters/codex/instructions/00-preamble.md"]
     + _CORE_SECTIONS
     + _CORE_TAIL
     + ["adapters/codex/instructions/90-runtime-codex.md"]),
]

EXCLUDED_NAMES = {"__pycache__", ".DS_Store"}
EXCLUDED_SUFFIXES = {".pyc"}
LINT_SUFFIXES = {".py", ".sh"}
LINT_NEEDLE = "dist/claude-code/plugin/"
LINT_ALLOW = ("core/gates", "core/skills", "render")
LINT_WINDOW = 2


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
            if LINT_NEEDLE not in text:
                continue
            lines = text.splitlines()
            for i, line in enumerate(lines):
                if LINT_NEEDLE not in line:
                    continue
                window = lines[max(0, i - LINT_WINDOW):i + LINT_WINDOW + 1]
                if any(tok in w for tok in LINT_ALLOW for w in window):
                    continue
                problems.append(
                    f"naked render-path self-reference in {f.relative_to(root)}:{i + 1} — "
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
        if (str(src.relative_to(root)), str(dst.relative_to(root))) in EXECUTABLE_MAPPINGS:
            src_mode = src.stat().st_mode & 0o111
            dst_mode = dst.stat().st_mode & 0o111 if dst.exists() else 0
            if not src_mode:
                problems.append(f"source is not executable: {src.relative_to(root)}")
            if dst.exists() and not dst_mode:
                problems.append(f"render is not executable: {dst.relative_to(root)}")
            elif dst.exists() and src_mode != dst_mode:
                problems.append(f"render executable mode differs from source: {dst.relative_to(root)}")
    managed_dirs = [d for d in _managed_target_dirs(root, mappings) if d.is_dir()]
    for managed in managed_dirs:
        for f in _dir_files(managed):
            if f not in expected:
                problems.append(f"orphan render (no core/adapter source): {f.relative_to(root)}")
    # Parents of file-mapped targets (e.g. the hooks/ root holding hooks.json)
    # are managed too, but only their immediate files — subdirectories there
    # are either dir-managed above or out of scope.
    file_parents = {
        (root / dst).parent for src, dst in mappings if (root / src).is_file()
    } - set(managed_dirs)
    for parent in file_parents:
        if not parent.is_dir():
            continue
        for f in sorted(parent.iterdir()):
            if f.is_file() and not _excluded(f) and f not in expected:
                problems.append(f"orphan render (no core/adapter source): {f.relative_to(root)}")
    problems.extend(lint(root, mappings))
    return problems


def write(root: Path, mappings) -> list[Path]:
    """Copy stale/missing targets; returns the list of written target paths."""
    written = []
    for src, dst in plan(root, mappings):
        if dst.exists() and src.read_bytes() == dst.read_bytes():
            pair = (str(src.relative_to(root)), str(dst.relative_to(root)))
            if pair not in EXECUTABLE_MAPPINGS or (src.stat().st_mode & 0o111) == (dst.stat().st_mode & 0o111):
                continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        written.append(dst)
    return written


# Permissions render by KEY-MERGE, not byte-copy: settings.json is BOTH
# hub-owned policy (the allow/deny/ask rules) and a live user-editable config
# surface (model, language, permissions.defaultMode). The hub owns only the
# three rule lists; the render splices them into the file in place, leaving
# every other key as the user left it, and --check compares only those lists.
PERMISSIONS_SOURCE = "core/permissions/rules.json"
PERMISSIONS_TARGET = "dist/claude-code/settings.json"
PERMISSIONS_KEY = "permissions"
PERMISSIONS_RULE_KEYS = ("allow", "deny", "ask")


def _settings_dumps(data: dict) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def _load_rules(source: Path) -> dict:
    """Load the hub rule lists; a source missing any of the three keys is a
    malformed security file, not silent drift — fail loud in both paths."""
    rules = json.loads(source.read_text())
    missing = [k for k in PERMISSIONS_RULE_KEYS if k not in rules]
    if missing:
        raise ValueError(f"{PERMISSIONS_SOURCE} is missing rule key(s): "
                         f"{', '.join(missing)}")
    return rules


def check_permissions(root: Path) -> list[str]:
    source = root / PERMISSIONS_SOURCE
    target = root / PERMISSIONS_TARGET
    if not source.exists() and not target.exists():
        return []
    if not source.exists():
        return [f"source missing: {PERMISSIONS_SOURCE}"]
    if not target.exists():
        return [f"render missing: {PERMISSIONS_TARGET}"]
    rules = _load_rules(source)
    perms = json.loads(target.read_text()).get(PERMISSIONS_KEY, {})
    drifted = [k for k in PERMISSIONS_RULE_KEYS if perms.get(k) != rules[k]]
    if drifted:
        return [f"permissions rules ({', '.join(drifted)}) differ from "
                f"{PERMISSIONS_SOURCE}: {PERMISSIONS_TARGET}"]
    return []


def write_permissions(root: Path) -> list[Path]:
    source = root / PERMISSIONS_SOURCE
    target = root / PERMISSIONS_TARGET
    if not source.exists() or not target.exists():
        return []
    rules = _load_rules(source)
    data = json.loads(target.read_text())
    perms = data.setdefault(PERMISSIONS_KEY, {})
    if all(perms.get(k) == rules[k] for k in PERMISSIONS_RULE_KEYS):
        return []
    for k in PERMISSIONS_RULE_KEYS:
        perms[k] = rules[k]
    target.write_text(_settings_dumps(data))
    return [target]


def _compose(root: Path, parts) -> tuple[str | None, list[str]]:
    missing = [p for p in parts if not (root / p).is_file()]
    if missing:
        return None, [f"compose part missing: {p}" for p in missing]
    return "".join((root / p).read_text() for p in parts), []


def check_compose(root: Path, mappings) -> list[str]:
    problems = []
    for target_rel, parts in mappings:
        target = root / target_rel
        # A tree with neither target nor parts has no instructions layer
        # (fixture trees) — silence is correct; anything partial is a problem.
        if not target.exists() and not any((root / p).exists() for p in parts):
            continue
        composed, missing = _compose(root, parts)
        problems.extend(missing)
        if composed is None:
            continue
        if not target.exists():
            problems.append(f"render missing: {target_rel}")
        elif target.read_text() != composed:
            problems.append(f"render differs from source: {target_rel}")
    return problems


def write_compose(root: Path, mappings) -> list[Path]:
    written = []
    for target_rel, parts in mappings:
        if not any((root / p).exists() for p in parts):
            continue
        composed, missing = _compose(root, parts)
        if missing:
            raise FileNotFoundError("; ".join(missing))
        target = root / target_rel
        if target.exists() and target.read_text() == composed:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(composed)
        written.append(target)
    return written


AGENTS_CORE_DIR = "core/agents"
AGENTS_OVERRIDES_DIR = "adapters/claude-code/agents"
AGENTS_DST_DIR = "dist/claude-code/plugin/agents"

CONTRACT_KEYS = {
    "name", "description", "needs-repo-read", "needs-write", "needs-web",
    "needs-docs-lookup", "reasoning-tier", "turn-budget", "background",
    "method-skills",
}
TIER_TO_MODEL_EFFORT = {
    "deep": ("opus", "high"),
    "standard": ("sonnet", "medium"),
    "light": ("sonnet", "low"),
}
CC_KEY_ORDER = [
    "name", "description", "tools", "model", "effort", "background",
    "maxTurns", "permissionMode", "skills",
]
_DOCS_LOOKUP_TOOLS = [
    "mcp__plugin_context7_context7__resolve-library-id",
    "mcp__plugin_context7_context7__query-docs",
]


def _split_frontmatter(text: str) -> tuple[str, str]:
    if not text.startswith("---\n"):
        raise ValueError("missing frontmatter")
    end = text.index("\n---\n", 4)
    return text[4:end + 1], text[end + 5:]


def derive_cc_meta(contract: dict, override: dict | None = None) -> dict:
    """Capability contract → Claude Code frontmatter dict.

    `review-only` is deliberately folded into `!needs-write` (that is what
    `permissionMode: plan` tracks on every current agent); a future agent that
    needs them split uses an adapter override instead of a new axis.
    """
    tools: list[str] = []
    if contract.get("needs-repo-read"):
        tools.append("Read")
        if contract.get("needs-write"):
            tools += ["Write", "Edit", "Glob", "Grep", "Bash", "TodoWrite"]
        else:
            tools += ["Grep", "Glob"]
    if contract.get("needs-web"):
        tools += ["WebSearch", "WebFetch"]
    if contract.get("needs-docs-lookup"):
        tools += _DOCS_LOOKUP_TOOLS
    model, effort = TIER_TO_MODEL_EFFORT[contract["reasoning-tier"]]
    meta = {
        "name": contract["name"],
        "description": contract["description"],
        "tools": tools,
        "model": model,
        "effort": effort,
    }
    if contract.get("background"):
        meta["background"] = True
    if contract.get("turn-budget"):
        meta["maxTurns"] = int(contract["turn-budget"])
    if not contract.get("needs-write"):
        meta["permissionMode"] = "plan"
    if contract.get("method-skills"):
        meta["skills"] = list(contract["method-skills"])
    for key, value in (override or {}).items():
        meta[key] = value
    return meta


def _emit_cc_frontmatter(meta: dict) -> str:
    lines = []
    for key in CC_KEY_ORDER:
        if key not in meta:
            continue
        value = meta[key]
        if key == "description":
            lines.append(f"description: {json.dumps(value, ensure_ascii=False)}")
        elif key == "skills":
            lines.append("skills:")
            lines.extend(f"  - {s}" for s in value)
        elif isinstance(value, bool):
            lines.append(f"{key}: {'true' if value else 'false'}")
        elif isinstance(value, list):
            lines.append(f"{key}: {', '.join(value)}")
        else:
            lines.append(f"{key}: {value}")
    return "\n".join(lines) + "\n"


def render_agent_file(core_text: str, override: dict | None) -> str:
    import yaml

    fm_text, body = _split_frontmatter(core_text)
    contract = yaml.safe_load(fm_text)
    unknown = set(contract) - CONTRACT_KEYS
    if unknown:
        raise ValueError(f"unknown contract key(s): {', '.join(sorted(unknown))}")
    return "---\n" + _emit_cc_frontmatter(derive_cc_meta(contract, override)) + "---\n" + body


def _agents_items(root: Path):
    import yaml

    core_dir = root / AGENTS_CORE_DIR
    overrides_dir = root / AGENTS_OVERRIDES_DIR
    core_files = sorted(core_dir.glob("*.md")) if core_dir.is_dir() else []
    names = {f.stem for f in core_files}
    strays = [
        f for f in sorted(overrides_dir.glob("*.yml"))
        if f.stem not in names
    ] if overrides_dir.is_dir() else []
    items = []
    for f in core_files:
        override_path = overrides_dir / f"{f.stem}.yml"
        override = (
            yaml.safe_load(override_path.read_text()) if override_path.is_file() else None
        )
        items.append((f, override, root / AGENTS_DST_DIR / f.name))
    return items, strays


def check_agents(root: Path) -> list[str]:
    problems = []
    items, strays = _agents_items(root)
    for stray in strays:
        problems.append(
            f"override without a core agent: {stray.relative_to(root)}")
    expected = set()
    for core_path, override, dst in items:
        expected.add(dst)
        try:
            rendered = render_agent_file(core_path.read_text(), override)
        except ImportError:
            raise
        except Exception as exc:
            problems.append(f"{core_path.relative_to(root)}: {exc!r}")
            continue
        if not dst.exists():
            problems.append(f"render missing: {dst.relative_to(root)}")
        elif dst.read_text() != rendered:
            problems.append(f"render differs from source: {dst.relative_to(root)}")
    dst_dir = root / AGENTS_DST_DIR
    if dst_dir.is_dir():
        for f in sorted(dst_dir.glob("*.md")):
            if f not in expected:
                problems.append(f"orphan render (no core agent): {f.relative_to(root)}")
    return problems


def write_agents(root: Path) -> list[Path]:
    written = []
    items, _ = _agents_items(root)
    for core_path, override, dst in items:
        rendered = render_agent_file(core_path.read_text(), override)
        if dst.exists() and dst.read_text() == rendered:
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(rendered)
        written.append(dst)
    return written


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="fail on any source↔render drift")
    mode.add_argument("--write", action="store_true", help="render sources into targets")
    args = parser.parse_args(argv)

    try:
        return _run(args)
    except ImportError as exc:
        print(f"pyyaml is required (agents section): {exc}")
        return 2


def _run(args) -> int:
    if args.write:
        written = (write(args.root, MAPPINGS) + write_agents(args.root)
                   + write_compose(args.root, COMPOSE_MAPPINGS)
                   + write_permissions(args.root))
        for path in written:
            print(f"rendered {path.relative_to(args.root)}")
        return 0

    problems = (check(args.root, MAPPINGS) + check_agents(args.root)
                + check_compose(args.root, COMPOSE_MAPPINGS)
                + check_permissions(args.root))
    for problem in problems:
        print(problem)
    if problems:
        print(f"{len(problems)} problem(s); render with: python3 tools/render_core.py --write")
        return 1
    print("render targets in sync with core/ + adapters/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
