#!/usr/bin/env python3
"""Unit tests for the Codex Phase-1 projection.

Run: ``.venv/bin/python3 tools/test_build_codex.py`` (exit 0 = pass).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
import tempfile
import tomllib
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
Write plans below {{mainframe.plans_root}}/audit.
"""


def _fixture_root() -> Path:
    root = Path(tempfile.mkdtemp())
    _write(
        root / "adapters/runtime-profiles.json",
        (_TOOLS.parent / "adapters/runtime-profiles.json").read_text(),
    )
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
    _write(root / "adapters/codex/gates/mainframe-hook.sh", "#!/bin/sh\nexit 0\n")
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
    assert "~/.codex/mainframe-agent-methods/sample-skill/tool.py" in body
    assert "~/.codex/plans/audit" in body
    assert "${CODEX_HOME:-$HOME/.codex}/plans/audit" not in body
    assert "{{mainframe.plans_root}}" not in body


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
                 "claude-code-research", "codex-exec"):
        text = SKILL.replace("sample-skill", name)
        if name == "task-workflow":
            text = text.replace("disable-model-invocation: true", "disable-model-invocation: false")
        _write(root / f"core/skills/{name}/SKILL.md", text)
    skills, dropped = bc.collect_skills(root)
    assert [name for name, _ in skills] == ["task-workflow"]
    assert {name for name, _ in dropped} == set(bc.UNPROJECTABLE_SKILLS)
    assert "task-workflow" not in bc.UNPROJECTABLE_SKILLS


def test_restricted_skills_are_private_and_keep_support_files():
    root = _fixture_root()
    methods = dict(bc.collect_private_methods(root))
    assert set(methods) == {"sample-skill"}
    text = methods["sample-skill"][Path("SKILL.md")].decode()
    assert "~/.codex/mainframe-agent-methods/sample-skill/tool.py" in text
    assert Path("more.md") in methods["sample-skill"]
    assert Path("tool.py") in methods["sample-skill"]


def test_private_method_links_respect_registry_partition():
    methods = dict(bc.collect_private_methods(_TOOLS.parent))
    frontend = methods["react-frontend-patterns"][Path("SKILL.md")].decode()
    assert (
        "~/.codex/mainframe-agent-methods/shadcn/SKILL.md" in frontend
    )
    assert "~/.codex/skills/surface-ticket/SKILL.md" in frontend
    assert "](../" not in frontend


def test_real_render_has_no_false_codex_tool_attributions():
    repo = _TOOLS.parent
    skills, dropped = bc.collect_skills(repo)
    rendered = dict(skills)
    assert len(skills) == 10
    assert "task-workflow" in rendered
    assert "task-workflow" not in {name for name, _ in dropped}

    all_markdown = "\n".join(
        content.decode()
        for _, files in skills
        for path, content in files.items()
        if path.suffix == ".md"
    )
    for tool in ("AskUserQuestion", "TodoWrite", "ExitPlanMode"):
        assert f"Codex: `{tool}`" not in all_markdown
    assert not re.search(r"\bCodex:\s*`[^`]+`", all_markdown)
    assert not re.search(
        r"\bCodex\b[^.\n]*\bAskUserQuestion\b",
        all_markdown,
    )

    workflow = "\n".join(
        content.decode()
        for path, content in rendered["task-workflow"].items()
        if path.suffix == ".md"
    )
    for claude_only_tool in (
        "advisor()", "AskUserQuestion", "TodoWrite", "EnterPlanMode", "ExitPlanMode",
    ):
        assert claude_only_tool not in workflow
    assert "Codex has no `advisor` tool" in workflow
    assert "independent review checkpoint" in workflow.lower()
    assert "`decision-review` skill" in workflow
    assert "Context7 first" in workflow
    assert "MCP tools" in workflow
    assert "sub-agent" in workflow
    for stage in ("recon", "verify", "commit"):
        assert stage in workflow.lower()


def test_permissions_map_only_clean_command_prefixes_and_report_omissions():
    root = _fixture_root()
    rules = json.loads((root / "core/permissions/rules.json").read_text())
    projected, omitted = bc.project_permissions(rules)
    assert (["git", "add"], "allow") in projected
    assert (["git", "push"], "allow") not in projected
    assert (["rm", "-rf", "/"], "forbidden") in projected
    assert (["sudo"], "prompt") in projected
    assert len(omitted) == 5
    report = {item["entry"]: item["reason"] for item in omitted}
    assert report["Bash(git push *)"] == (
        "allow-prefix would subsume a deny/ask variant "
        "(e.g. Bash(*git push --force*))"
    )
    assert "non-Bash" in report["WebSearch"]
    assert "operators/redirection" in report["Bash(cat > /tmp/*)"]
    assert "glob" in report["Bash(*git push --force*)"]
    assert "non-Bash" in report["Read(**/.env.production)"]
    assert "Bash(sudo *)" not in report


