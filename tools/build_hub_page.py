#!/usr/bin/env python3
"""Generate a self-contained local reference page for the MAINFRAME hub.

Walks the repo, extracts every artifact (skills / agents / hooks) plus the
relationships between them and the live `--dev` runtime state, then bakes it all
into one offline `hub.html` (data inlined — no server, no `fetch`, opens over
`file://`). Dev-only tool: telemetry is read-only and absence degrades to a
"dev not active" panel rather than an error.

Run: `.venv/bin/python3 tools/build_hub_page.py` (needs pyyaml, same `.venv` as
the validators). Output defaults to `workspace/runtime/hub.html`.
"""

import argparse
import ast
import datetime
import json
import os
import re
import sqlite3
import sys

import yaml

_ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hub_page_assets")
_DEFAULT_DB = os.path.expanduser("~/.claude/mainframe/telemetry/telemetry.db")
_DEFAULT_FEEDBACK = os.path.expanduser("~/.claude/mainframe/feedback")

# Layer columns, left to right, in the grouped graph layout.
LAYER_ORDER = ["events", "hooks", "agents", "skills", "dev"]

_SKILL_REF = re.compile(r"\]\(\.\./([a-z0-9][a-z0-9-]*)/SKILL\.md\)")
_AGENT_REF = re.compile(r"\]\(\.\./\.\./agents/([a-z0-9][a-z0-9-]*)\.md\)")
_SCRIPT_NAME = re.compile(r"([\w-]+\.py)")

# Top-level settings.json keys surfaced on the Config tab (the behaviour-shaping
# ones); permission lists, env and plugins are pulled out separately.
_SETTINGS_FLAG_KEYS = ["model", "effortLevel", "advisorModel", "outputStyle",
                       "language", "autoCompactEnabled", "autoMemoryEnabled",
                       "teammateMode"]
# (name, repo-relative path) layers that exist as reserved-but-empty directories.
_EMPTY_LAYER_PROBES = (("rules", "export/rules"), ("commands", "plugin-dist/commands"))


def parse_frontmatter(text):
    """Return (frontmatter dict, body). Empty dict when there is no frontmatter."""
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    meta = yaml.safe_load(parts[1]) or {}
    if not isinstance(meta, dict):
        return {}, text
    return meta, parts[2]


def _crossrefs(body):
    seen, out = set(), []
    for name in _SKILL_REF.findall(body) + _AGENT_REF.findall(body):
        if name not in seen:
            seen.add(name)
            out.append(name)
    return out


def _read(path):
    with open(path) as f:
        return f.read()


def collect_skills(root):
    """Skills from plugin-dist/skills/ (and dev/skills/, flagged dev=True)."""
    out = []
    for base, dev in (("plugin-dist/skills", False), ("dev/skills", True)):
        sdir = os.path.join(root, base)
        if not os.path.isdir(sdir):
            continue
        for name in sorted(os.listdir(sdir)):
            md = os.path.join(sdir, name, "SKILL.md")
            if not os.path.isfile(md):
                continue
            fm, body = parse_frontmatter(_read(md))
            out.append({
                "name": fm.get("name", name),
                "description": fm.get("description", ""),
                "when_to_use": fm.get("when_to_use", ""),
                "user_invocable": bool(fm.get("user-invocable", False)),
                "crossrefs": _crossrefs(body),
                "dev": dev,
            })
    return out


def collect_agents(root):
    adir = os.path.join(root, "plugin-dist/agents")
    out = []
    if not os.path.isdir(adir):
        return out
    for fn in sorted(os.listdir(adir)):
        if not fn.endswith(".md"):
            continue
        fm, _ = parse_frontmatter(_read(os.path.join(adir, fn)))
        skills = fm.get("skills") or []
        if not isinstance(skills, list):
            skills = []
        out.append({
            "name": fm.get("name", fn[:-3]),
            "description": fm.get("description", ""),
            "model": fm.get("model", ""),
            "tools": fm.get("tools", ""),
            "skills": skills,
        })
    return out


def _script_purpose(scripts_dir, script, cache):
    """First line of the script's module docstring, '' when unreadable/absent."""
    if script in cache:
        return cache[script]
    path = os.path.join(scripts_dir, script)
    purpose = ""
    if os.path.isfile(path):
        try:
            doc = ast.get_docstring(ast.parse(_read(path))) or ""
            purpose = doc.strip().split("\n", 1)[0].strip()
        except (SyntaxError, ValueError):
            purpose = ""
    cache[script] = purpose
    return purpose


