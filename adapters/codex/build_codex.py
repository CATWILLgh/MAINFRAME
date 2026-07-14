#!/usr/bin/env python3
"""Project MAINFRAME skills and permissions into Codex's native layout.

Sources: ``core/skills/*`` and ``core/permissions/rules.json``. Outputs:
``dist/codex/skills/<name>/`` and ``dist/codex/rules/mainframe.rules``.
The installer links those artifacts item-by-item into ``$CODEX_HOME``.

The permission projection is deliberately conservative. Codex rules match
shell-command argv prefixes only, so every source rule without an exact,
safe prefix projection is omitted and reported.

Run: ``.venv/bin/python3 adapters/codex/build_codex.py --root . [--dry-run]``
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import sys
import textwrap
from pathlib import Path

import yaml


GENERATED_MARKER = "Generated from MAINFRAME hub"
_MD_NOTE = (
    "<!-- {marker} ({source}) — do not edit; regenerate via "
    "./install.sh --codex. -->"
)
_YAML_NOTE = (
    "# {marker} ({source}) — do not edit; regenerate via "
    "./install.sh --codex."
)

# These are runtime/harness operations, not reusable domain methods. Keeping
# the complete known set makes the filter testable even when a source is not
# present in this checkout.
UNPROJECTABLE_SKILLS = {
    "claude-code-research": "research workflow depends on Claude Code-specific harness behavior",
    "keybindings-help": "edits Claude Code keybindings and has no Codex Phase-1 analogue",
    "task-workflow": "core workflow depends on Claude Code plan mode, advisor, Agent, AskUserQuestion, and TodoWrite",
    "update-config": "mutates Claude Code configuration and has no Codex Phase-1 analogue",
}

_PRELOAD_REWRITES = [
    (re.compile(r"\bPreloaded into the `[^`]+` sub-agent\.?", re.I),
     "Load explicitly with `${name}` before applying this method."),
    (re.compile(r"\bLoaded by the `[^`]+` agent only; closed to main-context auto-invocation\.?", re.I),
     "Load explicitly with `${name}` when this method is needed."),
    (re.compile(r"Triggered via agent frontmatter `skills:` preload,? not by direct user invocation\.?") ,
     "Invoke explicitly with `${name}`; Codex does not preload skills."),
    (re.compile(r"Triggered via agent frontmatter `skills:` preload,? not direct user invocation\.?") ,
     "Invoke explicitly with `${name}`; Codex does not preload skills."),
    (re.compile(r"\balso preloaded\b", re.I), "also loaded explicitly"),
    (re.compile(r"\bpreloaded\b", re.I), "loaded explicitly"),
]


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Split a Markdown document into frontmatter and body."""
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end < 0:
        return {}, text
    return yaml.safe_load(text[4:end]) or {}, text[end + 5:].lstrip("\n")


def is_projectable(name: str) -> bool:
    return name not in UNPROJECTABLE_SKILLS


