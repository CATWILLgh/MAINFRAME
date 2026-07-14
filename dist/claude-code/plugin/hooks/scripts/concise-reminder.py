#!/usr/bin/env python3
"""Stop hook: re-anchor reply concision on long runs, and measure the effect.

The active output style ("Explanatory Concise") lives in the system prompt and
is re-sent every request, so the concise+plain rule is always present — yet on
long autonomous runs adherence drifts: the model weighs the always-present rule
less as the recent tail grows (recency competition, not context loss). The
built-in per-turn output-style reminder cannot help here — custom file-based
styles get only a generic "follow your style" stub, not the rule itself (the
loader drops the `turnReminder` field). So a content-bearing re-anchor near the
recent tail is only reachable from a hook.

Stop is the right event: it fires once per main-agent turn (including unattended
auto-mode), so the cadence is immune to delegation — a run that delegates most
work still turns here — and the assistant's reply is readable from the
transcript, the only place its length is observable. PostToolUse was rejected:
its per-tool-call counter crawls in delegation-heavy runs and cannot see the
reply.

Pilot (ADR 0084): an UNPROVEN salience bet — re-injection can be deprioritised,
and reply length is a noisy proxy for concision. Every turn logs `reply_chars`
plus a `reminded` flag so the before/after effect is measurable before any
decision to keep it. Every N main-agent turns (default 8, env override) it emits
a non-blocking re-anchor note. Per-session turn counter, reset on SessionStart
(including compact, where the system prompt is fresh again).

Fail-safe: any error -> exit 0 (no-op).
"""

import hashlib
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from _hooklib import emit_note, load_payload, log_event, run
except Exception:
    sys.exit(0)

REMINDER_EVERY_N = 8
_STATE_DIR = os.path.join(tempfile.gettempdir(), "mainframe-concise")
# Tail cap: transcripts grow unboundedly; the last assistant message is near the
# end, so reading the final slice bounds cost without losing the target.
_MAX_TAIL_BYTES = 2_000_000

CONCISE_NOTE = (
    "Concise check (long run — re-anchor on the active output style): lead with "
    "the answer, then the detail; plain words a non-technical reader follows on "
    "the first read; short and laconic, no padding; identifiers and paths in "
    "`backticks`, the prose around them plain. Length tracks substance, not turn "
    "count. This is a reminder, not a block."
)


def _every():
    """Reminder interval in turns; env `MAINFRAME_CONCISE_REMINDER_EVERY` wins
    when it is a positive integer, else the default (lets the pilot retune)."""
    raw = os.environ.get("MAINFRAME_CONCISE_REMINDER_EVERY")
    if raw:
        try:
            value = int(raw)
            if value > 0:
                return value
        except ValueError:
            pass
    return REMINDER_EVERY_N


def _counter_path(session_id, state_dir=None):
    directory = state_dir or _STATE_DIR
    key = hashlib.sha256((session_id or "nosession").encode("utf-8")).hexdigest()[:16]
    return os.path.join(directory, key)


def _load(path):
    """Persisted (turn_count, last_fired_turn); (0, 0) when absent/garbage."""
    try:
        with open(path, encoding="utf-8") as fh:
            count, last_fired = fh.read().split()[:2]
            return int(count), int(last_fired)
    except (OSError, ValueError):
        return 0, 0


def _save(path, count, last_fired):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(f"{count} {last_fired}")
    except OSError:
        pass


def _reset(path):
    _save(path, 0, 0)


def should_remind(count, n):
    """Fire on every n-th turn, never on the warmup turn 0."""
    return count > 0 and n > 0 and count % n == 0


def _advance(count, last_fired, n):
    """Advance one turn -> (count, last_fired, turns_since_reminder, reminded).

    `turns_since_reminder` is measured against the PRIOR anchor. Stop fires after
    the reply is produced, so the reply on a fire turn was written before the
    nudge (it lands next turn): it must read as max-distance, not 0. The first
    truly nudged reply is the next turn at distance 1 — so the metric is a
    distance-from-reminder curve, not a fire-turn boolean (which would compare
    untreated replies and mask a real effect)."""
    count += 1
    turns_since = count - last_fired
    reminded = should_remind(count, n)
    if reminded:
        last_fired = count
    return count, last_fired, turns_since, reminded


def _content_chars(content):
    """Text-character count of a message `content` (string or block list);
    only `text` blocks count — tool_use / tool_result are not reply prose."""
    if isinstance(content, str):
        return len(content)
    if isinstance(content, list):
        total = 0
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                total += len(block.get("text") or "")
        return total
    return None


def last_assistant_chars(transcript_path):
    """Reply length of the last assistant message in the JSONL transcript, or
    None when the transcript is absent / unreadable / has no assistant turn."""
    if not transcript_path:
        return None
    try:
        path = os.path.expanduser(transcript_path)
        size = os.path.getsize(path)
        with open(path, "rb") as fh:
            if size > _MAX_TAIL_BYTES:
                fh.seek(size - _MAX_TAIL_BYTES)
                fh.readline()  # drop the partial line the seek landed inside
            raw = fh.read().decode("utf-8", "replace")
    except OSError:
        return None
    for line in reversed(raw.splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        if obj.get("type") != "assistant":
            continue
        return _content_chars((obj.get("message") or {}).get("content"))
    return None


def main():
    payload = load_payload()
    event = payload.get("hook_event_name") or ""
    path = _counter_path(str(payload.get("session_id") or ""))

    if event == "SessionStart":
        _reset(path)
        return

    # A re-invoked stop (a prior stop-gate blocked this turn) is not a new turn.
    if payload.get("stop_hook_active"):
        return
    # Stop is main-agent only (subagents fire SubagentStop); guard defensively
    # so a subagent reply never counts toward or receives the main-agent nudge.
    if payload.get("agent_id"):
        return

    count, last_fired = _load(path)
    count, last_fired, turns_since, reminded = _advance(count, last_fired, _every())
    _save(path, count, last_fired)
    chars = last_assistant_chars(payload.get("transcript_path"))

    if reminded:
        emit_note("Stop", CONCISE_NOTE)
    log_event("concise_reminder",
              {"turn": count, "reply_chars": chars if chars is not None else -1,
               "turns_since_reminder": turns_since, "reminded": reminded,
               "every": _every()}, payload)


if __name__ == "__main__":
    run(main)
