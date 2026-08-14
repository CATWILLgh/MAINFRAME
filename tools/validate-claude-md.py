#!/usr/bin/env python3
"""
Validator for the global CLAUDE.md of the MAINFRAME hub.

Checks the repository's CLAUDE.md size, import, link, and agnosticism rules.

Run modes:
  python3 tools/validate-claude-md.py <path>            # CLI: validate a specific file
  python3 tools/validate-claude-md.py <path> --json     # CLI: JSON output

Exit code:
  0 — no errors (warnings allowed)
  1 — errors present
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

# ---------- Configuration ----------

PROJECT_ROOT = Path(__file__).resolve().parent.parent

BLACKLIST_FILE = PROJECT_ROOT / "tools" / "agnostic-blacklist.txt"

MAX_LINES = 200
MAX_IMPORT_DEPTH = 5
OLD_DOMAIN = "docs.anthropic.com/en/docs/claude-code"

# Extract @import tokens from text.
# Take everything after @ up to whitespace/end-of-line/comma/paren.
IMPORT_RE = re.compile(r"@([~/]?[\w][\w./\-~]*)")


# ---------- Import-graph utilities ----------

def strip_html_comments(text: str) -> str:
    """Strip block-level HTML comments — Claude Code strips them before injection."""
    return re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)


def count_non_empty_lines(text: str) -> int:
    return sum(1 for line in text.splitlines() if line.strip())


def resolve_import_path(token: str, base: Path) -> Path:
    """Resolve @path relative to the importing file. Supports ~ and absolute paths."""
    if token.startswith("~"):
        return Path(os.path.expanduser(token)).resolve()
    if token.startswith("/"):
        return Path(token).resolve()
    return (base.parent / token).resolve()


def iter_imports(content: str):
    """
    Walk the lines of content, return [(line_num, token), ...] for all @import.
    Ignores @ inside triple-backtick blocks (there it is an example, not a directive).
    """
    in_code = False
    for line_num, line in enumerate(content.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        # @ must be at the start of the token (not part of an email or mid-word)
        for m in IMPORT_RE.finditer(line):
            # Filter out @ inside words: check there is no letter/digit before @
            start = m.start()
            if start > 0 and line[start - 1].isalnum():
                continue
            token = m.group(1)
            # An import must contain "/" or "." or start with ~/, otherwise it is not a path
            if "/" not in token and "." not in token and not token.startswith("~"):
                continue
            yield line_num, token


def build_import_graph(start: Path) -> tuple[list[tuple[Path, str, int]], list[dict]]:
    """
    Walk the import graph starting from start.
    Returns:
      - graph: [(path, content, depth), ...] for all existing and readable files
      - issues: errors found during the walk (depth exceeded, missing import, not UTF-8)
    """
    graph: list[tuple[Path, str, int]] = []
    issues: list[dict] = []
    visited: set[Path] = set()

    def walk(path: Path, depth: int, origin: Path | None, origin_line: int | None):
        path = path.resolve()
        if path in visited:
            return
        visited.add(path)

        if not path.exists():
            if origin is not None:
                issues.append({
                    "rule": "R4",
                    "level": "error",
                    "file": str(origin),
                    "line": origin_line,
                    "message": f"import `@{path_token_from(origin, path)}` does not exist (resolved: {path}).",
                })
            return

        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            issues.append({
                "rule": "FORMAT",
                "level": "warning",
                "file": str(path),
                "line": None,
                "message": "file is not UTF-8 — skipping.",
            })
            return

        graph.append((path, content, depth))

        # If depth is already at the limit — do not expand further imports,
        # but the fact of exceeding is recorded only on attempt.
        for line_num, token in iter_imports(content):
            child_depth = depth + 1
            if child_depth > MAX_IMPORT_DEPTH:
                issues.append({
                    "rule": "R3",
                    "level": "error",
                    "file": str(path),
                    "line": line_num,
                    "message": f"import depth `@{token}` exceeds {MAX_IMPORT_DEPTH} hops.",
                })
                continue
            child_path = resolve_import_path(token, path)
            walk(child_path, child_depth, origin=path, origin_line=line_num)

    walk(start, 0, origin=None, origin_line=None)
    return graph, issues


def path_token_from(origin: Path, resolved: Path) -> str:
    """Try to reconstruct how exactly the token was written (for a nicer message)."""
    try:
        return str(resolved.relative_to(origin.parent))
    except ValueError:
        return str(resolved)


# ---------- Rules ----------

def check_r1_size(graph: list) -> list[dict]:
    """≤ 200 lines after expanding imports and stripping HTML comments (Anthropic recommendation)."""
    total = 0
    for _, content, _ in graph:
        stripped = strip_html_comments(content)
        total += count_non_empty_lines(stripped)
    if total > MAX_LINES:
        return [{
            "rule": "R1",
            "level": "warning",
            "file": None,
            "line": None,
            "message": (
                f"total size after expanding imports: {total} non-empty lines "
                f"(Anthropic recommendation: ≤ {MAX_LINES}; more → lower adherence and more tokens)."
            ),
        }]
    return []


def check_r2_no_frontmatter(graph: list) -> list[dict]:
    """The root CLAUDE.md must not start with YAML frontmatter (it is only for .claude/rules/)."""
    if not graph:
        return []
    root_path, root_content, _ = graph[0]
    lines = root_content.splitlines()
    if lines and lines[0].strip() == "---":
        return [{
            "rule": "R2",
            "level": "warning",
            "file": str(root_path),
            "line": 1,
            "message": "YAML frontmatter at the start of the file is not documented for the root CLAUDE.md.",
        }]
    return []


def check_r5_old_domain(graph: list) -> list[dict]:
    """No links to the old domain docs.anthropic.com/en/docs/claude-code (returns 301)."""
    issues = []
    for path, content, _ in graph:
        for line_num, line in enumerate(content.splitlines(), 1):
            if OLD_DOMAIN in line:
                issues.append({
                    "rule": "R5",
                    "level": "warning",
                    "file": str(path),
                    "line": line_num,
                    "message": f"link to the old domain `{OLD_DOMAIN}` — replace with `code.claude.com/docs/en`.",
                })
    return issues


def load_blacklist() -> list[str]:
    if not BLACKLIST_FILE.exists():
        return []
    patterns = []
    for line in BLACKLIST_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        patterns.append(line)
    return patterns


def check_r6_agnostic(graph: list) -> list[dict]:
    """Project-agnosticism principle: blacklist in tools/agnostic-blacklist.txt, case-insensitive substring."""
    patterns = load_blacklist()
    if not patterns:
        return []
    issues = []
    for path, content, _ in graph:
        # HTML comments are stripped by Claude — our project-specific notes inside them are allowed.
        active = strip_html_comments(content)
        for line_num, line in enumerate(active.splitlines(), 1):
            line_lower = line.lower()
            for pat in patterns:
                if pat.lower() in line_lower:
                    issues.append({
                        "rule": "R6",
                        "level": "warning",
                        "file": str(path),
                        "line": line_num,
                        "message": f"found pattern `{pat}` — project-specific content in a global file violates the repository's agnosticism rule.",
                    })
    return issues


# ---------- Main logic ----------

def validate_target(target: Path) -> list[dict]:
    """Run all checks for a single target file."""
    if not target.exists():
        return [{
            "rule": "INFO",
            "level": "info",
            "file": str(target),
            "line": None,
            "message": "file does not exist — skipping (this is normal until the hub is assembled).",
        }]

    graph, graph_issues = build_import_graph(target)
    if not graph:
        return graph_issues or [{
            "rule": "INFO",
            "level": "info",
            "file": str(target),
            "line": None,
            "message": "could not read the file.",
        }]

    issues = list(graph_issues)
    issues.extend(check_r1_size(graph))
    issues.extend(check_r2_no_frontmatter(graph))
    issues.extend(check_r5_old_domain(graph))
    issues.extend(check_r6_agnostic(graph))
    return issues


def format_human(target: Path, issues: list[dict]) -> str:
    rel = relpath(target)
    if not issues:
        return f"OK {rel}"

    errors = [i for i in issues if i["level"] == "error"]
    warnings = [i for i in issues if i["level"] == "warning"]
    infos = [i for i in issues if i["level"] == "info"]

    parts = [f"CLAUDE.md validator — {rel}"]
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


def relpath(p: Path) -> str:
    try:
        return str(p.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(p)


def main() -> int:
    parser = argparse.ArgumentParser(description="CLAUDE.md validator per Anthropic rules + MAINFRAME principles.")
    parser.add_argument("path", nargs="?", help="Path to the file to validate (CLI mode).")
    parser.add_argument("--json", action="store_true", help="JSON output (CLI mode).")
    args = parser.parse_args()

    if not args.path:
        parser.print_help()
        return 2

    target = Path(args.path).resolve()
    issues = validate_target(target)

    if args.json:
        print(json.dumps(issues, ensure_ascii=False, indent=2))
    else:
        print(format_human(target, issues))

    has_errors = any(i["level"] == "error" for i in issues)
    return 1 if has_errors else 0


if __name__ == "__main__":
    sys.exit(main())
