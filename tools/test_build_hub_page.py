#!/usr/bin/env python3
"""Unit tests for the hub-visualization page generator (`build_hub_page`).

Run: `.venv/bin/python3 tools/test_build_hub_page.py` (exit 0 = pass). Needs
pyyaml (same `.venv` as the validators). Extraction + edge + layout logic is
pure and tested against temp fixtures; the render layer is smoke-checked only.
"""

import json
import os
import sqlite3
import sys
import tempfile

_TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _TOOLS)
import build_hub_page as bhp  # noqa: E402


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)


def _fixture_repo():
    """A minimal repo tree with two skills, one agent, one hooks.json."""
    root = tempfile.mkdtemp()
    _write(os.path.join(root, "adapters/claude-code/plugin/skills/surface-ticket/SKILL.md"),
           "---\nname: surface-ticket\nuser-invocable: false\n"
           "description: Capture a problem as a ticket.\n"
           "when_to_use: When a problem will not be fixed now.\n---\n\nbody\n")
    _write(os.path.join(root, "adapters/claude-code/plugin/skills/review-flow/SKILL.md"),
           "---\nname: review-flow\nuser-invocable: false\n"
           "description: The universal cycle.\nwhen_to_use: Any modifying task.\n---\n\n"
           "See [`surface-ticket`](../surface-ticket/SKILL.md) and "
           "[`mainframe-researcher`](../../agents/mainframe-researcher.md).\n")
    _write(os.path.join(root, "adapters/claude-code/agents/mainframe-decision-reviewer.md"),
           "---\nname: mainframe-decision-reviewer\ndescription: Adversarial review.\n"
           "model: opus\nskills:\n  - surface-ticket\n  - review-flow\n"
           "tools: Read, Grep, Glob\n---\n\nbody\n")
    # Mirror the real hooks.json shape: command is "python3", the script path
    # is in args[] — a parser that only reads command would miss every script.
    _write(os.path.join(root, "adapters/claude-code/plugin/hooks/hooks.json"), json.dumps({
        "hooks": {
            "Stop": [{"matcher": "*", "hooks": [
                {"type": "command", "command": "python3",
                 "args": ["${CLAUDE_PLUGIN_ROOT}/hooks/scripts/memory-reminder.py"]}]}],
            "PreToolUse": [{"matcher": "Bash", "hooks": [
                {"type": "command", "command": "python3",
                 "args": ["${CLAUDE_PLUGIN_ROOT}/hooks/scripts/secret-scan.py"]}]}],
        }
    }))
    _write(os.path.join(root, "adapters/claude-code/plugin/hooks/scripts/memory-reminder.py"),
           '#!/usr/bin/env python3\n"""Nudge the model to save a durable memory.\n\n'
           'More detail on the second paragraph.\n"""\nx = 1\n')
    return root


def test_parse_frontmatter_splits_meta_and_body():
    fm, body = bhp.parse_frontmatter(
        "---\nname: x\ndescription: hi\n---\n\nthe body\n")
    assert fm["name"] == "x"
    assert fm["description"] == "hi"
    assert "the body" in body


def test_parse_frontmatter_no_frontmatter_returns_empty_meta():
    fm, body = bhp.parse_frontmatter("no frontmatter here\n")
    assert fm == {}
    assert "no frontmatter" in body


def test_collect_skills_reads_fields_and_crossrefs():
    root = _fixture_repo()
    skills = {s["name"]: s for s in bhp.collect_skills(root)}
    assert set(skills) == {"surface-ticket", "review-flow"}
    assert skills["surface-ticket"]["user_invocable"] is False
    assert skills["surface-ticket"]["description"].startswith("Capture")
    assert "surface-ticket" in skills["review-flow"]["crossrefs"]
    assert "mainframe-researcher" in skills["review-flow"]["crossrefs"]
    assert skills["surface-ticket"]["crossrefs"] == []


def test_collect_agents_reads_skills_list():
    root = _fixture_repo()
    agents = {a["name"]: a for a in bhp.collect_agents(root)}
    assert "mainframe-decision-reviewer" in agents
    assert agents["mainframe-decision-reviewer"]["model"] == "opus"
    assert agents["mainframe-decision-reviewer"]["skills"] == ["surface-ticket", "review-flow"]


