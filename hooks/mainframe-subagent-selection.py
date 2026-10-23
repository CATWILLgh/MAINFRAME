#!/usr/bin/env python3
"""Require explicit model and reasoning-effort choices for subagent creation.

An adapter calls :func:`decision_reason` only after positively identifying a
native subagent-creation action that supports both selection controls. Missing
entire event payloads and unrecognized events are adapter nondecisions; a
recognized empty argument object means both selections are missing and must be
denied. The adapter owns event recognition, argument extraction, native naming,
and output encoding.

This detector checks explicit selection only. It has no model catalog, quality
inference, LLM calls, state, logs, network access, or product-specific behavior.
A returned reason denies creation; ``None`` allows it at this boundary.
"""

from __future__ import annotations


def decision_reason(model: object, reasoning_effort: object) -> str | None:
    """Return a denial reason for missing explicit selections, else ``None``."""
    for selection in (model, reasoning_effort):
        if (
            not isinstance(selection, str)
            or not selection.strip()
            or selection.strip().casefold() in {"inherit", "default", "auto"}
        ):
            return (
                "Subagent creation requires an explicit model and reasoning effort. "
                "Choose an available model and supported reasoning effort according "
                "to task complexity, importance, cost of error, and budget, then "
                "retry with explicit values."
            )
    return None
