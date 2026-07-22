#!/usr/bin/env python3
"""Unit tests for the `harness-feedback` receiver script.

Run: `python3 tools/test_feedback.py` (exit 0 = pass). Stdlib only. Uses a temp
target dir via the `MAINFRAME_FEEDBACK_DIR` env var so the real
`~/.claude/mainframe/feedback` is never touched. CLI-level tests spawn real subprocesses —
the actual skill scenario (agent runs the script via Bash).
"""

import json
import os
import stat
import subprocess
import sys
import tempfile
from unittest import mock

sys.dont_write_bytecode = True   # keep __pycache__ out of the validated skill dir

_SKILL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "..", "dev", "skills", "harness-feedback")
sys.path.insert(0, _SKILL_DIR)
import feedback

SCRIPT = os.path.join(_SKILL_DIR, "feedback.py")

GOOD_BODY = (
    "## Trigger\n"
    "`Bash(rm -r build/)` denied by the rm -rf ask-rule while cleaning a build dir.\n\n"
    "## Expected vs actual\n"
    "Expected: plain `rm -r` on a project subdir passes in auto-mode.\n"
    "Actual: classifier stalled the run on an ask-rule.\n"
)


def _run(args, body=GOOD_BODY, env_extra=None, cwd=None):
    env = dict(os.environ)
    env.pop("CLAUDE_SESSION_ID", None)
    env.pop("MAINFRAME_DIAGNOSTICS_CONFIG", None)
    env.pop("MAINFRAME_FEEDBACK_DIR", None)
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, SCRIPT] + args,
        input=body, capture_output=True, text=True, env=env, cwd=cwd,
    )


def _tmp():
    return tempfile.mkdtemp()


def _base_args():
    return ["--artifact", "permissions/rm-rf-ask", "--type", "false-positive",
            "--severity", "medium", "--title", "rm -r blocked on build dir"]


def _config(path, *, feedback_enabled=True, schema_version=1):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"schema_version": schema_version,
                   "events": False,
                   "feedback": feedback_enabled,
                   "ignored_extra_key": "allowed"}, fh)
    return path


def test_partial_activation_document_is_rejected():
    directory = os.path.join(_tmp(), "feedback")
    config = os.path.join(_tmp(), "diagnostics.json")
    with open(config, "w", encoding="utf-8") as stream:
        json.dump({"schema_version": 1, "feedback": True}, stream)
    result = _run(_base_args(), env_extra={
        "MAINFRAME_FEEDBACK_DIR": directory,
        "MAINFRAME_DIAGNOSTICS_CONFIG": config,
    })
    assert result.returncode != 0
    assert not os.path.exists(directory)


def _enabled_env(directory):
    config = os.path.join(_tmp(), "diagnostics.json")
    _config(config)
    return {"MAINFRAME_FEEDBACK_DIR": directory,
            "MAINFRAME_DIAGNOSTICS_CONFIG": config}


def test_writes_file_with_frontmatter():
    d = _tmp()
    r = _run(_base_args(), env_extra=_enabled_env(d))
    assert r.returncode == 0, r.stderr
    path = r.stdout.strip()
    assert path.startswith(d) and path.endswith(".md"), path
    assert os.path.isfile(path), path
    text = open(path, encoding="utf-8").read()
    assert text.startswith("---\n"), text[:40]
    for needle in ("artifact: ", "type: false-positive", "severity: medium",
                   "project: ", "date: ", "session: ", 'title: "'):
        assert needle in text, f"missing {needle!r} in frontmatter"
    assert "## Trigger" in text and "rm -r build" in text


def test_invalid_type_rejected():
    d = _tmp()
    args = _base_args()
    args[args.index("--type") + 1] = "praise"      # positive feedback is not a type
    r = _run(args, env_extra=_enabled_env(d))
    assert r.returncode != 0
    assert os.listdir(d) == [], "file must not be written on validation error"


def test_missing_trigger_section_rejected():
    d = _tmp()
    r = _run(_base_args(), body="It blocked me and I did not like it.\n",
             env_extra=_enabled_env(d))
    assert r.returncode != 0
    assert "Trigger" in r.stderr, r.stderr
    assert os.listdir(d) == []


