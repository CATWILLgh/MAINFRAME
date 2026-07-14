#!/usr/bin/env python3
"""PreToolUse hook: block a `git commit` that would put a real secret into history.

Scans only what the commit will add (`git diff --cached`, or `git diff HEAD` when
`-a`/`--all` stages tracked modifications) against a small set of HIGH-CONFIDENCE
vendor token shapes — the same gitleaks-derived catalog the `secrets-handling`
skill documents. Low-confidence entropy/keyword regexes are deliberately excluded:
across every project in unattended auto-mode they are a false-positive firehose
that trains the agent to ignore the gate.

Decisions (PreToolUse permissionDecision):
- `deny` — a high-confidence token shape was found in the added lines. The reason
  carries the TYPE and FILE only, never the value (the reason enters the
  transcript; echoing the secret would leak it).
- (no output, exit 0) — not a commit, not a git repo, an encrypted-secrets repo
  (SOPS / git-crypt auto-skipped), or nothing matched. Defer to other layers.

Fail-safe: any error defers via `run(main)` → exit 0. A bug here fails OPEN (does
not block), so it can never wedge an autonomous run.
"""

import os
import re
import shlex
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from _hooklib import (load_payload, emit_permission, log_event, run,
                          is_git_commit)
except Exception:
    sys.exit(0)

# High-confidence, vendor-specific token shapes (mirror of the `secrets-handling`
# skill's high-confidence table — keep the two in sync). Each almost never matches
# a non-secret, which is why blocking on them is safe across all projects.
SECRET_PATTERNS = [
    ("github_pat", re.compile(r"ghp_[0-9a-zA-Z]{36}")),
    ("github_oauth", re.compile(r"(?:gho|ghu|ghs|ghr)_[0-9a-zA-Z]{36}")),
    ("openai_key", re.compile(
        r"sk-(?:proj-|svcacct-|admin-)?[A-Za-z0-9_-]{20,74}"
        r"T3BlbkFJ[A-Za-z0-9_-]{20,74}")),
    ("aws_access_key", re.compile(
        r"(?:AKIA|ASIA|AGPA|AIDA|AROA|AIPA|ANPA|ANVA|A3T[A-Z0-9])[A-Z0-9]{16}")),
    ("slack_token", re.compile(
        r"xox[baprs]-[0-9]{8,13}-[0-9]{8,13}-[A-Za-z0-9]{24}")),
    ("stripe_key", re.compile(r"(?:sk|pk|rk)_(?:test|live)_[0-9a-zA-Z]{10,99}")),
    ("private_key_block", re.compile(r"-----BEGIN[ A-Z0-9_-]{0,100}PRIVATE KEY-----")),
]

# Well-known documentation/fixture placeholders that match a real shape but are
# not secrets (e.g. AWS's own `AKIAIOSFODNN7EXAMPLE`). Without this the gate would
# block legitimate doc and test commits — the main false-positive class.
_PLACEHOLDER_KEYWORDS = ("example", "placeholder")


def _is_placeholder(token):
    low = token.lower()
    if any(k in low for k in _PLACEHOLDER_KEYWORDS):
        return True
    if re.search(r"x{6,}", low):                 # masked value: xxxxxx...
        return True
    if re.search(r"(.)\1{7,}", token):           # 8+ identical run: aaaaaaaa...
        return True
    return False


def _repo_root(cwd):
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=cwd, stderr=subprocess.DEVNULL, timeout=2).decode().strip()
        return out or None
    except Exception:
        return None


def _is_encrypted_repo(root):
    """True for repos that intentionally commit ciphertext (SOPS / git-crypt).

    Such repos legitimately put encrypted-secret blobs into history; scanning them
    is pure noise. Vendor shapes do not match ciphertext anyway — this is the
    explicit, zero-config skip the user opted for over a marker file.
    """
    for marker in (".sops.yaml", ".sops.yml"):
        if os.path.exists(os.path.join(root, marker)):
            return True
    attrs = os.path.join(root, ".gitattributes")
    try:
        if os.path.exists(attrs):
            with open(attrs, "r", errors="replace") as fh:
                if "git-crypt" in fh.read():
                    return True
    except Exception:
        pass
    return False


def _commit_stages_all(command):
    """True if the commit auto-stages tracked modifications (`-a` / `--all`),
    which means the committed set is `git diff HEAD`, not just the index."""
    try:
        tokens = shlex.split(command)
    except ValueError:
        return False
    seen_commit = False
    for tok in tokens:
        if tok == "commit":
            seen_commit = True
            continue
        if not seen_commit:
            continue
        if tok == "--all":
            return True
        if tok.startswith("-") and not tok.startswith("--") and "a" in tok[1:]:
            return True
    return False


def _scan_diff_text(text):
    """Return [(kind, basename)] for high-confidence secrets on ADDED lines.

    The `+++ b/<path>` header sets the current file; only `+` body lines are
    scanned (a secret on a `-` line is leaving, not entering, history).
    """
    findings = []
    current = None
    for line in text.splitlines():
        if line.startswith("+++ "):
            path = line[4:]
            if path.startswith("b/"):
                path = path[2:]
            current = None if path == "/dev/null" else os.path.basename(path)
            continue
        if current is None:
            continue
        if not line.startswith("+") or line.startswith("+++"):
            continue
        body = line[1:]
        for kind, rx in SECRET_PATTERNS:
            match = rx.search(body)
            if match and not _is_placeholder(match.group(0)):
                findings.append((kind, current))
                break
    return findings


def _scan_staged(root, include_unstaged):
    args = (["git", "diff", "HEAD", "--unified=0", "--no-color"] if include_unstaged
            else ["git", "diff", "--cached", "--unified=0", "--no-color"])
    try:
        out = subprocess.check_output(
            args, cwd=root, stderr=subprocess.DEVNULL, timeout=5
        ).decode(errors="replace")
    except Exception:
        return []
    return _scan_diff_text(out)


def main():
    payload = load_payload()
    if payload.get("tool_name") != "Bash":
        return
    command = (payload.get("tool_input") or {}).get("command", "")
    if not is_git_commit(command):
        return

    cwd = (payload.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR")
           or os.getcwd())
    root = _repo_root(cwd)
    if root is None:
        return
    if _is_encrypted_repo(root):
        return

    findings = _scan_staged(root, _commit_stages_all(command))
    if not findings:
        return

    uniq = []
    for item in findings:
        if item not in uniq:
            uniq.append(item)

    listed = "; ".join(f"{kind} in {fname}" for kind, fname in uniq[:5])
    reason = (
        "Commit blocked — high-confidence secret(s) in the staged changes: "
        f"{listed}. Remove the secret(s) before committing (the value is "
        "intentionally not shown here). Pass it via an env-var or the `secret` "
        "helper instead; use a placeholder if an example is genuinely needed. "
        "Encrypted-secret repos (SOPS / git-crypt) are auto-skipped by this gate."
    )
    log_event("secret_block",
              {"types": [k for k, _ in uniq], "files": [f for _, f in uniq]},
              payload)
    emit_permission("deny", reason)


if __name__ == "__main__":
    run(main)