def test_permission_source_rejects_ambiguous_or_empty_policies():
    cases = (
        (
            '{"allow": [], "allow": [], "deny": ["Bash(rm -rf /)"], "ask": []}',
            "duplicate key",
        ),
        (
            '{"allow": [], "deny": ["Bash(rm -rf /)"], "ask": [], "extra": []}',
            "exactly allow, ask, and deny",
        ),
        (
            '{"allow": "Bash(git status)", "deny": [], "ask": []}',
            "list[str]",
        ),
        (
            '{"allow": [], "deny": [], "ask": []}',
            "cannot be empty",
        ),
    )
    for rules, message in cases:
        root = _fixture_root()
        _write(root / "core/permissions/rules.json", rules)
        try:
            bc._load_rules(root)
        except ValueError as error:
            assert message in str(error), (message, error)
        else:
            raise AssertionError(f"invalid permission source accepted: {rules}")


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
                                (["sudo"], "prompt"),
                                (["rm", "-rf", "/"], "forbidden")])
    assert 'prefix_rule(pattern=["git", "add"], decision="allow")' in rendered
    assert 'prefix_rule(pattern=["sudo"], decision="prompt")' in rendered
    assert 'prefix_rule(pattern=["rm", "-rf", "/"], decision="forbidden")' in rendered
    assert 'decision="deny"' not in rendered
    assert 'decision="ask"' not in rendered


def test_rules_render_rejects_unknown_native_decision():
    try:
        bc.render_rules([(["git", "status"], "deny")])
    except ValueError as error:
        assert "unsupported Codex decision" in str(error)
    else:
        assert False, "render_rules accepted an invalid native decision"


def test_native_validation_failure_precedes_all_publication():
    assert hasattr(bc, "validate_rules_native"), \
        "native Codex validation is not implemented"
    root = _fixture_root()
    fake_bin = root / "bin"
    fake_codex = fake_bin / "codex"
    _write(fake_codex, """#!/usr/bin/env python3
import json
print(json.dumps({"decision": "allow"}))
""")
    fake_codex.chmod(0o755)

    skills_out = root / "out/skills"
    rules_out = root / "out/rules/mainframe.rules"
    rules_out.parent.mkdir(parents=True)
    rules_out.write_text("existing valid rules\n")
    old_path = os.environ.get("PATH", "")
    os.environ["PATH"] = f"{fake_bin}{os.pathsep}{old_path}"
    try:
        try:
            bc.main([
                "--root", str(root),
                "--skills-out", str(skills_out),
                "--rules-out", str(rules_out),
                "--validate-native",
            ])
        except ValueError as error:
            assert "expected prompt" in str(error)
        else:
            assert False, "native decision mismatch did not fail the build"
    finally:
        os.environ["PATH"] = old_path

    assert rules_out.read_text() == "existing valid rules\n"
    assert not skills_out.exists()


def test_native_validation_rejects_non_object_json():
    root = _fixture_root()
    fake_codex = root / "bin/codex"
    _write(fake_codex, "#!/usr/bin/env python3\nprint('[]')\n")
    fake_codex.chmod(0o755)
    try:
        bc.validate_rules_native("", str(fake_codex))
    except ValueError as error:
        assert "non-object validation JSON" in str(error)
    else:
        assert False, "non-object native validation JSON was accepted"


def test_real_native_parser_when_available():
    codex_binary = shutil.which("codex")
    if codex_binary is None:
        return
    root = _TOOLS.parent
    rules = json.loads((root / "core/permissions/rules.json").read_text())
    projected, _ = bc.project_permissions(rules)
    bc.validate_rules_native(bc.render_rules(projected), codex_binary)


def test_summary_reports_each_dropped_skill_and_omitted_rule():
    output = StringIO()
    dropped = [("update-config", "harness-bound")]
    omitted = [{"tier": "allow", "entry": "WebSearch",
                "reason": "non-Bash permission"}]
    with redirect_stdout(output):
        bc._print_summary([("sample", {})], dropped,
                          [(["git", "add"], "allow")], omitted)
    text = output.getvalue()
    assert "update-config: harness-bound" in text
    assert "[allow] WebSearch: non-Bash permission" in text


