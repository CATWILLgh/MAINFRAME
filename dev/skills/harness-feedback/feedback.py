#!/usr/bin/env python3
"""Receiver for the `harness-feedback` skill: persist one structured feedback
file about mainframe-harness friction into the global feedback queue.

Usage (body on stdin, all metadata as flags):
    python3 feedback.py --artifact <hub artifact> --type <type> \
        --severity <low|medium|high> --title "<one line>" <<'EOF'
    ## Trigger
    <the exact command / tool call / file that hit the friction>
    ...
    EOF

Writes `$MAINFRAME_FEEDBACK_DIR` (default `~/.claude/feedback/`)
`/<YYYYMMDD-HHMMSS>-<project>-<slug>.md` and prints the written path.
Exit 0 = written; non-zero = rejected, reason on stderr. Stdlib only.
"""

import argparse
import datetime
import json
import os
import re
import sys

TYPES = ("false-positive", "friction", "unclear-instruction",
         "missing-capability", "other")
SEVERITIES = ("low", "medium", "high")
SLUG_MAX_WORDS = 7
WARN_DAILY_CAP = 5
TRIGGER_HEADING = "## Trigger"


def _slug(text):
    words = re.findall(r"[a-z0-9]+", text.lower())[:SLUG_MAX_WORDS]
    return "-".join(words) or "feedback"


def _sanitize_inline(text):
    """One safe frontmatter/filename token: no newlines, collapsed whitespace."""
    return re.sub(r"\s+", " ", text).strip()


def _project_key(cwd):
    base = os.path.basename(os.path.normpath(cwd)) or "unknown"
    return re.sub(r"[^A-Za-z0-9._-]+", "-", base).strip("-") or "unknown"


def _unique_path(directory, stem):
    path = os.path.join(directory, f"{stem}.md")
    n = 2
    while os.path.exists(path):
        path = os.path.join(directory, f"{stem}-{n}.md")
        n += 1
    return path


def _feedback_dir():
    return (os.environ.get("MAINFRAME_FEEDBACK_DIR")
            or os.path.expanduser("~/.claude/feedback"))


def _todays_count(directory, day_prefix, project):
    try:
        return sum(1 for f in os.listdir(directory)
                   if f.startswith(day_prefix) and f"-{project}-" in f)
    except OSError:
        return 0


def _parse_args(argv):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--artifact", required=True,
                   help="hub artifact the feedback is about (skill/hook/rule/agent name)")
    p.add_argument("--type", required=True, choices=TYPES)
    p.add_argument("--severity", default="medium", choices=SEVERITIES)
    p.add_argument("--title", required=True, help="one-line summary")
    return p.parse_args(argv)


def main(argv=None):
    args = _parse_args(argv)
    artifact = _sanitize_inline(args.artifact)
    title = _sanitize_inline(args.title)
    if not artifact or not title:
        sys.exit("feedback.py: --artifact and --title must be non-empty")

    body = "" if sys.stdin.isatty() else sys.stdin.read().strip()
    if not body:
        sys.exit("feedback.py: feedback body expected on stdin (heredoc); got nothing")
    if TRIGGER_HEADING not in body:
        sys.exit(f"feedback.py: body must contain a `{TRIGGER_HEADING}` section naming "
                 "the exact command / tool call / file that caused the friction — "
                 "feedback without a reproducible trigger is unactionable noise")

    now = datetime.datetime.now()
    project = _project_key(os.getcwd())
    directory = _feedback_dir()
    os.makedirs(directory, exist_ok=True)

    if _todays_count(directory, now.strftime("%Y%m%d"), project) >= WARN_DAILY_CAP:
        print(f"feedback.py: {WARN_DAILY_CAP}+ feedback files from `{project}` today — "
              "consider consolidating related friction into one report", file=sys.stderr)

    front = "\n".join((
        "---",
        f"date: {now.isoformat(timespec='seconds')}",
        f"project: {project}",
        f"session: {os.environ.get('CLAUDE_SESSION_ID', '')}",
        f"artifact: {artifact}",
        f"type: {args.type}",
        f"severity: {args.severity}",
        f"title: {json.dumps(title)}",
        "---",
    ))
    stem = f"{now.strftime('%Y%m%d-%H%M%S')}-{project}-{_slug(title)}"
    path = _unique_path(directory, stem)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(f"{front}\n\n# {title}\n\n{body}\n")
    print(path)


if __name__ == "__main__":
    main()