def test_empty_body_rejected():
    d = _tmp()
    r = _run(_base_args(), body="", env_extra=_enabled_env(d))
    assert r.returncode != 0
    assert os.listdir(d) == []


def test_session_env_captured():
    d = _tmp()
    env = _enabled_env(d)
    env["CLAUDE_SESSION_ID"] = "sess-42"
    r = _run(_base_args(), env_extra=env)
    assert r.returncode == 0, r.stderr
    text = open(r.stdout.strip(), encoding="utf-8").read()
    assert "session: sess-42" in text


def test_project_from_cwd():
    d = _tmp()
    proj = os.path.join(_tmp(), "my-proj")
    os.makedirs(proj)
    r = _run(_base_args(), env_extra=_enabled_env(d), cwd=proj)
    assert r.returncode == 0, r.stderr
    path = r.stdout.strip()
    assert "-my-proj-" in os.path.basename(path), path
    assert "project: my-proj" in open(path, encoding="utf-8").read()


def test_slug_sanitization():
    assert feedback._slug("Weird  Title!!  with   spaces") == "weird-title-with-spaces"
    assert feedback._slug("кириллица и точки...") == "feedback"   # non-ascii falls back
    assert len(feedback._slug("w " * 50).split("-")) <= feedback.SLUG_MAX_WORDS


def test_unique_path_suffixes_on_collision():
    d = _tmp()
    first = feedback._write_report(d, "x", "first")
    second = feedback._write_report(d, "x", "second")
    assert first == os.path.join(d, "x.md")
    assert second == os.path.join(d, "x-2.md")
    assert open(first, encoding="utf-8").read() == "first"
    assert open(second, encoding="utf-8").read() == "second"
    target = os.path.join(d, "target")
    with open(target, "w", encoding="utf-8") as fh:
        fh.write("unchanged")
    os.symlink(target, os.path.join(d, "x-3.md"))
    assert feedback._write_report(d, "x", "fourth").endswith("x-4.md")
    assert open(target, encoding="utf-8").read() == "unchanged"


def test_daily_cap_warns_but_still_writes():
    d = _tmp()
    proj = os.path.join(_tmp(), "busy-proj")
    os.makedirs(proj)
    env = _enabled_env(d)
    for _ in range(feedback.WARN_DAILY_CAP):
        r = _run(_base_args(), env_extra=env, cwd=proj)
        assert r.returncode == 0, r.stderr
    r = _run(_base_args(), env_extra=env, cwd=proj)
    assert r.returncode == 0, r.stderr
    assert "consider consolidating" in r.stderr.lower(), r.stderr
    assert len(os.listdir(d)) == feedback.WARN_DAILY_CAP + 1


def test_missing_config_fails_without_creating_output_directory():
    root = _tmp()
    output = os.path.join(root, "feedback")
    config = os.path.join(root, "missing.json")
    r = _run(_base_args(), env_extra={
        "MAINFRAME_FEEDBACK_DIR": output,
        "MAINFRAME_DIAGNOSTICS_CONFIG": config,
    })
    assert r.returncode != 0
    assert "diagnostics config" in r.stderr.lower(), r.stderr
    assert not os.path.exists(output)


def test_default_config_and_feedback_paths_are_supported():
    home = _tmp()
    runtime = os.path.join(home, ".claude", "mainframe")
    os.makedirs(runtime)
    _config(os.path.join(runtime, "diagnostics.json"))
    r = _run(_base_args(), env_extra={"HOME": home})
    assert r.returncode == 0, r.stderr
    assert os.path.dirname(r.stdout.strip()) == os.path.join(runtime, "feedback")


def test_feedback_false_fails_without_creating_output_directory():
    root = _tmp()
    output = os.path.join(root, "feedback")
    config = _config(os.path.join(root, "diagnostics.json"),
                     feedback_enabled=False)
    r = _run(_base_args(), env_extra={
        "MAINFRAME_FEEDBACK_DIR": output,
        "MAINFRAME_DIAGNOSTICS_CONFIG": config,
    })
    assert r.returncode != 0
    assert "disabled" in r.stderr.lower(), r.stderr
    assert not os.path.exists(output)