def test_collect_hooks_maps_event_matcher_script():
    root = _fixture_repo()
    hooks = bhp.collect_hooks(root)
    pairs = {(h["event"], h["script"]) for h in hooks}
    assert ("Stop", "memory-reminder.py") in pairs
    assert ("PreToolUse", "secret-scan.py") in pairs
    stop = [h for h in hooks if h["event"] == "Stop"][0]
    assert stop["matcher"] == "*"
    # purpose comes from the script's module docstring first line
    assert stop["purpose"] == "Nudge the model to save a durable memory."
    # script with no file on disk degrades to empty purpose, not a crash
    pre = [h for h in hooks if h["event"] == "PreToolUse"][0]
    assert pre["purpose"] == ""


def test_build_edges_covers_all_three_kinds():
    root = _fixture_repo()
    skills = bhp.collect_skills(root)
    agents = bhp.collect_agents(root)
    hooks = bhp.collect_hooks(root)
    edges = bhp.build_edges(skills, agents, hooks)
    triples = {(e["source"], e["target"], e["kind"]) for e in edges}
    assert ("review-flow", "surface-ticket", "skill-ref") in triples
    assert ("mainframe-decision-reviewer", "surface-ticket", "agent-skill") in triples
    assert ("mainframe-decision-reviewer", "review-flow", "agent-skill") in triples
    assert ("memory-reminder.py", "Stop", "hook-event") in triples


def test_build_edges_skips_crossref_to_unknown_node():
    root = _fixture_repo()
    skills = bhp.collect_skills(root)
    agents = bhp.collect_agents(root)
    edges = bhp.build_edges(skills, agents, [])
    # mainframe-researcher is referenced from review-flow but has no agent file in the
    # fixture; dropping the edge keeps the graph free of dangling targets.
    targets = {e["target"] for e in edges}
    assert "mainframe-researcher" not in targets


def test_dev_state_absent_db_reports_inactive():
    state = bhp.collect_dev_state(
        db_path="/nonexistent/telemetry.db", feedback_dir="/nonexistent/feedback")
    assert state["active"] is False
    assert state["telemetry"]["sessions"] == 0
    assert state["feedback"] == []


def test_dev_state_reads_event_counts_and_feedback():
    db = _telemetry_db([
        ("s1", "session", '{"phase":"start","source":"startup"}'),
        ("s1", "code_edit", '{"lang":"python","ext":".py","operation":"edit"}'),
        ("s2", "session", '{"phase":"start","source":"resume"}'),
    ], columns="session_id, event, payload")
    d = os.path.dirname(db)
    fb = os.path.join(d, "feedback")
    _write(os.path.join(fb, "20260101-120000-PROJ-some-friction.md"), "x")
    state = bhp.collect_dev_state(db_path=db, feedback_dir=fb)
    assert state["active"] is True
    assert state["telemetry"]["sessions"] == 2
    counts = dict(state["telemetry"]["event_counts"])
    assert counts["session"] == 2
    assert counts["code_edit"] == 1
    assert len(state["feedback"]) == 1


def test_compute_layout_groups_by_layer_with_distinct_columns():
    nodes = [
        {"id": "a", "layer": "skills"},
        {"id": "b", "layer": "skills"},
        {"id": "c", "layer": "agents"},
    ]
    pos = bhp.compute_layout(nodes, layer_order=["skills", "agents"])
    assert set(pos) == {"a", "b", "c"}
    # same layer shares a column (x), different layers do not
    assert pos["a"]["x"] == pos["b"]["x"]
    assert pos["a"]["x"] != pos["c"]["x"]
    assert pos["a"]["y"] != pos["b"]["y"]


