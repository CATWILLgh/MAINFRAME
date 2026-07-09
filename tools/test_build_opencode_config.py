#!/usr/bin/env python3
"""Unit tests for the OpenCode config/permission/MCP merge (`build_opencode`).

Run: `.venv/bin/python3 tools/test_build_opencode_config.py` (exit 0 = pass).
Needs pyyaml (same `.venv` as the validators). Covers permission projection,
MCP server translation, config merge/write, and the config-facing `main()`
paths. Shares its fixtures with the sibling `tools/test_build_opencode.py`
(agent projection + goldens) rather than duplicating them.
"""

import copy
import json
import os
import stat
import sys
import tempfile

_TOOLS = os.path.dirname(os.path.abspath(__file__))
_OC_ADAPTER = os.path.join(os.path.dirname(_TOOLS), "adapters", "opencode")
sys.path.insert(0, _TOOLS)
sys.path.insert(0, _OC_ADAPTER)
import build_opencode as bo
from test_build_opencode import (
    _write, _fixture_root, CC_PERMISSIONS, USER_CONFIG, CLAUDE_JSON,
)


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


def test_default_root_resolves_to_repo_root_not_adapters():
    # Regression: after the tools/ -> adapters/opencode/ relocation the default
    # root must still be the repo root (three levels up), or a bare run reads
    # no agents/permissions and clobbers the user's config with empties.
    repo = bo._default_root()
    assert os.path.isdir(os.path.join(repo, "core", "agents")), repo
    assert os.path.basename(repo) != "adapters", repo


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
