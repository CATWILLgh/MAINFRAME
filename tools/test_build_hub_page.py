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
import build_hub_page as bhp


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)


def _fixture_repo():
    """A minimal repo tree with two skills, one agent, one hooks.json."""
    root = tempfile.mkdtemp()
    _write(os.path.join(root, "plugin-dist/skills/surface-ticket/SKILL.md"),
           "---\nname: surface-ticket\nuser-invocable: false\n"
           "description: Capture a problem as a ticket.\n"
           "when_to_use: When a problem will not be fixed now.\n---\n\nbody\n")
    _write(os.path.join(root, "plugin-dist/skills/task-workflow/SKILL.md"),
           "---\nname: task-workflow\nuser-invocable: false\n"
           "description: The universal cycle.\nwhen_to_use: Any modifying task.\n---\n\n"
           "See [`surface-ticket`](../surface-ticket/SKILL.md) and "
           "[`web-search`](../../agents/web-search.md).\n")
    _write(os.path.join(root, "plugin-dist/agents/decision-reviewer.md"),
           "---\nname: decision-reviewer\ndescription: Adversarial review.\n"
           "model: opus\nskills:\n  - surface-ticket\n  - task-workflow\n"
           "tools: Read, Grep, Glob\n---\n\nbody\n")
    # Mirror the real hooks.json shape: command is "python3", the script path
    # is in args[] — a parser that only reads command would miss every script.
    _write(os.path.join(root, "plugin-dist/hooks/hooks.json"), json.dumps({
        "hooks": {
            "Stop": [{"matcher": "*", "hooks": [
                {"type": "command", "command": "python3",
                 "args": ["${CLAUDE_PLUGIN_ROOT}/hooks/scripts/memory-reminder.py"]}]}],
            "PreToolUse": [{"matcher": "Bash", "hooks": [
                {"type": "command", "command": "python3",
                 "args": ["${CLAUDE_PLUGIN_ROOT}/hooks/scripts/secret-scan.py"]}]}],
        }
    }))
    _write(os.path.join(root, "plugin-dist/hooks/scripts/memory-reminder.py"),
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
    assert set(skills) == {"surface-ticket", "task-workflow"}
    assert skills["surface-ticket"]["user_invocable"] is False
    assert skills["surface-ticket"]["description"].startswith("Capture")
    assert "surface-ticket" in skills["task-workflow"]["crossrefs"]
    assert "web-search" in skills["task-workflow"]["crossrefs"]
    assert skills["surface-ticket"]["crossrefs"] == []


def test_collect_agents_reads_skills_list():
    root = _fixture_repo()
    agents = {a["name"]: a for a in bhp.collect_agents(root)}
    assert "decision-reviewer" in agents
    assert agents["decision-reviewer"]["model"] == "opus"
    assert agents["decision-reviewer"]["skills"] == ["surface-ticket", "task-workflow"]


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
    assert ("task-workflow", "surface-ticket", "skill-ref") in triples
    assert ("decision-reviewer", "surface-ticket", "agent-skill") in triples
    assert ("decision-reviewer", "task-workflow", "agent-skill") in triples
    assert ("memory-reminder.py", "Stop", "hook-event") in triples


def test_build_edges_skips_crossref_to_unknown_node():
    root = _fixture_repo()
    skills = bhp.collect_skills(root)
    agents = bhp.collect_agents(root)
    edges = bhp.build_edges(skills, agents, [])
    # web-search is referenced from task-workflow but has no agent file in the
    # fixture; dropping the edge keeps the graph free of dangling targets.
    targets = {e["target"] for e in edges}
    assert "web-search" not in targets


def test_dev_state_absent_db_reports_inactive():
    state = bhp.collect_dev_state(
        db_path="/nonexistent/telemetry.db", feedback_dir="/nonexistent/feedback")
    assert state["active"] is False
    assert state["telemetry"]["sessions"] == 0
    assert state["feedback"] == []


def test_dev_state_reads_event_counts_and_feedback():
    d = tempfile.mkdtemp()
    db = os.path.join(d, "telemetry.db")
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE events (id INTEGER PRIMARY KEY, ts TEXT, "
                "session_id TEXT, agent_type TEXT, project TEXT, event TEXT, payload TEXT)")
    con.executemany("INSERT INTO events(session_id, event) VALUES (?,?)",
                    [("s1", "session"), ("s1", "code_edit"), ("s2", "session")])
    con.commit()
    con.close()
    fb = os.path.join(d, "feedback")
    _write(os.path.join(fb, "20260101-120000-PROJ-some-friction.md"), "x")
    state = bhp.collect_dev_state(db_path=db, feedback_dir=fb)
    assert state["active"] is True
    assert state["telemetry"]["sessions"] == 2
    counts = dict(state["telemetry"]["events"])
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
    assert "task-workflow" in html
    # the data must reach app.js as a window property: a top-level `const` is NOT
    # exposed on window, which silently blanked the page until this was caught.
    assert "window.HUB_DATA =" in html
    assert "const HUB_DATA" not in html


def _fixture_export(root):
    """Settings + misc-layer artifacts under export/ for the config collectors."""
    _write(os.path.join(root, "export/settings.json"), json.dumps({
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
        "advisorModel": "opus",
        "outputStyle": "Explanatory Concise",
        "language": "Russian",
    }))
    _write(os.path.join(root, "export/output-styles/explanatory-concise.md"),
           "---\nname: Explanatory Concise\n---\n\n# Explanatory Concise\n\n"
           "Concise with teaching insights.\n")
    _write(os.path.join(root, "export/templates/credentials-index.md"),
           "# Credentials index\n\nTemplate for a per-project secrets map.\n")
    os.makedirs(os.path.join(root, "export/rules"), exist_ok=True)
    os.makedirs(os.path.join(root, "plugin-dist/commands"), exist_ok=True)


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
