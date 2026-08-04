"""Project neutral MAINFRAME skills into ZCode's native skill dialect."""

from __future__ import annotations

import re
from pathlib import Path

import yaml


SUPPORTED_SKILL_FIELDS = ("name", "description", "when_to_use", "license", "metadata")
UNPROJECTABLE_SKILLS = {
    "codex-exec": "delegates work to Codex and is self-contradictory inside ZCode",
}
PRIVATE_METHODS_DIR = "mainframe-agent-methods"
_IGNORED_PARTS = frozenset({"__pycache__", ".DS_Store"})
_IGNORED_SUFFIXES = frozenset({".pyc", ".pyo"})


class _UniqueKeyLoader(yaml.SafeLoader):
    pass


def _construct_mapping(loader: yaml.SafeLoader, node: yaml.MappingNode) -> dict:
    loader.flatten_mapping(node)
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=False)
        if key in result:
            raise ValueError(f"duplicate field: {key}")
        result[key] = loader.construct_object(value_node, deep=False)
    return result


_UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping
)


def parse_frontmatter(text: str, source: str) -> tuple[dict, str]:
    if not text.startswith("---\n"):
        raise ValueError(f"{source}: missing opening frontmatter delimiter")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise ValueError(f"{source}: missing closing frontmatter delimiter")
    try:
        metadata = yaml.load(text[4:end], Loader=_UniqueKeyLoader)
    except (yaml.YAMLError, ValueError) as error:
        raise ValueError(f"{source}: invalid YAML frontmatter: {error}") from None
    if not isinstance(metadata, dict):
        raise ValueError(f"{source}: frontmatter must be a mapping")
    return metadata, text[end + 5 :].lstrip("\n")


def skill_contract(path: Path) -> tuple[dict, str]:
    metadata, body = parse_frontmatter(path.read_text(), str(path))
    name = metadata.get("name") or path.parent.name
    description = metadata.get("description")
    if not isinstance(name, str) or not name.strip():
        raise ValueError(f"{path}: missing name")
    if not isinstance(description, str) or not description.strip():
        raise ValueError(f"{path}: missing description")
    if name != path.parent.name:
        raise ValueError(f"{path}: skill name must match its directory")
    return metadata, body


def restricted_skill_names(skills_dir: Path) -> frozenset[str]:
    names = set()
    if not skills_dir.is_dir():
        return frozenset()
    for path in sorted(skills_dir.glob("*/SKILL.md")):
        metadata, _ = skill_contract(path)
        if metadata.get("disable-model-invocation") is True:
            names.add(path.parent.name)
    return frozenset(names)


def _rewrite_skill_roots(text: str, restricted: frozenset[str]) -> str:
    pattern = re.compile(r"~/.claude/skills/mainframe/skills/([a-z0-9-]+)")

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        root = PRIVATE_METHODS_DIR if name in restricted else "skills"
        return f"~/.zcode/{root}/{name}"

    return pattern.sub(replace, text)


def adapt_runtime_text(text: str, restricted: frozenset[str]) -> str:
    text = _rewrite_skill_roots(text, restricted)
    replacements = (
        ("{{mainframe.plans_root}}", "~/.zcode/plans"),
        ("{{mainframe.config_root}}", "~/.zcode"),
        ("~/.claude/credentials-index.md", "~/.zcode/credentials-index.md"),
        ("~/.claude/plans", "~/.zcode/plans"),
        ("~/.claude/mainframe", "~/.zcode/mainframe"),
        ("~/.claude/", "~/.zcode/"),
        ("../../dist/claude-code/CLAUDE.md", "~/.zcode/AGENTS.md"),
        ("dist/claude-code/CLAUDE.md", "~/.zcode/AGENTS.md"),
        ("CLAUDE.md", "AGENTS.md"),
        ("`EnterPlanMode`", "ZCode Plan Mode"),
        ("`ExitPlanMode`", "explicit plan approval"),
        ("`AskUserQuestion`", "the structured question interaction"),
        ("`TodoWrite`", "a persistent checklist"),
        ("the `Agent` tool", "ZCode subagent dispatch"),
        ("`run_in_background: true`", "background subagent dispatch"),
        ("headless `claude -p`", "headless `zcode --prompt`"),
        ("`advisor()`", "an independent review subagent"),
        ("advisor #1", "independent review checkpoint #1"),
        ("advisor #2", "independent review checkpoint #2"),
        ("Advisor #1", "Independent review checkpoint #1"),
        ("Advisor #2", "Independent review checkpoint #2"),
        ("Claude Code:", "ZCode:"),
    )
    for source, target in replacements:
        text = text.replace(source, target)
    text = re.sub(r"\bpreloaded\b", "provided", text, flags=re.IGNORECASE)
    text = re.sub(r"\badvisor\b", "independent reviewer", text, flags=re.IGNORECASE)
    return text


