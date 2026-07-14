#!/usr/bin/env python3
"""Unit tests for the OpenCode agent projection (`build_opencode`).

Run: `.venv/bin/python3 tools/test_build_opencode.py` (exit 0 = pass). Needs
pyyaml (same `.venv` as the validators). Covers agent frontmatter/body
projection, permission derivation, enrichment, and the committed-goldens
check. Config/permission/MCP merge mechanics live in the sibling
`tools/test_build_opencode_config.py`, which imports the fixtures below.
"""

import json
import os
import sys
import tempfile

_TOOLS = os.path.dirname(os.path.abspath(__file__))
_OC_ADAPTER = os.path.join(os.path.dirname(_TOOLS), "adapters", "opencode")
sys.path.insert(0, _OC_ADAPTER)
import build_opencode as bo


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)


READONLY_AGENT = (
    "---\n"
    "name: decision-reviewer\n"
    'description: "Adversarial review of a proposed decision."\n'
    "needs-repo-read: true\n"
    "needs-write: false\n"
    "needs-web: true\n"
    "needs-docs-lookup: true\n"
    "reasoning-tier: deep\n"
    "turn-budget: 50\n"
    "background: true\n"
    "method-skills:\n  - decision-review\n  - severity-calibration\n---\n\n"
    "You are an independent reviewer. Your skills `decision-review` and "
    "`severity-calibration` are preloaded — [SKILL.md](../skills/decision-review/SKILL.md) "
    "holds the method; consult `severity-calibration` (preloaded) for ratings. "
    "Run your preloaded skill's checklist first. "
    "The umbrella [CLAUDE.md](../../dist/claude-code/CLAUDE.md) rules apply.\n"
)

WRITE_AGENT = (
    "---\n"
    "name: python-backend-engineer\n"
    'description: "A Python backend task is in flight."\n'
    "needs-repo-read: true\n"
    "needs-write: true\n"
    "needs-web: false\n"
    "needs-docs-lookup: false\n"
    "reasoning-tier: standard\n"
    "background: true\n---\n\n"
    "You are a senior Python engineer.\n"
)

CC_PERMISSIONS = {
    "allow": [
        "Bash(git add *)",
        "WebSearch",
        "WebFetch(domain:github.com)",
        "mcp__plugin_context7_context7__resolve-library-id",
    ],
    "deny": [
        "Bash(rm -rf /)",
        "Read(**/.env.production)",
        "Read(~/.ssh/**)",
    ],
    "ask": [
        "Bash(rm -rf *)",
        "Bash(sudo *)",
    ],
}

USER_CONFIG = {
    "$schema": "https://opencode.ai/config.json",
    "model": "zai-coding-plan/glm-5",
    "mcp": {
        "context7": {
            "type": "local",
            "command": ["npx", "-y", "@upstash/context7-mcp"],
            "enabled": True,
        },
    },
    "provider": {"z-ai": {"options": {"apiKey": "user-secret"}}},
}

CLAUDE_JSON = {
    "mcpServers": {
        "codex": {"type": "stdio", "command": "codex",
                  "args": ["mcp-server"], "alwaysLoad": True},
        "with-secret": {"type": "stdio", "command": "srv", "args": [],
                        "env": {"API_KEY": "shh"}},
        "remote-one": {"type": "http", "url": "https://example.com/mcp"},
    }
}


def _fixture_root():
    root = tempfile.mkdtemp()
    _write(os.path.join(root, "core/agents/decision-reviewer.md"),
           READONLY_AGENT)
    _write(os.path.join(root, "core/agents/python-backend-engineer.md"),
           WRITE_AGENT)
    _write(os.path.join(root, "core/permissions/rules.json"),
           json.dumps(CC_PERMISSIONS))
    return root


def test_derive_permission_readonly_denies_side_effect_tools():
    perm = bo.derive_agent_permission({"needs-write": False, "needs-web": True})
    assert perm["bash"] == "deny"
    assert perm["edit"] == "deny"
    assert perm["task"] == "deny"
    assert "skill" not in perm  # skills are the agent's method, not a side effect
    assert "webfetch" not in perm
    assert "websearch" not in perm


