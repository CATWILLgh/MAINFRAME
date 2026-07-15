#!/usr/bin/env python3
"""Test OpenCode permission, MCP, config, and config-facing main paths."""

import copy
import contextlib
import io
import json
import os
import stat
import sys
import tempfile
from unittest import mock

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


def _main_args(root, cfg, out, state=None):
    args = ["--root", root, "--agents-out", out, "--config", cfg,
            "--claude-config", os.path.join(root, "absent-claude.json")]
    return args + (["--permission-state", state] if state else [])


def _assert_main_failure_without_writes(root, patch_open=None, state_text=None):
    cfg = os.path.join(root, "opencode.json")
    out = os.path.join(root, "out-agents")
    state = os.path.join(root, "permission-state.json")
    _write(cfg, json.dumps(USER_CONFIG, indent=2) + "\n")
    if state_text is not None:
        _write(state, state_text)
    before_cfg = open(cfg).read()
    before_state = open(state).read() if os.path.exists(state) else None
    default_state = cfg + ".mainframe-permissions.json"
    stderr = io.StringIO()
    failed = False
    manager = patch_open or contextlib.nullcontext()
    with manager, contextlib.redirect_stderr(stderr):
        try:
            explicit_state = state if state_text is not None else None
            rc = bo.main(_main_args(root, cfg, out, explicit_state))
            failed = rc != 0
        except SystemExit:
            failed = True
        except (OSError, TypeError, ValueError, AttributeError):
            failed = True
    assert "unrecognized arguments" not in stderr.getvalue(), stderr.getvalue()
    changed = open(cfg).read() != before_cfg
    assert failed, ("invalid permission input unexpectedly succeeded; "
                    f"config_changed={changed}, agents_written={os.path.exists(out)}")
    assert open(cfg).read() == before_cfg
    assert not os.path.exists(cfg + ".backup")
    assert not os.path.exists(out)
    if before_state is None:
        assert not os.path.exists(state)
    else:
        assert open(state).read() == before_state
    if state_text is None:
        assert not os.path.exists(default_state)


def _rules_path(root): return os.path.join(root, "core", "permissions", "rules.json")


def test_main_missing_rules_fails_before_writes():
    root = _fixture_root()
    os.unlink(_rules_path(root))
    _assert_main_failure_without_writes(root)


def test_main_invalid_rules_fail_before_writes():
    raw_rules = [
        '{"allow": [], "allow": [], "deny": [], "ask": []}', "{not json",
        "[]", '{"allow": [], "deny": []}',
        '{"allow": "bad", "deny": [], "ask": []}',
        '{"allow": [], "deny": [42], "ask": []}',
        '{"allow": [], "deny": [], "ask": []}',
        '{"allow": ["Bash(git add *)"], "deny": [], "ask": []}',
        '{"allow": [], "deny": ["WebSearch"], "ask": []}',
    ]
    for raw in raw_rules:
        root = _fixture_root()
        _write(_rules_path(root), raw)
        _assert_main_failure_without_writes(root)


def test_main_unreadable_rules_fail_before_writes():
    root = _fixture_root()
    rules = _rules_path(root)
    real_open = open
    def guarded_open(path, *args, **kwargs):
        if os.fspath(path) == rules:
            raise PermissionError(rules)
        return real_open(path, *args, **kwargs)

    _assert_main_failure_without_writes(
        root, mock.patch("builtins.open", side_effect=guarded_open))


def _merge_permissions(existing, generated, owned):
    assert hasattr(bo, "merge_permissions"), "merge_permissions is missing"
    return bo.merge_permissions(existing, generated, owned)


def test_merge_permissions_preserves_scalar_permission():
    merged, next_owned = _merge_permissions(
        "ask", {"bash": {"*": "allow"}}, {})
    assert merged == "ask"
    assert next_owned.get("bash") is None


def test_merge_permissions_preserves_unknown_entries_and_order():
    existing = {"edit": "ask", "fetch*": "deny"}
    generated = {"bash": {"*": "allow"}}
    merged, next_owned = _merge_permissions(existing, generated, {})
    assert list(merged) == ["edit", "fetch*", "bash"]
    assert merged["edit"] == "ask" and merged["fetch*"] == "deny"
    assert next_owned == {
        "edit": None, "fetch*": None, "bash": generated["bash"]}