def collect_hooks(root):
    path = os.path.join(root, "plugin-dist/hooks/hooks.json")
    if not os.path.isfile(path):
        return []
    data = json.loads(_read(path))
    scripts_dir = os.path.join(root, "plugin-dist/hooks/scripts")
    cache = {}
    out = []
    for event, groups in data.get("hooks", {}).items():
        for group in groups:
            matcher = group.get("matcher", "")
            for hook in group.get("hooks", []):
                # The script name lives in args[] ("python3" + ["…/foo.py"]),
                # not in command; search both so either shape resolves.
                text = hook.get("command", "") + " " + " ".join(hook.get("args") or [])
                m = _SCRIPT_NAME.search(text)
                if m:
                    out.append({"event": event, "matcher": matcher, "script": m.group(1),
                                "purpose": _script_purpose(scripts_dir, m.group(1), cache)})
    return out


def build_edges(skills, agents, hooks):
    """Edges from existing structure; targets that are not nodes are dropped."""
    skill_names = {s["name"] for s in skills}
    known = skill_names | {a["name"] for a in agents}
    edges = []
    for s in skills:
        for target in s["crossrefs"]:
            if target in known:
                edges.append({"source": s["name"], "target": target, "kind": "skill-ref"})
    for a in agents:
        for skill in a["skills"]:
            if skill in skill_names:
                edges.append({"source": a["name"], "target": skill, "kind": "agent-skill"})
    for h in hooks:
        edges.append({"source": h["script"], "target": h["event"], "kind": "hook-event"})
    return edges


def collect_dev_state(db_path, feedback_dir):
    """Read-only telemetry + feedback snapshot. Absence => dev not active."""
    state = {"active": False, "telemetry": {"sessions": 0, "events": []}, "feedback": []}
    if os.path.isfile(db_path):
        try:
            con = sqlite3.connect(db_path)
            try:
                sessions = con.execute(
                    "SELECT COUNT(DISTINCT session_id) FROM events").fetchone()[0]
                events = con.execute(
                    "SELECT event, COUNT(*) FROM events GROUP BY event ORDER BY 2 DESC"
                ).fetchall()
            finally:
                con.close()
            state["telemetry"] = {"sessions": sessions, "events": [list(r) for r in events]}
            state["active"] = True
        except sqlite3.Error:
            pass
    if os.path.isdir(feedback_dir):
        state["feedback"] = sorted(
            f for f in os.listdir(feedback_dir) if f.endswith(".md"))
    return state


def collect_settings(root):
    """Read-only snapshot of export/settings.json: permissions, env, key flags."""
    empty = {"permissions": {"allow": [], "deny": [], "ask": []},
             "mode": "", "env": {}, "plugins": {}, "flags": {}}
    path = os.path.join(root, "export/settings.json")
    if not os.path.isfile(path):
        return empty
    try:
        data = json.loads(_read(path))
    except (json.JSONDecodeError, ValueError):
        return empty
    perms = data.get("permissions") or {}
    return {
        "permissions": {k: list(perms.get(k) or []) for k in ("allow", "deny", "ask")},
        "mode": perms.get("defaultMode", ""),
        "env": data.get("env") or {},
        "plugins": data.get("enabledPlugins") or {},
        "flags": {k: data[k] for k in _SETTINGS_FLAG_KEYS if k in data},
    }


def _doc_summary(text):
    """First non-empty non-heading body line; falls back to the heading text."""
    _, body = parse_frontmatter(text)
    heading = ""
    for line in body.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("#"):
            heading = heading or line.lstrip("#").strip()
            continue
        return line
    return heading


def _collect_docs(directory, name_from_frontmatter):
    out = []
    if not os.path.isdir(directory):
        return out
    for fn in sorted(os.listdir(directory)):
        if not fn.endswith(".md"):
            continue
        text = _read(os.path.join(directory, fn))
        fm, _ = parse_frontmatter(text)
        name = (fm.get("name") if name_from_frontmatter else None) or fn[:-3]
        out.append({"name": name, "summary": _doc_summary(text)})
    return out


