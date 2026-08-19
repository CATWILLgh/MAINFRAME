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
import sys
import time

import yaml

import native_telemetry_receiver

from telemetry_data import (
    build_multi_report as build_multi_telemetry_report,
    build_permission_audit,
    build_report as build_telemetry_report,
)

_ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hub_page_assets")
_DEFAULT_DB = os.path.expanduser(
    "~/.claude/mainframe/claude-code/telemetry/telemetry.db")
_DEFAULT_CODEX_DB = os.path.expanduser(
    "~/.codex/mainframe/codex/telemetry/telemetry.db")
_DEFAULT_PI_DB = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..",
    "workspace", "runtime", "pi", "telemetry", "telemetry.db")
_DEFAULT_FEEDBACK = os.path.expanduser(
    "~/.claude/mainframe/claude-code/feedback")
_DEFAULT_PROJECTS = os.path.expanduser("~/.claude/projects")
_DEFAULT_USAGE_CACHE = os.path.expanduser("~/.claude/mainframe/usage-cache/usage-cache.json")
# Written by the observatory's OTLP receiver. A static build reads it so an
# offline snapshot can still say whether collection was working.
_DEFAULT_INGEST = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..",
    "workspace", "runtime", "observatory", "ingest.json")

# Layer columns, left to right, in the grouped graph layout.
LAYER_ORDER = ["events", "hooks", "agents", "skills", "dev"]

_SKILL_REF = re.compile(r"\]\(\.\./([a-z0-9][a-z0-9-]*)/SKILL\.md\)")
_AGENT_REF = re.compile(r"\]\(\.\./\.\./agents/([a-z0-9][a-z0-9-]*)\.md\)")
_SCRIPT_NAME = re.compile(r"([\w-]+\.py)")

# Top-level settings.json keys surfaced on the Config tab (the behaviour-shaping
# ones); permission lists, env and plugins are pulled out separately.
_SETTINGS_FLAG_KEYS = ["model", "effortLevel", "outputStyle",
                       "language", "autoCompactEnabled", "autoMemoryEnabled",
                       "teammateMode"]
# (name, repo-relative path) layers that exist as reserved-but-empty directories.
_EMPTY_LAYER_PROBES = (("rules", "adapters/claude-code/export/rules"), ("commands", "adapters/claude-code/plugin/commands"))
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
    """Skills from adapters/claude-code/plugin/skills/ (and dev/skills/, flagged dev=True)."""
    out = []
    for base, dev in (("adapters/claude-code/plugin/skills", False), ("dev/skills", True)):
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
    """User-level agents from adapters/claude-code/agents/."""
    adir = os.path.join(root, "adapters/claude-code/agents")
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
    path = os.path.join(root, "adapters/claude-code/plugin/hooks/hooks.json")
    if not os.path.isfile(path):
        return []
    data = json.loads(_read(path))
    scripts_dir = os.path.join(root, "adapters/claude-code/plugin/hooks/scripts")
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
            local_name = skill.removeprefix("mainframe:")
            if local_name in skill_names:
                edges.append({"source": a["name"], "target": local_name, "kind": "agent-skill"})
    for h in hooks:
        edges.append({"source": h["script"], "target": h["event"], "kind": "hook-event"})
    return edges


def collect_dev_state(
    db_path, feedback_dir, codex_db_path=None, pi_db_path=None,
    start_timestamp=None, end_timestamp=None, include_sensitive=False,
):
    """Build the UI from the same validated stream exposed to machine readers."""
    telemetry = (
        build_multi_telemetry_report({
            **{"claude-code": db_path},
            **({"codex": codex_db_path} if codex_db_path is not None else {}),
            **({"pi": pi_db_path} if pi_db_path is not None else {}),
        }, start_timestamp=start_timestamp, end_timestamp=end_timestamp)
        if codex_db_path is not None or pi_db_path is not None
        else build_telemetry_report(
            db_path, adapter_id="claude-code",
            start_timestamp=start_timestamp, end_timestamp=end_timestamp,
        )
    )
    state = {"active": telemetry["active"], "telemetry": telemetry, "feedback": []}
    if include_sensitive:
        state["permission_audit"] = [
            build_permission_audit(
                path, adapter_id, start_timestamp, end_timestamp,
            )
            for adapter_id, path in (
                ("claude-code", db_path),
                *(([("codex", codex_db_path)]) if codex_db_path is not None else []),
            )
        ]
    if os.path.isdir(feedback_dir):
        state["feedback"] = sorted(
            f for f in os.listdir(feedback_dir) if f.endswith(".md"))
    return state


