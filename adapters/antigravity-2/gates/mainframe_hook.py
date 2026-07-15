#!/usr/bin/env python3
"""Fail-open bridge from Antigravity Desktop 2.x hooks to MAINFRAME gates."""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Callable

from mainframe_runtime import (
    DETECTOR_TIMEOUT_SECONDS,
    MEMORY_LOADER_TIMEOUT_SECONDS,
    POST_DETECTORS,
    PRE_DETECTORS,
    STOP_DETECTORS,
    event_deadline,
    remaining_timeout,
    run_detector_group,
    run_json_command,
)
from mainframe_state import (
    MAX_STATE_FILES,
    atomic_json as _atomic_json,
    prune_state_directory,
    read_json as _read_json,
)


MAX_INPUT_BYTES = 1_048_576
MAX_MEMORY_INJECTION_BYTES = 30_000
MAX_STOP_REASON_BYTES = 30_000
MAX_QUEUED_NOTES = 12
MEMORY_SENTINEL = "<MAINFRAME_PROJECT_MEMORY>"
MEMORY_SENTINEL_END = "</MAINFRAME_PROJECT_MEMORY>"
MEMORY_REMINDER = (
    "Memory check (skip if nothing applies): if a durable, reusable fact "
    "surfaced, save it to MAINFRAME project memory now and run its size check. "
    "Keep MEMORY.md a concise index, move detail to topic files, deduplicate, "
    "and supersede stale facts. Never store credentials, current plans, tasks, "
    "or temporary progress. Nothing to save is a fine answer."
)

TOOL_NAMES = {
    "run_command": "Bash",
    "write_to_file": "Write",
    "replace_file_content": "Edit",
    "multi_replace_file_content": "MultiEdit",
}
DetectorRunner = Callable[[str, dict, float], dict | None]
MemoryLoader = Callable[[dict, float], str]


def _hash(*parts: object) -> str:
    value = "\0".join(str(part) for part in parts)
    return hashlib.sha256(value.encode("utf-8", "replace")).hexdigest()[:24]


def _desktop_transcript(payload: dict) -> bool:
    value = payload.get("transcriptPath")
    if not isinstance(value, str):
        return False
    normalized = value.replace("\\", "/")
    return (
        "/.gemini/antigravity/" in normalized
        and "/.gemini/antigravity-cli/" not in normalized
    )


def _workspace_paths(payload: dict) -> list[str]:
    paths = payload.get("workspacePaths")
    if not isinstance(paths, list):
        return []
    return sorted({path for path in paths if isinstance(path, str) and path})


def _combined_stop_reason(blockers: list[tuple[str, object]]) -> str:
    normalized = []
    for name, raw_reason in sorted(blockers):
        reason = raw_reason.strip() if isinstance(raw_reason, str) else ""
        normalized.append((name, reason or "No reason provided."))
    names = ", ".join(name for name, _reason in normalized)
    details = "\n".join(f"[{name}] {reason}" for name, reason in normalized)
    prefix = f"Blocking detectors: {names}\n"
    available = MAX_STOP_REASON_BYTES - len(prefix.encode("utf-8"))
    bounded = details.encode("utf-8")[:max(0, available)].decode("utf-8", "ignore")
    return prefix + bounded


def _value(args: dict, official: str, fallback: str) -> object:
    return args.get(official, args.get(fallback))


def _translate_tool_input(name: str, args: dict) -> dict:
    if name == "run_command":
        return {
            "command": _value(args, "CommandLine", "command") or "",
            "cwd": _value(args, "Cwd", "cwd") or "",
        }
    target = _value(args, "TargetFile", "file_path") or ""
    if name == "write_to_file":
        return {
            "file_path": target,
            "content": _value(args, "CodeContent", "content") or "",
        }
    if name == "replace_file_content":
        return {
            "file_path": target,
            "old_string": _value(args, "TargetContent", "old_string") or "",
            "new_string": _value(args, "ReplacementContent", "new_string") or "",
        }
    if name == "multi_replace_file_content":
        chunks = _value(args, "ReplacementChunks", "edits")
        edits = []
        if isinstance(chunks, list):
            for chunk in chunks:
                if isinstance(chunk, dict):
                    edits.append({
                        "old_string": _value(chunk, "TargetContent", "old_string") or "",
                        "new_string": _value(chunk, "ReplacementContent", "new_string") or "",
                    })
        return {"file_path": target, "edits": edits}
    return args