def _rewrite_codex_prose(text: str, name: str) -> str:
    """Remove Claude Code runtime assumptions while preserving the method."""
    text = text.replace("~/.claude/skills/mainframe/skills/", "~/.codex/skills/")
    text = text.replace("~/.claude/", "~/.codex/")
    text = text.replace("CLAUDE.md", "AGENTS.md")
    text = text.replace("Direct reads of the credentials store are denied by `settings.json` patterns.",
                        "Direct reads of the credentials store are forbidden by policy; Codex `.rules` cannot express path-glob read denials.")
    text = text.replace("Direct read of `~/.ssh/id_*` / `~/.netrc` is denied.",
                        "Direct read of `~/.ssh/id_*` / `~/.netrc` is forbidden by policy.")
    text = text.replace("Direct read denied.", "Direct read forbidden by policy.")
    text = text.replace(
        "These are enforced by `permissions.deny` in `settings.json` and by `path-validation.py` (PreToolUse hook). The skill is the policy; the hook is the safety net.",
        "These are policy requirements. Codex Phase 1 has no path-glob read-rule equivalent, so `mainframe.rules` does not enforce them.")
    text = text.replace("# denied by hook", "# forbidden by policy")
    text = re.sub(
        r"^- `path-validation\.py` \(PreToolUse hook\).*$\n?",
        "- Codex Phase 1 has no path-validation hook; direct-read safety depends on this policy.\n",
        text, flags=re.M)
    text = re.sub(
        r"^- `secret-commit-gate\.py` \(PreToolUse hook\).*$\n?",
        "- Codex Phase 1 has no secret-commit hook; inspect staged changes before committing.\n",
        text, flags=re.M)
    text = text.replace(
        "the auto-mode classifier evaluates each tool call in isolation, cannot see conversational authorization, and hard-denies cross-project credential reads (witnessed 2026-06-15); and ",
        "direct reads would bypass the managed credential flow; ")
    text = text.replace(
        "Claude Code's Bash subprocess always reads `~/.zshenv` (not `.zshrc`), so the secrets are present in env for all commands you run, including unattended auto-runs.",
        "A Codex shell may inherit variables loaded by `~/.zshenv`; verify the variable exists and do not assume every shell startup path sourced it.")
    text = text.replace("Claude Code", "Codex")
    text = text.replace("current Bash subprocess state", "current shell state")
    text = re.sub(r"`Explore` subagent \(the built-in read-only\s+search agent\)",
                  "explicit read-only sub-agent", text)
    text = text.replace("(`Read`/`Grep`/`Glob`)",
                        "(file-reading and search tools)")
    text = text.replace("Co-Authored-By: Claude", "Co-Authored-By: AI")
    text = text.replace("Claude / AI", "AI")
    for rx, replacement in _PRELOAD_REWRITES:
        text = rx.sub(replacement.format(name=name), text)
    return text


def _skill_title(body: str, name: str) -> str:
    match = re.search(r"^#\s+(.+?)\s*$", body, re.M)
    return match.group(1).strip() if match else name.replace("-", " ").title()


def _short_description(description: str) -> str:
    compact = re.sub(r"\s+", " ", description).strip()
    first = re.split(r"(?<=[.!?])\s+", compact, maxsplit=1)[0]
    return textwrap.shorten(first, width=100, placeholder="…")


def _default_prompt(name: str, description: str) -> str:
    compact = re.sub(r"\s+", " ", description).strip()
    first = re.split(r"(?<=[.!?])\s+", compact, maxsplit=1)[0]
    verb = first.split(" ", 1)[0].lower().rstrip(":") if first else ""
    if verb in {"apply", "audit", "create", "design", "operate", "persist",
                "produce", "run", "use", "verify"}:
        phrase = textwrap.shorten(first[0].lower() + first[1:], width=120,
                                  placeholder="…").rstrip(".")
    else:
        phrase = "apply this skill's guidance to the current task"
    return f"Use ${name} to {phrase}."


def _openai_yaml(name: str, title: str, description: str) -> str:
    source = f"core/skills/{name}/SKILL.md"
    values = {
        "display_name": title,
        "short_description": _short_description(description),
        "default_prompt": _default_prompt(name, description),
    }
    lines = [_YAML_NOTE.format(marker=GENERATED_MARKER, source=source),
             "interface:"]
    for key, value in values.items():
        lines.append(f"  {key}: {json.dumps(value, ensure_ascii=False)}")
    return "\n".join(lines) + "\n"


