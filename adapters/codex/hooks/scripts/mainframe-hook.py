#!/usr/bin/env python3
"""Single-process dispatcher for MAINFRAME's native Codex hook guarantees."""

from __future__ import annotations

from contextlib import redirect_stdout
import importlib.util
import io
import json
import os
from pathlib import Path
import shlex
import sys


SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

MAX_SECTIONS = 8
MAX_STOP_CHARS = 8_000

HEALTH_MODULES = (
    "_bash_patterns.py",
    "_comment_findings.py",
    "_edit_snapshot.py",
    "_fallow_state.py",
    "_git_authority.py",
    "_hooklib.py",
    "_length_check.py",
    "_length_state.py",
    "_marker_state.py",
    "_markers.py",
    "_notice_state.py",
    "_path_validation.py",
    "_python_findings.py",
    "_secret_commit.py",
    "comment-discipline-reminder.py",
    "comment_extract.py",
    "fallow-quality-note.py",
    "length-quality-note.py",
    "nodejs-security-scan.py",
    "python-security-scan.py",
    "python-security-stop-gate.py",
    "scan-suppression-markers.py",
    "stop-gate-comment-discipline.py",
    "stop-gate-suppression-markers.py",
    "ticket-id-format-reminder.py",
)


def _payload() -> dict:
    value = json.load(sys.stdin)
    if not isinstance(value, dict):
        raise ValueError("hook payload must be a JSON object")
    return value


def _snapshot_module():
    return importlib.import_module("_edit_snapshot")


def _capture(payload: dict) -> None:
    snapshot = _snapshot_module()
    rows = []
    for path in snapshot.paths(payload):
        existed = path.exists()
        content = snapshot.read_text(path)
        if content is None:
            continue
        rows.append({"path": str(path), "existed": existed, "text": content})
        _run_module(
            "length-quality-note.py",
            _synthetic_payload(payload, path, "Write", content=content),
        )
    if rows:
        snapshot.atomic_write(payload, rows)
    snapshot.cleanup()


def _load_snapshot(payload: dict) -> list[dict]:
    snapshot = _snapshot_module()
    return snapshot.consume(payload)


def _synthetic_payload(
    source: dict,
    path: Path,
    tool_name: str,
    *,
    content: str = "",
    edits: list[dict[str, str]] | None = None,
) -> dict:
    value = dict(source)
    value["tool_name"] = tool_name
    if tool_name == "Write":
        value["tool_input"] = {"file_path": str(path), "content": content}
    else:
        value["tool_input"] = {"file_path": str(path), "edits": edits or []}
    return value


def _load_module(filename: str):
    name = "mainframe_codex_" + filename.replace("-", "_").replace(".", "_")
    spec = importlib.util.spec_from_file_location(name, SCRIPT_DIR / filename)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {filename}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _invoke_loaded(module, payload: dict) -> list[dict]:
    original_stdin = sys.stdin
    output = io.StringIO()
    try:
        sys.stdin = io.StringIO(json.dumps(payload))
        with redirect_stdout(output):
            module.main()
    finally:
        sys.stdin = original_stdin
    return [
        json.loads(line)
        for line in output.getvalue().splitlines()
        if line.strip()
    ]


def _run_module(filename: str, payload: dict) -> list[dict]:
    return _invoke_loaded(_load_module(filename), payload)


def _notes(rows: list[dict]) -> list[str]:
    result = []
    for row in rows:
        specific = row.get("hookSpecificOutput")
        text = specific.get("additionalContext") if isinstance(specific, dict) else None
        if isinstance(text, str) and text.strip():
            result.append(text.strip())
    return result


def _failure_notice(payload: dict, component: str, exc: Exception) -> str | None:
    notice = _load_module("_notice_state.py")
    if not notice.claim_once(
        "hook-failure-" + component,
        payload.get("session_id"),
        payload.get("agent_id"),
    ):
        return None
    return (
        f"MAINFRAME check `{component}` is unavailable ({type(exc).__name__}). "
        "Return this fact to the immediate caller before claiming verification "
        "that depends on this check. Other hook checks remain active."
    )


def _checked_module(
    filename: str, payload: dict, failures: list[str]
) -> list[dict]:
    try:
        return _run_module(filename, payload)
    except Exception as exc:
        notice = _failure_notice(payload, filename, exc)
        if notice:
            failures.append(notice)
        return []


