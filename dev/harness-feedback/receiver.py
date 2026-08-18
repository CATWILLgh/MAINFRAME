#!/usr/bin/env python3
"""Persist one structured adapter harness report and enqueue optional analysis."""

import argparse
import datetime
import json
import os
import re
import subprocess
import sys


TYPES = ("false-positive", "friction", "unclear-instruction",
         "missing-capability", "other")
SEVERITIES = ("low", "medium", "high")
SLUG_MAX_WORDS = 7
WARN_DAILY_CAP = 5
TRIGGER_HEADING = "## Trigger"


def _project_root():
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))


def _slug(text):
    words = re.findall(r"[a-z0-9]+", text.lower())[:SLUG_MAX_WORDS]
    return "-".join(words) or "feedback"


def _sanitize_inline(text):
    return re.sub(r"\s+", " ", text).strip()


def _project_key(cwd):
    base = os.path.basename(os.path.normpath(cwd)) or "unknown"
    return re.sub(r"[^A-Za-z0-9._-]+", "-", base).strip("-") or "unknown"


def _unique_path(directory, stem):
    path = os.path.join(directory, f"{stem}.md")
    number = 2
    while os.path.exists(path):
        path = os.path.join(directory, f"{stem}-{number}.md")
        number += 1
    return path


def _feedback_dir(adapter):
    override = os.environ.get("MAINFRAME_FEEDBACK_DIR")
    if override:
        return override
    return os.path.join(_project_root(), "workspace", "runtime", adapter, "feedback")


def _model_lab_worker():
    override = os.environ.get("MAINFRAME_MODEL_LAB_WORKER")
    if override:
        return override
    return os.path.join(
        _project_root(), "adapters", "claude-code", "dev", "model-lab",
        "spark-feedback-worker.py")


def _launch_model_lab(path, adapter):
    """Detach optional Claude analysis without affecting the durable write."""
    if adapter != "claude-code" or os.environ.get("MAINFRAME_MODEL_LAB_DISABLE") == "1":
        return False
    worker = _model_lab_worker()
    if not os.path.isfile(worker):
        return False
    try:
        subprocess.Popen(
            [sys.executable, worker, path],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            start_new_session=True,
            env=dict(os.environ),
        )
        return True
    except OSError:
        return False


def _todays_count(directory, day_prefix, project):
    try:
        return sum(
            1 for filename in os.listdir(directory)
            if filename.startswith(day_prefix) and f"-{project}-" in filename
        )
    except OSError:
        return 0


def _parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--type", required=True, choices=TYPES)
    parser.add_argument("--severity", default="medium", choices=SEVERITIES)
    parser.add_argument("--title", required=True)
    return parser.parse_args(argv)


def _session_id(adapter):
    if adapter == "claude-code":
        return os.environ.get("CLAUDE_SESSION_ID", "")
    return os.environ.get("CODEX_THREAD_ID") or os.environ.get("CODEX_SESSION_ID", "")


def main(adapter, argv=None):
    if adapter not in {"claude-code", "codex"}:
        raise ValueError(f"unsupported adapter: {adapter}")
    args = _parse_args(argv)
    artifact = _sanitize_inline(args.artifact)
    title = _sanitize_inline(args.title)
    if not artifact or not title:
        raise SystemExit("feedback.py: --artifact and --title must be non-empty")

    body = "" if sys.stdin.isatty() else sys.stdin.read().strip()
    if not body:
        raise SystemExit("feedback.py: feedback body expected on stdin (heredoc); got nothing")
    if TRIGGER_HEADING not in body:
        raise SystemExit(
            f"feedback.py: body must contain a `{TRIGGER_HEADING}` section naming "
            "the exact command / tool call / file that caused the friction — "
            "feedback without a reproducible trigger is unactionable noise")

    now = datetime.datetime.now()
    project = _project_key(os.getcwd())
    directory = _feedback_dir(adapter)
    os.makedirs(directory, exist_ok=True)
    if _todays_count(directory, now.strftime("%Y%m%d"), project) >= WARN_DAILY_CAP:
        print(
            f"feedback.py: {WARN_DAILY_CAP}+ feedback files from `{project}` today — "
            "consider consolidating related friction into one report",
            file=sys.stderr,
        )

    frontmatter = "\n".join((
        "---",
        "schema: 2",
        f"adapter: {adapter}",
        f"model_lab_eligible: {'true' if adapter == 'claude-code' else 'false'}",
        f"date: {now.isoformat(timespec='seconds')}",
        f"project: {project}",
        f"session: {_session_id(adapter)}",
        f"artifact: {artifact}",
        f"type: {args.type}",
        f"severity: {args.severity}",
        f"title: {json.dumps(title)}",
        "---",
    ))
    stem = f"{now.strftime('%Y%m%d-%H%M%S')}-{project}-{_slug(title)}"
    path = _unique_path(directory, stem)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(f"{frontmatter}\n\n# {title}\n\n{body}\n")
    print(path)
    _launch_model_lab(path, adapter)
    return 0