class Bridge:
    def __init__(
        self,
        plugin_root: Path,
        state_dir: Path,
        detector_runner: DetectorRunner | None = None,
        memory_loader: MemoryLoader | None = None,
    ) -> None:
        self.plugin_root = plugin_root
        self.state_dir = state_dir
        self.detector_runner = detector_runner
        self.memory_loader = memory_loader or self._load_memory

    def handle(self, event: str, payload: dict) -> dict:
        try:
            if not _desktop_transcript(payload):
                return {}
            handlers = {
                "PreToolUse": self._pre_tool,
                "PostToolUse": self._post_tool,
                "PreInvocation": self._pre_invocation,
                "PostInvocation": self._post_invocation,
                "Stop": self._stop,
            }
            handler = handlers.get(event)
            return handler(payload, event_deadline(event)) if handler else {}
        except Exception:
            return {}

    def _neutral_payload(self, payload: dict, tool_call: dict) -> dict:
        name = str(tool_call.get("name", ""))
        tool = TOOL_NAMES.get(name, name)
        args = tool_call.get("args")
        args = args if isinstance(args, dict) else {}
        roots = _workspace_paths(payload)
        project = roots[0] if roots else ""
        translated = _translate_tool_input(name, args)
        cwd = translated.get("cwd") if name == "run_command" else None
        return {
            "hook_event_name": "PreToolUse",
            "tool_name": tool,
            "tool_input": translated,
            "cwd": cwd or project,
            "project_dir": project,
            "transcript_path": payload.get("transcriptPath") or "",
        }

    def _cache_path(self, payload: dict) -> Path:
        key = _hash(payload.get("conversationId"), payload.get("stepIdx"))
        return self.state_dir / "tool-cache" / f"{key}.json"

    def _run_detectors(
        self, names: tuple[str, ...], payload: dict, deadline: float
    ) -> list[dict | None]:
        if self.detector_runner is None:
            return run_detector_group(self.plugin_root, names, payload, deadline)
        results = []
        for name in names:
            timeout = remaining_timeout(deadline, DETECTOR_TIMEOUT_SECONDS[name])
            if timeout <= 0:
                results.append(None)
                continue
            try:
                results.append(self.detector_runner(name, payload, timeout))
            except Exception:
                results.append(None)
        return results

    def _pre_tool(self, payload: dict, deadline: float) -> dict:
        call = payload.get("toolCall")
        if not isinstance(call, dict):
            return {}
        neutral = self._neutral_payload(payload, call)
        _atomic_json(self._cache_path(payload), neutral)
        verdicts = [result for result in self._run_detectors(
            PRE_DETECTORS, neutral, deadline
        ) if result]
        for result in verdicts:
            try:
                self._queue_result(payload, result)
            except OSError:
                pass
        return self._pre_verdict(verdicts)

    @staticmethod
    def _pre_verdict(results: list[dict]) -> dict:
        priority = {"allow": 0, "ask": 1, "deny": 2}
        selected: tuple[int, str, str] | None = None
        for result in results:
            output = result.get("hookSpecificOutput") or {}
            decision = output.get("permissionDecision")
            if decision not in priority:
                continue
            reason = str(output.get("permissionDecisionReason") or "MAINFRAME gate")
            candidate = (priority[decision], decision, reason)
            if selected is None or candidate[0] > selected[0]:
                selected = candidate
        return {"decision": selected[1], "reason": selected[2]} if selected else {}

    def _post_tool(self, payload: dict, deadline: float) -> dict:
        cache = self._cache_path(payload)
        prune_state_directory(cache.parent)
        neutral = _read_json(cache, {})
        try:
            cache.unlink()
        except OSError:
            pass
        if not isinstance(neutral, dict) or not neutral:
            return {}
        neutral["hook_event_name"] = "PostToolUse"
        neutral["tool_error"] = payload.get("error")
        for result in self._run_detectors(POST_DETECTORS, neutral, deadline):
            if result:
                try:
                    self._queue_result(payload, result)
                except OSError:
                    pass
        return {}

    def _queue_path(self, payload: dict) -> Path:
        return self.state_dir / "notes" / f"{_hash(payload.get('conversationId'))}.json"

    def _queue_result(self, payload: dict, result: dict) -> None:
        output = result.get("hookSpecificOutput") or {}
        notes = [output.get("additionalContext"), result.get("systemMessage")]
        additions = [str(note) for note in notes if note]
        if not additions:
            return
        path = self._queue_path(payload)
        existing = _read_json(path, [])
        queue = existing if isinstance(existing, list) else []
        for note in additions:
            if note not in queue:
                queue.append(note)
        _atomic_json(path, queue[-MAX_QUEUED_NOTES:])

    def _pre_invocation(self, payload: dict, deadline: float) -> dict:
        timeout = remaining_timeout(deadline, MEMORY_LOADER_TIMEOUT_SECONDS)
        if timeout <= 0:
            return {}
        try:
            memory = self.memory_loader(payload, timeout)
        except Exception:
            return {}
        if not memory:
            return {}
        memory = memory.replace(MEMORY_SENTINEL, "[memory delimiter removed]")
        memory = memory.replace(MEMORY_SENTINEL_END, "[memory delimiter removed]")
        prefix = f"{MEMORY_SENTINEL}\n"
        suffix = f"\n{MEMORY_SENTINEL_END}"
        budget = MAX_MEMORY_INJECTION_BYTES - len((prefix + suffix).encode())
        bounded = memory.encode()[:budget].decode("utf-8", "ignore")
        return {"injectSteps": [{"ephemeralMessage": prefix + bounded + suffix}]}

    def _post_invocation(self, payload: dict, _deadline: float) -> dict:
        path = self._queue_path(payload)
        prune_state_directory(path.parent)
        notes = _read_json(path, [])
        try:
            path.unlink()
        except OSError:
            pass
        if not isinstance(notes, list) or not notes:
            return {}
        return {"injectSteps": [{"ephemeralMessage": "\n\n".join(notes)}]}

    def _stop(self, payload: dict, deadline: float) -> dict:
        roots = _workspace_paths(payload)
        project = roots[0] if roots else ""
        neutral = {
            "hook_event_name": "Stop",
            "cwd": project,
            "project_dir": project,
            "transcript_path": payload.get("transcriptPath") or "",
            "transcript_bytes": payload.get("transcriptBytes"),
            "stop_hook_active": False,
        }
        blockers = []
        results = self._run_detectors(STOP_DETECTORS, neutral, deadline)
        for name, result in zip(STOP_DETECTORS, results, strict=True):
            if isinstance(result, dict) and result.get("decision") == "block":
                blockers.append((name, result.get("reason")))
        if blockers:
            if self._stop_seen(payload):
                return {}
            return {"decision": "continue", "reason": _combined_stop_reason(blockers)}
        if not payload.get("fullyIdle", False):
            return {}
        memory_payload = {
            **neutral,
            "memory_backend": "antigravity-2",
            "memory_note": MEMORY_REMINDER,
        }
        result = self._run_detectors(
            ("memory-reminder.py",), memory_payload, deadline
        )[0]
        output = result.get("hookSpecificOutput") if result else None
        note = output.get("additionalContext") if isinstance(output, dict) else None
        if not note or self._stop_seen(payload):
            return {}
        return {"decision": "continue", "reason": str(note)}

    def _stop_seen(self, payload: dict) -> bool:
        path = self.state_dir / "stop-loop" / (
            f"{_hash(payload.get('conversationId'), payload.get('executionNum'))}.stamp"
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        prune_state_directory(path.parent, max_files=MAX_STATE_FILES - 1)
        try:
            descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            return True
        with os.fdopen(descriptor, "w") as stream:
            stream.write("1")
        return False

    def _load_memory(self, payload: dict, timeout: float) -> str:
        store = self.plugin_root / "memory" / "store.py"
        if not store.is_file():
            return ""
        workspaces = _workspace_paths(payload)
        command = [
            sys.executable,
            str(store),
            "load",
            "--runtime",
            "antigravity-2",
            "--store-root",
            str(Path.home() / ".gemini/antigravity/mainframe-memory"),
        ]
        for workspace in workspaces:
            if isinstance(workspace, str) and workspace:
                command.extend(("--workspace", workspace))
        data = run_json_command(command, time.monotonic() + timeout, timeout)
        prompt = data.get("prompt") if data else None
        return str(prompt) if prompt else ""


def process_input(raw: bytes, bridge: Bridge, event: str) -> bytes:
    if len(raw) > MAX_INPUT_BYTES:
        return b"{}\n"
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return b"{}\n"
    if not isinstance(payload, dict):
        return b"{}\n"
    return (json.dumps(bridge.handle(event, payload), separators=(",", ":")) + "\n").encode()


def main() -> int:
    raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
    plugin_root = Path(__file__).resolve().parent.parent
    state = Path(os.environ.get(
        "ANTIGRAVITY_MAINFRAME_STATE_DIR",
        str(Path.home() / ".gemini/antigravity/mainframe-hook-state"),
    )).expanduser()
    event = sys.argv[1] if len(sys.argv) == 2 and sys.argv[1] in {
        "PreToolUse", "PostToolUse", "PreInvocation", "PostInvocation", "Stop"
    } else ""
    sys.stdout.buffer.write(process_input(raw, Bridge(plugin_root, state), event))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
