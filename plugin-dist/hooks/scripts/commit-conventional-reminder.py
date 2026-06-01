#!/usr/bin/env python3
"""PreToolUse hook: remind about Conventional Commits before a `git commit` runs.

Fires for BOTH the main agent and subagents — PreToolUse runs inside subagents
(payload carries `agent_id`/`agent_type`). This is the only cross-agent path for
the hub, because per-agent frontmatter `hooks:` are ignored for plugin subagents
(see memory `plugin-subagent-frontmatter-caveats`). The reminder carries the rules
INLINE rather than "go read the skill": a subagent without the `Skill` tool in its
`tools:` allowlist cannot load the `git-conventional-commits` skill on demand.

Design (non-blocking, low-noise):
- Stdlib only. Reads PreToolUse payload from stdin.
- Filter: only the Bash tool, only commands that invoke `git commit`.
- Smart-skip: if the commit subject is already Conventional Commits-shaped, stay
  silent — a reminder on a correct commit is noise that trains the reader to
  ignore it. Fires only when the subject is non-conventional, absent, or the
  command carries a banned AI-attribution trailer.
- Subagent-aware: the skill-pointer line differs for main agent vs subagent.
- Non-blocking: emits only `additionalContext`; never `permissionDecision`
  (deny/ask become defer in auto-mode and would break autonomous runs).
- Fail-safe: ANY error -> exit 0 with no output. The hook must never break a
  `git commit`.
"""

import json
import re
import sys

# `git [-c k=v | -C path | --opts] commit ...` — the commit subcommand specifically.
# `-c`/`-C` take a value token, so match them before the generic flag alternative.
COMMIT_RE = re.compile(r"\bgit\b(?:\s+-[cC]\s+\S+|\s+--?\S+)*\s+commit\b")

# Conventional Commits v1.0.0 subject: type(scope)!: description
CONV_RE = re.compile(
    r"^(?:feat|fix|docs|refactor|test|chore|ci|perf|build|style|revert)"
    r"(?:\([^)]+\))?!?:\s+\S"
)

# Banned AI-attribution trailers (hub override of default tooling).
AI_TRAILER_RE = re.compile(
    r"Co-Authored-By:\s*Claude|Generated with \[?Claude|AI-assisted", re.IGNORECASE
)


def extract_subject(cmd):
    """Best-effort extraction of the commit subject from `-m` or a heredoc."""
    m = re.search(r"-m\s+(['\"])(.*?)\1", cmd, re.DOTALL)
    if m:
        msg = m.group(2).strip()
        return msg.splitlines()[0].strip() if msg else None
    if "<<" in cmd:
        lines = cmd.splitlines()
        for i, line in enumerate(lines):
            if re.search(r"<<-?\s*['\"]?[A-Za-z_]\w*", line):
                for nxt in lines[i + 1:]:
                    if nxt.strip():
                        return nxt.strip()
                break
    return None


def main():
    payload = json.load(sys.stdin)
    if payload.get("tool_name") != "Bash":
        return
    command = (payload.get("tool_input") or {}).get("command", "")
    if not command or not COMMIT_RE.search(command):
        return

    subject = extract_subject(command)
    has_trailer = bool(AI_TRAILER_RE.search(command))
    already_conventional = bool(subject and CONV_RE.match(subject))

    if already_conventional and not has_trailer:
        return

    if has_trailer:
        lead = ("this `git commit` contains a banned AI-attribution trailer "
                "(e.g. `Co-Authored-By: Claude`) — remove it.")
    elif subject:
        lead = (f"this `git commit` subject `{subject[:72]}` is not "
                f"Conventional Commits-shaped.")
    else:
        lead = "this `git commit` has no inline message to check."

    if payload.get("agent_id"):
        skill_line = ("  - These essentials are authoritative here; the "
                      "`git-conventional-commits` skill may not be loadable in a "
                      "subagent (no `Skill` tool in the allowlist).\n")
    else:
        skill_line = ("  - Full method: invoke the `git-conventional-commits` "
                      "skill before composing the message.\n")

    note = (
        f"commit-convention reminder: {lead} Use Conventional Commits v1.0.0:\n"
        "  - Format `type(scope)!: description` — imperative, no trailing period.\n"
        "  - Types: feat, fix, docs, refactor, test, chore, ci, perf, build, style.\n"
        "  - `type`/`scope`/footer tokens stay English; description and body use the "
        "repo's commit language (repo directive -> existing history -> English).\n"
        "  - Multi-line message: `git commit -F /dev/stdin <<'EOF'` heredoc, not "
        "`-m` (which mangles non-ASCII, newlines, and backticks).\n"
        "  - No AI-attribution trailers (`Co-Authored-By: Claude`, `Generated with "
        "Claude Code`).\n"
        "  - Split unrelated changes into atomic commits by type and scope.\n"
        f"{skill_line}"
        "This is a reminder, not a block — if the message is already correct, proceed."
    )
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse", "additionalContext": note}}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