def render_skill_dir(skill_dir: Path) -> dict[Path, bytes]:
    """Render one skill directory, including relative resources it needs."""
    source = skill_dir / "SKILL.md"
    meta, body = parse_frontmatter(source.read_text())
    name = str(meta.get("name") or skill_dir.name)
    description = str(meta.get("description") or "").strip()
    if not description:
        raise ValueError(f"{source}: missing description")
    body = _rewrite_codex_prose(body, name)
    description = _rewrite_codex_prose(description, name)
    front = yaml.safe_dump({"name": name, "description": description},
                           sort_keys=False, allow_unicode=True,
                           width=100000).rstrip("\n")
    note = _MD_NOTE.format(marker=GENERATED_MARKER,
                           source=f"core/skills/{skill_dir.name}/SKILL.md")
    files: dict[Path, bytes] = {
        Path("SKILL.md"): f"---\n{front}\n---\n\n{note}\n\n{body}".encode(),
    }

    for path in sorted(skill_dir.rglob("*")):
        if not path.is_file() or path == source:
            continue
        rel = path.relative_to(skill_dir)
        if rel == Path("agents/openai.yaml"):
            continue
        if path.suffix.lower() == ".md":
            aux_note = _MD_NOTE.format(
                marker=GENERATED_MARKER,
                source=f"core/skills/{skill_dir.name}/{rel.as_posix()}")
            rendered = aux_note + "\n\n" + _rewrite_codex_prose(
                path.read_text(), name)
            files[rel] = rendered.encode()
        else:
            files[rel] = path.read_bytes()

    title = _skill_title(body, name)
    files[Path("agents/openai.yaml")] = _openai_yaml(
        name, title, description).encode()
    return files


def collect_skills(root: Path) -> tuple[list[tuple[str, dict[Path, bytes]]], list[tuple[str, str]]]:
    skills_dir = root / "core" / "skills"
    rendered = []
    dropped = []
    if not skills_dir.is_dir():
        return rendered, dropped
    for skill_dir in sorted(p for p in skills_dir.iterdir() if p.is_dir()):
        if not (skill_dir / "SKILL.md").is_file():
            continue
        if not is_projectable(skill_dir.name):
            dropped.append((skill_dir.name, UNPROJECTABLE_SKILLS[skill_dir.name]))
            continue
        rendered.append((skill_dir.name, render_skill_dir(skill_dir)))
    return rendered, dropped


def _split_bash(entry: str) -> str | None:
    if not entry.startswith("Bash(") or not entry.endswith(")"):
        return None
    return entry[5:-1]


def _argv_prefix(entry: str) -> tuple[list[str] | None, str | None]:
    inner = _split_bash(entry)
    if inner is None:
        return None, "non-Bash permission; Codex prefix_rule covers shell commands only"
    if re.search(r"[|><;&]", inner):
        return None, "contains shell operators/redirection, not one argv prefix"
    if inner.endswith(" *"):
        inner = inner[:-2]
    if re.search(r"[*?\[]", inner):
        return None, "contains a glob that does not reduce to exact argv tokens"
    try:
        tokens = shlex.split(inner)
    except ValueError:
        return None, "cannot be parsed into argv tokens"
    if not tokens:
        return None, "empty command pattern"
    if any(token.startswith("~") for token in tokens):
        return None, "uses shell tilde expansion, so source text is not runtime argv"
    return tokens, None


def _leading_command_family(entry: str) -> list[str]:
    """Extract literal leading argv tokens from a Bash glob rule."""
    inner = _split_bash(entry)
    if inner is None:
        return []
    original = inner.strip()
    # A leading ``*`` in hub rules means "command may occur here" rather than
    # being part of the command name (for example, ``*git push --force*``).
    inner = inner.lstrip()
    inner = inner.lstrip("*").lstrip()
    try:
        raw_tokens = shlex.split(inner)
    except ValueError:
        return []
    family = []
    for token in raw_tokens:
        if re.search(r"[*?\[]", token) or re.search(r"[|><;&]", token):
            break
        family.append(token)
    if not family:
        wrapped_command = re.fullmatch(r"\*([A-Za-z0-9_.+-]+)\*", original)
        if wrapped_command:
            family.append(wrapped_command.group(1))
    return family