def test_derive_permission_write_capable_keeps_bash_and_edit():
    perm = bo.derive_agent_permission({"needs-write": True, "needs-web": False})
    assert "bash" not in perm
    assert "edit" not in perm
    assert perm["task"] == "deny"  # no contract axis grants nested dispatch
    assert "skill" not in perm
    assert perm["webfetch"] == "deny"
    assert perm["websearch"] == "deny"


def test_derive_tools_disable_mirrors_permission_denies():
    tools = bo.derive_agent_tools({"needs-write": False, "needs-web": True})
    assert tools == {"bash": False, "edit": False, "write": False, "task": False}
    tools = bo.derive_agent_tools({"needs-write": True, "needs-web": False})
    assert tools == {"webfetch": False, "websearch": False, "task": False}


def test_project_agent_maps_frontmatter_and_drops_hub_keys():
    meta, body = bo.parse_frontmatter(READONLY_AGENT)
    out = bo.project_agent(meta, body)
    fm, out_body = bo.parse_frontmatter(out)
    assert set(fm) == {"description", "mode", "steps", "permission", "tools"}
    assert fm["tools"]["bash"] is False and fm["tools"]["task"] is False
    assert fm["mode"] == "subagent"
    assert fm["steps"] == 50  # turn-budget maps to OpenCode's soft step cap
    assert fm["description"] == "Adversarial review of a proposed decision."
    assert fm["permission"]["bash"] == "deny"


def test_project_agent_preserves_body_and_marks_generated():
    meta, body = bo.parse_frontmatter(READONLY_AGENT)
    out = bo.project_agent(meta, body)
    assert "You are an independent reviewer." in out
    assert bo.GENERATED_MARKER in out


def test_project_agent_rewrites_skill_links_and_preload_phrase():
    import os
    meta, body = bo.parse_frontmatter(READONLY_AGENT)
    out = bo.project_agent(meta, body)
    assert "](../skills/" not in out
    assert "](../../dist/claude-code/CLAUDE.md" not in out
    home = os.path.expanduser("~")
    assert f"]({home}/.claude/skills/mainframe/skills/decision-review/SKILL.md" in out
    assert f"]({home}/.claude/CLAUDE.md" in out
    assert "preloaded" not in out  # every phrasing rewritten, incl. the note
    assert "available via the `skill` tool" in out
    assert "(load via the `skill` tool)" in out
    assert "your loaded skill's" in out


def test_project_agent_adds_runtime_skill_note():
    meta, body = bo.parse_frontmatter(READONLY_AGENT)
    out = bo.project_agent(meta, body)
    assert 'skill({ name: "decision-review" })' in out
    assert 'skill({ name: "severity-calibration" })' in out


def test_project_agent_without_skills_has_no_skill_note():
    meta, body = bo.parse_frontmatter(WRITE_AGENT)
    out = bo.project_agent(meta, body)
    assert "skill({" not in out
    fm, _ = bo.parse_frontmatter(out)
    assert "steps" not in fm  # no turn-budget in the source


def test_enrichment_merges_model_color_and_mode():
    meta, body = bo.parse_frontmatter(READONLY_AGENT)
    enrich = {"agents": {"decision-reviewer": {
        "model": "openai/gpt-5.5", "color": "#d94f4f", "mode": "all",
        "temperature": 0.2}}}
    out = bo.project_agent(meta, body, enrich=enrich)
    fm, _ = bo.parse_frontmatter(out)
    assert fm["model"] == "openai/gpt-5.5"
    assert fm["color"] == "#d94f4f"
    assert fm["mode"] == "all"  # enrichment overrides the subagent default
    assert fm["temperature"] == 0.2
    assert fm["steps"] == 50  # untouched keys survive


