#!/usr/bin/env python3
"""Build the self-contained MAINFRAME plugin for Antigravity Desktop 2.x."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

import yaml

TOOLS = Path(__file__).resolve().parents[2] / "tools"
sys.path.insert(0, str(TOOLS))

from detector_projection import project_hooklib_fallbacks
from agent_contract import parse_agent_source
from antigravity_modules import compatibility, runtime, skill_projection
from antigravity_modules import validate_native_app
from source_boundary import SourceBoundary, SourcePath


HANDLER_TIMEOUT_SECONDS = runtime.HANDLER_TIMEOUT_SECONDS
BUNDLE_IDENTIFIER = compatibility.BUNDLE_IDENTIFIER
LEGACY_SUPPORTED_MAJOR = compatibility.LEGACY_SUPPORTED_MAJOR
adapt_runtime_markdown = skill_projection.adapt_runtime_markdown
adapt_skill_markdown = skill_projection.adapt_skill_markdown
validate_skill_projection_inventory = skill_projection.validate_skill_projection_inventory
validate_projected_skill_markdown = skill_projection.validate_projected_skill_markdown


ADAPTER_VERSION = "0.1.0"
RULE_MAX_CHARS = 12_000
PLUGIN_COMMAND = "python3 ~/.gemini/config/plugins/mainframe/scripts/mainframe_hook.py"
HOOK_EVENTS = (
    "PreToolUse",
    "PostToolUse",
    "PreInvocation",
    "PostInvocation",
    "Stop",
)
GENERATED_MARKER = "Generated from MAINFRAME hub"
ANTIGRAVITY_FEEDBACK_FALLBACK = (
    'os.path.expanduser("~/.gemini/config/skills/'
    'harness-feedback")')
ANTIGRAVITY_TELEMETRY_FALLBACK = (
    'os.path.expanduser("~/.gemini/antigravity/mainframe-telemetry/telemetry.db")')
ANTIGRAVITY_DIAGNOSTICS_FALLBACK = (
    'os.path.expanduser("~/.gemini/antigravity/mainframe/diagnostics.json")')
DETECTOR_PATH_REWRITES = (
    (
        "~/.claude/hooks/path-validation.py",
        "~/.gemini/config/plugins/mainframe/scripts/detectors/path-validation.py",
    ),
    (
        "# ~/.claude/mainframe is the hub-OWNED namespace (a --dev symlink into the\n"
        "    # hub repo). ~/.claude/telemetry is unusable as an opt-in marker: Claude\n"
        "    # Code itself creates and uses it, so it exists on every machine.",
        "# Antigravity owns this persistent telemetry path independently of plugin files.",
    ),
)

def parse_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end < 0:
        return {}, text
    return yaml.safe_load(text[4:end]) or {}, text[end + 5 :].lstrip("\n")


def _adapt_markdown(text: str) -> str:
    return skill_projection.adapt_runtime_markdown(text)


def _adapt_description(text: str) -> str:
    text = _adapt_markdown(text)
    return re.sub(
        r"\s*Picked via empirical tournament\s*\([^)]*\)\s*—[^.]*\.",
        "",
        text,
    ).strip()


def _json_bytes(data: object) -> bytes:
    return (json.dumps(data, indent=2, sort_keys=True) + "\n").encode()


def _plugin_manifest() -> bytes:
    return _json_bytes(
        {
            "description": "MAINFRAME rules, skills, gates, agents, and memory.",
            "name": "mainframe",
            "version": ADAPTER_VERSION,
        }
    )


def _hooks_manifest() -> bytes:
    namespace = {}
    for event in HOOK_EVENTS:
        handler = {
            "type": "command",
            "command": f"{PLUGIN_COMMAND} {event}",
            "timeout": runtime.HANDLER_TIMEOUT_SECONDS[event],
        }
        if event in {"PreToolUse", "PostToolUse"}:
            namespace[event] = [{"matcher": "*", "hooks": [handler]}]
        else:
            namespace[event] = [handler]
    return _json_bytes({"mainframe": namespace})


def split_rule_text(text: str, limit: int = RULE_MAX_CHARS) -> list[str]:
    """Split on `## ` headings so each part stays inside the host's rule cap.

    The neutral bricks are single files by design; Antigravity is the only host
    that caps an individual rule, so the split belongs to this adapter rather
    than to the shared source layout.
    """
    if len(text) <= limit:
        return [text]
    parts: list[str] = []
    current = ""
    for section in re.split(r"(?m)^(?=## )", text):
        if not section:
            continue
        if len(section) > limit:
            raise ValueError(
                f"Antigravity rule section exceeds {limit} characters"
            )
        if current and len(current) + len(section) > limit:
            parts.append(current)
            current = section
        else:
            current += section
    if current:
        parts.append(current)
    return parts


def _rule_parts(source: SourcePath) -> list[str]:
    try:
        return split_rule_text(source.read_text())
    except ValueError as error:
        raise ValueError(f"{error}: {source.label}") from error


def _collect_rules(root: Path, files: dict[Path, bytes]) -> None:
    sources = (
        ("core", root / "core" / "instructions"),
        ("adapter", root / "adapters" / "antigravity-2" / "instructions"),
    )
    for prefix, directory in sources:
        for source in SourceBoundary(root, directory).files("*.md"):
            parts = _rule_parts(source)
            stem, suffix = source.path.stem, source.path.suffix
            for index, part in enumerate(parts, start=1):
                name = stem if len(parts) == 1 else f"{stem}-{index}"
                files[Path("rules") / f"{prefix}-{name}{suffix}"] = part.encode()


def _copy_tree(
    root: Path, source: Path, target: Path, files: dict[Path, bytes]
) -> None:
    for item in SourceBoundary(root, source).files():
        files[target / item.path.relative_to(source)] = item.read_bytes()


def _project_detector(source: SourcePath, destination: Path) -> bytes:
    text = source.read_text()
    if source.path.name == "_hooklib.py":
        text = project_hooklib_fallbacks(
            text,
            Path(source.label),
            feedback=ANTIGRAVITY_FEEDBACK_FALLBACK,
            telemetry=ANTIGRAVITY_TELEMETRY_FALLBACK,
            diagnostics=ANTIGRAVITY_DIAGNOSTICS_FALLBACK,
        )
    for claude_path, antigravity_path in DETECTOR_PATH_REWRITES:
        text = text.replace(claude_path, antigravity_path)
    if "~/.claude/" in text:
        raise ValueError(
            f"projected Antigravity runtime retains a Claude path: {destination}"
        )
    return text.encode()


def _collect_detectors(root: Path, files: dict[Path, bytes]) -> None:
    source = root / "core" / "gates" / "detectors"
    target = Path("scripts/detectors")
    for item in SourceBoundary(root, source).files():
        destination = target / item.path.relative_to(source)
        files[destination] = _project_detector(item, destination)


def _copy_skill(
    root: Path, source: Path, target: Path, files: dict[Path, bytes]
) -> None:
    for item in SourceBoundary(root, source).files():
        path = item.path
        relative = path.relative_to(source)
        destination = target / relative
        if path.suffix.casefold() != ".md":
            files[destination] = item.read_bytes()
            continue
        meta, body = parse_frontmatter(
            skill_projection.adapt_skill_markdown(
                source.name, relative, item.read_text()
            )
        )
        note = f"<!-- {GENERATED_MARKER} ({path.relative_to(source.parent.parent.parent)}). -->\n\n"
        if relative == Path("SKILL.md"):
            projected = {
                "name": str(meta.get("name") or source.name),
                "description": re.sub(
                    r"\s*Picked via empirical tournament\s*\([^)]*\)\s*—[^.]*\.",
                    "",
                    str(meta.get("description") or ""),
                ).strip(),
            }
            front = yaml.safe_dump(
                projected, allow_unicode=True, sort_keys=False, width=100_000
            ).rstrip()
            files[destination] = f"---\n{front}\n---\n\n{note}{body}".encode()
        else:
            files[destination] = f"{note}{body}".encode()


def _delegate_skill(
    source: SourcePath, known_methods: frozenset[str]
) -> tuple[str, bytes]:
    parsed = parse_agent_source(
        source.read_text(), source=f"core/agents/{source.path.name}"
    )
    contract = parsed.contract
    missing = set(contract.method_skills) - known_methods
    if missing:
        raise ValueError(
            f"core/agents/{source.path.name}: unknown method skills: {sorted(missing)}"
        )
    name = contract.name
    allow_write = contract.needs_write
    allow_mcp = contract.needs_web
    allow_delegate = False
    turn_budget = contract.turn_budget or 20
    method_skills = contract.method_skills
    frontmatter = yaml.safe_dump(
        {
            "name": f"delegate-{name}",
            "description": f"Delegate to the MAINFRAME {name} specialist.",
        },
        allow_unicode=True,
        sort_keys=False,
        width=100_000,
    ).rstrip()
    projected = (
        f"enable_write_tools: {str(allow_write).lower()}\n"
        f"enable_mcp_tools: {str(allow_mcp).lower()}\n"
        f"enable_subagent_tools: {str(allow_delegate).lower()}"
    )
    body = _adapt_markdown(parsed.body.lstrip("\n"))
    description = _adapt_description(contract.description)
    method_requirement = ""
    if method_skills:
        paths = "\n".join(
            f"- `~/.gemini/config/plugins/mainframe/skills/{skill}/SKILL.md`"
            for skill in method_skills
        )
        method_requirement = (
            "Required method skills:\n\n"
            f"{paths}\n\n"
            "Before any task action, the subagent must read every required "
            "method skill above and follow its routing instructions.\n\n"
        )
    rendered = (
        f"---\n{frontmatter}\n---\n\n"
        f"<!-- {GENERATED_MARKER} (core/agents/{source.path.name}). -->\n\n"
        f"# Delegate to {name}\n\n"
        "Call `define_subagent` for this conversation, then immediately call "
        "`invoke_subagent` with the user's bounded task. Use only these "
        "documented capability booleans when defining it:\n\n"
        f"```yaml\n{projected}\n```\n\n"
        f"Soft turn budget: {turn_budget}. Ask the subagent to return "
        "its best grounded result by then, but do not claim runtime enforcement.\n\n"
        "Use the following description and instructions verbatim in the dynamic "
        "subagent definition.\n\n"
        f"Description: {description}\n\n{method_requirement}{body.rstrip()}\n"
    )
    skill_projection.validate_projected_skill_markdown(
        f"core/agents/{source.path.name}", rendered
    )
    return f"delegate-{name}", rendered.encode()


def _collect_skills_and_agents(root: Path, files: dict[Path, bytes]) -> None:
    skills = root / "core" / "skills"
    skill_directories = SourceBoundary(root, skills).directories()
    known_methods = frozenset(skill.name for skill in skill_directories)
    skill_texts = {
        skill.name: {
            source.path.relative_to(skill).as_posix(): source.read_text()
            for source in SourceBoundary(root, skill).files()
            if source.path.suffix.casefold() == ".md"
        }
        for skill in skill_directories
    }
    skill_projection.validate_skill_projection_inventory(skill_texts)
    for skill in skill_directories:
        _copy_skill(root, skill, Path("skills") / skill.name, files)
    agents = root / "core" / "agents"
    for agent in SourceBoundary(root, agents).files("*.md"):
        name, content = _delegate_skill(agent, known_methods)
        files[Path("skills") / name / "SKILL.md"] = content


def _collect_runtime(root: Path, files: dict[Path, bytes]) -> None:
    gate_root = root / "core" / "gates"
    _collect_detectors(root, files)
    _copy_tree(root, gate_root / "rules", Path("scripts/rules"), files)
    _copy_tree(root, root / "core" / "memory", Path("memory"), files)
    hook = root / "adapters" / "antigravity-2" / "gates" / "mainframe_hook.py"
    runtime = hook.with_name("mainframe_runtime.py")
    state = hook.with_name("mainframe_state.py")
    boundary = SourceBoundary(root, hook.parent)
    for source in (hook, runtime, state):
        if not source.exists() and not source.is_symlink():
            raise ValueError(
                f"missing Antigravity hook bridge file: {boundary.label(source)}"
            )
        files[Path("scripts") / source.name] = boundary.file(source).read_bytes()


def render_plugin(root: Path) -> dict[Path, bytes]:
    root = root.resolve(strict=True)
    files: dict[Path, bytes] = {
        Path("hooks.json"): _hooks_manifest(),
        Path("plugin.json"): _plugin_manifest(),
    }
    _collect_rules(root, files)
    _collect_skills_and_agents(root, files)
    _collect_runtime(root, files)
    return dict(sorted(files.items(), key=lambda item: item[0].as_posix()))


def _publish(files: dict[Path, bytes], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{out.name}-", dir=out.parent))
    try:
        for relative, content in files.items():
            destination = staging / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content)
        for relative in (
            Path("scripts/mainframe_hook.py"),
            Path("scripts/mainframe_state.py"),
            Path("memory/store.py"),
        ):
            path = staging / relative
            if path.exists():
                path.chmod(0o755)
        if out.exists():
            shutil.rmtree(out)
        staging.replace(out)
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def _is_current(files: dict[Path, bytes], out: Path) -> bool:
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
    parser.add_argument("--validate-native", action="store_true")
    parser.add_argument("--app", type=Path, default=Path("/Applications/Antigravity.app"))
    args = parser.parse_args(argv)

    root = args.root.resolve()
    out = args.out or root / "dist" / "antigravity-2" / "plugin"
    out = out if out.is_absolute() else root / out
    try:
        version = validate_native_app(args.app) if args.validate_native else None
        files = render_plugin(root)
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    if args.check:
        if _is_current(files, out):
            print(f"Antigravity 2.x plugin is current: {out}")
            return 0
        print(f"Antigravity 2.x plugin drift: {out}", file=sys.stderr)
        return 1
    summary = {"files": len(files), "out": str(out), "nativeVersion": version}
    if args.dry_run:
        print(json.dumps(summary, sort_keys=True))
        return 0
    _publish(files, out)
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
