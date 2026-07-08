#!/usr/bin/env python3
"""Unit tests for the OpenCode projection generator (`build_opencode`).

Run: `.venv/bin/python3 tools/test_build_opencode.py` (exit 0 = pass). Needs
pyyaml (same `.venv` as the validators). All projection and merge logic is
pure and tested against temp fixtures; filesystem effects (rolling backup,
dry-run) are tested on temp copies — the real ~/.config is never touched.
"""

import copy
import json
import os
import stat
import sys
import tempfile

_TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _TOOLS)
import build_opencode as bo


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)


READONLY_AGENT = (
    "---\n"
    "name: decision-reviewer\n"
    'description: "Adversarial review of a proposed decision."\n'
    "tools: Read, Grep, Glob, WebSearch, WebFetch, "
    "mcp__plugin_context7_context7__resolve-library-id\n"
    "model: opus\n"
    "effort: high\n"
    "background: true\n"
    "maxTurns: 50\n"
    "permissionMode: plan\n"
    "skills:\n  - decision-review\n---\n\n"
    "You are an independent reviewer.\n"
)

WRITE_AGENT = (
    "---\n"
    "name: python-backend-engineer\n"
    'description: "A Python backend task is in flight."\n'
    "tools: Read, Write, Edit, Glob, Grep, Bash, TodoWrite\n"
    "model: sonnet\n"
    "effort: medium\n"
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
    _write(os.path.join(root, "plugin-dist/agents/decision-reviewer.md"),
           READONLY_AGENT)
    _write(os.path.join(root, "plugin-dist/agents/python-backend-engineer.md"),
           WRITE_AGENT)
    _write(os.path.join(root, "export/settings.json"),
           json.dumps({"permissions": CC_PERMISSIONS}))
    return root


def test_derive_permission_readonly_denies_side_effect_tools():
    perm = bo.derive_agent_permission(
        ["Read", "Grep", "Glob", "WebSearch", "WebFetch"])
    assert perm["bash"] == "deny"
    assert perm["edit"] == "deny"
    assert perm["task"] == "deny"
    assert perm["skill"] == "deny"
    assert "webfetch" not in perm
    assert "websearch" not in perm


def test_derive_permission_write_capable_keeps_bash_and_edit():
    perm = bo.derive_agent_permission(
        ["Read", "Write", "Edit", "Glob", "Grep", "Bash", "TodoWrite"])
    assert "bash" not in perm
    assert "edit" not in perm
    assert "task" not in perm
    assert "skill" not in perm
    assert perm["webfetch"] == "deny"
    assert perm["websearch"] == "deny"


def test_project_agent_maps_frontmatter_and_drops_hub_keys():
    meta, body = bo.parse_frontmatter(READONLY_AGENT)
    out = bo.project_agent(meta, body)
    fm, out_body = bo.parse_frontmatter(out)
    assert set(fm) == {"description", "mode", "permission"}
    assert fm["mode"] == "subagent"
    assert fm["description"] == "Adversarial review of a proposed decision."
    assert fm["permission"]["bash"] == "deny"


def test_project_agent_preserves_body_and_marks_generated():
    meta, body = bo.parse_frontmatter(READONLY_AGENT)
    out = bo.project_agent(meta, body)
    assert "You are an independent reviewer." in out
    assert bo.GENERATED_MARKER in out


def test_project_permissions_maps_bash_and_read():
    perm, report = bo.project_permissions(CC_PERMISSIONS)
    assert perm["bash"]["rm -rf /"] == "deny"
    assert perm["bash"]["rm -rf *"] == "ask"
    assert perm["bash"]["sudo *"] == "ask"
    assert perm["read"]["**/.env.production"] == "deny"
    assert perm["read"]["~/.ssh/**"] == "deny"


def test_project_permissions_reports_unprojectable_and_omitted_allow():
    perm, report = bo.project_permissions(CC_PERMISSIONS)
    assert "WebSearch" in report["skipped"]
    assert "WebFetch(domain:github.com)" in report["skipped"]
    assert "mcp__plugin_context7_context7__resolve-library-id" in report["skipped"]
    assert report["allow_omitted"] == 1  # Bash(git add *) — by design
    assert "git add *" not in perm["bash"]


def test_project_permissions_empty_pattern_is_unprojectable():
    perm, report = bo.project_permissions({"deny": ["Bash()"]})
    assert "Bash()" in report["skipped"]
    assert "" not in perm["bash"]


def test_project_permissions_orders_deny_after_ask():
    perm, _ = bo.project_permissions(CC_PERMISSIONS)
    keys = list(perm["bash"])
    assert keys[0] == "*"  # explicit default anchor
    assert keys.index("rm -rf *") < keys.index("rm -rf /")
    assert perm["bash"]["*"] == "allow"


def test_project_mcp_translates_stdio_without_env_only():
    servers, report = bo.project_mcp(CLAUDE_JSON["mcpServers"])
    assert servers["codex"] == {
        "type": "local", "command": ["codex", "mcp-server"], "enabled": True}
    assert "with-secret" in report["skipped"]  # env values never copied
    assert "remote-one" in report["skipped"]   # non-stdio not translated
    assert "with-secret" not in servers


def test_merge_preserves_user_keys_and_adds_own():
    merged = bo.merge_config(
        copy.deepcopy(USER_CONFIG), {"bash": {"*": "allow"}},
        {"codex": {"type": "local", "command": ["codex", "mcp-server"],
                   "enabled": True}})
    assert merged["model"] == USER_CONFIG["model"]
    assert merged["provider"] == USER_CONFIG["provider"]
    assert merged["mcp"]["context7"] == USER_CONFIG["mcp"]["context7"]
    assert merged["mcp"]["codex"]["command"] == ["codex", "mcp-server"]
    assert merged["permission"] == {"bash": {"*": "allow"}}


def test_merge_does_not_clobber_user_defined_same_name_server():
    existing = copy.deepcopy(USER_CONFIG)
    existing["mcp"]["codex"] = {"type": "local", "command": ["my-codex"],
                                "enabled": False}
    merged = bo.merge_config(
        existing, {}, {"codex": {"type": "local",
                                 "command": ["codex", "mcp-server"],
                                 "enabled": True}})
    assert merged["mcp"]["codex"]["command"] == ["my-codex"]


def test_merge_is_idempotent():
    once = bo.merge_config(copy.deepcopy(USER_CONFIG),
                           {"bash": {"*": "allow"}}, {})
    twice = bo.merge_config(copy.deepcopy(once), {"bash": {"*": "allow"}}, {})
    assert once == twice


def test_write_config_keeps_single_rolling_backup_mode_0600():
    d = tempfile.mkdtemp()
    cfg = os.path.join(d, "opencode.json")
    _write(cfg, json.dumps({"v": 1}))
    bo.write_config(cfg, {"v": 2})
    backup = cfg + ".backup"
    assert json.load(open(backup)) == {"v": 1}
    assert stat.S_IMODE(os.stat(backup).st_mode) == 0o600
    bo.write_config(cfg, {"v": 3})
    assert json.load(open(backup)) == {"v": 2}  # overwritten, not accumulated
    assert json.load(open(cfg)) == {"v": 3}


def test_write_config_without_existing_file_creates_no_backup():
    d = tempfile.mkdtemp()
    cfg = os.path.join(d, "opencode.json")
    bo.write_config(cfg, {"v": 1})
    assert json.load(open(cfg)) == {"v": 1}
    assert not os.path.exists(cfg + ".backup")


def test_write_config_creates_missing_target_directory():
    d = tempfile.mkdtemp()
    cfg = os.path.join(d, "fresh", "opencode", "opencode.json")
    bo.write_config(cfg, {"v": 1})
    assert json.load(open(cfg)) == {"v": 1}


def test_main_corrupt_config_exits_clearly_without_touching_it():
    root = _fixture_root()
    cfg = os.path.join(root, "opencode.json")
    _write(cfg, "{not json")
    exited = False
    try:
        bo.main(["--root", root,
                 "--agents-out", os.path.join(root, "out-agents"),
                 "--config", cfg])
    except SystemExit as e:
        exited = True
        assert "not valid JSON" in str(e.code)
    assert exited
    assert open(cfg).read() == "{not json"  # never overwritten
    assert not os.path.exists(cfg + ".backup")


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


def test_main_dry_run_writes_nothing():
    root = _fixture_root()
    out = os.path.join(root, "out-agents")
    cfg = os.path.join(root, "opencode.json")
    _write(cfg, json.dumps(USER_CONFIG))
    before = open(cfg).read()
    rc = bo.main(["--root", root, "--agents-out", out, "--config", cfg,
                  "--dry-run"])
    assert rc == 0
    assert not os.path.exists(out)
    assert open(cfg).read() == before
    assert not os.path.exists(cfg + ".backup")


def test_main_missing_claude_config_still_succeeds():
    root = _fixture_root()
    out = os.path.join(root, "out-agents")
    cfg = os.path.join(root, "opencode.json")
    _write(cfg, json.dumps(USER_CONFIG))
    rc = bo.main(["--root", root, "--agents-out", out, "--config", cfg,
                  "--claude-config", os.path.join(root, "absent.json")])
    assert rc == 0
    merged = json.load(open(cfg))
    assert "codex" not in merged["mcp"]  # no source — nothing invented


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