def _managed_state_summary(adapter_id, directory):
    items = []
    if os.path.isdir(directory):
        for filename in sorted(os.listdir(directory)):
            if not filename.endswith(".json"):
                continue
            path = os.path.join(directory, filename)
            try:
                payload = json.loads(_read(path))
            except (OSError, ValueError, TypeError):
                items.append({"name": filename[:-5], "status": "state-unreadable"})
                continue
            target = payload.get("target")
            status = "present" if target and os.path.exists(target) else "state-only"
            items.append({"name": filename[:-5], "status": status})
    return {"adapter_id": adapter_id, "items": items}


def collect_installation_state(root):
    home = os.path.expanduser("~")
    claude = _managed_state_summary(
        "claude-code", os.path.join(home, ".claude", ".mainframe-managed-artifacts")
    )
    codex = _managed_state_summary(
        "codex", os.path.join(home, ".codex", ".mainframe-managed-artifacts")
    )
    for name, target in (
        ("settings", os.path.join(home, ".claude", ".mainframe-settings-state.json")),
        ("config", os.path.join(home, ".codex", ".mainframe-config-state.json")),
        ("hooks", os.path.join(home, ".codex", ".mainframe-hooks-state.json")),
    ):
        bucket = claude if name == "settings" else codex
        bucket["items"].append({
            "name": name, "status": "present" if os.path.isfile(target) else "missing",
        })
    pi_source = os.path.realpath(os.path.join(root, "adapters/pi/bin/mainframe-pi"))
    pi_target = os.path.join(home, ".local", "bin", "mainframe-pi")
    pi_present = os.path.islink(pi_target) and os.path.realpath(pi_target) == pi_source
    pi = {"adapter_id": "pi", "items": [{
        "name": "launcher", "status": "present" if pi_present else "missing",
    }]}
    return [claude, codex, pi]


def _model_lab_findings(payload, limit=5):
    candidate = payload.get("candidate")
    audit = payload.get("audit")
    rows = []
    if isinstance(candidate, dict):
        rows = candidate.get("candidates") or []
        values = [row.get("hypothesis") for row in rows if isinstance(row, dict)]
    elif isinstance(audit, dict) and isinstance(audit.get("hypotheses"), list):
        rows = audit["hypotheses"]
        values = [row.get("statement") for row in rows if isinstance(row, dict)]
    elif isinstance(audit, dict) and isinstance(audit.get("hook_findings"), list):
        rows = audit["hook_findings"]
        values = [row.get("finding") for row in rows if isinstance(row, dict)]
    else:
        values = []
    return [str(value).strip()[:500] for value in values if str(value or "").strip()][
        :max(0, int(limit))
    ]


def _model_lab_finding_count(payload):
    candidate = payload.get("candidate")
    audit = payload.get("audit")
    if isinstance(candidate, dict) and isinstance(candidate.get("candidates"), list):
        return len(candidate["candidates"])
    if isinstance(audit, dict):
        for key in ("hypotheses", "hook_findings"):
            if isinstance(audit.get(key), list):
                return len(audit[key])
    return 0