def test_merge_permissions_wildcards_block_matching_new_actions():
    for key, action in (("*", "bash"), ("b*", "bash"),
                        ("?ash", "bash"), ("bash *", "bash"),
                        ("r*", "read")):
        existing = {key: "deny"}
        generated = {action: {"*": "allow"}}
        merged, next_owned = _merge_permissions(existing, generated, {})
        assert merged == existing, (key, merged)
        again, _ = _merge_permissions(merged, generated, next_owned)
        assert again == existing, (key, again)


def test_merge_permissions_nonmatching_wildcard_allows_new_action():
    generated = {"bash": {"*": "allow"}}
    for pattern in ("z*", "[b]ash"):
        merged, next_owned = _merge_permissions(
            {pattern: "deny"}, generated, {})
        assert list(merged) == [pattern, "bash"]
        assert next_owned == {pattern: None, "bash": generated["bash"]}


def test_merge_permissions_owned_action_updates_and_removes():
    old = {"*": "allow", "old *": "deny"}
    new = {"*": "allow", "new *": "deny"}
    merged, next_owned = _merge_permissions(
        {"edit": "ask", "bash": old}, {"bash": new}, {"bash": old})
    assert merged == {"edit": "ask", "bash": new}
    assert next_owned == {"bash": new, "edit": None}
    removed, final_owned = _merge_permissions(merged, {}, next_owned)
    assert removed == {"edit": "ask"}
    assert final_owned == {"edit": None}


def test_merge_permissions_user_change_relinquishes_ownership():
    old = {"*": "allow"}
    user = {"custom *": "deny"}
    merged, next_owned = _merge_permissions(
        {"bash": user}, {"bash": old}, {"bash": old})
    assert merged == {"bash": user}
    changed, _ = _merge_permissions(
        merged, {"bash": {"new *": "deny"}}, next_owned)
    assert changed == {"bash": user}


def test_merge_permissions_user_deletion_is_not_readded():
    old = {"*": "allow"}
    merged, next_owned = _merge_permissions({}, {"bash": old}, {"bash": old})
    assert merged == {}
    again, _ = _merge_permissions(merged, {"bash": old}, next_owned)
    assert again == {}


def test_merge_permissions_without_state_never_adopts_existing_action():
    old = {"*": "allow"}
    merged, next_owned = _merge_permissions({"bash": old}, {"bash": old}, {})
    assert merged == {"bash": old}
    changed, _ = _merge_permissions(
        merged, {"bash": {"new *": "deny"}}, next_owned)
    assert changed == {"bash": old}


def test_main_invalid_permission_state_fails_before_writes():
    invalid_states = [
        "{not json", '{"version": 1, "version": 1, "actions": {}}',
        '{"version": true, "actions": {}}', '{"version": 1, "actions": '
        '{"bash": "invalid"}}',
    ]
    for state_text in invalid_states:
        _assert_main_failure_without_writes(_fixture_root(), state_text=state_text)


def test_main_writes_secret_free_state_mode_0600_and_is_idempotent():
    root = _fixture_root()
    cfg = os.path.join(root, "opencode.json")
    out = os.path.join(root, "out-agents")
    state = os.path.join(root, "permission-state.json")
    _write(cfg, json.dumps(USER_CONFIG))
    try:
        assert bo.main(_main_args(root, cfg, out, state)) == 0
    except SystemExit as exc:
        raise AssertionError("--permission-state is not supported") from exc
    state_data = json.load(open(state))
    assert state_data["version"] == 1
    assert state_data["actions"] == json.load(open(cfg))["permission"]
    assert stat.S_IMODE(os.stat(state).st_mode) == 0o600
    assert "provider" not in state_data and "apiKey" not in state_data
    before = (open(cfg).read(), open(state).read())
    assert bo.main(_main_args(root, cfg, out, state)) == 0
    assert (open(cfg).read(), open(state).read()) == before


def test_write_permission_state_publish_failure_preserves_old_state():
    directory = tempfile.mkdtemp()
    state = os.path.join(directory, "state.json")
    _write(state, '{"old": true}\n')
    with mock.patch("permission_config.os.replace", side_effect=OSError("boom")):
        try:
            bo.write_permission_state(state, {"bash": {"*": "allow"}})
            raise AssertionError("publish failure was swallowed")
        except OSError:
            pass
    assert open(state).read() == '{"old": true}\n'
    assert os.listdir(directory) == ["state.json"]


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
