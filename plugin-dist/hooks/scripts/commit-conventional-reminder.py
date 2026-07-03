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

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from _hooklib import load_payload, emit_note, log_event, run, is_git_commit
except Exception:
    sys.exit(0)

# Conventional Commits v1.0.0 subject: type(scope)!: description
CONV_RE = re.compile(
    r"^(?:feat|fix|docs|refactor|test|chore|ci|perf|build|style|revert)"
    r"(?:\([^)]+\))?!?:\s+\S"
)

# Banned AI-attribution trailers (hub override of default tooling).
AI_TRAILER_RE = re.compile(
    r"Co-Authored-By:\s*Claude|Generated with \[?Claude|AI-assisted", re.IGNORECASE
)


# `-\w*m` covers bundled short flags (`-am`, `-qm`), not just bare `-m`.
_M_QUOTED_RE = re.compile(r"(?<!\w)-\w*m\s+(['\"])(.*?)\1", re.DOTALL)
_M_UNQUOTED_RE = re.compile(r"(?<!\w)-\w*m\s+([^\s'\";|&<>]+)")
_HEREDOC_OPEN_RE = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_]\w*)\1")
_COMMIT_STDIN_RE = re.compile(r"git\s+commit.*(?:-F|--file)[=\s]*(?:/dev/stdin|-)(?:\s|$)")


def extract_subject(cmd):
    """Best-effort extraction of the commit subject from `-m` or the heredoc
    that feeds `git commit -F /dev/stdin` — never from text owned by another
    command in the same compound (the false-positive class in harness feedback
    20260610-162716 / 20260611-141832). One line-walk splits the command into
    plain lines and heredoc bodies: `-m` is searched in plain text only (a body
    mentioning `-m '…'` must not hijack extraction), and a body is read as the
    message only when its opener line is the `git commit … -F /dev/stdin`."""
    lines = cmd.splitlines()
    plain, heredoc_subject, i = [], None, 0
    while i < len(lines):
        line = lines[i]
        plain.append(line)
        opener = _HEREDOC_OPEN_RE.search(line)
        if not opener:
            i += 1
            continue
        delim = opener.group(2)
        end = i + 1
        while end < len(lines) and lines[end].strip() != delim:
            end += 1
        if heredoc_subject is None and _COMMIT_STDIN_RE.search(line):
            heredoc_subject = next(
                (b.strip() for b in lines[i + 1:end] if b.strip()), None)
        i = end + 1  # skip the body: its lines are data, not command text
    plain_text = "\n".join(plain)
    m = _M_QUOTED_RE.search(plain_text)
    if m:
        msg = m.group(2).strip()
        return msg.splitlines()[0].strip() if msg else None
    m = _M_UNQUOTED_RE.search(plain_text)
    if m:
        return m.group(1)
    return heredoc_subject


def main():
    payload = load_payload()
    if payload.get("tool_name") != "Bash":
        return
    command = (payload.get("tool_input") or {}).get("command", "")
    if not command or not is_git_commit(command):
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
    emit_note("PreToolUse", note)
    rule = ("ai-trailer" if has_trailer
            else "non-conventional-subject" if subject
            else "no-inline-message")
    log_event("incident", {"hook": "commit-conventional-reminder",
                           "rule_id": rule}, payload)


if __name__ == "__main__":
    run(main)