def test_render_inlines_data_and_is_self_contained():
    root = _fixture_repo()
    manifest = bhp.build_manifest(root, db_path="/nonexistent", feedback_dir="/nonexistent")
    html = bhp.render(manifest, build_stamp="2026-06-13T10:00:00")
    assert "surface-ticket" in html
    assert "2026-06-13T10:00:00" in html
    # self-contained: no remote script/style, so it opens offline over file://
    assert "src=\"http" not in html
    assert "href=\"http" not in html
    assert "review-flow" in html
    # the data must reach app.js as a window property: a top-level `const` is NOT
    # exposed on window, which silently blanked the page until this was caught.
    assert "window.HUB_DATA =" in html
    assert "const HUB_DATA" not in html
    assert "window.HUB_AUTO_REFRESH_MS = 0" in html
    assert "static snapshot" in html

    live = bhp.render(manifest, build_stamp="2026-06-13T10:00:00",
                      auto_refresh_ms=15000)
    assert "window.HUB_AUTO_REFRESH_MS = 15000" in live
    assert "auto refresh · 15s" in live


def _fixture_export(root):
    """Settings + misc-layer artifacts under adapters/claude-code/export/ for the config collectors."""
    _write(os.path.join(root, "adapters/claude-code/export/settings.json"), json.dumps({
        "env": {"FOO": "1"},
        "permissions": {
            "allow": ["Bash(ls *)", "WebSearch"],
            "deny": ["Bash(rm -rf /)"],
            "ask": ["Bash(npm install *)", "Bash(sudo *)", "Bash(pip install *)"],
            "defaultMode": "auto",
        },
        "enabledPlugins": {"context7@official": True, "frontend@official": False},
        "model": "opus[1m]",
        "effortLevel": "xhigh",
        "outputStyle": "Explanatory Concise",
        "language": "Russian",
    }))
    _write(os.path.join(root, "adapters/claude-code/export/output-styles/explanatory-concise.md"),
           "---\nname: Explanatory Concise\n---\n\n# Explanatory Concise\n\n"
           "Concise with teaching insights.\n")
    _write(os.path.join(root, "shared/credentials/credentials-index.template.md"),
           "# Credentials index\n\nTemplate for a per-project secrets map.\n")
    os.makedirs(os.path.join(root, "adapters/claude-code/export/rules"), exist_ok=True)
    os.makedirs(os.path.join(root, "adapters/claude-code/plugin/commands"), exist_ok=True)


def test_collect_settings_reads_permissions_env_and_flags():
    root = tempfile.mkdtemp()
    _fixture_export(root)
    s = bhp.collect_settings(root)
    assert [len(s["permissions"][k]) for k in ("allow", "deny", "ask")] == [2, 1, 3]
    assert "Bash(sudo *)" in s["permissions"]["ask"]
    assert s["mode"] == "auto"
    assert s["env"] == {"FOO": "1"}
    assert s["flags"]["model"] == "opus[1m]"
    assert s["flags"]["effortLevel"] == "xhigh"
    assert s["plugins"] == {"context7@official": True, "frontend@official": False}


def test_collect_settings_absent_file_is_empty_not_crash():
    s = bhp.collect_settings("/nonexistent-root-xyz")
    assert s["permissions"] == {"allow": [], "deny": [], "ask": []}
    assert s["env"] == {}
    assert s["flags"] == {}


def test_collect_misc_reads_styles_templates_and_empty_layers():
    root = tempfile.mkdtemp()
    _fixture_export(root)
    m = bhp.collect_misc(root)
    styles = {x["name"]: x for x in m["output_styles"]}
    assert "Explanatory Concise" in styles
    assert "teaching" in styles["Explanatory Concise"]["summary"].lower()
    templates = {x["name"]: x for x in m["templates"]}
    assert "credentials-index" in templates
    assert "secrets map" in templates["credentials-index"]["summary"].lower()
    empty = {x["name"] for x in m["empty_layers"]}
    assert empty == {"rules", "commands"}