def test_enrichment_passes_variant_and_options():
    meta, body = bo.parse_frontmatter(READONLY_AGENT)
    out = bo.project_agent(meta, body, enrich={"agents": {
        "decision-reviewer": {"variant": "xhigh",
                              "options": {"reasoningEffort": "xhigh"}}}})
    fm, _ = bo.parse_frontmatter(out)
    assert fm["variant"] == "xhigh"
    assert fm["options"] == {"reasoningEffort": "xhigh"}


def test_enrichment_absent_and_unknown_keys_are_safe():
    meta, body = bo.parse_frontmatter(READONLY_AGENT)
    plain = bo.project_agent(meta, body)
    assert plain == bo.project_agent(meta, body, enrich=None)
    out = bo.project_agent(meta, body, enrich={"agents": {
        "decision-reviewer": {"model": "x/y", "typo_key": "boom"}}})
    fm, _ = bo.parse_frontmatter(out)
    assert fm["model"] == "x/y"
    assert "typo_key" not in fm  # unknown keys never reach the frontmatter


def test_main_applies_enrichment_file():
    root = _fixture_root()
    out = os.path.join(root, "out-agents")
    cfg = os.path.join(root, "opencode.json")
    _write(cfg, json.dumps(USER_CONFIG))
    _write(os.path.join(root, "workspace/opencode-enrich.json"), json.dumps(
        {"agents": {"python-backend-engineer": {"model": "z/m",
                                                "color": "#3b82f6"}}}))
    rc = bo.main(["--root", root, "--agents-out", out, "--config", cfg])
    assert rc == 0
    fm, _ = bo.parse_frontmatter(
        open(os.path.join(out, "python-backend-engineer.md")).read())
    assert fm["model"] == "z/m" and fm["color"] == "#3b82f6"
    fm2, _ = bo.parse_frontmatter(
        open(os.path.join(out, "decision-reviewer.md")).read())
    assert "model" not in fm2  # agents not in the file stay untouched


def test_main_generates_agents_and_merges_config():
    root = _fixture_root()
    out = os.path.join(root, "out-agents")
    cfg = os.path.join(root, "opencode.json")
    _write(cfg, json.dumps(USER_CONFIG))
    claude_cfg = os.path.join(root, "claude.json")
    _write(claude_cfg, json.dumps(CLAUDE_JSON))
    rc = bo.main(["--root", root, "--agents-out", out, "--config", cfg,
                  "--claude-config", claude_cfg])
    assert rc == 0
    generated = sorted(os.listdir(out))
    assert generated == ["decision-reviewer.md", "python-backend-engineer.md"]
    fm, _ = bo.parse_frontmatter(open(os.path.join(out, generated[0])).read())
    assert fm["mode"] == "subagent"
    merged = json.load(open(cfg))
    assert merged["provider"] == USER_CONFIG["provider"]
    assert merged["mcp"]["codex"]["type"] == "local"
    assert merged["permission"]["bash"]["rm -rf /"] == "deny"


def test_real_repo_agents_match_committed_goldens():
    """OC-side golden: the 7 real contracts render byte-identically.

    Deterministic on any machine: HOME is pinned (prose rewrites embed it)
    and enrichment is off (the real enrich file is machine-local).
    """
    repo = os.path.dirname(_TOOLS)
    golden_dir = os.path.join(_TOOLS, "..", "dist", "opencode", "agents-golden")
    old_home = os.environ.get("HOME")
    os.environ["HOME"] = "/home/u"
    try:
        agents = bo._collect_agents(repo, enrich=None)
    finally:
        if old_home is None:
            del os.environ["HOME"]
        else:
            os.environ["HOME"] = old_home
    assert sorted(f for f, _ in agents) == sorted(os.listdir(golden_dir))
    for fname, rendered in agents:
        golden = open(os.path.join(golden_dir, fname)).read()
        assert rendered == golden, f"OC golden drift: {fname}"


def _run_all():
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    failures = 0
    for t in tests:
        try:
            t()
            print(f"  ok   {t.__name__}")
        except AssertionError as e:
            failures += 1
            print(f"  FAIL {t.__name__}: {e}")
    print(f"{len(tests) - failures}/{len(tests)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(_run_all())