def _model_lab_summary(payload, findings, finding_count):
    summary = str(payload.get("summary") or "").strip()
    audit = payload.get("audit")
    if not summary and isinstance(audit, dict):
        summary = str(audit.get("summary") or "").strip()
    if summary:
        return summary[:600]
    if findings:
        label = "review candidate" if finding_count == 1 else "review candidates"
        return f"{finding_count} {label} stored; open the findings below for review."[:600]
    if isinstance(audit, dict):
        observations = audit.get("observations")
        probes = audit.get("probes")
        if isinstance(observations, list) or isinstance(probes, list):
            return (
                f"Stored {len(observations or [])} observations and "
                f"{len(probes or [])} proposed probes."
            )
    return "The model completed, but no review findings were stored."


def collect_model_lab_reports(root, limit=40):
    runtime = os.path.join(root, "workspace", "runtime")
    reports = []
    if not os.path.isdir(runtime):
        return reports
    for directory, _subdirs, filenames in os.walk(runtime):
        if f"{os.sep}model-lab{os.sep}" not in directory + os.sep:
            continue
        for filename in filenames:
            if not filename.endswith(".json"):
                continue
            path = os.path.join(directory, filename)
            try:
                payload = json.loads(_read(path))
            except (OSError, ValueError, TypeError):
                continue
            if not isinstance(payload, dict) or not payload.get("producer"):
                continue
            findings = _model_lab_findings(payload)
            finding_count = _model_lab_finding_count(payload)
            producer = str(payload.get("producer") or "unknown")[:80]
            provider = str(payload.get("provider") or "").strip()
            if not provider and producer == "spark-telemetry-triage":
                provider = "openai"
            elif not provider and producer == "gemini-telemetry-audit":
                provider = "google-antigravity"
            reports.append({
                "adapter_id": str(payload.get("adapter") or "unknown")[:40],
                "producer": producer,
                "provider": (provider or "unknown")[:80],
                "model": str(payload.get("model") or "unknown")[:100],
                "effort": str(payload.get("effort") or "unknown")[:40],
                "generated_at": str(
                    payload.get("generated_at") or payload.get("created_at") or ""
                )[:40],
                "summary": _model_lab_summary(payload, findings, finding_count),
                "finding_count": finding_count,
                "findings": findings,
                "review_required": bool(payload.get("review_required", True)),
                "artifact": os.path.relpath(path, root),
            })
    reports.sort(key=lambda item: item["generated_at"], reverse=True)
    return reports[:max(0, int(limit))]


def _iter_jsonl(projects_dir):
    for dirpath, _dirs, files in os.walk(projects_dir):
        for fn in files:
            if fn.endswith(".jsonl"):
                yield os.path.join(dirpath, fn)


def _parse_transcript(path):
    """Per-file usage split into main vs subagent scopes, each with the fixes a
    naive line-sum misses. An assistant reply is many streaming JSONL snapshots
    sharing one `message.id`; keep ONE row per id (terminal max-`output_tokens`)
    and read only top-level `message.usage`, never `usage.iterations[]` (it
    restates the same numbers). `isSidechain` lines are subagent turns, kept in a
    separate scope so the page can show a combined total AND a main/subagent
    split — they are the same runs against the same limits. A kept message with
    no `usage` lands in a visible `no_usage` bucket.
    """
    try:
        fh = open(path, encoding="utf-8", errors="replace")
    except OSError:
        return None
    main, sub = {}, {}
    with fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue  # tolerate a truncated trailing line on a live session
            if not isinstance(e, dict) or e.get("type") != "assistant":
                continue
            msg = e.get("message") or {}
            key = msg.get("id") or e.get("uuid")
            if key is None:
                continue
            bucket = sub if e.get("isSidechain") else main
            out = (msg.get("usage") or {}).get("output_tokens") or 0
            prev = bucket.get(key)
            if prev is None or out >= prev["out"]:
                bucket[key] = {"out": out, "usage": msg.get("usage"),
                               "model": msg.get("model") or "",
                               "ts": e.get("timestamp") or "",
                               "sid": e.get("sessionId") or ""}
    return {"main": _scope_agg(main), "sub": _scope_agg(sub)}


