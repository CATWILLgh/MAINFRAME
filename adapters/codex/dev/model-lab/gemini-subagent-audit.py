#!/usr/bin/env python3
"""Blind, retryable Gemini analysis of one sanitized Codex subagent transcript."""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time


MODEL = "gemini-3.7-flash-high"
EFFORT = "high"
SCHEMA = 1
MAX_ATTEMPTS = 5
MAX_SOURCE_CHARS = 800_000
MAX_MESSAGES = 160
TIMEOUT_SECONDS = 360
RETRY_SECONDS = (60, 300, 1800, 7200, 21600)
STALE_PROCESSING_SECONDS = 600

SECRET_PATTERNS = (
    re.compile(r"(?i)(authorization\s*:\s*(?:bearer|basic)\s+)[^\s\"']+"),
    re.compile(r"(?i)\b(api[_-]?key|access[_-]?token|secret|password)\s*[:=]\s*[^\s,;]+"),
    re.compile(r"-----BEGIN [^-]+PRIVATE KEY-----.*?-----END [^-]+PRIVATE KEY-----", re.S),
    re.compile(r"\b(?:sk|rk|pk|ghp|github_pat)_[A-Za-z0-9_-]{16,}\b"),
)


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _iso(value: datetime.datetime | None = None) -> str:
    return (value or _now()).isoformat(timespec="seconds")


def _atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def _redact(text: str) -> str:
    value = text.replace("\x00", "")
    for pattern in SECRET_PATTERNS:
        value = pattern.sub(lambda match: (match.group(1) if match.lastindex else "") + "[REDACTED]", value)
    return value


def _text_parts(content: object) -> list[str]:
    if isinstance(content, str):
        return [content]
    if not isinstance(content, list):
        return []
    parts = []
    for item in content:
        if not isinstance(item, dict):
            continue
        if item.get("type") in {"input_text", "output_text", "text"}:
            text = item.get("text")
            if isinstance(text, str):
                parts.append(text)
    return parts