def _telemetry_db(rows, columns="ts, session_id, agent_type, event, payload"):
    """Create a telemetry DB and insert rows; returns the db path."""
    d = tempfile.mkdtemp()
    db = os.path.join(d, "telemetry.db")
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE events (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, "
                "schema_version INTEGER DEFAULT 2, session_id TEXT, prompt_id TEXT, "
                "agent_id TEXT, agent_type TEXT, tool_use_id TEXT, project TEXT, "
                "hook_event TEXT, event TEXT, payload TEXT)")
    ph = ",".join("?" for _ in columns.split(","))
    con.executemany(f"INSERT INTO events({columns}) VALUES ({ph})", rows)
    con.commit()
    con.close()
    return db


def test_dev_state_breaks_down_by_agent_and_day():
    db = _telemetry_db([
        ("2026-06-01T10:00:00Z", "s1", "Explore", "subagent_start", "{}"),
        ("2026-06-01T11:00:00Z", "s1", "Explore", "subagent_start", "{}"),
        ("2026-06-02T09:00:00Z", "s2", "", "session",
         '{"phase":"start","source":"startup"}'),
    ])
    state = bhp.collect_dev_state(db_path=db, feedback_dir="/nonexistent")
    by_agent = dict(state["telemetry"]["by_agent"])
    assert by_agent["Explore"] == 2
    assert by_agent["(main context)"] == 1
    by_day = dict(state["telemetry"]["by_day"])
    assert by_day["2026-06-01"] == 2
    assert by_day["2026-06-02"] == 1


def test_payload_breakdown_uses_validated_stream_and_surfaces_bad_rows():
    db = _telemetry_db([
        ("skill_request", '{"skill":"review-flow","invoker":"model"}'),
        ("skill_request", '{"skill":"review-flow","invoker":"model"}'),
        ("skill_request", '{"skill":"surface-ticket","invoker":"user"}'),
        ("skill_request", '{"other":"x"}'),
        ("skill_request", "not json"),
    ], columns="event, payload")
    state = bhp.collect_dev_state(db_path=db, feedback_dir="/nonexistent")
    b = next(item for item in state["telemetry"]["breakdowns"]
             if item["event"] == "skill_request")
    assert b["total"] == 3
    items = dict(b["items"])
    assert items["review-flow"] == 2
    assert items["surface-ticket"] == 1
    assert "(unrecognized)" not in items
    assert state["telemetry"]["invalid_rows"] == 2


def test_hook_effectiveness_aggregates_outcomes_and_skips_malformed_rows():
    db = _telemetry_db([
        ("2026-08-11T10:00:00", "s1", "", "hook_signal",
         '{"hook":"check.py","rule_id":"r","outcome":"noted",'
         '"count":3,"context_chars":120}'),
        ("2026-08-11T10:01:00", "s1", "", "hook_signal",
         '{"hook":"check.py","rule_id":"r","outcome":"resolved",'
         '"count":2,"context_chars":0}'),
        ("2026-08-11T10:02:00", "s2", "", "hook_signal",
         '{"hook":"check.py","rule_id":"r","outcome":"blocked",'
         '"count":1,"context_chars":80}'),
        ("2026-08-11T10:03:00", "s2", "", "hook_signal", "not json"),
    ])
    state = bhp.collect_dev_state(db_path=db, feedback_dir="/nonexistent")
    rows = state["telemetry"]["hook_effectiveness"]
    assert rows == [{
        "hook": "check.py", "rule_id": "r", "signals": 3, "sessions": 2,
        "noted": 3, "asked": 0, "blocked": 1, "resolved": 2,
        "context_chars": 200, "last_seen": "2026-08-11T10:02:00",
    }]