def _scope_agg(rows):
    """Aggregate one scope's de-duplicated rows: per-model totals, per-day
    {msgs, tok}, per-hour msgs, sessions, no-usage count, and message count."""
    models, days, hours, sessions = {}, {}, {}, set()
    no_usage = 0
    for row in rows.values():
        if row["sid"]:
            sessions.add(row["sid"])
        usage = row["usage"]
        tok = ((usage.get("input_tokens") or 0)
               + (usage.get("output_tokens") or 0)) if usage else 0
        ts = row["ts"]
        if ts:
            d = days.setdefault(ts[:10], {"msgs": 0, "tok": 0})
            d["msgs"] += 1
            d["tok"] += tok
            try:
                h = str(int(ts[11:13]))
                hours[h] = hours.get(h, 0) + 1
            except (ValueError, IndexError):
                pass
        if not usage:
            no_usage += 1
            continue
        m = models.setdefault(row["model"], {"in": 0, "out": 0,
                              "cache_read": 0, "cache_creation": 0, "msgs": 0})
        m["in"] += usage.get("input_tokens") or 0
        m["out"] += usage.get("output_tokens") or 0
        m["cache_read"] += usage.get("cache_read_input_tokens") or 0
        m["cache_creation"] += usage.get("cache_creation_input_tokens") or 0
        m["msgs"] += 1
    return {"models": models, "days": days, "hours": hours,
            "sessions": sorted(sessions), "no_usage": no_usage, "msgs": len(rows)}


def _streaks(days):
    """(current, longest) consecutive-day runs over 'YYYY-MM-DD' strings;
    'current' is the run ending at the most recent active day."""
    uniq = sorted(set(days))
    if not uniq:
        return 0, 0
    dates = [datetime.date.fromisoformat(d) for d in uniq]
    longest = run = 1
    for i in range(1, len(dates)):
        run = run + 1 if (dates[i] - dates[i - 1]).days == 1 else 1
        longest = max(longest, run)
    return run, longest


def _aggregate_usage(aggs):
    """Merge per-file scope aggregates into the manifest usage block: a combined
    headline (main + subagents — same runs, same limits) PLUS a main/subagent
    split. 'in' is raw input_tokens, 'total' = in+out (cache EXCLUDED, matching
    the Desktop UI); cache is surfaced separately because it dwarfs the headline."""
    def blank():
        return {"models": {}, "days": {}, "hours": {}, "sessions": set(),
                "no_usage": 0, "msgs": 0}

    def merge(into, s):
        into["msgs"] += s["msgs"]
        into["no_usage"] += s["no_usage"]
        into["sessions"].update(s["sessions"])
        for model, mm in s["models"].items():
            t = into["models"].setdefault(model, {"in": 0, "out": 0,
                                "cache_read": 0, "cache_creation": 0, "msgs": 0})
            for k in t:
                t[k] += mm.get(k, 0)
        for d, dd in s["days"].items():
            x = into["days"].setdefault(d, {"msgs": 0, "tok": 0})
            x["msgs"] += dd["msgs"]
            x["tok"] += dd["tok"]
        for h, n in s["hours"].items():
            into["hours"][h] = into["hours"].get(h, 0) + n

    main, sub, comb = blank(), blank(), blank()
    for agg in aggs:
        merge(main, agg["main"])
        merge(sub, agg["sub"])
        merge(comb, agg["main"])
        merge(comb, agg["sub"])

    def scope_totals(s):
        tin = sum(m["in"] for m in s["models"].values())
        tout = sum(m["out"] for m in s["models"].values())
        return {"messages": s["msgs"], "in": tin, "out": tout, "total": tin + tout,
                "cache": sum(m["cache_read"] + m["cache_creation"]
                             for m in s["models"].values())}

    tin = sum(m["in"] for m in comb["models"].values())
    tout = sum(m["out"] for m in comb["models"].values())
    grand = tin + tout
    model_list = [{"model": name, "in": m["in"], "out": m["out"],
                   "total": m["in"] + m["out"],
                   "cache": m["cache_read"] + m["cache_creation"], "msgs": m["msgs"],
                   "share": round((m["in"] + m["out"]) / grand, 4) if grand else 0}
                  for name, m in comb["models"].items()]
    model_list.sort(key=lambda x: -x["total"])
    hours = comb["hours"]
    return {
        "active": True,
        "sessions": len(comb["sessions"]),
        "messages": comb["msgs"],
        "tokens": {"in": tin, "out": tout, "total": grand,
                   "cache_read": sum(m["cache_read"] for m in comb["models"].values()),
                   "cache_creation": sum(m["cache_creation"] for m in comb["models"].values())},
        "split": {"main": scope_totals(main), "sub": scope_totals(sub)},
        "models": model_list,
        "by_day": sorted([d, dd["msgs"], dd["tok"]] for d, dd in comb["days"].items()),
        "by_hour": [[h, hours.get(str(h), 0)] for h in range(24)],
        "active_days": len(comb["days"]),
        "peak_hour": (max(range(24), key=lambda h: hours.get(str(h), 0))
                      if hours else None),
        "current_streak": _streaks(list(comb["days"]))[0],
        "longest_streak": _streaks(list(comb["days"]))[1],
        "favorite_model": model_list[0]["model"] if model_list else "",
        "no_usage": comb["no_usage"],
        "files": len(aggs),
    }