def _safe_files(skill_dir: Path) -> list[Path]:
    root = skill_dir.resolve(strict=True)
    files = []
    for path in sorted(skill_dir.rglob("*")):
        relative = path.relative_to(skill_dir)
        if any(part in _IGNORED_PARTS for part in relative.parts):
            continue
        if path.suffix in _IGNORED_SUFFIXES:
            continue
        if path.is_symlink():
            resolved = path.resolve(strict=True)
            if not resolved.is_file() or not resolved.is_relative_to(root):
                raise ValueError(f"{path}: skill link escapes its source directory")
        if path.is_file():
            files.append(path)
    return files


def _supported_metadata(metadata: dict, restricted: frozenset[str]) -> dict:
    supported = {}
    for field in SUPPORTED_SKILL_FIELDS:
        if field not in metadata:
            continue
        value = metadata[field]
        supported[field] = (
            adapt_runtime_text(value, restricted) if isinstance(value, str) else value
        )
    return supported


def _render_skill_markdown(
    metadata: dict, body: str, source: str, restricted: frozenset[str]
) -> bytes:
    front = yaml.safe_dump(
        _supported_metadata(metadata, restricted),
        sort_keys=False,
        allow_unicode=True,
        width=100_000,
    ).rstrip("\n")
    note = f"<!-- Generated from MAINFRAME hub ({source}) — do not edit. -->"
    return f"---\n{front}\n---\n\n{note}\n\n{body}".encode()


def project_public_skill(
    skill_dir: Path, restricted: frozenset[str]
) -> dict[Path, bytes]:
    source = skill_dir / "SKILL.md"
    metadata, body = skill_contract(source)
    body = adapt_runtime_text(body, restricted)
    files = {
        Path("SKILL.md"): _render_skill_markdown(
            metadata,
            body,
            f"core/skills/{skill_dir.name}/SKILL.md",
            restricted,
        )
    }
    for path in _safe_files(skill_dir):
        if path == source or path.relative_to(skill_dir) == Path("agents/openai.yaml"):
            continue
        relative = path.relative_to(skill_dir)
        content = path.read_bytes()
        if path.suffix.casefold() == ".md":
            text = adapt_runtime_text(content.decode(), restricted)
            note = (
                f"<!-- Generated from MAINFRAME hub "
                f"(core/skills/{skill_dir.name}/{relative.as_posix()}) — do not edit. -->\n\n"
            )
            content = (note + text).encode()
        files[relative] = content
    return files


def _private_link_target(
    name: str, target: str, restricted: frozenset[str]
) -> str:
    if target.startswith(("#", "/", "~", "http://", "https://")):
        return target
    path, separator, fragment = target.partition("#")
    cross_skill = re.fullmatch(r"\.\./([a-z0-9-]+)/SKILL\.md", path)
    if cross_skill:
        target_name = cross_skill.group(1)
        if target_name in restricted:
            return f"#private-method-{target_name}"
        return f"~/.zcode/skills/{target_name}/SKILL.md"
    runtime = f"~/.zcode/{PRIVATE_METHODS_DIR}/{name}/{path}"
    return runtime + (f"#{fragment}" if separator else "")


def private_method_body(
    skill_dir: Path, restricted: frozenset[str]
) -> str:
    _, body = skill_contract(skill_dir / "SKILL.md")
    body = re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)",
        lambda match: (
            f"[{match.group(1)}]("
            f"{_private_link_target(skill_dir.name, match.group(2), restricted)})"
        ),
        body,
    )
    return adapt_runtime_text(body, restricted).strip()


def project_private_support(
    skill_dir: Path, restricted: frozenset[str]
) -> dict[Path, bytes]:
    files = {}
    for path in _safe_files(skill_dir):
        relative = path.relative_to(skill_dir)
        if relative in {Path("SKILL.md"), Path("agents/openai.yaml")}:
            continue
        content = path.read_bytes()
        if path.suffix.casefold() == ".md":
            content = adapt_runtime_text(content.decode(), restricted).encode()
        files[relative] = content
    return files