def _quality(payload: dict) -> None:
    snapshot = _snapshot_module()
    outputs: list[dict] = []
    failures: list[str] = []
    for saved in _load_snapshot(payload):
        path = Path(saved["path"])
        before = saved.get("text") or ""
        after = snapshot.read_text(path)
        if after is None:
            continue
        exact = _synthetic_payload(payload, path, "Write", content=after)
        diff_payload = _synthetic_payload(
            payload, path, "MultiEdit", edits=snapshot.edits(before, after)
        )
        for filename in (
            "scan-suppression-markers.py",
            "comment-discipline-reminder.py",
            "python-security-scan.py",
        ):
            try:
                module = _load_module(filename)
                if hasattr(module, "read_git_head"):
                    module.read_git_head = lambda _path, baseline=before: baseline
                outputs.extend(_invoke_loaded(module, exact))
            except Exception as exc:
                notice = _failure_notice(payload, filename, exc)
                if notice:
                    failures.append(notice)
        outputs.extend(_checked_module("nodejs-security-scan.py", diff_payload, failures))
        outputs.extend(_checked_module("fallow-quality-note.py", diff_payload, failures))
        outputs.extend(_checked_module("length-quality-note.py", exact, failures))
        if not saved.get("existed"):
            outputs.extend(_checked_module("ticket-id-format-reminder.py", exact, failures))
    notes = list(dict.fromkeys(_notes(outputs) + failures))
    if notes:
        _emit_context(
            payload["hook_event_name"],
            "\n\n".join(notes[:MAX_SECTIONS]),
            system_message="\n\n".join(failures) if failures else None,
        )


def _rule_handles(command: str, reason: str) -> bool:
    try:
        tokens = shlex.split(command)
    except ValueError:
        return False
    if len(tokens) < 2 or os.path.basename(tokens[0]) != "git":
        return False
    subcommand = tokens[1]
    if subcommand in {
        "push", "switch", "checkout", "pull", "merge", "rebase", "reset",
        "cherry-pick", "revert", "restore", "clean", "update-index",
        "update-ref", "read-tree",
    }:
        return True
    if subcommand == "apply":
        return len(tokens) > 2 and tokens[2] in {
            "--cached", "--index", "--3way", "-3", "--intent-to-add", "-N",
        }
    if subcommand == "commit":
        return len(tokens) > 2 and tokens[2] == "--amend"
    if subcommand == "stash":
        return len(tokens) > 2 and tokens[2] in {
            "push", "pop", "apply", "drop", "clear", "branch", "save",
        }
    if subcommand == "worktree":
        return len(tokens) > 2 and tokens[2] in {
            "add", "move", "remove", "lock", "unlock", "prune", "repair",
        }
    if subcommand == "branch" and len(tokens) > 2:
        return tokens[2].split("=", 1)[0] in {
            "-d", "-D", "-m", "-M", "-c", "-C", "--delete", "--move",
            "--copy", "--force", "--edit-description", "--set-upstream-to",
            "--unset-upstream", "--create-reflog", "--track", "--no-track",
        }
    return False


def _rm_rule_handles(command: str) -> bool:
    try:
        tokens = shlex.split(command)
    except ValueError:
        return False
    return (
        len(tokens) >= 2
        and tokens[0] in {"rm", "/bin/rm"}
        and tokens[1] in {
            "-r", "-R", "-rf", "-rF", "-fr", "-fR", "-Rf", "-RF",
            "--recursive",
        }
    )


def _command(payload: dict) -> None:
    snapshot = _snapshot_module()
    command = (payload.get("tool_input") or {}).get("command") or ""
    notes: list[str] = []
    reasons: list[str] = []

    path_module = _load_module("_path_validation.py")
    cwd = payload.get("cwd") or os.getcwd()
    project = str(snapshot.project_root(Path(cwd).resolve()))
    path_reason = path_module.decision_reason(command, cwd, project)
    if path_reason:
        reasons.append(
            "Recursive deletion was not safely attributable: " + path_reason
            + ". Use a literal narrow target and let normal approval review it."
        )
    else:
        tokens = path_module.tokenize(command)
        recursive = bool(tokens) and any(
            (index := path_module._direct_rm_index(segment)) is not None
            and path_module._recursive_rm_at(segment, index)
            for segment in path_module.split_subcommands(tokens)
        )
        if recursive and not _rm_rule_handles(command):
            reasons.append(
                "Recursive deletion must use a simple direct `rm -rf <literal>` "
                "form so Codex command rules can review the resolved target."
            )

    git_module = _load_module("_git_authority.py")
    decision, git_reason = git_module.authority_decision(
        command, payload.get("agent_id")
    )
    if decision == "deny" and git_reason:
        reasons.append(git_reason)
    elif decision == "ask" and git_reason and not _rule_handles(command, git_reason):
        reasons.append(
            git_reason
            + " Use the simple direct Git form so Codex command rules can review it."
        )

    for row in _run_module("_secret_commit.py", payload):
        specific = row.get("hookSpecificOutput") or {}
        if specific.get("permissionDecision") == "deny":
            reason = specific.get("permissionDecisionReason")
            if isinstance(reason, str):
                reasons.append(reason)

    notes.extend(_notes(_run_module("_bash_patterns.py", payload)))
    if reasons:
        _emit_deny("\n\n".join(dict.fromkeys(reasons))[:5000])
    elif notes:
        _emit_context("PreToolUse", "\n\n".join(dict.fromkeys(notes)))


