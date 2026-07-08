#!/usr/bin/env python3
"""Project MAINFRAME hub artifacts into OpenCode's config layout.

Sources: `plugin-dist/agents/*.md`, `export/settings.json` (permissions),
`~/.claude.json` (MCP servers). Outputs: OpenCode agent markdown files
(default `workspace/runtime/opencode/agents/`, symlinked by
`install.sh --opencode`) and a merge of hub-managed keys into the user's
`~/.config/opencode/opencode.json`.

The permission projection is best-effort convenience, NOT a safety boundary:
OpenCode resolves permissions last-match-wins and its `ask` degrades to
`allow` under `--auto` (and hangs headless without it). Deny entries are
emitted last so they win on overlap; the summary lists everything that could
not be projected.

Run: `.venv/bin/python3 tools/build_opencode.py [--dry-run]` (needs pyyaml).
"""

import argparse
import copy
import json
import os
import shutil
import sys

import yaml

GENERATED_MARKER = "Generated from MAINFRAME hub"

_GENERATED_NOTE = (
    "<!-- {marker} (plugin-dist/agents/{name}.md) — do not edit;"
    " regenerate via ./install.sh --opencode.\n"
    "     Hub-only keys are dropped here: model tier, effort, background,"
    " skills preload, maxTurns,\n"
    "     and Claude-Code-specific tool names (mcp__*, TodoWrite) — the"
    " agent runs on OpenCode defaults for those. -->"
)

_CC_TOOLS_TO_OPENCODE = {"Bash": "bash", "Read": "read"}


def parse_frontmatter(text):
    """Split a markdown document into (frontmatter dict, body)."""
    if not text.startswith("---\n"):
        return {}, text
    parts = text.split("\n---\n", 1)
    if len(parts) != 2:
        return {}, text
    meta = yaml.safe_load(parts[0][4:]) or {}
    return meta, parts[1].lstrip("\n")


def derive_agent_permission(tools):
    """Deny in OpenCode what the hub agent's tools allowlist never granted."""
    toolset = set(tools)
    perm = {}
    if "Bash" not in toolset:
        perm["bash"] = "deny"
    if not toolset & {"Edit", "Write"}:
        perm["edit"] = "deny"
    if "WebFetch" not in toolset:
        perm["webfetch"] = "deny"
    if "WebSearch" not in toolset:
        perm["websearch"] = "deny"
    # A read-only agent must not regain side effects through sub-tasks or
    # skills — OpenCode defaults both to allow.
    if "bash" in perm and "edit" in perm:
        perm["task"] = "deny"
        perm["skill"] = "deny"
    return perm


def project_agent(meta, body):
    """Render one hub agent as OpenCode agent markdown, or None to skip."""
    description = meta.get("description")
    if not description:
        return None
    tools = [t.strip() for t in str(meta.get("tools", "")).split(",")
             if t.strip()]
    fm = {"description": description, "mode": "subagent"}
    perm = derive_agent_permission(tools)
    if perm:
        fm["permission"] = perm
    front = yaml.safe_dump(fm, sort_keys=False, allow_unicode=True,
                           width=100000).rstrip("\n")
    note = _GENERATED_NOTE.format(marker=GENERATED_MARKER,
                                  name=meta.get("name", "unknown"))
    return f"---\n{front}\n---\n\n{note}\n\n{body}"


def _split_cc_pattern(entry):
    """`Bash(git add *)` → ("bash", "git add *"); unprojectable → None."""
    if not entry.endswith(")") or "(" not in entry:
        return None
    tool, inner = entry.split("(", 1)
    action = _CC_TOOLS_TO_OPENCODE.get(tool)
    pattern = inner[:-1]
    if action is None or not pattern:
        return None
    return action, pattern


def project_permissions(cc_permissions):
    """CC allow/ask/deny lists → OpenCode permission maps + honesty report.

    Allow entries are omitted by design (OpenCode defaults to allow); ask
    entries are emitted before deny so that under last-match-wins an
    overlapping deny stays the winner.
    """
    maps = {"bash": {"*": "allow"}, "read": {}}
    skipped, allow_omitted = [], 0
    for verdict in ("ask", "deny"):
        for entry in cc_permissions.get(verdict, []):
            parsed = _split_cc_pattern(entry)
            if parsed is None:
                skipped.append(entry)
                continue
            action, pattern = parsed
            maps[action][pattern] = verdict
    for entry in cc_permissions.get("allow", []):
        if _split_cc_pattern(entry) is None:
            skipped.append(entry)
        else:
            allow_omitted += 1
    permission = {k: v for k, v in maps.items() if v}
    return permission, {"skipped": skipped, "allow_omitted": allow_omitted}


def project_mcp(mcp_servers):
    """CC stdio MCP entries → OpenCode `mcp` dialect.

    Entries with `env` are never translated: copying their values would
    multiply plaintext secrets into opencode.json. Non-stdio transports have
    no 1:1 OpenCode equivalent here either — both land in the report.
    """
    servers, skipped = {}, []
    for name, entry in mcp_servers.items():
        if entry.get("type") != "stdio" or entry.get("env"):
            skipped.append(name)
            continue
        command = [entry.get("command", "")] + list(entry.get("args", []))
        servers[name] = {"type": "local", "command": command, "enabled": True}
    return servers, {"skipped": skipped}


