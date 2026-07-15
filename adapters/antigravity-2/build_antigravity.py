#!/usr/bin/env python3
"""Build the self-contained MAINFRAME plugin for Antigravity Desktop 2.x."""

from __future__ import annotations

import argparse
import json
import plistlib
import re
import shutil
import sys
import tempfile
from pathlib import Path

import yaml


ADAPTER_VERSION = "0.1.0"
BUNDLE_IDENTIFIER = "com.google.antigravity"
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

_RUNTIME_REWRITES = (
    ("~/.claude/skills/mainframe/skills/", "~/.gemini/config/plugins/mainframe/skills/"),
    ("~/.claude/plans", "~/.gemini/antigravity/mainframe-plans"),
    ("`AskUserQuestion`", "ask the user directly in chat"),
    ("`TodoWrite`", "a persistent checklist"),
    ("`EnterPlanMode`", "interactive planning"),
    ("`ExitPlanMode`", "explicit plan approval"),
    ("the `Agent` tool", "`define_subagent` followed by `invoke_subagent`"),
    ("`run_in_background: true`", "background subagent execution"),
    ("`Explore`", "a read-only search subagent"),
    ("`WebSearch`", "web research tools"),
    ("`WebFetch`", "web research tools"),
)


def parse_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end < 0:
        return {}, text
    return yaml.safe_load(text[4:end]) or {}, text[end + 5 :].lstrip("\n")


def _adapt_markdown(text: str) -> str:
    for source, replacement in _RUNTIME_REWRITES:
        text = text.replace(source, replacement)
    text = text.replace(
        "Claude Code's Bash subprocess always reads `~/.zshenv`",
        "The shell subprocess reads `~/.zshenv`",
    )
    text = text.replace(
        "uses `EnterPlanMode` / `ExitPlanMode` when present",
        "uses an explicit interactive planning and approval exchange",
    )
    text = text.replace("](../skills/", "](~/.gemini/config/plugins/mainframe/skills/")
    text = text.replace("preloaded skill", "referenced skill")
    text = text.replace("preloaded `", "referenced `")
    text = text.replace("is preloaded", "is available")
    text = re.sub(r"\bpreloaded\b", "available", text, flags=re.IGNORECASE)
    text = text.replace("`skills:` frontmatter", "delegation contract")
    text = re.sub(
        r"\[CLAUDE\.md\]\(\.\./\.\./dist/claude-code/CLAUDE\.md\)",
        "`MAINFRAME plugin rules`",
        text,
    )
    text = text.replace("CLAUDE.md", "MAINFRAME plugin rules")
    return text


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
        handler = {"type": "command", "command": f"{PLUGIN_COMMAND} {event}"}
        if event in {"PreToolUse", "PostToolUse"}:
            namespace[event] = [{"matcher": "*", "hooks": [handler]}]
        else:
            namespace[event] = [handler]
    return _json_bytes({"mainframe": namespace})


def _read_rule(path: Path) -> bytes:
    text = path.read_text()
    if len(text) > RULE_MAX_CHARS:
        raise ValueError(
            f"Antigravity rule exceeds {RULE_MAX_CHARS} characters: {path}"
        )
    return text.encode()


def _collect_rules(root: Path, files: dict[Path, bytes]) -> None:
    sources = (
        ("core", root / "core" / "instructions"),
        ("adapter", root / "adapters" / "antigravity-2" / "instructions"),
    )
    for prefix, directory in sources:
        if not directory.is_dir():
            continue
        for source in sorted(directory.glob("*.md")):
            files[Path("rules") / f"{prefix}-{source.name}"] = _read_rule(source)


def _projectable_file(path: Path) -> bool:
    return (
        path.is_file()
        and "__pycache__" not in path.parts
        and path.suffix not in {".pyc", ".pyo"}
    )


def _copy_tree(source: Path, target: Path, files: dict[Path, bytes]) -> None:
    if not source.is_dir():
        return
    for path in sorted(item for item in source.rglob("*") if _projectable_file(item)):
        files[target / path.relative_to(source)] = path.read_bytes()


