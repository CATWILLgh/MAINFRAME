"""Persist bounded Codex subagent-analysis jobs outside the hook hot path."""

from __future__ import annotations

import datetime
import hashlib
import json
import os
from pathlib import Path
import tempfile


SCHEMA = 1
MAX_PENDING = 256


def _codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex").resolve()


def _telemetry_enabled() -> bool:
    return (
        _codex_home() / "mainframe" / "codex" / "telemetry" / "enabled"
    ).is_file()


def queue_root() -> Path:
    override = os.environ.get("MAINFRAME_CODEX_SUBAGENT_QUEUE")
    if override:
        return Path(override).expanduser().resolve()
    return (
        _codex_home()
        / "mainframe"
        / "codex"
        / "model-lab"
        / "gemini"
        / "subagent-audits"
    )


def _safe_transcript(value: object) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    candidate = Path(value).expanduser()
    try:
        if candidate.is_symlink() or not candidate.is_file():
            return None
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(Path.home().resolve())
    except (OSError, RuntimeError, ValueError):
        return None
    return resolved


def enqueue(payload: dict) -> str:
    """Create one idempotent private job; never raise into the hook."""
    try:
        if not _telemetry_enabled():
            return "disabled"
        agent_id = str(payload.get("agent_id") or "").strip()
        session_id = str(payload.get("session_id") or "").strip()
        transcript = _safe_transcript(payload.get("agent_transcript_path"))
        if not agent_id or not session_id or transcript is None:
            return "ignored"

        root = queue_root()
        pending = root / "pending"
        pending.mkdir(parents=True, mode=0o700, exist_ok=True)
        if sum(1 for item in pending.iterdir() if item.suffix == ".json") >= MAX_PENDING:
            return "full"

        identity = hashlib.sha256(
            f"{session_id}\0{agent_id}\0{transcript}".encode("utf-8", "replace")
        ).hexdigest()
        target = pending / f"subagent-{identity[:24]}.json"
        if target.exists() or (root / "completed" / target.name).exists():
            return "deduplicated"
        now = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
        record = {
            "schema": SCHEMA,
            "origin": "runtime",
            "status": "queued",
            "attempts": 0,
            "next_attempt_at": now,
            "created_at": now,
            "session_id": session_id[:128],
            "agent_id": agent_id[:128],
            "agent_type": str(payload.get("agent_type") or "unknown")[:128],
            "runtime_model": str(payload.get("model") or "unknown")[:128],
            "runtime_effort": "unavailable",
            "effort_evidence": "Codex hook input has no documented effort field",
            "transcript_path": str(transcript),
        }
        fd, temporary = tempfile.mkstemp(prefix="job-", suffix=".tmp", dir=pending)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(record, handle, ensure_ascii=False, separators=(",", ":"))
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.link(temporary, target)
            except FileExistsError:
                return "deduplicated"
            finally:
                try:
                    os.unlink(temporary)
                except FileNotFoundError:
                    pass
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
        return "queued"
    except Exception:
        return "error"