def collect_usage(projects_dir=_DEFAULT_PROJECTS, cache_path=_DEFAULT_USAGE_CACHE):
    """Token/usage stats from local session transcripts, with a per-file
    mtime+size cache so a rebuild reparses only new/changed files (cold ~8s over
    ~2600 files; warm sub-second). Absent projects dir => not active, like
    collect_dev_state."""
    if not os.path.isdir(projects_dir):
        return {"active": False}
    old = {}
    try:
        with open(cache_path) as fh:
            old = json.load(fh)
    except (OSError, json.JSONDecodeError, ValueError):
        old = {}
    new_cache, aggs = {}, []
    for path in _iter_jsonl(projects_dir):
        try:
            st = os.stat(path)
        except OSError:
            continue
        prev = old.get(path)
        prev_agg = prev.get("agg") if isinstance(prev, dict) else None
        # "main" gates the cache schema: a stale-shape entry (pre-split) misses
        # and is reparsed, so the cache self-migrates without a manual wipe.
        if (isinstance(prev_agg, dict) and "main" in prev_agg
                and prev.get("mtime") == st.st_mtime and prev.get("size") == st.st_size):
            agg = prev_agg
        else:
            agg = _parse_transcript(path)
            if agg is None:
                continue
        new_cache[path] = {"mtime": st.st_mtime, "size": st.st_size, "agg": agg}
        aggs.append(agg)
    try:
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        with open(cache_path, "w") as fh:
            json.dump(new_cache, fh)
    except OSError:
        pass
    return _aggregate_usage(aggs)


def collect_settings(root):
    """Read-only snapshot of adapters/claude-code/export/settings.json: permissions, env, key flags."""
    empty = {"permissions": {"allow": [], "deny": [], "ask": []},
             "mode": "", "env": {}, "plugins": {}, "flags": {}}
    path = os.path.join(root, "adapters/claude-code/export/settings.json")
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


def _collect_secret_templates(directory):
    templates = _collect_docs(directory, False)
    return [
        {**item, "name": item["name"].removesuffix(".template")}
        for item in templates
        if item["name"].endswith(".template")
    ]


def collect_misc(root):
    """Output styles, templates, and explicit markers for reserved-empty layers."""
    empty = [{"name": name, "path": rel}
             for name, rel in _EMPTY_LAYER_PROBES
             if _is_empty_layer(os.path.join(root, rel))]
    return {
        "output_styles": _collect_docs(os.path.join(root, "adapters/claude-code/export/output-styles"), True),
        "templates": _collect_secret_templates(os.path.join(root, "shared/credentials")),
        "empty_layers": empty,
    }


