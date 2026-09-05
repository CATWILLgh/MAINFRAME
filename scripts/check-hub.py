#!/usr/bin/env python3
"""Validate portable source structure, not installed agent behavior."""

import ast
import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
MARKERS = {
    "MAINFRAME_ROOT", "CREDENTIALS_INDEX", "SUBAGENT_ROLE", "TOOL_SCOPE",
    "MODEL_CHOICE", "HOOK_BINDING", "COMMAND_BINDING",
}


def check_catalog(root, templates, skills):
    errors = []
    resources = (templates / "skills", templates / "hooks/scripts", templates / "hooks/rules")
    units = {str(p.relative_to(root)) for p in templates.rglob("*")
             if p.is_file() and not any(p.is_relative_to(area) for area in resources)}
    units.update(str(p.relative_to(root)) for p in skills)
    units.update({"docs/official-sources.md", "goals/adapt.md", "shared/credentials/"})

    try:
        catalog = json.loads((root / "examples/progress.json").read_text())
    except (OSError, ValueError) as exc:
        return [f"Cannot read progress example: {exc}"]
    if not isinstance(catalog, dict) or set(catalog) != {"items"}:
        return ["Progress example must contain only items"]
    if not isinstance(catalog["items"], list):
        return ["Progress items must be a list"]
    seen = set()
    for row in catalog["items"]:
        if not isinstance(row, dict) or set(row) != {"source", "purpose", "done"}:
            errors.append("Each progress row needs only source, purpose, done")
            continue
        source = row["source"]
        if not isinstance(source, str) or not source or source.startswith("/") or ".." in Path(source).parts:
            errors.append(f"Invalid source: {source!r}")
            continue
        if source in seen:
            errors.append(f"Duplicate source: {source}")
        seen.add(source)
        if not (root / source).exists():
            errors.append(f"Missing source: {source}")
        if row["done"] is not False:
            errors.append(f"Example must start with boolean false: {source}")
        purpose = row["purpose"]
        if not isinstance(purpose, str) or not purpose.strip() or "\n" in purpose or len(purpose) > 280:
            errors.append(f"Purpose must be one short sentence: {source}")
    for source in sorted(units - seen):
        errors.append(f"Unlisted source unit: {source}")
    for source in sorted(seen - units):
        errors.append(f"Unexpected source unit: {source}")

    return errors


def check_skills(root, skills):
    errors = []
    for skill in skills:
        text = skill.read_text()
        match = re.match(r"\A---\nname: ([a-z0-9-]+)\ndescription: ([^\n]+)\n---\n", text)
        if not match:
            errors.append(f"Invalid portable skill header: {skill.relative_to(root)}")
            continue
        name, description = match.groups()
        if name != skill.parent.name or len(name) > 64 or "--" in name or name.startswith("-") or name.endswith("-"):
            errors.append(f"Skill name does not match its directory: {skill}")
        if not description.strip() or len(description) > 1024:
            errors.append(f"Invalid skill description: {skill}")

    return errors


def source_files(root, templates):
    sources = [p for p in templates.rglob("*") if p.is_file() and "__pycache__" not in p.parts]
    for directory in ("goals", "examples", "scripts"):
        sources.extend(p for p in (root / directory).rglob("*") if p.is_file() and "__pycache__" not in p.parts)
    sources.extend(root / p for p in (
        "README.md", "CONTRIBUTING.md", "AGENTS.md", ".agents/repository.json",
        "docs/principles.md", "docs/migration.md", "docs/official-sources.md",
        "shared/credentials/credentials-index.template.md",
    ))
    return sources


def check_sources(root, sources):
    errors = []
    for path in sources:
        rel = str(path.relative_to(root))
        if path.is_symlink() or not path.is_file():
            errors.append(f"Missing or symlinked portable source: {rel}")
            continue
        if path.suffix == ".py":
            try:
                ast.parse(path.read_text(), filename=rel)
            except SyntaxError as exc:
                errors.append(f"Invalid Python: {rel}: {exc}")
        if path.suffix == ".json":
            try:
                json.loads(path.read_text())
            except ValueError as exc:
                errors.append(f"Invalid JSON: {rel}: {exc}")
        if path.suffix != ".md":
            continue
        text = path.read_text()
        for marker in re.findall(r"\{\{([A-Z_]+)\}\}", text):
            if marker not in MARKERS:
                errors.append(f"Unknown adaptation marker {marker}: {rel}")
        # Fenced examples illustrate consumer input, not repository dependencies.
        prose = re.sub(r"(?ms)^```[^\n]*\n.*?^```[^\n]*$", "", text)
        for target in re.findall(r"\[[^\]\n]+\]\(([^)\n]+)\)", prose):
            target = target.strip().strip("<>")
            if urlsplit(target).scheme or target.startswith("#"):
                continue
            target = unquote(target.split("#", 1)[0])
            candidate = (path.parent / target).resolve()
            if not candidate.is_relative_to(root) or not candidate.exists():
                errors.append(f"Broken or escaping reference: {rel} -> {target}")
            elif any(part in {"adapters", "tools", "dev", "workspace", ".local"}
                     for part in candidate.relative_to(root).parts):
                errors.append(f"Reference depends on retired/local runtime: {rel} -> {target}")
    return errors


def check(root):
    root = root.resolve()
    templates = root / "templates"
    skills = sorted((templates / "skills").glob("*/SKILL.md"))
    return (check_catalog(root, templates, skills)
            + check_skills(root, skills)
            + check_sources(root, source_files(root, templates)))


if __name__ == "__main__":
    findings = check(ROOT)
    if findings:
        print("\n".join(findings), file=sys.stderr)
        sys.exit(1)
    count = len(json.loads((ROOT / "examples/progress.json").read_text())["items"])
    print(f"Hub structure valid: {count} source units; catalog, links, skill headers, JSON and Python syntax checked.")
    print("Installed discovery, hooks and model behavior require the native installation goal.")