def _fixture_health(root):
    """A tree seeded with one broken cross-ref, one orphan, one missing script."""
    _write(os.path.join(root, "adapters/claude-code/plugin/skills/alpha/SKILL.md"),
           "---\nname: alpha\n---\n\nSee [`ghost`](../ghost/SKILL.md).\n")
    _write(os.path.join(root, "adapters/claude-code/plugin/skills/anchor/SKILL.md"),
           "---\nname: anchor\n---\n\nSee [`alpha`](../alpha/SKILL.md).\n")
    _write(os.path.join(root, "adapters/claude-code/plugin/skills/beta/SKILL.md"),
           "---\nname: beta\n---\n\nno refs here\n")
    _write(os.path.join(root, "adapters/claude-code/agents/gamma.md"),
           "---\nname: gamma\nskills:\n  - delta\n---\n\nbody\n")
    _write(os.path.join(root, "adapters/claude-code/plugin/hooks/hooks.json"), json.dumps({"hooks": {
        "Stop": [{"matcher": "*", "hooks": [{"type": "command", "command": "python3",
                  "args": ["${CLAUDE_PLUGIN_ROOT}/hooks/scripts/present.py"]}]}],
        "PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "python3",
                  "args": ["${CLAUDE_PLUGIN_ROOT}/hooks/scripts/absent.py"]}]}],
    }}))
    _write(os.path.join(root, "adapters/claude-code/plugin/hooks/scripts/present.py"),
           '"""Present hook."""\nx = 1\n')
    return root


def test_compute_health_flags_dangling_orphans_and_missing_scripts():
    root = _fixture_health(tempfile.mkdtemp())
    skills = bhp.collect_skills(root)
    agents = bhp.collect_agents(root)
    hooks = bhp.collect_hooks(root)
    health = bhp.compute_health(skills, agents, hooks, root)
    dangling = {(d["source"], d["target"]) for d in health["dangling"]}
    assert ("alpha", "ghost") in dangling          # skill cross-ref to a non-existent skill
    assert ("gamma", "delta") in dangling          # agent preloads a non-existent skill
    assert health["orphans"] == ["beta"]           # no edge in or out
    assert health["missing_scripts"] == ["absent.py"]


def test_compute_health_all_resolved_is_empty():
    root = tempfile.mkdtemp()
    _write(os.path.join(root, "adapters/claude-code/plugin/skills/solo/SKILL.md"),
           "---\nname: solo\n---\n\nSee [`peer`](../peer/SKILL.md).\n")
    _write(os.path.join(root, "adapters/claude-code/plugin/skills/peer/SKILL.md"),
           "---\nname: peer\n---\n\nSee [`solo`](../solo/SKILL.md).\n")
    health = bhp.compute_health(bhp.collect_skills(root), [], [], root)
    assert health == {"dangling": [], "orphans": [], "missing_scripts": []}


def test_compute_health_resolves_namespaced_agent_skills():
    root = tempfile.mkdtemp()
    skills = [{"name": "ticket", "crossrefs": []}]
    agents = [{"name": "worker", "skills": ["mainframe:ticket"]}]
    health = bhp.compute_health(skills, agents, [], root)
    assert health == {"dangling": [], "orphans": [], "missing_scripts": []}


def _usage_fixture():
    """A temp projects dir with one transcript covering every correctness trap:
    streaming partials sharing one message.id, an iterations[] that restates the
    usage, a sidechain (subagent) line, and an assistant line with no usage."""
    proj = tempfile.mkdtemp()
    sess = os.path.join(proj, "demo-project")
    lines = [
        {"type": "assistant", "timestamp": "2026-06-01T03:00:00.000Z", "sessionId": "s1",
         "message": {"id": "mA", "model": "claude-opus-4-8",
                     "usage": {"input_tokens": 10, "output_tokens": 100,
                               "cache_read_input_tokens": 1000,
                               "cache_creation_input_tokens": 50}}},
        {"type": "assistant", "timestamp": "2026-06-01T03:00:01.000Z", "sessionId": "s1",
         "message": {"id": "mA", "model": "claude-opus-4-8",
                     "usage": {"input_tokens": 10, "output_tokens": 500,
                               "cache_read_input_tokens": 1000,
                               "cache_creation_input_tokens": 50,
                               "iterations": [{"output_tokens": 500, "input_tokens": 10}]}}},
        {"type": "user", "timestamp": "2026-06-01T03:00:02.000Z", "sessionId": "s1",
         "message": {"role": "user", "content": "hi"}},
        {"type": "assistant", "timestamp": "2026-06-02T05:00:00.000Z", "sessionId": "s1",
         "message": {"id": "mB", "model": "claude-sonnet-4-6",
                     "usage": {"input_tokens": 20, "output_tokens": 200,
                               "cache_read_input_tokens": 0,
                               "cache_creation_input_tokens": 0}}},
        {"type": "assistant", "timestamp": "2026-06-02T05:01:00.000Z", "sessionId": "s1",
         "isSidechain": True,
         "message": {"id": "mC", "model": "claude-haiku-4-5",
                     "usage": {"input_tokens": 5, "output_tokens": 900}}},
        {"type": "assistant", "timestamp": "2026-06-02T06:00:00.000Z", "sessionId": "s1",
         "message": {"id": "mD", "model": "claude-opus-4-8"}},
    ]
    _write(os.path.join(sess, "s1.jsonl"),
           "\n".join(json.dumps(line) for line in lines) + "\n")
    return proj


