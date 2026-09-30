#!/usr/bin/env python3
"""Thin Cline file-hook transport for unchanged MAINFRAME detectors.

Cline runs an executable file named after the hook event with one JSON payload
on standard input and reads one JSON object from standard output. This transport
keeps every canonical detector unchanged and owns only that native contract:

* exit silently when nothing is found, so a clean call never draws attention;
* fail open on missing input, launch failure, timeout, or detector exception,
  because an unavailable check is not a dangerous finding;
* hard-block with ``cancel`` only for a positively recognized canonical finding;
* deliver every advisory through ``contextModification`` and never block for one.

``cancel`` in Cline stops the whole run with the reason recorded, so it is used
only where the canonical contract requires a hard block.
"""

from __future__ import annotations

from contextlib import closing, contextmanager
import difflib
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import signal
import sqlite3
import stat
import subprocess
import sys
import time
from typing import BinaryIO


HOOKS = Path(__file__).resolve().parent
HOOK_NAMES = frozenset({
    "mainframe-secret-access", "mainframe-rg-short-replace",
    "mainframe-destructive-operations", "mainframe-commit-secrets",
    "mainframe-code-quality", "mainframe-fallow-quality",
})
SHELL_TOOLS = frozenset({"run_commands"})
EDIT_TOOLS = frozenset({"apply_patch", "editor"})
FALLOW_SUFFIXES = frozenset({".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".mts", ".cts", ".vue", ".svelte"})
MAX_INPUT_BYTES = 1_048_576
MAX_MESSAGE_CHARS = 6_000
MAX_COMMANDS = 64
MAX_EDIT_PATHS = 24
MAX_ID_CHARS = 512
MAX_EVENTS = 4_096
EVENT_TTL = 7 * 24 * 60 * 60
SNAPSHOT_TTL = 3600
MAX_SNAPSHOT_BYTES = 2_000_000
COMMIT_BUDGET_SECONDS = 3.0
FALLOW_BUDGET_SECONDS = 7
PATCH_PATH = re.compile(r"^\*\*\* (?:(?:Add|Update|Delete) File:|Move to:) (.+)$")


def _enabled(name: str) -> bool:
    return name in HOOK_NAMES and not (HOOKS / (".disabled-" + name)).exists()


def _read_payload(stream: BinaryIO) -> dict | None:
    raw = stream.read(MAX_INPUT_BYTES + 1)
    if len(raw) > MAX_INPUT_BYTES:
        return None
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _state_root(raw: str) -> Path | None:
    try:
        candidate = Path(raw)
        if not candidate.is_absolute() or candidate.is_symlink():
            return None
        candidate.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(candidate, 0o700)
        meta = candidate.stat()
        if not stat.S_ISDIR(meta.st_mode) or meta.st_uid != os.getuid() or meta.st_mode & 0o077:
            return None
        return candidate
    except OSError:
        return None


def _database(state: Path) -> Path | None:
    path = state / "events.sqlite3"
    try:
        if path.is_symlink():
            return None
        flags = os.O_CREAT | os.O_WRONLY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(path, flags, 0o600)
        try:
            meta = os.fstat(descriptor)
            if not stat.S_ISREG(meta.st_mode) or meta.st_uid != os.getuid() or meta.st_mode & 0o077:
                return None
        finally:
            os.close(descriptor)
        return path
    except OSError:
        return None


def _connection(state: Path):
    path = _database(state)
    if path is None:
        return None
    con = sqlite3.connect(path, timeout=0.1)
    con.execute("CREATE TABLE IF NOT EXISTS events (id TEXT PRIMARY KEY, expires REAL)")
    con.execute("CREATE TABLE IF NOT EXISTS snapshots "
                "(id TEXT PRIMARY KEY, path TEXT, before BLOB, existed INTEGER, expires REAL)")
    con.execute("CREATE TABLE IF NOT EXISTS snapshot_files "
                "(operation TEXT, path_key TEXT, path TEXT, before BLOB, existed INTEGER, "
                "expires REAL, PRIMARY KEY(operation,path_key))")
    return con


def claim_event(state: Path, identity: str) -> bool:
    """Admit one delivery for a bounded identity, or report a duplicate."""
    if not isinstance(identity, str) or not identity:
        return False
    con = _connection(state)
    if con is None:
        return False
    key = hashlib.sha256(("cline\0" + identity).encode()).hexdigest()
    with closing(con), con:
        con.execute("BEGIN IMMEDIATE")
        now = time.time()
        con.execute("DELETE FROM events WHERE expires <= ?", (now,))
        con.execute("DELETE FROM snapshots WHERE expires <= ?", (now,))
        con.execute("DELETE FROM snapshot_files WHERE expires <= ?", (now,))
        if con.execute("SELECT 1 FROM events WHERE id=?", (key,)).fetchone():
            return False
        if con.execute("SELECT count(*) FROM events").fetchone()[0] >= MAX_EVENTS:
            return False
        con.execute("INSERT INTO events VALUES (?,?)", (key, now + EVENT_TTL))
    return True


def _load_detector(name: str):
    if not _enabled(name):
        return None
    path = HOOKS / "detectors" / (name + ".py")
    if not path.is_file() or path.is_symlink():
        return None
    spec = importlib.util.spec_from_file_location(
        "mainframe_cline_" + name.replace("-", "_"), path
    )
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@contextmanager
def _budget(seconds: float):
    """Bound one detector call; an expired budget is unavailable protection."""
    def _expire(signum, frame):
        raise TimeoutError("detector budget exhausted")

    try:
        previous = signal.signal(signal.SIGALRM, _expire)
        signal.setitimer(signal.ITIMER_REAL, seconds)
    except (ValueError, AttributeError, OSError):
        yield
        return
    try:
        yield
    finally:
        try:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, previous)
        except (ValueError, OSError):
            pass


def _decoded(value):
    """Decode a stringified structured value without inventing one."""
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (ValueError, TypeError):
            return None
    return value if isinstance(value, (dict, list)) else None


def _workspace(data: dict) -> Path | None:
    info = data.get("workspaceInfo")
    candidates = []
    if isinstance(info, dict) and isinstance(info.get("rootPath"), str):
        candidates.append(info["rootPath"])
    roots = data.get("workspaceRoots")
    if isinstance(roots, list):
        candidates.extend(root for root in roots if isinstance(root, str))
    for candidate in candidates:
        if not candidate or len(candidate) > 4096:
            continue
        try:
            path = Path(candidate).resolve(strict=True)
        except (OSError, RuntimeError):
            continue
        if path.is_dir():
            return path
    return None


def _project_root(cwd: Path) -> Path:
    try:
        result = subprocess.run(
            ["git", "-C", str(cwd), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=2, check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            root = Path(result.stdout.strip()).resolve(strict=True)
            if root.is_dir():
                return root
    except (OSError, RuntimeError, subprocess.SubprocessError):
        pass
    return cwd


def _tool(data: dict) -> tuple[str, dict] | None:
    for key in ("tool_call", "tool_result"):
        record = data.get(key)
        if isinstance(record, dict) and isinstance(record.get("name"), str):
            inputs = record.get("input")
            return record["name"], inputs if isinstance(inputs, dict) else {}
    for key in ("preToolUse", "postToolUse"):
        record = data.get(key)
        if not isinstance(record, dict) or not isinstance(record.get("toolName"), str):
            continue
        parameters = record.get("parameters")
        if isinstance(parameters, dict):
            decoded = {name: _decoded(value) if isinstance(value, str) else value
                       for name, value in parameters.items()}
            return record["toolName"], decoded
        return record["toolName"], {}
    return None


def _commands(name: str, inputs: dict) -> list[str]:
    if name not in SHELL_TOOLS:
        return []
    raw = inputs.get("commands")
    raw = _decoded(raw) if isinstance(raw, str) else raw
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, list):
        return []
    bounded = []
    for command in raw[:MAX_COMMANDS]:
        if isinstance(command, str) and command:
            bounded.append(command)
    return bounded


def _edit_paths(name: str, inputs: dict, cwd: Path) -> list[str]:
    if name not in EDIT_TOOLS:
        return []
    if name == "apply_patch":
        patch = inputs.get("input")
        if not isinstance(patch, str):
            return []
        values = [match.group(1) for line in patch.splitlines()
                  if (match := PATCH_PATH.match(line))]
    else:
        values = [inputs[key] for key in ("path", "file_path", "filePath") if key in inputs]
        values = [value for value in values if isinstance(value, str) and value]
        if values and any(value != values[0] for value in values):
            return []
        values = values[:1]
    values = list(dict.fromkeys(values))
    if not values or len(values) > MAX_EDIT_PATHS:
        return []
    root = _project_root(cwd)
    result = []
    try:
        for value in values:
            if not value or "\0" in value:
                return []
            path = Path(value)
            path = (path if path.is_absolute() else cwd / path).resolve(strict=False)
            path.relative_to(root)
            result.append(str(path))
    except (OSError, RuntimeError, ValueError):
        return []
    return result


def _identity(data: dict) -> tuple[str, str] | None:
    scope = data.get("taskId")
    record = data.get("tool_call") or data.get("tool_result")
    operation = record.get("id") if isinstance(record, dict) else None
    if not all(isinstance(value, str) and 0 < len(value) <= MAX_ID_CHARS
               for value in (scope, operation)):
        return None
    return scope, operation


def _bounded(text: str) -> str:
    stripped = text.strip()
    return stripped if len(stripped) <= MAX_MESSAGE_CHARS else stripped[:MAX_MESSAGE_CHARS] + " …"




def _output(*, contexts: list[str], denials: list[str]) -> dict | None:
    """Encode one native result; silence stays silence."""
    denials = list(dict.fromkeys(item for item in denials if item))
    if denials:
        return {"cancel": True, "errorMessage": _bounded("\n\n".join(denials))}
    contexts = list(dict.fromkeys(item for item in contexts if item))
    if contexts:
        return {"contextModification": _bounded("\n\n".join(contexts))}
    return None


def _shell_findings(commands: list[str], cwd: Path, project_root: Path,
                    home_root: str, contexts: list[str], denials: list[str]) -> None:
    secret = _load_detector("mainframe-secret-access")
    destructive = _load_detector("mainframe-destructive-operations")
    commit = _load_detector("mainframe-commit-secrets")
    short_replace = _load_detector("mainframe-rg-short-replace")
    for command in commands:
        try:
            if secret is not None:
                reason = secret.decision_reason(command)
                if reason:
                    denials.append(reason)
            if destructive is not None:
                reason = destructive.decision_reason(
                    command, str(cwd), str(project_root), home_root
                )
                if reason:
                    denials.append(reason)
            if commit is not None:
                with _budget(COMMIT_BUDGET_SECONDS):
                    result = commit.check_command(command, str(cwd))
                if result.block_reason:
                    denials.append(result.block_reason)
                elif result.advisory:
                    contexts.append(result.advisory)
            if short_replace is not None:
                note = short_replace.advisory_message(command)
                if note:
                    contexts.append(note)
        except Exception:
            continue


def _save_fallow_snapshot(identity: tuple[str, str], paths: list[str], state: Path) -> None:
    """Keep bounded per-file before-images for one TS/JS edit operation."""
    if not _enabled("mainframe-fallow-quality") or not paths:
        return
    snapshots = []
    total = 0
    for raw_path in paths:
        path = Path(raw_path)
        if path.suffix.lower() not in FALLOW_SUFFIXES:
            continue
        existed = path.is_file() and not path.is_symlink()
        try:
            before = path.read_bytes() if existed else b""
        except OSError:
            continue
        total += len(before)
        if total > MAX_SNAPSHOT_BYTES:
            return
        snapshots.append((path, before, existed))
    if not snapshots:
        return
    con = _connection(state)
    if con is None:
        return
    key = hashlib.sha256((identity[0] + "\0" + identity[1]).encode()).hexdigest()
    with closing(con), con:
        con.execute("DELETE FROM snapshot_files WHERE operation=?", (key,))
        expires = time.time() + SNAPSHOT_TTL
        con.executemany(
            "INSERT INTO snapshot_files VALUES (?,?,?,?,?,?)",
            ((key, hashlib.sha256(str(path).encode()).hexdigest(), str(path), before,
              int(existed), expires) for path, before, existed in snapshots),
        )


def _take_fallow_snapshots(identity: tuple[str, str], state: Path):
    con = _connection(state)
    if con is None:
        return None
    key = hashlib.sha256((identity[0] + "\0" + identity[1]).encode()).hexdigest()
    with closing(con), con:
        rows = con.execute(
            "SELECT path,before,existed FROM snapshot_files WHERE operation=? ORDER BY path",
            (key,),
        ).fetchall()
        con.execute("DELETE FROM snapshot_files WHERE operation=?", (key,))
    if not rows:
        return None
    snapshots = []
    total = 0
    for row in rows:
        path = Path(row[0])
        try:
            if path.is_symlink():
                return None
            after = path.read_bytes() if path.is_file() else b""
        except OSError:
            return None
        total += len(after)
        if total > MAX_SNAPSHOT_BYTES:
            return None
        snapshots.append((path, bytes(row[1]), after, bool(row[2])))
    return snapshots


def _fallow_post(identity: tuple[str, str], workspace: Path, state: Path) -> str | None:
    detector = _load_detector("mainframe-fallow-quality")
    snapshots = _take_fallow_snapshots(identity, state)
    if detector is None or snapshots is None:
        return None
    paths = []
    wholly_owned = []
    diffs = []
    try:
        root = _project_root(workspace)
        for path, before, after, existed in snapshots:
            relative = path.relative_to(root).as_posix()
            before_text = before.decode("utf-8", "replace")
            after_text = after.decode("utf-8", "replace")
            if before_text == after_text:
                continue
            paths.append(str(path))
            if not existed:
                wholly_owned.append(str(path))
            diffs.append("".join(difflib.unified_diff(
                before_text.splitlines(keepends=True), after_text.splitlines(keepends=True),
                fromfile="a/" + relative, tofile="b/" + relative)))
    except (OSError, RuntimeError, ValueError):
        return None
    if not diffs:
        return None
    diff = "".join(diffs)
    try:
        result = detector.analyze(str(root), paths, diff,
                                  wholly_owned_paths=wholly_owned,
                                  timeout_seconds=FALLOW_BUDGET_SECONDS)
    except Exception:
        return None
    message = result.advisory or result.unavailable
    if not message:
        return None
    kind = "unavailable" if result.unavailable else hashlib.sha256(diff.encode()).hexdigest()
    return message if claim_event(state, identity[0] + "\0fallow\0" + identity[1] + "\0" + kind) else None


def _quality_capture(scope: str, root: str, operation: str, paths: list[str],
                     state: Path) -> str | None:
    detector = _load_detector("mainframe-code-quality")
    if detector is None:
        return None
    try:
        result = detector.capture_before(
            scope, root, operation, paths,
            state_namespace="mainframe-cline", state_root=state,
        )
    except Exception:
        return None
    return result.advisory


def _quality_record(scope: str, root: str, operation: str, succeeded: bool,
                    state: Path) -> str | None:
    detector = _load_detector("mainframe-code-quality")
    if detector is None:
        return None
    try:
        result = detector.record_after(
            scope, root, operation, succeeded=succeeded,
            state_namespace="mainframe-cline", state_root=state,
        )
    except Exception:
        return None
    return result.advisory


def pre_tool(data: dict, state: Path) -> dict | None:
    workspace, tool = _workspace(data), _tool(data)
    if workspace is None or tool is None:
        return None
    name, inputs = tool
    contexts: list[str] = []
    denials: list[str] = []
    if name in SHELL_TOOLS:
        commands = _commands(name, inputs)
        if commands:
            _shell_findings(commands, workspace, _project_root(workspace),
                            str(Path.home()), contexts, denials)
    elif name in EDIT_TOOLS:
        identity = _identity(data)
        paths = _edit_paths(name, inputs, workspace)
        if identity and paths:
            _save_fallow_snapshot(identity, paths, state)
            note = _quality_capture(identity[0], str(_project_root(workspace)),
                                    identity[1], paths, state)
            if note:
                contexts.append(note)
    return _output(contexts=contexts, denials=denials)


def post_tool(data: dict, state: Path) -> dict | None:
    workspace, tool = _workspace(data), _tool(data)
    identity = _identity(data)
    if workspace is None or tool is None or identity is None:
        return None
    name, inputs = tool
    if name not in EDIT_TOOLS or not _edit_paths(name, inputs, workspace):
        return None
    record = data.get("postToolUse")
    succeeded = True
    if isinstance(record, dict) and isinstance(record.get("success"), bool):
        succeeded = record["success"]
    if not claim_event(state, identity[0] + "\0quality-post\0" + identity[1]):
        return None
    notes = [note for note in (
        _quality_record(identity[0], str(_project_root(workspace)), identity[1],
                        succeeded, state),
        _fallow_post(identity, workspace, state),
    ) if note]
    if not notes:
        return None
    return _output(contexts=notes, denials=[])


def dispatch(event: str, data: dict, state: Path) -> dict | None:
    if event == "tool_call":
        return pre_tool(data, state)
    if event == "tool_result":
        return post_tool(data, state)
    return None


def main() -> None:
    if len(sys.argv) != 3:
        return
    try:
        sys.dont_write_bytecode = True
        state = _state_root(sys.argv[2])
        data = _read_payload(sys.stdin.buffer)
        if state is None or data is None:
            return
        result = dispatch(sys.argv[1], data, state)
        if result is not None:
            print(json.dumps(result, ensure_ascii=True, separators=(",", ":")))
    except Exception:
        return


if __name__ == "__main__":
    main()