def sanitized_transcript(path: Path) -> dict:
    """Extract task/result prose and tool names without tool arguments or results."""
    messages: list[dict] = []
    tool_calls = 0
    turns: set[str] = set()
    malformed = 0
    truncated = False
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                malformed += 1
                continue
            payload = row.get("payload") if isinstance(row, dict) else None
            if not isinstance(payload, dict):
                continue
            row_type = row.get("type")
            payload_type = payload.get("type")
            if row_type == "turn_context" and isinstance(payload.get("turn_id"), str):
                turns.add(payload["turn_id"])
                # Deliberately omit model and effort: Gemini must classify blind.
                continue
            if row_type == "event_msg" and payload_type == "task_started":
                if isinstance(payload.get("turn_id"), str):
                    turns.add(payload["turn_id"])
                continue
            if row_type == "response_item" and payload_type == "message":
                role = str(payload.get("role") or "unknown")
                if role not in {"user", "assistant"}:
                    continue
                text = "\n".join(_text_parts(payload.get("content"))).strip()
                if text:
                    messages.append({"role": role, "text": _redact(text)[:20_000]})
            elif row_type == "event_msg" and payload_type == "user_message":
                text = payload.get("message")
                if isinstance(text, str) and text.strip():
                    messages.append({"role": "user", "text": _redact(text.strip())[:20_000]})
            elif row_type == "response_item" and payload_type in {
                "function_call", "custom_tool_call", "local_shell_call", "mcp_tool_call"
            }:
                tool_calls += 1
                name = payload.get("name") or payload.get("tool_name") or payload_type
                messages.append({"role": "tool", "name": str(name)[:120]})
            elif row_type == "event_msg" and payload_type in {"task_complete", "task_failed"}:
                text = payload.get("last_agent_message") or payload.get("message")
                if isinstance(text, str) and text.strip():
                    messages.append({"role": "outcome", "text": _redact(text.strip())[:20_000]})

    deduplicated = []
    for message in messages:
        if deduplicated and message == deduplicated[-1]:
            continue
        deduplicated.append(message)
    messages = deduplicated

    if len(messages) > MAX_MESSAGES:
        messages = messages[:80] + messages[-80:]
        truncated = True
    result = {
        "format": "codex-transcript-derived-v1",
        "turns_observed": len(turns),
        "tool_calls_observed": tool_calls,
        "malformed_rows": malformed,
        "truncated": truncated,
        "messages": messages,
    }
    encoded = json.dumps(result, ensure_ascii=False, separators=(",", ":"))
    if len(encoded) > MAX_SOURCE_CHARS:
        bounded = messages[:40] + messages[-40:]
        for message in bounded:
            if isinstance(message.get("text"), str):
                message["text"] = message["text"][:8_000]
        result["messages"] = bounded
        result["truncated"] = True
        while (
            len(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
            > MAX_SOURCE_CHARS
            and len(result["messages"]) > 2
        ):
            del result["messages"][len(result["messages"]) // 2]
    return result


def _prompt(source: dict) -> str:
    return """You are analyzing one Codex subagent execution for MAINFRAME.

Use only SANITIZED_TRANSCRIPT. It intentionally omits the actual model,
reasoning effort, tool arguments, tool results, filesystem paths, and secrets.
Classify the task, apparent complexity, execution shape, and observed outcome.
Do not recommend a model or effort. Do not infer successful work from tool use
alone. Evidence must quote or closely point to observable sanitized content.
Return exactly the supplied JSON schema in concise English.

SANITIZED_TRANSCRIPT:
""" + json.dumps(source, ensure_ascii=False, separators=(",", ":"))


def _valid_result(value: object) -> bool:
    if not isinstance(value, dict) or set(value) != {
        "task", "complexity", "work_type", "outcome", "execution", "evidence", "limitations"
    }:
        return False
    if value.get("complexity") not in {"small", "medium", "large", "unknown"}:
        return False
    if value.get("work_type") not in {"exploration", "research", "implementation", "review", "testing", "other", "unknown"}:
        return False
    if value.get("outcome") not in {"completed", "partial", "blocked", "cancelled", "unknown"}:
        return False
    execution = value.get("execution")
    if not isinstance(execution, dict) or set(execution) != {"turns", "tool_calls", "repeated_actions", "assessment"}:
        return False
    if execution.get("assessment") not in {"efficient", "mixed", "wasteful", "unknown"}:
        return False
    if any(not isinstance(execution.get(key), int) or execution[key] < 0 for key in ("turns", "tool_calls", "repeated_actions")):
        return False
    return (
        isinstance(value.get("task"), str) and bool(value["task"].strip())
        and isinstance(value.get("evidence"), list) and bool(value["evidence"])
        and all(isinstance(item, str) and item.strip() for item in value["evidence"])
        and isinstance(value.get("limitations"), list)
        and all(isinstance(item, str) and item.strip() for item in value["limitations"])
    )


def _parse_wrapper(text: str) -> tuple[dict, dict]:
    wrapper = json.loads(text)
    if not isinstance(wrapper, dict):
        raise ValueError("wrapper must be an object")
    result = wrapper.get("structured_output")
    if isinstance(result, str):
        result = json.loads(result)
    return result, {key: wrapper[key] for key in ("conversation_id", "model", "usage") if key in wrapper}


def _normalized_usage(value: object) -> dict | None:
    if not isinstance(value, dict):
        return None
    try:
        normalized = {
            "input_tokens": int(value.get("input_tokens", 0)),
            "cached_input_tokens": int(value.get("cache_read_tokens", 0)),
            "cache_write_tokens": int(value.get("cache_write_tokens", 0)),
            "output_tokens": int(value.get("output_tokens", 0)),
            "reasoning_output_tokens": int(value.get("thinking_tokens", 0)),
            "total_tokens": int(value.get("total_tokens", 0)),
        }
    except (TypeError, ValueError):
        return None
    return normalized if not any(item < 0 for item in normalized.values()) else None


def _record_usage(root: Path, job: dict, usage: dict | None, elapsed_ms: int) -> None:
    if usage is None:
        return
    scripts = root / "adapters/codex/hooks/scripts"
    try:
        sys.path.insert(0, str(scripts))
        import _hooklib

        identity = f"{job.get('session_id', '')}:{job.get('agent_id', '')}:{usage}"
        _hooklib.log_event(
            "model_usage",
            {
                "sample_id": hashlib.sha256(
                    f"codex-subagent-audit:{identity}".encode()
                ).hexdigest(),
                "source": "model-lab",
                "request_count": 1,
                "duration_ms": max(0, elapsed_ms),
                **usage,
            },
            {
                "session_id": str(job.get("session_id") or ""),
                "agent_id": str(job.get("agent_id") or ""),
                "agent_type": str(job.get("agent_type") or ""),
                "model": os.environ.get("MAINFRAME_GEMINI_MODEL", MODEL),
                "_telemetry_origin": "model-lab",
            },
        )
    except Exception:
        pass


def _queue_failure(job_path: Path, job: dict, reason: str) -> str:
    attempts = int(job.get("attempts") or 0) + 1
    job.update({"attempts": attempts, "last_error": reason[:240], "last_attempt_at": _iso()})
    processing = job_path
    root = processing.parent.parent
    if attempts >= MAX_ATTEMPTS:
        job.update({"status": "blocked", "next_attempt_at": ""})
        destination = root / "blocked" / processing.name.replace(".processing", ".json")
        _atomic_json(destination, job)
        processing.unlink(missing_ok=True)
        return "blocked"
    job.update({
        "status": "queued",
        "next_attempt_at": _iso(_now() + datetime.timedelta(seconds=RETRY_SECONDS[attempts - 1])),
    })
    destination = root / "pending" / processing.name.replace(".processing", ".json")
    _atomic_json(destination, job)
    processing.unlink(missing_ok=True)
    return "retryable"


def process(job_path: Path, root: Path) -> tuple[str, str]:
    try:
        job = json.loads(job_path.read_text(encoding="utf-8"))
        if not isinstance(job, dict) or job.get("schema") != SCHEMA:
            raise ValueError("invalid queue record")
        transcript = Path(job["transcript_path"]).resolve(strict=True)
        transcript.relative_to(Path.home().resolve())
        source = sanitized_transcript(transcript)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        return _queue_failure(job_path, locals().get("job", {}), type(error).__name__), ""

    source_digest = hashlib.sha256(
        json.dumps(source, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    schema = root / "adapters/codex/dev/model-lab/schemas/subagent-audit.json"
    binary = os.environ.get("MAINFRAME_ANTIGRAVITY_BIN", "agy")
    command = [
        binary, "--print", _prompt(source), "--model",
        os.environ.get("MAINFRAME_GEMINI_MODEL", MODEL), "--effort", EFFORT,
        "--mode", "plan", "--sandbox", "--disable-slash-commands",
        "--json-schema", str(schema), "--output-format", "json", "--print-timeout", "5m",
    ]
    started = time.monotonic()
    try:
        with tempfile.TemporaryDirectory(prefix="mainframe-codex-subagent-audit-") as cwd:
            proc = subprocess.run(command, cwd=cwd, text=True, capture_output=True, timeout=TIMEOUT_SECONDS, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        return _queue_failure(job_path, job, type(error).__name__), ""
    if proc.returncode != 0:
        return _queue_failure(job_path, job, f"agy-exit-{proc.returncode}"), ""
    try:
        result, cli = _parse_wrapper(proc.stdout)
    except (ValueError, json.JSONDecodeError, TypeError):
        return _queue_failure(job_path, job, "invalid-wrapper"), ""
    _record_usage(
        root,
        job,
        _normalized_usage(cli.get("usage")),
        int((time.monotonic() - started) * 1000),
    )
    if not _valid_result(result):
        return _queue_failure(job_path, job, "invalid-result"), ""

    output = root / "workspace/runtime/codex/model-lab/gemini/subagent-audits"
    destination = output / f"subagent-{job['agent_id'][:48]}-{source_digest[:12]}.json"
    envelope = {
        "schema": SCHEMA,
        "adapter": "codex",
        "producer": "gemini-subagent-audit",
        "provider": "google-antigravity",
        "analysis_model": os.environ.get("MAINFRAME_GEMINI_MODEL", MODEL),
        "analysis_effort": EFFORT,
        "generated_at": _iso(),
        "source": {
            "session_id": job["session_id"], "agent_id": job["agent_id"],
            "agent_type": job.get("agent_type", "unknown"),
            "origin": job.get("origin", "runtime"),
            "sha256": source_digest, "transcript_format": source["format"],
            "truncated": source["truncated"], "malformed_rows": source["malformed_rows"],
        },
        "runtime": {
            "model": job.get("runtime_model", "unknown"),
            "effort": job.get("runtime_effort", "unavailable"),
            "effort_evidence": job.get("effort_evidence", "unavailable"),
        },
        "review_required": True,
        "analysis": result,
        "cli": cli,
    }
    _atomic_json(destination, envelope)
    completed = job_path.parent.parent / "completed" / job_path.name.replace(".processing", ".json")
    job.update({"status": "completed", "artifact": str(destination), "completed_at": _iso()})
    _atomic_json(completed, job)
    job_path.unlink(missing_ok=True)
    return "completed", str(destination)


def claim_next(queue_root: Path) -> Path | None:
    pending = queue_root / "pending"
    processing = queue_root / "processing"
    processing.mkdir(parents=True, mode=0o700, exist_ok=True)
    now = _now()
    for stale in processing.glob("*.processing"):
        try:
            age = now.timestamp() - stale.stat().st_mtime
            if age < STALE_PROCESSING_SECONDS:
                continue
            recovered = pending / (stale.stem + ".json")
            if not recovered.exists():
                os.replace(stale, recovered)
        except OSError:
            continue
    try:
        candidates = sorted(pending.glob("*.json"), key=lambda path: path.stat().st_mtime)
    except OSError:
        return None
    for source in candidates:
        try:
            value = json.loads(source.read_text(encoding="utf-8"))
            next_at = datetime.datetime.fromisoformat(str(value.get("next_attempt_at") or "").replace("Z", "+00:00"))
            if next_at.tzinfo is None:
                next_at = next_at.replace(tzinfo=datetime.timezone.utc)
            if next_at > now:
                continue
            target = processing / (source.stem + ".processing")
            os.replace(source, target)
            return target
        except (OSError, ValueError, json.JSONDecodeError):
            continue
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue-root", required=True)
    parser.add_argument("--project-root", required=True)
    args = parser.parse_args()
    job = claim_next(Path(args.queue_root).expanduser().resolve())
    if job is None:
        print(json.dumps({"status": "idle"}))
        return 0
    status, artifact = process(job, Path(args.project_root).resolve())
    print(json.dumps({"status": status, "artifact": artifact}))
    return 0 if status in {"completed", "retryable", "blocked"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