def test_main_writes_skill_pair_resources_and_rules():
    root = _fixture_root()
    skills_out = root / "out/skills"
    private_methods_out = root / "out/private-methods"
    rules_out = root / "out/rules/mainframe.rules"
    rc = bc.main(["--root", str(root), "--skills-out", str(skills_out),
                  "--private-methods-out", str(private_methods_out),
                  "--rules-out", str(rules_out)])
    assert rc == 0
    assert not (skills_out / "sample-skill").exists()
    assert (private_methods_out / "sample-skill/SKILL.md").is_file()
    assert (private_methods_out / "sample-skill/agents/openai.yaml").is_file()
    assert (private_methods_out / "sample-skill/more.md").is_file()
    assert rules_out.is_file()
    assert rules_out.stat().st_mode & 0o777 == 0o644


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


def test_hooks_json_shape_events_and_launcher():
    data = json.loads(bc.render_hooks_json())
    assert set(data) == {"hooks"}
    hooks = data["hooks"]
    assert set(hooks) == {"PreToolUse", "PostToolUse", "Stop"}
    for event, groups in hooks.items():
        assert isinstance(groups, list) and len(groups) == 1
        group = groups[0]
        assert group["matcher"] == ".*"
        assert group["hooks"], f"{event} has no hook entries"
        for entry in group["hooks"]:
            assert entry["type"] == "command"
            assert entry["async"] is False
            assert "${CODEX_HOME:-$HOME/.codex}/mainframe-hook.sh" in entry["command"]
            assert f" {event} " in entry["command"]


def test_hooks_json_blocking_gates_are_pretooluse_only():
    data = json.loads(bc.render_hooks_json())
    pre = " ".join(e["command"] for e in data["hooks"]["PreToolUse"][0]["hooks"])
    assert "secret-commit-gate.py" in pre
    assert "path-validation.py" in pre
    # A stop-gate on the pre-tool path would fire a turn-end check per tool call.
    assert "stop-gate-suppression-markers.py" not in pre


def test_hooks_json_mapped_detectors_exist_in_core():
    detectors = _TOOLS.parent / "core/gates/detectors"
    for event, names in bc.GATE_HOOKS.items():
        for name in names:
            assert (detectors / name).is_file(), \
                f"{event}: {name} missing in core/gates/detectors"


def test_main_writes_hooks_json_and_executable_launcher():
    root = _fixture_root()
    hooks_out = root / "out/hooks.json"
    launcher_out = root / "out/mainframe-hook.sh"
    rc = bc.main(["--root", str(root),
                  "--skills-out", str(root / "out/skills"),
                  "--rules-out", str(root / "out/rules/mainframe.rules"),
                  "--hooks-out", str(hooks_out),
                  "--launcher-out", str(launcher_out)])
    assert rc == 0
    assert "PreToolUse" in json.loads(hooks_out.read_text())["hooks"]
    assert launcher_out.is_file()
    assert os.access(launcher_out, os.X_OK)


AGENT_RO = """---
name: sample-reviewer
description: "An independent review of a proposed decision. Read-only."
needs-repo-read: true
needs-write: false
needs-web: true
needs-docs-lookup: true
reasoning-tier: deep
turn-budget: 50
background: true
method-skills:
  - decision-review
  - severity-calibration
---

You are a reviewer. Your skill `decision-review` is preloaded — its [SKILL.md](../skills/decision-review/SKILL.md) holds the method. Follow the umbrella [CLAUDE.md](../../dist/claude-code/CLAUDE.md). Ground objections with (`Read`/`Grep`/`Glob`).
"""

AGENT_WRITE = """---
name: sample-engineer
description: "A Python backend task is in flight. Write-capable."
needs-repo-read: true
needs-write: true
needs-web: false
needs-docs-lookup: true
reasoning-tier: standard
background: true
method-skills:
  - python-backend-patterns
---

Implement the endpoint. Recon first via [recon.md](../skills/python-backend-patterns/recon.md).
"""


def test_agent_toml_read_only_restricts_and_maps_effort():
    source = bc.parse_agent_source(AGENT_RO)
    data = tomllib.loads(bc.render_agent(source.contract, source.body))
    assert data["name"] == "sample-reviewer"
    assert data["model_reasoning_effort"] == "high"        # deep -> high
    assert data["sandbox_mode"] == "read-only"             # needs-write:false -> restrict
    assert "web_search" not in data                        # needs-web:true -> never elevate
    di = data["developer_instructions"]
    assert "$decision-review" in di and "$severity-calibration" in di
    assert "within roughly 50 steps" in di                 # turn-budget -> soft cap (only cost lever on Codex)


