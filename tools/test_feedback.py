#!/usr/bin/env python3
"""Unit tests for the `harness-feedback` receiver script.

Run: `python3 tools/test_feedback.py` (exit 0 = pass). Stdlib only. Uses a temp
target dir via the `MAINFRAME_FEEDBACK_DIR` env var so the real
`workspace/runtime/<adapter>/feedback` queues are never touched. CLI-level tests
spawn real subprocesses — the actual skill scenario (agent runs the script via
Bash). Model analysis is disabled except in its dedicated launch test.
"""

import importlib.util
import os
import json
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True   # keep __pycache__ out of the validated skill dir

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RECEIVER = os.path.join(ROOT, "dev", "harness-feedback", "receiver.py")
SPEC = importlib.util.spec_from_file_location("mainframe_harness_feedback", RECEIVER)
assert SPEC is not None and SPEC.loader is not None
feedback = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(feedback)
SCRIPTS = {
    "claude-code": os.path.join(
        ROOT, "adapters", "claude-code", "dev", "skills", "harness-feedback", "feedback.py"),
    "codex": os.path.join(
        ROOT, "adapters", "codex", "dev", "skills", "harness-feedback", "feedback.py"),
}

GOOD_BODY = (
    "## Trigger\n"
    "`Bash(rm -r build/)` denied by the rm -rf ask-rule while cleaning a build dir.\n\n"
    "## Expected vs actual\n"
    "Expected: plain `rm -r` on a project subdir passes in auto-mode.\n"
    "Actual: classifier stalled the run on an ask-rule.\n"
)


def _run(args, body=GOOD_BODY, env_extra=None, cwd=None, adapter="claude-code"):
    env = dict(os.environ)
    env.pop("CLAUDE_SESSION_ID", None)
    env.pop("CODEX_THREAD_ID", None)
    env.pop("CODEX_SESSION_ID", None)
    env["MAINFRAME_MODEL_LAB_DISABLE"] = "1"
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, SCRIPTS[adapter]] + args,
        input=body, capture_output=True, text=True, env=env, cwd=cwd,
    )


def _tmp():
    return tempfile.mkdtemp()


def _base_args():
    return ["--artifact", "permissions/rm-rf-ask", "--type", "false-positive",
            "--severity", "medium", "--title", "rm -r blocked on build dir"]


def test_writes_file_with_frontmatter():
    d = _tmp()
    r = _run(_base_args(), env_extra={"MAINFRAME_FEEDBACK_DIR": d})
    assert r.returncode == 0, r.stderr
    path = r.stdout.strip()
    assert path.startswith(d) and path.endswith(".md"), path
    assert os.path.isfile(path), path
    text = open(path, encoding="utf-8").read()
    assert text.startswith("---\n"), text[:40]
    for needle in ("schema: 2", "adapter: claude-code",
                   "model_lab_eligible: true", "artifact: ",
                   "type: false-positive", "severity: medium",
                   "project: ", "date: ", "session: ", 'title: "'):
        assert needle in text, f"missing {needle!r} in frontmatter"
    assert "## Trigger" in text and "rm -r build" in text


def test_invalid_type_rejected():
    d = _tmp()
    args = _base_args()
    args[args.index("--type") + 1] = "praise"      # positive feedback is not a type
    r = _run(args, env_extra={"MAINFRAME_FEEDBACK_DIR": d})
    assert r.returncode != 0
    assert os.listdir(d) == [], "file must not be written on validation error"


def test_missing_trigger_section_rejected():
    d = _tmp()
    r = _run(_base_args(), body="It blocked me and I did not like it.\n",
             env_extra={"MAINFRAME_FEEDBACK_DIR": d})
    assert r.returncode != 0
    assert "Trigger" in r.stderr, r.stderr
    assert os.listdir(d) == []


def test_empty_body_rejected():
    d = _tmp()
    r = _run(_base_args(), body="", env_extra={"MAINFRAME_FEEDBACK_DIR": d})
    assert r.returncode != 0
    assert os.listdir(d) == []


def test_session_env_captured():
    d = _tmp()
    r = _run(_base_args(), env_extra={"MAINFRAME_FEEDBACK_DIR": d,
                                      "CLAUDE_SESSION_ID": "sess-42"})
    assert r.returncode == 0, r.stderr
    text = open(r.stdout.strip(), encoding="utf-8").read()
    assert "session: sess-42" in text