def test_invalid_configs_fail_closed_without_output_directory():
    invalid_documents = (
        "[]",
        "{}",
        '{"schema_version": true, "feedback": true}',
        '{"schema_version": 2, "feedback": true}',
        '{"schema_version": 1, "feedback": 1}',
        "not-json",
    )
    for document in invalid_documents:
        root = _tmp()
        output = os.path.join(root, "feedback")
        config = os.path.join(root, "diagnostics.json")
        with open(config, "w", encoding="utf-8") as fh:
            fh.write(document)
        r = _run(_base_args(), env_extra={
            "MAINFRAME_FEEDBACK_DIR": output,
            "MAINFRAME_DIAGNOSTICS_CONFIG": config,
        })
        assert r.returncode != 0, document
        assert not os.path.exists(output), document


def test_unreadable_config_fails_closed_without_output_directory():
    root = _tmp()
    output = os.path.join(root, "feedback")
    config = _config(os.path.join(root, "diagnostics.json"))
    os.chmod(config, 0)
    try:
        r = _run(_base_args(), env_extra={
            "MAINFRAME_FEEDBACK_DIR": output,
            "MAINFRAME_DIAGNOSTICS_CONFIG": config,
        })
    finally:
        os.chmod(config, 0o600)
    assert r.returncode != 0
    assert not os.path.exists(output)


def test_symlink_config_fails_closed_without_output_directory():
    root = _tmp()
    output = os.path.join(root, "feedback")
    target = _config(os.path.join(root, "real-diagnostics.json"))
    config = os.path.join(root, "diagnostics.json")
    os.symlink(target, config)
    r = _run(_base_args(), env_extra={
        "MAINFRAME_FEEDBACK_DIR": output,
        "MAINFRAME_DIAGNOSTICS_CONFIG": config,
    })
    assert r.returncode != 0
    assert "symlink" in r.stderr.lower(), r.stderr
    assert not os.path.exists(output)


def test_foreign_owned_config_fails_closed_without_output_directory():
    root = _tmp()
    output = os.path.join(root, "feedback")
    config = _config(os.path.join(root, "diagnostics.json"))
    previous = os.environ.get("MAINFRAME_DIAGNOSTICS_CONFIG")
    os.environ["MAINFRAME_DIAGNOSTICS_CONFIG"] = config
    try:
        with mock.patch.object(feedback.os, "geteuid", return_value=os.geteuid() + 1):
            feedback._load_activation()
    except SystemExit as error:
        assert "user-owned" in str(error)
    else:
        raise AssertionError("foreign-owned diagnostics config was accepted")
    finally:
        if previous is None:
            os.environ.pop("MAINFRAME_DIAGNOSTICS_CONFIG", None)
        else:
            os.environ["MAINFRAME_DIAGNOSTICS_CONFIG"] = previous
    assert not os.path.exists(output)


def test_output_permissions_are_private():
    root = _tmp()
    output = os.path.join(root, "feedback")
    r = _run(_base_args(), env_extra=_enabled_env(output))
    assert r.returncode == 0, r.stderr
    assert stat.S_IMODE(os.stat(output).st_mode) == 0o700
    assert stat.S_IMODE(os.stat(r.stdout.strip()).st_mode) == 0o600


def test_permissive_user_owned_output_directory_is_tightened():
    output = os.path.join(_tmp(), "feedback")
    os.mkdir(output, 0o777)
    os.chmod(output, 0o777)
    r = _run(_base_args(), env_extra=_enabled_env(output))
    assert r.returncode == 0, r.stderr
    assert stat.S_IMODE(os.stat(output).st_mode) == 0o700


def test_symlink_output_directory_is_rejected():
    root = _tmp()
    real_output = os.path.join(root, "real-feedback")
    os.mkdir(real_output)
    output = os.path.join(root, "feedback")
    os.symlink(real_output, output)
    r = _run(_base_args(), env_extra=_enabled_env(output))
    assert r.returncode != 0
    assert os.listdir(real_output) == []


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"  ok {t.__name__}")
    print(f"OK feedback — {len(tests)} tests passed")


if __name__ == "__main__":
    main()
