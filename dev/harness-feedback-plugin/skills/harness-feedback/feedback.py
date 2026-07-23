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

Requires an enabled diagnostics document from `$MAINFRAME_DIAGNOSTICS_CONFIG`
(default `{{mainframe.diagnostics_config}}`). Writes one private report to
`$MAINFRAME_FEEDBACK_DIR` (default `{{mainframe.feedback_dir}}`) and prints
the written path. Exit 0 = written; non-zero = rejected, reason on stderr.
Stdlib only.
"""

import argparse
import datetime
import json
import os
import re
import stat
import sys

TYPES = ("false-positive", "friction", "unclear-instruction",
         "missing-capability", "other")
SEVERITIES = ("low", "medium", "high")
SLUG_MAX_WORDS = 7
WARN_DAILY_CAP = 5
TRIGGER_HEADING = "## Trigger"
SCHEMA_VERSION = 1
PRIVATE_DIR_MODE = 0o700
PRIVATE_FILE_MODE = 0o600
MAX_COLLISION_ATTEMPTS = 1000


def _slug(text):
    words = re.findall(r"[a-z0-9]+", text.lower())[:SLUG_MAX_WORDS]
    return "-".join(words) or "feedback"


def _sanitize_inline(text):
    """One safe frontmatter/filename token: no newlines, collapsed whitespace."""
    return re.sub(r"\s+", " ", text).strip()


def _project_key(cwd):
    base = os.path.basename(os.path.normpath(cwd)) or "unknown"
    return re.sub(r"[^A-Za-z0-9._-]+", "-", base).strip("-") or "unknown"


def _feedback_dir():
    return (os.environ.get("MAINFRAME_FEEDBACK_DIR")
            or os.path.expanduser("~/.claude/mainframe/feedback"))


def _diagnostics_config():
    return (os.environ.get("MAINFRAME_DIAGNOSTICS_CONFIG")
            or os.path.expanduser("~/.claude/mainframe/diagnostics.json"))


def _load_activation():
    path = _diagnostics_config()
    try:
        before = os.lstat(path)
    except OSError as error:
        raise SystemExit(f"feedback.py: diagnostics config unavailable: {error.strerror}")
    if stat.S_ISLNK(before.st_mode):
        raise SystemExit("feedback.py: diagnostics config must not be a symlink")
    if (not stat.S_ISREG(before.st_mode) or before.st_uid != os.geteuid()
            or not before.st_mode & 0o444):
        raise SystemExit(
            "feedback.py: diagnostics config must be a readable user-owned file")
    flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW
    try:
        fd = os.open(path, flags)
        with os.fdopen(fd, encoding="utf-8") as stream:
            opened = os.fstat(stream.fileno())
            if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
                raise OSError("diagnostics config changed while opening")
            if opened.st_uid != os.geteuid() or not stat.S_ISREG(opened.st_mode):
                raise OSError("diagnostics config ownership or type changed")
            document = json.load(stream)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise SystemExit(f"feedback.py: invalid diagnostics config: {error}")
    if not isinstance(document, dict):
        raise SystemExit("feedback.py: invalid diagnostics config schema")
    if (type(document.get("schema_version")) is not int
            or document["schema_version"] != SCHEMA_VERSION
            or type(document.get("events")) is not bool
            or type(document.get("feedback")) is not bool):
        raise SystemExit("feedback.py: invalid diagnostics config schema")
    if not document["events"]:
        raise SystemExit("feedback.py: DEV is disabled in diagnostics config")
    if not document["feedback"]:
        raise SystemExit("feedback.py: feedback is disabled in diagnostics config")


def _open_feedback_dir(directory):
    try:
        entry = os.lstat(directory)
    except FileNotFoundError:
        try:
            parent = os.stat(os.path.dirname(directory) or ".")
        except OSError as error:
            raise SystemExit(f"feedback.py: feedback parent unavailable: {error.strerror}")
        if not stat.S_ISDIR(parent.st_mode) or parent.st_uid != os.geteuid():
            raise SystemExit("feedback.py: feedback parent must be a user-owned directory")
        try:
            os.mkdir(directory, PRIVATE_DIR_MODE)
            entry = os.lstat(directory)
        except OSError as error:
            raise SystemExit(f"feedback.py: cannot create feedback directory: {error.strerror}")
    except OSError as error:
        raise SystemExit(f"feedback.py: feedback directory unavailable: {error.strerror}")
    if stat.S_ISLNK(entry.st_mode):
        raise SystemExit("feedback.py: feedback directory must not be a symlink")
    flags = os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW
    try:
        descriptor = os.open(directory, flags)
        opened = os.fstat(descriptor)
        if not stat.S_ISDIR(opened.st_mode) or opened.st_uid != os.geteuid():
            raise OSError("feedback directory must be real and user-owned")
        os.fchmod(descriptor, PRIVATE_DIR_MODE)
        if stat.S_IMODE(os.fstat(descriptor).st_mode) != PRIVATE_DIR_MODE:
            raise OSError("feedback directory mode is not 0700")
        return descriptor
    except OSError as error:
        if "descriptor" in locals():
            os.close(descriptor)
        raise SystemExit(f"feedback.py: insecure feedback directory: {error}")


def _report_name(stem, attempt):
    suffix = "" if attempt == 1 else f"-{attempt}"
    return f"{stem}{suffix}.md"


def _create_report(directory_fd, directory, stem, content):
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW
    for attempt in range(1, MAX_COLLISION_ATTEMPTS + 1):
        name = _report_name(stem, attempt)
        try:
            fd = os.open(name, flags, PRIVATE_FILE_MODE, dir_fd=directory_fd)
        except FileExistsError:
            continue
        try:
            opened = os.fstat(fd)
            os.fchmod(fd, PRIVATE_FILE_MODE)
            secured = os.fstat(fd)
            if (not stat.S_ISREG(opened.st_mode) or opened.st_uid != os.geteuid()
                    or stat.S_IMODE(secured.st_mode) != PRIVATE_FILE_MODE):
                raise OSError("created report is not a private user-owned regular file")
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                fd = -1
                stream.write(content)
            return os.path.join(directory, name)
        except OSError:
            if fd >= 0:
                os.close(fd)
            os.unlink(name, dir_fd=directory_fd)
            raise
    raise OSError("feedback report collision limit reached")


def _write_report(directory, stem, content, directory_fd=None):
    owned_descriptor = directory_fd is None
    descriptor = (_open_feedback_dir(directory) if owned_descriptor
                  else directory_fd)
    try:
        return _create_report(descriptor, directory, stem, content)
    except OSError as error:
        raise SystemExit(f"feedback.py: cannot write feedback report: {error}")
    finally:
        if owned_descriptor:
            os.close(descriptor)


def _todays_count(directory_fd, day_prefix, project):
    try:
        return sum(1 for f in os.listdir(directory_fd)
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

    _load_activation()
    now = datetime.datetime.now()
    project = _project_key(os.getcwd())
    directory = _feedback_dir()
    directory_fd = _open_feedback_dir(directory)

    if _todays_count(directory_fd, now.strftime("%Y%m%d"), project) >= WARN_DAILY_CAP:
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
    content = f"{front}\n\n# {title}\n\n{body}\n"
    try:
        path = _write_report(directory, stem, content, directory_fd)
    finally:
        os.close(directory_fd)
    print(path)


if __name__ == "__main__":
    main()