def test_codex_session_selects_codex_queue_contract():
    d = _tmp()
    r = _run(_base_args(), adapter="codex",
             env_extra={"MAINFRAME_FEEDBACK_DIR": d,
                        "CODEX_THREAD_ID": "thread-42"})
    assert r.returncode == 0, r.stderr
    text = open(r.stdout.strip(), encoding="utf-8").read()
    assert "adapter: codex" in text
    assert "model_lab_eligible: false" in text
    assert "session: thread-42" in text


def test_installed_copy_finds_receiver_through_managed_delivery_state():
    home = _tmp()
    installed = os.path.join(home, ".agents", "skills", "harness-feedback")
    os.makedirs(installed)
    script = os.path.join(installed, "feedback.py")
    shutil.copyfile(SCRIPTS["codex"], script)
    state_dir = os.path.join(home, ".codex", ".mainframe-managed-artifacts")
    os.makedirs(state_dir)
    source = os.path.join(
        ROOT, "adapters", "codex", "dev", "skills", "harness-feedback"
    )
    with open(os.path.join(state_dir, "dev-harness-feedback.json"), "w") as handle:
        json.dump({"source": source, "target": installed}, handle)
    output = _tmp()
    env = dict(os.environ)
    env.update({
        "HOME": home, "MAINFRAME_FEEDBACK_DIR": output,
        "MAINFRAME_MODEL_LAB_DISABLE": "1",
    })
    result = subprocess.run(
        [sys.executable, script] + _base_args(), input=GOOD_BODY,
        capture_output=True, text=True, env=env,
    )
    assert result.returncode == 0, result.stderr
    assert os.path.isfile(result.stdout.strip())


def test_codex_entrypoint_does_not_need_session_detection():
    d = _tmp()
    r = _run(_base_args(), adapter="codex",
             env_extra={"MAINFRAME_FEEDBACK_DIR": d})
    assert r.returncode == 0, r.stderr
    text = open(r.stdout.strip(), encoding="utf-8").read()
    assert "adapter: codex" in text
    assert "session: " in text


def test_project_from_cwd():
    d = _tmp()
    proj = os.path.join(_tmp(), "my-proj")
    os.makedirs(proj)
    r = _run(_base_args(), env_extra={"MAINFRAME_FEEDBACK_DIR": d}, cwd=proj)
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
    first = os.path.join(d, "x.md")
    open(first, "w").close()
    assert feedback._unique_path(d, "x") == os.path.join(d, "x-2.md")


def test_daily_cap_warns_but_still_writes():
    d = _tmp()
    proj = os.path.join(_tmp(), "busy-proj")
    os.makedirs(proj)
    env = {"MAINFRAME_FEEDBACK_DIR": d}
    for _ in range(feedback.WARN_DAILY_CAP):
        r = _run(_base_args(), env_extra=env, cwd=proj)
        assert r.returncode == 0, r.stderr
    r = _run(_base_args(), env_extra=env, cwd=proj)
    assert r.returncode == 0, r.stderr
    assert "consider consolidating" in r.stderr.lower(), r.stderr
    assert len(os.listdir(d)) == feedback.WARN_DAILY_CAP + 1


def test_detaches_optional_worker_after_write():
    root = _tmp()
    out = os.path.join(root, "feedback")
    marker = os.path.join(root, "worker-ran")
    worker = os.path.join(root, "worker.py")
    with open(worker, "w", encoding="utf-8") as handle:
        handle.write(
            "import os, pathlib, sys\n"
            "pathlib.Path(os.environ['TEST_WORKER_MARKER']).write_text(sys.argv[1])\n"
        )
    r = _run(
        _base_args(),
        env_extra={
            "MAINFRAME_FEEDBACK_DIR": out,
            "MAINFRAME_MODEL_LAB_DISABLE": "0",
            "MAINFRAME_MODEL_LAB_WORKER": worker,
            "TEST_WORKER_MARKER": marker,
        },
    )
    assert r.returncode == 0, r.stderr
    for _ in range(40):
        if os.path.exists(marker):
            break
        import time
        time.sleep(0.025)
    assert os.path.isfile(marker), "detached worker did not run"
    assert open(marker, encoding="utf-8").read() == r.stdout.strip()


def test_missing_worker_never_breaks_feedback():
    d = _tmp()
    r = _run(
        _base_args(),
        env_extra={
            "MAINFRAME_FEEDBACK_DIR": d,
            "MAINFRAME_MODEL_LAB_DISABLE": "0",
            "MAINFRAME_MODEL_LAB_WORKER": os.path.join(d, "absent.py"),
        },
    )
    assert r.returncode == 0, r.stderr
    assert os.path.isfile(r.stdout.strip())


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"  ok {t.__name__}")
    print(f"OK feedback — {len(tests)} tests passed")


if __name__ == "__main__":
    main()