def test_agent_toml_write_agent_omits_sandbox_and_denies_web():
    source = bc.parse_agent_source(AGENT_WRITE)
    data = tomllib.loads(bc.render_agent(source.contract, source.body))
    assert "sandbox_mode" not in data                      # needs-write:true -> inherit, never elevate
    assert data["web_search"] == "disabled"                # needs-web:false -> restrict
    assert data["model_reasoning_effort"] == "medium"      # standard -> medium
    assert "within roughly" not in data["developer_instructions"]  # no turn-budget -> no soft cap


def test_agent_developer_instructions_have_no_repo_relative_paths():
    for src in (AGENT_RO, AGENT_WRITE):
        source = bc.parse_agent_source(src)
        di = tomllib.loads(
            bc.render_agent(source.contract, source.body)
        )["developer_instructions"]
        assert "../" not in di, f"dead repo path leaked: {di}"
        assert "CLAUDE.md" not in di                        # rewritten to AGENTS.md
        assert "dist/claude-code" not in di


def test_reasoning_tier_effort_map_is_low_medium_high():
    assert bc._REASONING_EFFORT == {"light": "low", "standard": "medium", "deep": "high"}


def test_collect_agents_real_repo_all_valid_toml():
    agents = bc.collect_agents(_TOOLS.parent)
    names = [n for n, _ in agents]
    assert "decision-reviewer" in names and "web-search" in names
    assert len(names) == 7
    for name, toml_text in agents:
        data = tomllib.loads(toml_text)                    # must be well-formed TOML
        assert data["name"] == name
        assert data["description"] and data["developer_instructions"]
        assert not re.search(r"\]\(\.\./", data["developer_instructions"])


def test_real_agents_embed_private_methods_but_reference_public_skills():
    agents = dict(bc.collect_agents(_TOOLS.parent))
    reviewer = tomllib.loads(agents["decision-reviewer"])["developer_instructions"]
    assert "Private method: decision-review" in reviewer
    assert "$decision-review" not in reviewer
    assert "$severity-calibration" in reviewer
    assert "~/.codex/mainframe-agent-methods/" in reviewer

    frontend = tomllib.loads(
        agents["react-frontend-engineer"]
    )["developer_instructions"]
    for name in ("react-frontend-patterns", "shadcn", "frontend-design"):
        assert f"Private method: {name}" in frontend
        assert f"${name}" not in frontend
        assert f"~/.codex/skills/{name}" not in frontend
    assert "$surface-ticket" in frontend
    assert (
        "~/.codex/mainframe-agent-methods/react-frontend-patterns/recon.js"
        in frontend
    )
    assert len(frontend.encode()) < bc.MAX_AGENT_INSTRUCTION_BYTES


def test_agents_have_no_false_codex_tool_attributions():
    blob = "\n".join(t for _, t in bc.collect_agents(_TOOLS.parent))
    assert not re.search(r"\bCodex:\s*`[^`]+`", blob)
    for tool in ("AskUserQuestion", "TodoWrite", "ExitPlanMode"):
        assert f"Codex: `{tool}`" not in blob


def test_main_writes_agents():
    root = _fixture_root()
    for name, restricted in (
        ("decision-review", True),
        ("severity-calibration", False),
    ):
        skill = SKILL.replace("sample-skill", name)
        if not restricted:
            skill = skill.replace(
                "disable-model-invocation: true",
                "disable-model-invocation: false",
            )
        _write(root / f"core/skills/{name}/SKILL.md", skill)
    _write(root / "core/agents/sample-reviewer.md", AGENT_RO)
    agents_out = root / "out/agents"
    rc = bc.main(["--root", str(root),
                  "--skills-out", str(root / "out/skills"),
                  "--rules-out", str(root / "out/rules/mainframe.rules"),
                  "--hooks-out", str(root / "out/hooks.json"),
                  "--launcher-out", str(root / "out/mainframe-hook.sh"),
                  "--agents-out", str(agents_out)])
    assert rc == 0
    data = tomllib.loads((agents_out / "sample-reviewer.toml").read_text())
    assert data["name"] == "sample-reviewer"


def test_collect_agents_rejects_unknown_method_at_adapter_boundary():
    root = _fixture_root()
    _write(
        root / "core/agents/sample-reviewer.md",
        AGENT_RO.replace("decision-review", "unknown-method"),
    )
    try:
        bc.collect_agents(root)
    except ValueError as error:
        assert "unknown method skills" in str(error)
        assert "unknown-method" in str(error)
    else:
        raise AssertionError("Codex accepted an unknown method skill")


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
