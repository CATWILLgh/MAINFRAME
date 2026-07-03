#!/usr/bin/env python3
"""Tests for commit-conventional-reminder.py `extract_subject`.

Covers the two harness-feedback false positives (20260610-162716,
20260611-141832): a heredoc body line misread as the commit subject, and the
first heredoc of a compound command validated instead of the one feeding
`git commit -F /dev/stdin`.
"""

import importlib.util
import os

_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                       "plugin-dist", "hooks", "scripts",
                       "commit-conventional-reminder.py")
spec = importlib.util.spec_from_file_location("commit_conventional_reminder", _SCRIPT)
ccr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ccr)

extract_subject = ccr.extract_subject


def test_quoted_m_single_line():
    assert extract_subject("git commit -m 'feat(x): add y'") == "feat(x): add y"


def test_quoted_m_multiline_takes_first_line():
    assert extract_subject('git commit -m "fix: z\n\nbody text"') == "fix: z"


def test_unquoted_m_word():
    # Feedback 20260610: `-m init` (no quotes) must be read as the subject...
    cmd = "git commit -q --allow-empty -m init"
    assert extract_subject(cmd) == "init"


def test_unquoted_m_ignores_unrelated_heredoc():
    # ...even when an unrelated heredoc follows in the same compound command.
    cmd = (
        "git commit -q --allow-empty -m init\n"
        "python3 feedback.py --type friction <<'EOF'\n"
        "## Trigger\n"
        "something\n"
        "EOF"
    )
    assert extract_subject(cmd) == "init"


def test_combined_flags_am():
    assert extract_subject("git commit -am 'fix: y'") == "fix: y"


def test_commit_owned_heredoc():
    cmd = (
        "git commit -F /dev/stdin <<'EOF'\n"
        "docs(scope): subject line\n"
        "\n"
        "body\n"
        "EOF"
    )
    assert extract_subject(cmd) == "docs(scope): subject line"


def test_second_heredoc_owned_by_commit_wins():
    # Feedback 20260611: first heredoc feeds `cat >>`, second feeds the commit.
    cmd = (
        "cat >> docs/tickets/3b7e4a.md <<'EOF'\n"
        "## Resolution (2026-06-11)\n"
        "details\n"
        "EOF\n"
        "git add docs/tickets/ && git commit -F /dev/stdin <<'EOF'\n"
        "docs(tickets): close 3b7e4a\n"
        "\n"
        "body\n"
        "EOF"
    )
    assert extract_subject(cmd) == "docs(tickets): close 3b7e4a"


def test_heredoc_not_owned_by_commit_gives_none():
    cmd = (
        "cat > notes.md <<'EOF'\n"
        "## Heading\n"
        "EOF\n"
        "git commit -F /tmp/msg.txt"
    )
    assert extract_subject(cmd) is None


def test_fake_opener_inside_heredoc_body_is_skipped():
    # A body line that LOOKS like a heredoc opener must not derail the scan.
    cmd = (
        "cat > gen.sh <<'EOF'\n"
        "cat <<INNER\n"
        "not a real opener at execution depth we care about\n"
        "INNER\n"
        "EOF\n"
        "git commit -F /dev/stdin <<'MSG'\n"
        "chore(gen): regenerate script\n"
        "MSG"
    )
    assert extract_subject(cmd) == "chore(gen): regenerate script"


def test_dash_f_dash_variant():
    cmd = "git commit -F - <<'EOF'\nrefactor(core): split module\nEOF"
    assert extract_subject(cmd) == "refactor(core): split module"


def test_glued_dash_f_stdin():
    cmd = "git commit -F/dev/stdin <<'EOF'\nperf(io): batch reads\nEOF"
    assert extract_subject(cmd) == "perf(io): batch reads"


def test_m_like_text_inside_heredoc_body_does_not_hijack():
    # Caught live: the commit that shipped the owner-binding fix mentioned
    # `-am 'msg'` in its own body, and the -m regex read `msg` as the subject.
    cmd = (
        "git commit -F /dev/stdin <<'EOF'\n"
        "fix(hooks): bind commit-subject extraction\n"
        "\n"
        "- Bundled short flags (`-am 'msg'`) now parse.\n"
        "EOF"
    )
    assert extract_subject(cmd) == "fix(hooks): bind commit-subject extraction"


def test_no_message_returns_none():
    assert extract_subject("git commit") is None


def _run_all():
    import sys
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  ok  {name}")
            except AssertionError as exc:
                failures += 1
                print(f"FAIL  {name}: {exc!r}")
    total = sum(1 for n, f in globals().items()
                if n.startswith("test_") and callable(f))
    print(f"\n{total - failures}/{total} passed")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    _run_all()
