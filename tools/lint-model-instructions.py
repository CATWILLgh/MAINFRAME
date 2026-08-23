#!/usr/bin/env python3
"""Lint high-confidence lexical hazards in MAINFRAME model instructions.

This checker intentionally implements only deterministic projections of the
human authoring contracts. It does not decide whether an arbitrary absolute is
a valid invariant and never rewrites prompts.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parent.parent
ALLOWLIST_PATH = ROOT / "tools" / "model-instruction-lint-allowlist.json"

ADAPTER_PATTERNS = {
    "claude-code": (
        "adapters/claude-code/export/CLAUDE.md",
        "adapters/claude-code/export/output-styles/*.md",
        "adapters/claude-code/agents/*.md",
        "adapters/claude-code/plugin/skills/*/SKILL.md",
        "adapters/claude-code/optional/skills/*/SKILL.md",
        "adapters/claude-code/dev/skills/*/SKILL.md",
    ),
    "codex": (
        "adapters/codex/export/AGENTS.md",
        "adapters/codex/agents/*.toml.template",
        "adapters/codex/skills/*/SKILL.md",
        "adapters/codex/optional/skills/*/SKILL.md",
        "adapters/codex/dev/skills/*/SKILL.md",
    ),
}

AUTHORING_PATTERN = ".agents/skills/**/*.md"

DISCOVERY_PRESSURE = re.compile(
    r"(?i)(?:\b(?:critical|important)\s*:\s*(?:you\s+)?must\b"
    r"|\byou\s+must\b.{0,100}\b(?:use|call|invoke|delegate)\b)"
)
JUDGMENT_ABSOLUTE = re.compile(
    r"(?i)\b(?:always|must(?:\s+always)?)\s+"
    r"(?:use|call|invoke|delegate|search|ask|clarify)\b"
)
IF_IN_DOUBT = re.compile(
    r"(?i)\bif\s+(?:you(?:'re| are)?\s+)?(?:in\s+)?doubt\b.{0,80}"
    r"\b(?:use|call|invoke|delegate|search|ask)\b"
)
EXPOSE_REASONING = re.compile(
    r"(?i)^\s*(?:[-*+]\s*)?(?:please\s+)?"
    r"(?:show|reveal|display|print|write|transcribe|echo|provide|explain)\b"
    r".{0,120}\b(?:chain[- ]of[- ]thought|private reasoning|internal reasoning|hidden reasoning)\b"
)
BROAD_STYLE = re.compile(
    r"(?i)^\s*(?:[-*+]\s*)?"
    r"(?:be|stay|keep (?:the response|responses|answers?)|write|produce|deliver)\s+"
    r"(?:very\s+)?(?:concise|brief|short|friendly|empathetic|thorough|robust|production[- ]ready)"
    r"[.!]?\s*$"
)


@dataclass(frozen=True)
class Finding:
    rule: str
    level: str
    adapter: str
    file: str
    line: int
    message: str


def relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def discover(adapter: str, include_authoring: bool = True) -> list[tuple[str, Path]]:
    selected = ADAPTER_PATTERNS if adapter == "all" else {adapter: ADAPTER_PATTERNS[adapter]}
    found: set[tuple[str, Path]] = set()
    for owner, patterns in selected.items():
        for pattern in patterns:
            for path in ROOT.glob(pattern):
                if path.is_file():
                    found.add((owner, path.resolve()))
    if include_authoring:
        for path in ROOT.glob(AUTHORING_PATTERN):
            if path.is_file():
                found.add(("authoring", path.resolve()))
    return sorted(found, key=lambda item: (item[0], str(item[1])))


def strip_inline_link_targets(line: str) -> str:
    return re.sub(r"\[([^]]+)\]\([^)]+\)", r"\1", line)


def strip_inline_code(line: str) -> str:
    return re.sub(r"`[^`]*`", "", line)


def load_allowlist() -> list[dict[str, str]]:
    if not ALLOWLIST_PATH.exists():
        return []
    data = json.loads(ALLOWLIST_PATH.read_text(encoding="utf-8"))
    entries = data.get("entries")
    if data.get("schema_version") != 1 or not isinstance(entries, list):
        raise ValueError(f"invalid allowlist schema: {ALLOWLIST_PATH}")
    return entries


def is_allowed(rule: str, path: Path, raw_line: str, allowlist: list[dict[str, str]]) -> bool:
    name = relative(path)
    return any(
        entry.get("rule") == rule
        and entry.get("file") == name
        and entry.get("contains", "") in raw_line
        and bool(entry.get("reason"))
        for entry in allowlist
    )


def frontmatter_lines(lines: list[str]) -> set[int]:
    if not lines or lines[0].strip() != "---":
        return set()
    result: set[int] = set()
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            break
        result.add(index + 1)
    return result


def discovery_lines(path: Path, lines: list[str]) -> set[int]:
    result: set[int] = set()
    if path.suffix == ".md":
        metadata = frontmatter_lines(lines)
        for number in metadata:
            line = lines[number - 1]
            if re.match(r"^\s*(?:description|when_to_use)\s*:", line):
                result.add(number)
    elif path.name.endswith(".toml.template"):
        for number, line in enumerate(lines, 1):
            if re.match(r"^\s*description\s*=", line):
                result.add(number)
    return result


def normalized_instruction_line(line: str) -> str | None:
    value = strip_inline_link_targets(line).strip()
    value = re.sub(r"^[-*+]\s+", "", value)
    value = re.sub(r"\s+", " ", value).strip().casefold()
    if len(value) < 48 or value.startswith(("#", "|", "http://", "https://")):
        return None
    if value in {"authoritative basis", "rules"}:
        return None
    return value


def lexical_findings(adapter: str, line: str, is_discovery: bool) -> list[tuple[str, str, str]]:
    found: list[tuple[str, str, str]] = []
    if is_discovery and DISCOVERY_PRESSURE.search(line):
        found.append((
            "MI-CLAUDE-001" if adapter == "claude-code" else "MI-COMMON-004",
            "error" if adapter == "claude-code" else "warning",
            "aggressive discovery pressure; state the actual selection condition instead",
        ))
    if JUDGMENT_ABSOLUTE.search(line):
        found.append((
            "MI-COMMON-004",
            "warning",
            "absolute wording controls a judgment call; confirm a real invariant or write a decision rule",
        ))
    if adapter == "claude-code" and IF_IN_DOUBT.search(line):
        found.append((
            "MI-CLAUDE-005",
            "warning",
            "blanket uncertainty trigger can overuse tools or skills on current Claude models",
        ))
    if EXPOSE_REASONING.search(line):
        found.append((
            "MI-COMMON-010",
            "error",
            "request conclusions and evidence, not exposed private chain-of-thought",
        ))
    if BROAD_STYLE.search(line):
        found.append((
            "MI-COMMON-005",
            "warning",
            "standalone style label is ambiguous; name the content or writing behavior it must preserve",
        ))
    return found


def lint_file(adapter: str, path: Path) -> list[Finding]:
    lines = path.read_text(encoding="utf-8").splitlines()
    discovery = discovery_lines(path, lines)
    findings: list[Finding] = []
    duplicates: dict[str, int] = {}
    allowlist = load_allowlist()
    in_fence = False

    def add(rule: str, level: str, number: int, message: str) -> None:
        if is_allowed(rule, path, lines[number - 1], allowlist):
            return
        findings.append(Finding(rule, level, adapter, relative(path), number, message))

    for number, raw in enumerate(lines, 1):
        if raw.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence or raw.lstrip().startswith("<!--"):
            continue

        line = strip_inline_code(strip_inline_link_targets(raw))
        for rule, level, message in lexical_findings(adapter, line, number in discovery):
            add(rule, level, number, message)

        normalized = normalized_instruction_line(line)
        if normalized is not None:
            previous = duplicates.get(normalized)
            if previous is not None:
                add(
                    "MI-COMMON-002",
                    "warning",
                    number,
                    f"exact instruction text already appears on line {previous}",
                )
            else:
                duplicates[normalized] = number

    return findings


def lint_paths(paths: Iterable[tuple[str, Path]]) -> list[Finding]:
    findings: list[Finding] = []
    for adapter, path in paths:
        findings.extend(lint_file(adapter, path))
    return findings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true", help="lint all configured instruction surfaces")
    parser.add_argument("--adapter", choices=("all", "claude-code", "codex"), default="all")
    parser.add_argument("--no-authoring", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("paths", nargs="*", type=Path)
    args = parser.parse_args()

    if args.paths:
        paths = [("custom", path.resolve()) for path in args.paths]
    else:
        paths = discover(args.adapter, include_authoring=not args.no_authoring)
    findings = lint_paths(paths)

    if args.json:
        print(json.dumps([asdict(item) for item in findings], indent=2, ensure_ascii=False))
    elif not findings:
        print(f"OK model instructions ({len(paths)} files)")
    else:
        for item in findings:
            print(
                f"{item.level.upper()} {item.rule} {item.file}:{item.line}: "
                f"{item.message}"
            )
        errors = sum(item.level == "error" for item in findings)
        warnings = sum(item.level == "warning" for item in findings)
        print(f"{errors} error(s), {warnings} warning(s), {len(paths)} file(s)")

    return 1 if any(item.level == "error" for item in findings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