def project_permissions(rules: dict) -> tuple[list[tuple[list[str], str]], list[dict[str, str]]]:
    """Return safe Codex prefixes plus a reason for every omission."""
    projected: list[tuple[list[str], str]] = []
    omitted: list[dict[str, str]] = []
    seen: dict[tuple[str, ...], str] = {}
    restricted_families = [
        (entry, family)
        for tier in ("deny", "ask")
        for entry in rules.get(tier, [])
        if (family := _leading_command_family(entry))
    ]
    for tier in ("allow", "deny", "ask"):
        for entry in rules.get(tier, []):
            if tier == "ask":
                omitted.append({"tier": tier, "entry": entry,
                                "reason": "ask tier omitted; Codex prompts by default"})
                continue
            tokens, reason = _argv_prefix(entry)
            if reason:
                omitted.append({"tier": tier, "entry": entry, "reason": reason})
                continue
            if tier == "allow":
                example = next(
                    (restricted_entry
                     for restricted_entry, family in restricted_families
                     if family[:len(tokens)] == tokens),
                    None,
                )
                if example is not None:
                    omitted.append({
                        "tier": tier,
                        "entry": entry,
                        "reason": (
                            "allow-prefix would subsume a deny/ask variant "
                            f"(e.g. {example})"
                        ),
                    })
                    continue
            decision = tier
            key = tuple(tokens or [])
            previous = seen.get(key)
            if previous and previous != decision:
                raise ValueError(
                    f"conflicting Codex prefix {list(key)!r}: {previous} vs {decision}")
            if previous:
                continue
            seen[key] = decision
            projected.append((list(key), decision))
    return projected, omitted


def render_rules(projected: list[tuple[list[str], str]]) -> str:
    lines = [
        "# Generated from MAINFRAME hub (core/permissions/rules.json) — do not edit;",
        "# regenerate via ./install.sh --codex.",
    ]
    for tokens, decision in projected:
        pattern = json.dumps(tokens, ensure_ascii=False, separators=(", ", ": "))
        lines.append(f'prefix_rule(pattern={pattern}, decision="{decision}")')
    return "\n".join(lines) + "\n"


def _load_rules(root: Path) -> dict:
    path = root / "core" / "permissions" / "rules.json"
    data = json.loads(path.read_text())
    missing = [key for key in ("allow", "deny", "ask") if key not in data]
    if missing:
        raise ValueError(f"{path}: missing rule key(s): {', '.join(missing)}")
    return data


def _write_skills(out: Path, skills: list[tuple[str, dict[Path, bytes]]]) -> None:
    expected = {name for name, _ in skills}
    out.mkdir(parents=True, exist_ok=True)
    for existing in out.iterdir():
        if existing.name not in expected:
            if existing.is_dir() and not existing.is_symlink():
                shutil.rmtree(existing)
            else:
                existing.unlink()
    for name, files in skills:
        target = out / name
        if target.exists() and not target.is_dir():
            target.unlink()
        target.mkdir(parents=True, exist_ok=True)
        expected_files = {target / rel for rel in files}
        for existing in sorted(target.rglob("*"), reverse=True):
            if existing.is_file() and existing not in expected_files:
                existing.unlink()
            elif existing.is_dir() and not any(existing.iterdir()):
                existing.rmdir()
        for rel, content in files.items():
            path = target / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)


def _print_summary(skills, dropped, projected, omitted) -> None:
    print(f"skills rendered: {len(skills)}")
    print(f"skills dropped by projectability filter: {len(dropped)}")
    for name, reason in dropped:
        print(f"  - {name}: {reason}")
    print(f"rules mapped: {len(projected)}")
    print(f"rules omitted: {len(omitted)}")
    for item in omitted:
        print(f"  - [{item['tier']}] {item['entry']}: {item['reason']}")


def _default_root() -> Path:
    return Path(__file__).resolve().parents[2]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=_default_root())
    parser.add_argument("--skills-out", type=Path, default=None)
    parser.add_argument("--rules-out", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    skills_out = args.skills_out or root / "dist" / "codex" / "skills"
    rules_out = args.rules_out or root / "dist" / "codex" / "rules" / "mainframe.rules"

    skills, dropped = collect_skills(root)
    projected, omitted = project_permissions(_load_rules(root))
    if args.dry_run:
        print(f"[dry-run] would write skills to {skills_out}")
        print(f"[dry-run] would write rules to {rules_out}")
    else:
        _write_skills(skills_out, skills)
        rules_out.parent.mkdir(parents=True, exist_ok=True)
        rules_out.write_text(render_rules(projected))
        print(f"wrote skills to {skills_out}")
        print(f"wrote rules to {rules_out}")
    _print_summary(skills, dropped, projected, omitted)
    return 0


if __name__ == "__main__":
    sys.exit(main())