def _copy_skill(source: Path, target: Path, files: dict[Path, bytes]) -> None:
    for path in sorted(item for item in source.rglob("*") if _projectable_file(item)):
        relative = path.relative_to(source)
        destination = target / relative
        if path.suffix != ".md":
            files[destination] = path.read_bytes()
            continue
        meta, body = parse_frontmatter(path.read_text())
        body = _adapt_markdown(body)
        note = f"<!-- {GENERATED_MARKER} ({path.relative_to(source.parent.parent.parent)}). -->\n\n"
        if relative == Path("SKILL.md"):
            projected = {
                "name": str(meta.get("name") or source.name),
                "description": _adapt_description(str(meta.get("description") or "")),
            }
            front = yaml.safe_dump(
                projected, allow_unicode=True, sort_keys=False, width=100_000
            ).rstrip()
            files[destination] = f"---\n{front}\n---\n\n{note}{body}".encode()
        else:
            files[destination] = f"{note}{body}".encode()


def _delegate_skill(source: Path) -> tuple[str, bytes] | None:
    meta, body = parse_frontmatter(source.read_text())
    name = str(meta.get("name") or source.stem)
    description = meta.get("description")
    if not description:
        return None
    allow_write = bool(meta.get("needs-write"))
    allow_mcp = bool(meta.get("needs-mcp") or meta.get("needs-web"))
    allow_delegate = bool(meta.get("needs-delegation", False))
    turn_budget = int(meta.get("turn-budget") or 20)
    method_skills = tuple(str(item) for item in meta.get("method-skills") or ())
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
    body = _adapt_markdown(body)
    description = _adapt_description(str(description))
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
        f"<!-- {GENERATED_MARKER} (core/agents/{source.name}). -->\n\n"
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
    return f"delegate-{name}", rendered.encode()


def _collect_skills_and_agents(root: Path, files: dict[Path, bytes]) -> None:
    skills = root / "core" / "skills"
    if skills.is_dir():
        for skill in sorted(path for path in skills.iterdir() if path.is_dir()):
            _copy_skill(skill, Path("skills") / skill.name, files)
    agents = root / "core" / "agents"
    if agents.is_dir():
        for agent in sorted(agents.glob("*.md")):
            rendered = _delegate_skill(agent)
            if rendered is not None:
                name, content = rendered
                files[Path("skills") / name / "SKILL.md"] = content


def _collect_runtime(root: Path, files: dict[Path, bytes]) -> None:
    gate_root = root / "core" / "gates"
    _copy_tree(gate_root / "detectors", Path("scripts/detectors"), files)
    _copy_tree(gate_root / "rules", Path("scripts/rules"), files)
    _copy_tree(root / "core" / "memory", Path("memory"), files)
    hook = root / "adapters" / "antigravity-2" / "gates" / "mainframe_hook.py"
    state = hook.with_name("mainframe_state.py")
    for source in (hook, state):
        if not source.is_file():
            raise ValueError(f"missing Antigravity hook bridge file: {source}")
        files[Path("scripts") / source.name] = source.read_bytes()


def render_plugin(root: Path) -> dict[Path, bytes]:
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


def validate_native_app(app: Path) -> str:
    plist_path = app / "Contents" / "Info.plist"
    try:
        with plist_path.open("rb") as handle:
            metadata = plistlib.load(handle)
            version = str(metadata["CFBundleShortVersionString"])
            identifier = str(metadata["CFBundleIdentifier"])
    except (OSError, KeyError, plistlib.InvalidFileException) as error:
        raise ValueError(f"cannot read Antigravity app metadata: {plist_path}") from error
    if identifier != BUNDLE_IDENTIFIER:
        raise ValueError(
            f"Antigravity bundle identifier {BUNDLE_IDENTIFIER} is required; "
            f"found {identifier!r} at {app}"
        )
    if version.split(".", 1)[0] != "2":
        raise ValueError(
            f"Antigravity major version 2 is required; found {version} at {app}"
        )
    return version


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