def _stop(payload: dict) -> None:
    if payload.get("stop_hook_active"):
        return
    filenames = [
        "stop-gate-suppression-markers.py",
        "stop-gate-comment-discipline.py",
        "python-security-stop-gate.py",
    ]
    if payload.get("hook_event_name") == "Stop":
        filenames.extend(("fallow-quality-note.py", "length-quality-note.py"))
    rows: list[dict] = []
    failures: list[str] = []
    for filename in filenames:
        rows.extend(_checked_module(filename, payload, failures))
    reasons = []
    for row in rows:
        reason = row.get("reason") if row.get("decision") == "block" else None
        if isinstance(reason, str) and reason.strip():
            reasons.append(reason.strip())
    reasons.extend(_notes(rows))
    reasons.extend(failures)
    if reasons:
        unique_reasons = list(dict.fromkeys(reasons))[:MAX_SECTIONS]
        reason_text = "\n\n".join(unique_reasons)
        output = {
            "decision": "block",
            "reason": reason_text[:MAX_STOP_CHARS],
        }
        if failures:
            output["systemMessage"] = "\n\n".join(failures)
        print(json.dumps(output))


def _health(payload: dict) -> None:
    failures = []
    for filename in HEALTH_MODULES:
        try:
            _load_module(filename)
        except (Exception, SystemExit) as exc:
            failures.append(f"{filename}: {type(exc).__name__}")
    if failures:
        try:
            notice = _load_module("_notice_state.py")
            topic = "startup-health\0" + "\0".join(failures)
            if payload.get("session_id") and not notice.claim_once(
                topic, payload.get("session_id"), payload.get("agent_id")
            ):
                return
        except (Exception, SystemExit):
            # A broken notice helper must not hide the runtime failure it was
            # supposed to deduplicate.
            pass
        _emit_context(
            "SessionStart",
            "MAINFRAME hook checks are partially unavailable: "
            + "; ".join(failures)
            + ". Return this fact to the immediate caller before claiming "
            "hook-backed verification.",
            system_message=(
                "MAINFRAME hook checks are partially unavailable: "
                + "; ".join(failures)
            ),
        )


def _emit_context(
    event: str, text: str, *, system_message: str | None = None
) -> None:
    output = {
        "hookSpecificOutput": {
            "hookEventName": event,
            "additionalContext": text,
        }
    }
    if system_message:
        output["systemMessage"] = system_message
    print(json.dumps(output))


def _emit_deny(reason: str, *, system_message: str | None = None) -> None:
    output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }
    if system_message:
        output["systemMessage"] = system_message
    print(json.dumps(output))


def _failure(payload: dict, exc: Exception) -> None:
    event = str(payload.get("hook_event_name") or "unknown")
    text = (
        "MAINFRAME hook failure: the deterministic check for " + event
        + " is unavailable (" + type(exc).__name__ + "). Return this fact to "
        "the immediate caller before claiming the affected operation or task "
        "is verified."
    )
    if event != "PreToolUse" or payload.get("tool_name") != "Bash":
        notice = _failure_notice(payload, "dispatcher-" + event, exc)
        if notice is None:
            return
        text = notice
    if event == "PreToolUse" and payload.get("tool_name") == "Bash":
        _emit_deny(text, system_message=text)
    elif event in {"Stop", "SubagentStop"}:
        print(json.dumps({
            "decision": "block",
            "reason": text,
            "systemMessage": text,
        }))
    else:
        _emit_context(event, text, system_message=text)


def main() -> None:
    payload: dict = {}
    try:
        payload = _payload()
        event = payload.get("hook_event_name")
        if event == "SessionStart":
            _health(payload)
        elif event == "PreToolUse":
            if payload.get("tool_name") == "Bash":
                _command(payload)
            else:
                _capture(payload)
        elif event == "PostToolUse":
            _quality(payload)
        elif event in {"Stop", "SubagentStop"}:
            _stop(payload)
    except Exception as exc:
        _failure(payload, exc)


if __name__ == "__main__":
    main()