def compute_health(skills, agents, hooks, root):
    """Integrity findings the graph hides: broken refs, orphans, missing scripts.

    build_edges drops any edge whose target is not a node, so a typo'd cross-ref
    or a `skills:` entry pointing at a deleted skill vanishes silently — this
    surfaces exactly those, plus skills with no graph connection at all and hook
    scripts registered in hooks.json but absent from disk.
    """
    skill_names = {s["name"] for s in skills}
    known = skill_names | {a["name"] for a in agents}

    dangling = []
    for s in skills:
        for ref in s["crossrefs"]:
            if ref not in known:
                dangling.append({"kind": "skill-crossref", "source": s["name"], "target": ref})
    for a in agents:
        for sk in a["skills"]:
            local_name = sk.removeprefix("mainframe:")
            if local_name not in skill_names:
                dangling.append({"kind": "agent-skill", "source": a["name"], "target": sk})

    connected = set()
    for s in skills:
        for ref in s["crossrefs"]:
            if ref in known:
                connected.add(s["name"])
                connected.add(ref)
    for a in agents:
        for sk in a["skills"]:
            local_name = sk.removeprefix("mainframe:")
            if local_name in skill_names:
                connected.add(local_name)
    orphans = sorted(s["name"] for s in skills if s["name"] not in connected)

    scripts_dir = os.path.join(root, "adapters/claude-code/plugin/hooks/scripts")
    missing, seen = [], set()
    for h in hooks:
        if h["script"] in seen:
            continue
        seen.add(h["script"])
        if not os.path.isfile(os.path.join(scripts_dir, h["script"])):
            missing.append(h["script"])

    return {"dangling": dangling, "orphans": orphans, "missing_scripts": missing}


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
    col_w, row_h, x0, y0 = 250, 54, 80, 80
    by_layer = {}
    for n in nodes:
        by_layer.setdefault(n["layer"], []).append(n["id"])
    ordered = list(layer_order) + [
        layer_name for layer_name in by_layer if layer_name not in layer_order]
    pos = {}
    for li, layer in enumerate(ordered):
        x = x0 + li * col_w
        for j, nid in enumerate(by_layer.get(layer, [])):
            pos[nid] = {"x": x, "y": y0 + j * row_h}
    return pos


def build_manifest(root, db_path=_DEFAULT_DB, feedback_dir=_DEFAULT_FEEDBACK,
                   projects_dir=_DEFAULT_PROJECTS, usage_cache=_DEFAULT_USAGE_CACHE,
                   codex_db_path=None, pi_db_path=None,
                   start_timestamp=None, end_timestamp=None,
                   include_sensitive=False):
    skills = collect_skills(root)
    agents = collect_agents(root)
    hooks = collect_hooks(root)
    nodes = build_nodes(skills, agents, hooks)
    return {
        "skills": skills,
        "agents": agents,
        "hooks": hooks,
        "edges": build_edges(skills, agents, hooks),
        "ingest": native_telemetry_receiver.read_ingest_health(_DEFAULT_INGEST),
        "dev_state": collect_dev_state(
            db_path, feedback_dir,
            _DEFAULT_CODEX_DB if codex_db_path is None and db_path == _DEFAULT_DB
            else codex_db_path,
            _DEFAULT_PI_DB if pi_db_path is None and db_path == _DEFAULT_DB
            else pi_db_path,
            start_timestamp=start_timestamp,
            end_timestamp=end_timestamp,
            include_sensitive=include_sensitive,
        ),
        "usage": collect_usage(projects_dir, usage_cache),
        "settings": collect_settings(root),
        "misc": collect_misc(root),
        "installation": collect_installation_state(root),
        "analyses": collect_model_lab_reports(root),
        "health": compute_health(skills, agents, hooks, root),
        "nodes": nodes,
        "layout": compute_layout(nodes, LAYER_ORDER),
        "layer_order": LAYER_ORDER,
    }