def merge_config(existing, permission, mcp_servers):
    """Merge hub-managed keys into the user's config, touching nothing else.

    `mcp.<name>` is only added when absent — a user-customized server of the
    same name wins. `permission` is hub-managed and replaced wholesale: a
    per-key merge would put final rule ORDER outside the generator's control,
    and order decides outcomes under last-match-wins.
    """
    merged = copy.deepcopy(existing)
    mcp = merged.setdefault("mcp", {})
    for name, server in mcp_servers.items():
        if name not in mcp:
            mcp[name] = server
    if permission:
        merged["permission"] = permission
    return merged


def write_config(path, data):
    """Write config JSON with one rolling backup of the previous version.

    A single overwritten `.backup` (0600) instead of timestamped copies: the
    file carries the user's API keys, so accumulating snapshots of it would
    multiply plaintext secrets.
    """
    if os.path.exists(path):
        backup = path + ".backup"
        shutil.copy2(path, backup)
        os.chmod(backup, 0o600)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def _load_json(path):
    if not os.path.isfile(path):
        return None
    with open(path) as f:
        try:
            return json.load(f)
        except json.JSONDecodeError as e:
            raise SystemExit(
                f"error: {path} is not valid JSON ({e}); nothing was "
                f"written — fix or remove the file and re-run") from e


def _collect_agents(root):
    agents_dir = os.path.join(root, "plugin-dist", "agents")
    out = []
    for fname in sorted(os.listdir(agents_dir)) if os.path.isdir(agents_dir) else []:
        if not fname.endswith(".md"):
            continue
        with open(os.path.join(agents_dir, fname)) as f:
            meta, body = parse_frontmatter(f.read())
        rendered = project_agent(meta, body)
        if rendered is None:
            print(f"[skip] {fname}: no description in frontmatter")
            continue
        out.append((fname, rendered))
    return out


def _print_summary(agents, perm_report, mcp_report, replaced_permission):
    print(f"agents projected: {len(agents)}")
    print(f"allow entries omitted by design: {perm_report['allow_omitted']}")
    if perm_report["skipped"]:
        print(f"permission entries with no OpenCode equivalent "
              f"({len(perm_report['skipped'])}):")
        for entry in perm_report["skipped"]:
            print(f"  - {entry}")
    if mcp_report["skipped"]:
        print("MCP servers NOT translated (secret-bearing env or non-stdio): "
              + ", ".join(mcp_report["skipped"]))
    if replaced_permission:
        print("NOTE: an existing differing `permission` block was replaced "
              "(previous version is in opencode.json.backup).")
    print("Caveats — the projected permission map is best-effort, NOT a "
          "safety boundary:")
    print("  - OpenCode resolves last-match-wins; deny entries are emitted "
          "last on purpose.")
    print("  - `ask` hangs a headless run without --auto, and degrades to "
          "allow WITH --auto.")
    print("  - Hub hooks (security gates, validators) do not transfer; "
          "OpenCode runs have thinner guardrails than Claude Code.")


def main(argv=None):
    default_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=default_root)
    parser.add_argument("--agents-out", default=None,
                        help="default: <root>/workspace/runtime/opencode/agents")
    parser.add_argument("--config", default=os.path.expanduser(
        "~/.config/opencode/opencode.json"))
    parser.add_argument("--claude-config", default=os.path.expanduser(
        "~/.claude.json"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    agents_out = args.agents_out or os.path.join(
        args.root, "workspace", "runtime", "opencode", "agents")
    agents = _collect_agents(args.root)

    settings = _load_json(os.path.join(args.root, "export", "settings.json"))
    permission, perm_report = project_permissions(
        (settings or {}).get("permissions", {}))

    claude_cfg = _load_json(args.claude_config)
    if claude_cfg is None:
        print(f"[skip] {args.claude_config} not found — no MCP projection")
        servers, mcp_report = {}, {"skipped": []}
    else:
        servers, mcp_report = project_mcp(claude_cfg.get("mcpServers", {}))

    existing = _load_json(args.config) or {}
    merged = merge_config(existing, permission, servers)
    replaced = ("permission" in existing
                and existing["permission"] != merged.get("permission"))

    if args.dry_run:
        print(f"[dry-run] would write {len(agents)} agent file(s) to "
              f"{agents_out}")
        print(f"[dry-run] would merge keys into {args.config}: "
              f"permission + mcp({', '.join(servers) or 'none'})")
    else:
        os.makedirs(agents_out, exist_ok=True)
        for fname, rendered in agents:
            with open(os.path.join(agents_out, fname), "w") as f:
                f.write(rendered)
        write_config(args.config, merged)
        print(f"wrote {len(agents)} agent file(s) to {agents_out}")
        print(f"merged hub-managed keys into {args.config}")

    _print_summary(agents, perm_report, mcp_report, replaced)
    return 0


if __name__ == "__main__":
    sys.exit(main())
