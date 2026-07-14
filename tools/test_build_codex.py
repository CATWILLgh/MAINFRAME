#!/usr/bin/env python3
"""Unit tests for the Codex Phase-1 projection.

Run: ``.venv/bin/python3 tools/test_build_codex.py`` (exit 0 = pass).
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

import yaml


_TOOLS = Path(__file__).resolve().parent
_ADAPTER = _TOOLS.parent / "adapters" / "codex"
sys.path.insert(0, str(_ADAPTER))
import build_codex as bc


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


SKILL = """---
name: sample-skill
user-invocable: false
disable-model-invocation: true
description: Run a sample method from ~/.claude/ with Claude Code.
when_to_use: Loaded by an agent.
---

# Sample Method

Preloaded into the `sample-agent` sub-agent. Read [more](more.md).
Use (`Read`/`Grep`/`Glob`) and ~/.claude/skills/mainframe/skills/sample-skill/tool.py.
"""


def _fixture_root() -> Path:
    root = Path(tempfile.mkdtemp())
    _write(root / "core/skills/sample-skill/SKILL.md", SKILL)
    _write(root / "core/skills/sample-skill/more.md", "See CLAUDE.md.\n")
    _write(root / "core/skills/sample-skill/tool.py", "print('ok')\n")
    _write(root / "core/permissions/rules.json", json.dumps({
        "allow": ["Bash(git add *)", "Bash(git push *)", "WebSearch",
                  "Bash(cat > /tmp/*)"],
        "deny": ["Bash(rm -rf /)", "Read(**/.env.production)",
                 "Bash(*git push --force*)"],
        "ask": ["Bash(sudo *)"],
    }))
    return root


def test_skill_frontmatter_reduced_and_body_rewritten():
    root = _fixture_root()
    files = bc.render_skill_dir(root / "core/skills/sample-skill")
    text = files[Path("SKILL.md")].decode()
    meta, body = bc.parse_frontmatter(text)
    assert set(meta) == {"name", "description"}
    assert meta["name"] == "sample-skill"
    assert "~/.codex/" in meta["description"] and "Claude Code" not in meta["description"]
    assert bc.GENERATED_MARKER in body
    assert "Load explicitly with `$sample-skill`" in body
    assert "file-reading and search tools" in body
    assert "~/.codex/skills/sample-skill/tool.py" in body


def test_openai_yaml_shape_and_trigger():
    root = _fixture_root()
    files = bc.render_skill_dir(root / "core/skills/sample-skill")
    text = files[Path("agents/openai.yaml")].decode()
    data = yaml.safe_load(text)
    assert set(data) == {"interface"}
    interface = data["interface"]
    assert set(interface) == {"display_name", "short_description", "default_prompt"}
    assert interface["display_name"] == "Sample Method"
    assert interface["short_description"].startswith("Run a sample method")
    assert interface["default_prompt"].startswith("Use $sample-skill to ")


def test_auxiliary_files_are_preserved_and_markdown_adapted():
    root = _fixture_root()
    files = bc.render_skill_dir(root / "core/skills/sample-skill")
    more = files[Path("more.md")].decode()
    assert bc.GENERATED_MARKER in more and "AGENTS.md" in more
    assert files[Path("tool.py")] == b"print('ok')\n"


def test_projectability_filter_drops_harness_skills_only():
    root = _fixture_root()
    for name in ("task-workflow", "update-config", "keybindings-help",
                 "claude-code-research"):
        text = SKILL.replace("sample-skill", name)
        _write(root / f"core/skills/{name}/SKILL.md", text)
    skills, dropped = bc.collect_skills(root)
    assert [name for name, _ in skills] == ["sample-skill"]
    assert {name for name, _ in dropped} == set(bc.UNPROJECTABLE_SKILLS)


def test_permissions_map_only_clean_command_prefixes_and_report_omissions():
    root = _fixture_root()
    rules = json.loads((root / "core/permissions/rules.json").read_text())
    projected, omitted = bc.project_permissions(rules)
    assert (["git", "add"], "allow") in projected
    assert (["git", "push"], "allow") not in projected
    assert (["rm", "-rf", "/"], "deny") in projected
    assert len(omitted) == 6
    report = {item["entry"]: item["reason"] for item in omitted}
    assert report["Bash(git push *)"] == (
        "allow-prefix would subsume a deny/ask variant "
        "(e.g. Bash(*git push --force*))"
    )
    assert "non-Bash" in report["WebSearch"]
    assert "operators/redirection" in report["Bash(cat > /tmp/*)"]
    assert "glob" in report["Bash(*git push --force*)"]
    assert "prompts by default" in report["Bash(sudo *)"]


def test_no_allow_prefix_subsumes_a_deny_or_ask_command_family():
    root = _fixture_root()
    rules = json.loads((root / "core/permissions/rules.json").read_text())
    projected, _ = bc.project_permissions(rules)
    rendered = bc.render_rules(projected)
    assert 'prefix_rule(pattern=["git", "push"], decision="allow")' not in rendered
    restricted = [
        (entry, family)
        for tier in ("deny", "ask")
        for entry in rules[tier]
        if (family := bc._leading_command_family(entry))
    ]
    violations = [
        (tokens, entry)
        for tokens, decision in projected
        if decision == "allow"
        for entry, family in restricted
        if family[:len(tokens)] == tokens
    ]
    assert not violations
    assert bc._leading_command_family("Bash(*git push --force*)") == ["git", "push"]
    assert bc._leading_command_family("Bash(*git reset --hard*)") == ["git", "reset"]
    assert bc._leading_command_family("Bash(*mkfs*)") == ["mkfs"]


def test_rules_render_native_prefix_rule_syntax():
    rendered = bc.render_rules([(["git", "add"], "allow"),
                                (["rm", "-rf", "/"], "deny")])
    assert 'prefix_rule(pattern=["git", "add"], decision="allow")' in rendered
    assert 'prefix_rule(pattern=["rm", "-rf", "/"], decision="deny")' in rendered
    assert "ask" not in rendered


def test_summary_reports_each_dropped_skill_and_omitted_rule():
    output = StringIO()
    dropped = [("task-workflow", "harness-bound")]
    omitted = [{"tier": "allow", "entry": "WebSearch",
                "reason": "non-Bash permission"}]
    with redirect_stdout(output):
        bc._print_summary([("sample", {})], dropped,
                          [(["git", "add"], "allow")], omitted)
    text = output.getvalue()
    assert "task-workflow: harness-bound" in text
    assert "[allow] WebSearch: non-Bash permission" in text


def test_main_writes_skill_pair_resources_and_rules():
    root = _fixture_root()
    skills_out = root / "out/skills"
    rules_out = root / "out/rules/mainframe.rules"
    rc = bc.main(["--root", str(root), "--skills-out", str(skills_out),
                  "--rules-out", str(rules_out)])
    assert rc == 0
    assert (skills_out / "sample-skill/SKILL.md").is_file()
    assert (skills_out / "sample-skill/agents/openai.yaml").is_file()
    assert (skills_out / "sample-skill/more.md").is_file()
    assert rules_out.is_file()


def test_real_repo_subset_matches_committed_goldens():
    repo = _TOOLS.parent
    golden = repo / "dist/codex/skills-golden"
    old_home = os.environ.get("HOME")
    os.environ["HOME"] = "/home/u"
    try:
        skills, _ = bc.collect_skills(repo)
    finally:
        if old_home is None:
            del os.environ["HOME"]
        else:
            os.environ["HOME"] = old_home
    rendered = dict(skills)
    assert sorted(p.name for p in golden.iterdir()) == [
        "code-audit", "curl-requests", "secrets-handling"]
    for name in sorted(p.name for p in golden.iterdir()):
        for rel in (Path("SKILL.md"), Path("agents/openai.yaml")):
            expected = (golden / name / rel).read_bytes()
            assert rendered[name][rel] == expected, f"Codex golden drift: {name}/{rel}"


def _run_all() -> int:
    tests = [value for key, value in sorted(globals().items())
             if key.startswith("test_") and callable(value)]
    failures = 0
    for test in tests:
        try:
            test()
            print(f"  ok   {test.__name__}")
        except AssertionError as error:
            failures += 1
            print(f"  FAIL {test.__name__}: {error}")
    print(f"{len(tests) - failures}/{len(tests)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(_run_all())