def render(manifest, build_stamp, assets_dir=_ASSETS, auto_refresh_ms=0,
           live=False, control_token=""):
    template = _read(os.path.join(assets_dir, "template.html"))
    style = _read(os.path.join(assets_dir, "style.css"))
    app_js = _read(os.path.join(assets_dir, "app.js"))
    i18n_js = _read(os.path.join(assets_dir, "i18n.js"))
    # `<\/` keeps an accidental "</script>" inside the JSON from closing the tag.
    data = json.dumps(manifest, ensure_ascii=False).replace("</", "<\\/")
    return (template
            .replace("{{BUILD_STAMP}}", build_stamp)
            .replace("{{SNAPSHOT_MODE}}", (f"auto refresh · {auto_refresh_ms // 1000}s"
                                            if auto_refresh_ms else "static snapshot"))
            .replace("{{AUTO_REFRESH_MS}}", str(auto_refresh_ms))
            .replace("{{LIVE_MODE}}", "true" if live else "false")
            .replace("{{CONTROL_TOKEN}}", json.dumps(control_token))
            .replace("{{STYLE}}", style)
            .replace("{{DATA}}", data)
            .replace("{{I18N_JS}}", i18n_js)
            .replace("{{APP_JS}}", app_js))


def write_snapshot(root, out, db_path, feedback_dir, projects_dir, usage_cache,
                   auto_refresh_ms=0, codex_db_path=None):
    manifest = build_manifest(root, db_path=db_path, feedback_dir=feedback_dir,
                              projects_dir=projects_dir, usage_cache=usage_cache,
                              codex_db_path=codex_db_path)
    stamp = datetime.datetime.now().isoformat(timespec="seconds")
    html = render(manifest, build_stamp=stamp, auto_refresh_ms=auto_refresh_ms)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    temporary = f"{out}.tmp-{os.getpid()}"
    try:
        with open(temporary, "w") as handle:
            handle.write(html)
        os.replace(temporary, out)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    dev = "active" if manifest["dev_state"]["active"] else "not active"
    usage = manifest["usage"]
    usage_note = (f", usage {usage['sessions']} sessions / "
                  f"{usage['tokens']['total']:,} tokens" if usage.get("active") else "")
    print(f"wrote {out}  ({len(manifest['nodes'])} nodes, "
          f"{len(manifest['edges'])} edges, dev {dev}{usage_note})", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=os.path.join(os.path.dirname(_ASSETS), ".."))
    parser.add_argument("--out", default=None,
                        help="output path (default: <root>/workspace/runtime/hub.html)")
    parser.add_argument("--db", default=_DEFAULT_DB)
    parser.add_argument("--codex-db", default=_DEFAULT_CODEX_DB)
    parser.add_argument("--feedback", default=_DEFAULT_FEEDBACK)
    parser.add_argument("--projects", default=_DEFAULT_PROJECTS)
    parser.add_argument("--usage-cache", default=_DEFAULT_USAGE_CACHE)
    parser.add_argument("--watch", action="store_true",
                        help="rebuild continuously and make the page reload itself")
    parser.add_argument("--interval", type=float, default=15.0,
                        help="watch/reload interval in seconds (default: 15)")
    args = parser.parse_args()

    if args.interval < 2:
        parser.error("--interval must be at least 2 seconds")

    root = os.path.abspath(args.root)
    out = os.path.abspath(args.out or os.path.join(root, "workspace/runtime/hub.html"))
    refresh_ms = round(args.interval * 1000) if args.watch else 0
    try:
        while True:
            write_snapshot(root, out, args.db, args.feedback, args.projects,
                           args.usage_cache, auto_refresh_ms=refresh_ms,
                           codex_db_path=args.codex_db)
            if not args.watch:
                break
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("watch stopped", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