def test_collect_usage_combines_main_and_subagents_with_split():
    proj = _usage_fixture()
    cache = os.path.join(tempfile.mkdtemp(), "usage-cache.json")
    u = bhp.collect_usage(projects_dir=proj, cache_path=cache)
    assert u["active"] is True
    # combined: streaming still deduped (mA out=500, not 600); subagent mC INCLUDED
    assert u["tokens"]["out"] == 1600        # main 700 + subagent 900
    assert u["tokens"]["in"] == 35           # mA 10 + mB 20 + mC 5
    assert u["tokens"]["total"] == 1635
    assert u["tokens"]["cache_read"] == 1000 and u["tokens"]["cache_creation"] == 50
    assert u["messages"] == 4                # mA, mB, mD (main) + mC (subagent)
    assert u["no_usage"] == 1                # mD
    assert u["sessions"] == 1
    # split surfaces main vs subagents separately
    assert u["split"]["main"]["messages"] == 3 and u["split"]["main"]["total"] == 730
    assert u["split"]["sub"]["messages"] == 1 and u["split"]["sub"]["total"] == 905


def test_collect_usage_per_model_includes_subagents_and_by_day_tokens():
    proj = _usage_fixture()
    cache = os.path.join(tempfile.mkdtemp(), "usage-cache.json")
    u = bhp.collect_usage(projects_dir=proj, cache_path=cache)
    models = {m["model"]: m for m in u["models"]}
    assert models["claude-opus-4-8"]["total"] == 510
    assert models["claude-sonnet-4-6"]["total"] == 220
    assert models["claude-haiku-4-5"]["total"] == 905   # subagent model now counted
    assert u["favorite_model"] == "claude-haiku-4-5"
    assert u["active_days"] == 2
    # by_day now carries [date, messages, tokens]
    byday = {d: (msgs, tok) for d, msgs, tok in u["by_day"]}
    assert byday["2026-06-01"] == (1, 510)
    assert byday["2026-06-02"] == (3, 1125)   # mB 220 + mC 905 + mD 0 (no-usage)


def test_collect_usage_absent_projects_degrades():
    u = bhp.collect_usage(projects_dir="/no/such/dir",
                          cache_path=os.path.join(tempfile.mkdtemp(), "c.json"))
    assert u == {"active": False}


def test_collect_usage_cache_written_and_reused():
    proj = _usage_fixture()
    cache = os.path.join(tempfile.mkdtemp(), "usage-cache.json")
    first = bhp.collect_usage(projects_dir=proj, cache_path=cache)
    assert os.path.isfile(cache)
    second = bhp.collect_usage(projects_dir=proj, cache_path=cache)  # cache hit
    assert first == second


def test_streaks_current_and_longest():
    assert bhp._streaks([]) == (0, 0)
    assert bhp._streaks(["2026-06-01"]) == (1, 1)
    # 3 consecutive, gap, 1 → longest 3, current (run ending at latest) 1
    assert bhp._streaks(["2026-06-01", "2026-06-02", "2026-06-03",
                         "2026-06-07"]) == (1, 3)
    assert bhp._streaks(["2026-06-01", "2026-06-02", "2026-06-03"]) == (3, 3)


def _run_all():
    fns = [v for k, v in sorted(globals().items())
           if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"  ok  {fn.__name__}")
        except Exception as exc:
            failed += 1
            print(f"FAIL  {fn.__name__}: {exc!r}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_run_all())
