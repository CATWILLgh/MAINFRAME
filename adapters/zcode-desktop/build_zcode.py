#!/usr/bin/env python3
"""Build MAINFRAME's direct-file projection for ZCode Desktop."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

import yaml

TOOLS = Path(__file__).resolve().parents[2] / "tools"
sys.path.insert(0, str(TOOLS))

from agent_contract import AgentContract, parse_agent_source
from skill_projection import (
    PRIVATE_METHODS_DIR,
    UNPROJECTABLE_SKILLS,
    adapt_runtime_text,
    private_method_body,
    project_private_support,
    project_public_skill,
    restricted_skill_names,
    skill_contract,
)


GENERATED_MARKER = "Generated from MAINFRAME hub"
CORE_INSTRUCTION_FILES = (
    "05-title.md",
    "10-partnership.md",
    "15-communication.md",
    "20-honesty.md",
    "25-no-flattery.md",
    "30-thinking-decisions.md",
    "35-evidence-sources.md",
    "40-verification.md",
    "45-output-format.md",
    "50-engineering-practices.md",
    "55-problem-solving.md",
    "60-orchestration.md",
    "80-git-commits.md",
    "85-destructive-actions.md",
)
ADAPTER_INSTRUCTION_FILES = ("00-preamble.md", "90-runtime-zcode-desktop.md")
READ_TOOLS = frozenset({"Glob", "Grep", "Read"})
WRITE_TOOLS = frozenset({"Bash", "Edit", "Write"})
WEB_TOOLS = frozenset({"WebFetch", "WebSearch"})
DEFAULT_PROJECTION_PATH = Path("dist/zcode-desktop/projection")


def _instruction_sources(root: Path) -> list[Path]:
    core_dir = root / "core/instructions"
    adapter_dir = root / "adapters/zcode-desktop/instructions"
    if core_dir.exists():
        unknown = sorted(path.name for path in core_dir.glob("*.md") if path.name not in CORE_INSTRUCTION_FILES)
        if unknown:
            raise ValueError(f"unmapped neutral instruction parts: {', '.join(unknown)}")
    parts = [adapter_dir / ADAPTER_INSTRUCTION_FILES[0]]
    parts.extend(core_dir / name for name in CORE_INSTRUCTION_FILES)
    parts.append(adapter_dir / ADAPTER_INSTRUCTION_FILES[1])
    missing = [path for path in parts if not path.is_file()]
    if missing:
        labels = ", ".join(str(path.relative_to(root)) for path in missing)
        raise ValueError(f"missing ZCode instruction part: {labels}")
    return parts


def render_instructions(root: Path, restricted: frozenset[str]) -> bytes:
    text = "".join(path.read_text() for path in _instruction_sources(root))
    text = adapt_runtime_text(text, restricted)
    if "~/.claude" in text or "dist/claude-code" in text:
        raise ValueError("projected ZCode instructions retain a Claude path")
    return text.encode()


def _collect_skills(
    root: Path,
) -> tuple[dict[str, dict[Path, bytes]], dict[str, tuple[str, dict[Path, bytes]]]]:
    skills_dir = root / "core/skills"
    restricted = restricted_skill_names(skills_dir)
    public = {}
    private = {}
    if not skills_dir.is_dir():
        return public, private
    for skill_dir in sorted(path for path in skills_dir.iterdir() if path.is_dir()):
        source = skill_dir / "SKILL.md"
        if not source.is_file():
            continue
        skill_contract(source)
        name = skill_dir.name
        if name in UNPROJECTABLE_SKILLS:
            continue
        if name in restricted:
            private[name] = (
                private_method_body(skill_dir, restricted),
                project_private_support(skill_dir, restricted),
            )
        else:
            public[name] = project_public_skill(skill_dir, restricted)
    return public, private


def _agent_tools(contract: AgentContract) -> list[str]:
    tools = set()
    if contract.needs_repo_read or contract.needs_write:
        tools.update(READ_TOOLS)
    if contract.needs_write:
        tools.update(WRITE_TOOLS)
    if contract.needs_web:
        tools.update(WEB_TOOLS)
    return sorted(tools)


def _strip_repo_links(text: str) -> str:
    import re

    def replace(match: re.Match[str]) -> str:
        target = match.group(2)
        return match.group(0) if target.startswith(("http://", "https://", "~")) else match.group(1)

    return re.sub(r"\[([^\]]+)\]\(([^)]+)\)", replace, text)


def render_agent(
    contract: AgentContract,
    body: str,
    public_methods: set[str],
    private_methods: dict[str, tuple[str, dict[Path, bytes]]],
    restricted: frozenset[str],
) -> bytes:
    metadata = {
        "name": contract.name,
        "description": adapt_runtime_text(contract.description, restricted),
        "tools": _agent_tools(contract),
    }
    front = yaml.safe_dump(metadata, sort_keys=False, allow_unicode=True, width=100_000).rstrip("\n")
    lead = []
    public = [name for name in contract.method_skills if name in public_methods]
    if public:
        lead.append("Load and apply these MAINFRAME skills as your method: " + ", ".join(f"${name}" for name in public) + ".")
    if contract.turn_budget is not None:
        lead.append(f"Work within roughly {contract.turn_budget} steps; return a partial result instead of running open-endedly.")
    embedded = [
        f"## Private method: {name}\n\n{private_methods[name][0]}"
        for name in contract.method_skills
        if name in private_methods
    ]
    if embedded:
        lead.append(
            "Apply the private methods below. Their supporting files live under "
            f"`~/.zcode/{PRIVATE_METHODS_DIR}/`; they are intentionally absent from "
            "ZCode's skill discovery roots.\n\n" + "\n\n".join(embedded)
        )
    projected_body = _strip_repo_links(adapt_runtime_text(body, restricted)).strip()
    rendered_body = "\n\n".join([*lead, projected_body]).strip()
    note = f"<!-- {GENERATED_MARKER} (core/agents/{contract.name}.md) — do not edit. -->"
    return f"---\n{front}\n---\n\n{note}\n\n{rendered_body}\n".encode()


def _collect_agents(
    root: Path,
    public: dict[str, dict[Path, bytes]],
    private: dict[str, tuple[str, dict[Path, bytes]]],
) -> dict[str, bytes]:
    agents = {}
    known = set(public) | set(private)
    restricted = frozenset(private)
    for path in sorted((root / "core/agents").glob("*.md")):
        source = parse_agent_source(path.read_text(), source=str(path.relative_to(root)))
        missing = sorted(set(source.contract.method_skills) - known)
        if missing:
            raise ValueError(f"{path}: unknown method skills: {missing}")
        agents[source.contract.name] = render_agent(
            source.contract, source.body, set(public), private, restricted
        )
    return agents


def _validate_text_paths(files: dict[Path, bytes]) -> None:
    for path, content in files.items():
        if path.suffix.casefold() not in {".md", ".py", ".js", ".json", ".yaml", ".yml"}:
            continue
        if b"~/.claude" in content or b"dist/claude-code" in content:
            raise ValueError(f"projected ZCode file retains a Claude path: {path}")


def render_projection(root: Path) -> dict[Path, bytes]:
    root = root.resolve(strict=True)
    public, private = _collect_skills(root)
    restricted = frozenset(private)
    agents = _collect_agents(root, public, private)
    files = {Path("AGENTS.md"): render_instructions(root, restricted)}
    for name, tree in public.items():
        for relative, content in tree.items():
            files[Path("skills") / name / relative] = content
    for name, (_, tree) in private.items():
        for relative, content in tree.items():
            files[Path(PRIVATE_METHODS_DIR) / name / relative] = content
    for name, content in agents.items():
        files[Path("agents") / f"{name}.md"] = content
    files = dict(sorted(files.items(), key=lambda item: item[0].as_posix()))
    _validate_text_paths(files)
    return files


def publish_projection(files: dict[Path, bytes], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{out.name}-", dir=out.parent))
    try:
        for relative, content in files.items():
            target = staging / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        if out.exists():
            shutil.rmtree(out)
        staging.replace(out)
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def is_current(files: dict[Path, bytes], out: Path) -> bool:
    if not out.is_dir():
        return False
    existing = {
        path.relative_to(out): path.read_bytes()
        for path in out.rglob("*")
        if path.is_file()
    }
    return existing == files


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--out", type=Path)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    out = args.out or root / DEFAULT_PROJECTION_PATH
    out = out if out.is_absolute() else root / out
    try:
        files = render_projection(root)
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    if args.check:
        if is_current(files, out):
            print(f"ZCode Desktop projection is current: {out}")
            return 0
        print(f"ZCode Desktop projection drift: {out}", file=sys.stderr)
        return 1
    summary = {"files": len(files), "out": str(out)}
    if args.dry_run:
        print(json.dumps(summary, sort_keys=True))
        return 0
    publish_projection(files, out)
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