def _is_empty_layer(directory):
    return (not os.path.isdir(directory)) or not any(
        f.endswith(".md") for f in os.listdir(directory))


def collect_misc(root):
    """Output styles, templates, and explicit markers for reserved-empty layers."""
    empty = [{"name": name, "path": rel}
             for name, rel in _EMPTY_LAYER_PROBES
             if _is_empty_layer(os.path.join(root, rel))]
    return {
        "output_styles": _collect_docs(os.path.join(root, "export/output-styles"), True),
        "templates": _collect_docs(os.path.join(root, "export/templates"), False),
        "empty_layers": empty,
    }


def build_nodes(skills, agents, hooks):
    nodes = []
    for s in skills:
        nodes.append({"id": s["name"], "label": s["name"],
                      "layer": "dev" if s["dev"] else "skills"})
    for a in agents:
        nodes.append({"id": a["name"], "label": a["name"], "layer": "agents"})
    seen_scripts, seen_events = set(), set()
    for h in hooks:
        if h["script"] not in seen_scripts:
            seen_scripts.add(h["script"])
            nodes.append({"id": h["script"], "label": h["script"], "layer": "hooks"})
        if h["event"] not in seen_events:
            seen_events.add(h["event"])
            nodes.append({"id": h["event"], "label": h["event"], "layer": "events"})
    return nodes


def compute_layout(nodes, layer_order):
    """Group nodes into one column per layer: same layer shares x, distinct y."""
    col_w, row_h, x0, y0 = 280, 64, 90, 90
    by_layer = {}
    for n in nodes:
        by_layer.setdefault(n["layer"], []).append(n["id"])
    ordered = list(layer_order) + [l for l in by_layer if l not in layer_order]
    pos = {}
    for li, layer in enumerate(ordered):
        x = x0 + li * col_w
        for j, nid in enumerate(by_layer.get(layer, [])):
            pos[nid] = {"x": x, "y": y0 + j * row_h}
    return pos


def build_manifest(root, db_path=_DEFAULT_DB, feedback_dir=_DEFAULT_FEEDBACK):
    skills = collect_skills(root)
    agents = collect_agents(root)
    hooks = collect_hooks(root)
    nodes = build_nodes(skills, agents, hooks)
    return {
        "skills": skills,
        "agents": agents,
        "hooks": hooks,
        "edges": build_edges(skills, agents, hooks),
        "dev_state": collect_dev_state(db_path, feedback_dir),
        "settings": collect_settings(root),
        "misc": collect_misc(root),
        "nodes": nodes,
        "layout": compute_layout(nodes, LAYER_ORDER),
        "layer_order": LAYER_ORDER,
    }


def render(manifest, build_stamp, assets_dir=_ASSETS):
    template = _read(os.path.join(assets_dir, "template.html"))
    style = _read(os.path.join(assets_dir, "style.css"))
    app_js = _read(os.path.join(assets_dir, "app.js"))
    # `<\/` keeps an accidental "</script>" inside the JSON from closing the tag.
    data = json.dumps(manifest, ensure_ascii=False).replace("</", "<\\/")
    return (template
            .replace("{{BUILD_STAMP}}", build_stamp)
            .replace("{{STYLE}}", style)
            .replace("{{DATA}}", data)
            .replace("{{APP_JS}}", app_js))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=os.path.join(os.path.dirname(_ASSETS), ".."))
    parser.add_argument("--out", default=None,
                        help="output path (default: <root>/workspace/runtime/hub.html)")
    parser.add_argument("--db", default=_DEFAULT_DB)
    parser.add_argument("--feedback", default=_DEFAULT_FEEDBACK)
    args = parser.parse_args()

    root = os.path.abspath(args.root)
    out = args.out or os.path.join(root, "workspace/runtime/hub.html")
    manifest = build_manifest(root, db_path=args.db, feedback_dir=args.feedback)
    stamp = datetime.datetime.now().isoformat(timespec="seconds")
    html = render(manifest, build_stamp=stamp)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        f.write(html)
    dev = "active" if manifest["dev_state"]["active"] else "not active"
    print(f"wrote {out}  ({len(manifest['nodes'])} nodes, "
          f"{len(manifest['edges'])} edges, dev {dev})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
