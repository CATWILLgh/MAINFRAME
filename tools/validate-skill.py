#!/usr/bin/env python3
"""
Validator for skills in MAINFRAME hub (adapters/claude-code/plugin/skills/**).

Checks Anthropic spec + hub discipline limits (see docs/layers/skills.md).

Run with the project's local venv (which has tiktoken and pyyaml):
  .venv/bin/python3 tools/validate-skill.py <skill_dir>
  .venv/bin/python3 tools/validate-skill.py --all
  .venv/bin/python3 tools/validate-skill.py --from-hook         # reads stdin
  .venv/bin/python3 tools/validate-skill.py --session-start     # short summary

Exit code:
  0 — no errors (warnings allowed)
  1 — at least one error
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# ---- venv import bootstrap ----
PROJECT_ROOT = Path(__file__).resolve().parent.parent
_VENV_SITE = PROJECT_ROOT / ".venv" / "lib"
if _VENV_SITE.exists():
    for site_dir in _VENV_SITE.glob("python*/site-packages"):
        if str(site_dir) not in sys.path:
            sys.path.insert(0, str(site_dir))

try:
    import tiktoken  # type: ignore
    import yaml  # type: ignore
except ImportError as e:
    # Graceful degradation: if deps missing, do not block the hook.
    # Print a hint and exit 0 — user can install when they need validation.
    print(
        f"[validate-skill] skipped: missing dependency ({e}). "
        f"Run: python3 -m venv .venv && .venv/bin/pip install tiktoken pyyaml",
        file=sys.stderr,
    )
    sys.exit(0)


# ---- Configuration ----

SKILLS_DIR = PROJECT_ROOT / "adapters/claude-code/plugin" / "skills"
DEV_SKILLS_DIR = PROJECT_ROOT / "dev" / "skills"

# Limits (see docs/layers/skills.md)
MAX_SKILL_TOKENS = 5000          # body that survives auto-compaction in full
MAX_SKILL_LINES = 500            # Anthropic recommendation at first load
MAX_SUPPORT_TOKENS = 5000        # hub discipline
MAX_SUPPORT_LINES = 60           # hub discipline (distilled snippets)
MAX_DEPTH = 1                    # SKILL.md + one level of supporting files
MAX_DESC_CHARS = 1024            # Anthropic
MAX_DESC_PLUS_WHEN_CHARS = 1536  # Anthropic combined cap

REQUIRED_FRONTMATTER = ("name", "description")

# Anthropic skill name format: lowercase, alphanumeric + dashes/underscores, ≤ 64 chars.
# Leading underscore is allowed — empirically works in Claude Code (verified with _symlink-test canary).
NAME_RE = re.compile(r"^[a-z0-9_][a-z0-9_-]{0,63}$")

# Tokenizer — cl100k_base is the same family Claude uses; counts are close enough
# for our purposes (we set thresholds with safety margin, not exact tracking)
_ENCODER = tiktoken.get_encoding("cl100k_base")


# ---- Helpers ----

def parse_frontmatter(content: str):
    """Return (frontmatter dict or None, body string)."""
    if not content.startswith("---"):
        return None, content
    # Find closing --- on its own line
    lines = content.splitlines(keepends=True)
    if not lines:
        return None, content
    closing_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            closing_idx = i
            break
    if closing_idx is None:
        return None, content
    fm_text = "".join(lines[1:closing_idx])
    body = "".join(lines[closing_idx + 1:])
    try:
        fm = yaml.safe_load(fm_text) or {}
        if not isinstance(fm, dict):
            return None, content
        return fm, body
    except yaml.YAMLError:
        return None, content


def count_tokens(text: str) -> int:
    return len(_ENCODER.encode(text))


def count_non_empty_lines(text: str) -> int:
    return sum(1 for line in text.splitlines() if line.strip())


_MD_LINK_RE = re.compile(r"\[[^\]]+\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
_AT_IMPORT_RE = re.compile(r"(?<![\w@])@([~/]?[\w][\w./\-~]*)")


def extract_referenced_paths(content: str, base: Path):
    """Yield resolved absolute paths referenced from markdown body."""
    # Strip code blocks first — links inside fenced code are examples, not real refs
    stripped = strip_code_fences(content)
    for m in _MD_LINK_RE.finditer(stripped):
        link = m.group(1).strip()
        if link.startswith(("http://", "https://", "mailto:")) or link.startswith("#"):
            continue
        link = link.split("#", 1)[0]  # drop anchor
        if not link:
            continue
        if link.startswith("~"):
            target = Path(link).expanduser().resolve()
        elif link.startswith("/"):
            target = Path(link).resolve()
        else:
            target = (base / link).resolve()
        yield target
    for m in _AT_IMPORT_RE.finditer(stripped):
        token = m.group(1)
        if "/" not in token and "." not in token and not token.startswith("~"):
            continue
        if token.startswith("~"):
            target = Path(token).expanduser().resolve()
        elif token.startswith("/"):
            target = Path(token).resolve()
        else:
            target = (base / token).resolve()
        yield target


def strip_code_fences(content: str) -> str:
    """Drop fenced code blocks (```...```) from content."""
    out = []
    in_fence = False
    for line in content.splitlines():
        if line.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if not in_fence:
            out.append(line)
    return "\n".join(out)


def issue(rule: str, level: str, file: Path, message: str, line: int | None = None) -> dict:
    return {
        "rule": rule,
        "level": level,
        "file": str(file),
        "line": line,
        "message": message,
    }


# ---- Per-skill validation ----

def validate_skill(skill_dir: Path) -> list[dict]:
    """Validate one skill directory. Returns list of issues."""
    skill_dir = skill_dir.resolve()
    if not skill_dir.exists() or not skill_dir.is_dir():
        return [issue("STRUCTURE", "error", skill_dir, "skill directory does not exist or is not a directory")]

    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return [issue("STRUCTURE", "error", skill_dir, "SKILL.md is missing in skill directory")]

    try:
        content = skill_md.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return [issue("FORMAT", "error", skill_md, "SKILL.md is not UTF-8")]

    issues: list[dict] = []

    # Frontmatter
    fm, body = parse_frontmatter(content)
    if fm is None:
        issues.append(issue("FM-PARSE", "error", skill_md,
                            "could not parse YAML frontmatter (must start with '---' and close with '---')", line=1))
        body = content
        fm = {}

    # Required fields
    for field in REQUIRED_FRONTMATTER:
        if field not in fm:
            issues.append(issue("FM-REQUIRED", "error", skill_md,
                                f"required frontmatter field `{field}` is missing"))

    # Name format
    name = fm.get("name", "")
    if name and not NAME_RE.match(str(name)):
        issues.append(issue("NAME-FMT", "error", skill_md,
                            f"name `{name}` must be lowercase alphanumeric with dashes/underscores, ≤ 64 chars"))

    # Name matches directory
    if name and str(name) != skill_dir.name:
        issues.append(issue("NAME-DIR", "warning", skill_md,
                            f"name `{name}` does not match directory name `{skill_dir.name}`"))

    # description length
    desc = str(fm.get("description", ""))
    if desc and len(desc) > MAX_DESC_CHARS:
        issues.append(issue("DESC-LEN", "error", skill_md,
                            f"description is {len(desc)} chars (Anthropic limit {MAX_DESC_CHARS})"))

    # description + when_to_use combined cap
    when = str(fm.get("when_to_use", ""))
    combined_len = len(desc) + len(when)
    if combined_len > MAX_DESC_PLUS_WHEN_CHARS:
        issues.append(issue("DESC-WHEN-LEN", "error", skill_md,
                            f"description+when_to_use is {combined_len} chars (Anthropic cap {MAX_DESC_PLUS_WHEN_CHARS})"))

    # Body size (tokens + lines)
    body_tokens = count_tokens(body)
    if body_tokens > MAX_SKILL_TOKENS:
        issues.append(issue("BODY-TOKENS", "warning", skill_md,
                            f"SKILL.md body is {body_tokens} tokens (post-compaction safe limit {MAX_SKILL_TOKENS})"))

    body_lines = count_non_empty_lines(body)
    if body_lines > MAX_SKILL_LINES:
        issues.append(issue("BODY-LINES", "warning", skill_md,
                            f"SKILL.md body is {body_lines} non-empty lines (Anthropic recommendation ≤ {MAX_SKILL_LINES})"))

    # Supporting files inside the skill directory
    referenced: set[Path] = set()
    for target in extract_referenced_paths(body, skill_md.parent):
        try:
            rel = target.relative_to(skill_dir)
        except ValueError:
            continue  # link points outside the skill dir, ignore
        # Depth = directory levels below skill_dir; SKILL.md itself is depth 0
        depth = len(rel.parts) - 1
        if depth > MAX_DEPTH:
            issues.append(issue("DEPTH", "warning", skill_md,
                                f"reference `{rel}` is at depth {depth} (max {MAX_DEPTH}); Claude may only preview it"))
        referenced.add(target.resolve())

    # All .md files inside the skill dir, except SKILL.md
    for supp in skill_dir.rglob("*"):
        if not supp.is_file():
            continue
        supp_resolved = supp.resolve()
        if supp_resolved == skill_md.resolve():
            continue
        # Skip hidden files / system trash
        if supp.name.startswith(".") or supp.name == "Thumbs.db":
            continue

        # Check size only for text-like extensions
        text_exts = {".md", ".txt", ".yml", ".yaml", ".json"}
        if supp.suffix.lower() in text_exts:
            try:
                supp_content = supp.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                issues.append(issue("FORMAT", "warning", supp, "not UTF-8"))
                continue

            supp_tokens = count_tokens(supp_content)
            if supp_tokens > MAX_SUPPORT_TOKENS:
                issues.append(issue("SUPP-TOKENS", "warning", supp,
                                    f"supporting file is {supp_tokens} tokens (limit {MAX_SUPPORT_TOKENS})"))

            supp_lines = count_non_empty_lines(supp_content)
            if supp_lines > MAX_SUPPORT_LINES:
                issues.append(issue("SUPP-LINES", "warning", supp,
                                    f"supporting file is {supp_lines} non-empty lines (limit {MAX_SUPPORT_LINES})"))

        # Dead-supporting check: file exists but not linked from SKILL.md
        if supp_resolved not in referenced:
            issues.append(issue("DEAD-SUPP", "warning", supp,
                                "file inside skill directory is not referenced from SKILL.md — Claude will not load it"))

    return issues


# ---- Output formatting ----

def relpath(p: Path) -> str:
    try:
        return str(p.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(p)


def format_human(target: Path, issues: list[dict]) -> str:
    rel = relpath(target)
    if not issues:
        return f"OK {rel}"
    errors = [i for i in issues if i["level"] == "error"]
    warnings = [i for i in issues if i["level"] == "warning"]
    infos = [i for i in issues if i["level"] == "info"]
    parts = [f"Validator (skill) — {rel}"]
    for label, bucket in (("errors", errors), ("warnings", warnings), ("info", infos)):
        if not bucket:
            continue
        parts.append(f"\n{label} ({len(bucket)}):")
        for i in bucket:
            loc = ""
            if i.get("file"):
                loc = relpath(Path(i["file"]))
                if i.get("line"):
                    loc += f":{i['line']}"
                loc = f" {loc} —"
            parts.append(f"  [{i['rule']}]{loc} {i['message']}")
    return "\n".join(parts)


# ---- Skill discovery ----

def find_skill_dir_for_file(file_path: Path) -> Path | None:
    """Find the enclosing skill directory — an immediate child of
    adapters/claude-code/plugin/skills/ or dev/skills/. None if outside both roots."""
    for root in (SKILLS_DIR, DEV_SKILLS_DIR):
        try:
            rel = file_path.resolve().relative_to(root.resolve())
        except ValueError:
            continue
        if rel.parts:
            return root / rel.parts[0]
    return None


def all_skill_dirs() -> list[Path]:
    dirs = []
    for root in (SKILLS_DIR, DEV_SKILLS_DIR):
        if root.exists():
            dirs += [p for p in root.iterdir()
                     if p.is_dir() and not p.name.startswith(".")]
    return sorted(dirs)


# ---- Modes ----

def run_session_start() -> int:
    skills = all_skill_dirs()
    if not skills:
        print("## Skills (adapters/claude-code/plugin/skills/ + dev/skills/) — no skills yet")
        return 0
    print("## Skills validation (adapters/claude-code/plugin/skills/ + dev/skills/)")
    for s in skills:
        iss = validate_skill(s)
        errors = [i for i in iss if i["level"] == "error"]
        warnings = [i for i in iss if i["level"] == "warning"]
        rel = relpath(s)
        if not errors and not warnings:
            print(f"- `{rel}` — OK")
        else:
            print(f"- `{rel}` — errors={len(errors)}, warnings={len(warnings)}")
            for i in (errors + warnings)[:2]:
                line_part = f":{i['line']}" if i.get("line") else ""
                print(f"  - [{i['rule']}]{line_part} {i['message']}")
            if len(errors) + len(warnings) > 2:
                print(f"  - … run `.venv/bin/python3 tools/validate-skill.py {rel}` for full report")
    return 0


def run_from_hook() -> int:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    tool_input = data.get("tool_input") or {}
    file_path = tool_input.get("file_path") or tool_input.get("notebook_path")
    if not file_path:
        return 0

    skill_dir = find_skill_dir_for_file(Path(file_path))
    if skill_dir is None:
        return 0  # not under adapters/claude-code/plugin/skills/, exit instantly

    issues = validate_skill(skill_dir)
    if not issues:
        return 0
    print(format_human(skill_dir, issues), file=sys.stderr)
    has_errors = any(i["level"] == "error" for i in issues)
    return 1 if has_errors else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Validator for skills in adapters/claude-code/plugin/skills/.")
    parser.add_argument("path", nargs="?", help="Path to a skill directory or any file inside one.")
    parser.add_argument("--all", action="store_true", help="Validate every skill under adapters/claude-code/plugin/skills/.")
    parser.add_argument("--json", action="store_true", help="JSON output (CLI mode).")
    parser.add_argument("--from-hook", action="store_true", help="PostToolUse hook mode (reads stdin).")
    parser.add_argument("--session-start", action="store_true", help="SessionStart hook mode (short summary).")
    args = parser.parse_args()

    if args.session_start:
        return run_session_start()
    if args.from_hook:
        return run_from_hook()
    if args.all:
        any_error = False
        for s in all_skill_dirs():
            iss = validate_skill(s)
            if args.json:
                print(json.dumps({"skill": relpath(s), "issues": iss}, ensure_ascii=False, indent=2))
            else:
                print(format_human(s, iss))
                print()
            if any(i["level"] == "error" for i in iss):
                any_error = True
        return 1 if any_error else 0

    if not args.path:
        parser.print_help()
        return 2

    target = Path(args.path).resolve()
    # If the user passed a file inside a skill, resolve to the enclosing skill dir
    if target.is_file():
        sd = find_skill_dir_for_file(target)
        if sd is not None:
            target = sd
    issues = validate_skill(target)
    if args.json:
        print(json.dumps(issues, ensure_ascii=False, indent=2))
    else:
        print(format_human(target, issues))
    return 1 if any(i["level"] == "error" for i in issues) else 0


if __name__ == "__main__":
    sys.exit(main())
