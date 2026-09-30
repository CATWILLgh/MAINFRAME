"""Small adaptation-state construction and conservative migration."""

from __future__ import annotations

from copy import deepcopy
from collections import Counter
from typing import Iterable, Mapping

from .core import Conflict


Component = tuple[str, str]
DELIVERY_VALUES = ("pending", "installed", "unsupported")
VERIFICATION_VALUES = ("pending", "passed")


def component_keys(source: dict) -> tuple[Component, ...]:
    return tuple(
        (category, name)
        for category, group in source["components"].items()
        for name in group
    )


def _text(value) -> str | None:
    if not isinstance(value, str):
        return None
    return " ".join(value.split()) or None


def set_component(
    state: dict,
    component: Component,
    *,
    delivery: str,
    verification: str | None = None,
    next_action: str | None = None,
    reason: str | None = None,
) -> None:
    category, name = component
    try:
        source = state["components"][category][name]["source"]
    except (KeyError, TypeError) as error:
        raise Conflict(f"Unknown adaptation component: {category}.{name}") from error
    if delivery not in DELIVERY_VALUES:
        raise Conflict(f"Invalid delivery state for {category}.{name}: {delivery}")
    next_action, reason = _text(next_action), _text(reason)
    row = {"source": source, "delivery": delivery}
    if delivery == "unsupported":
        if verification is not None:
            raise Conflict(f"Unsupported component cannot have verification: {category}.{name}")
        if not reason:
            raise Conflict(f"Unsupported component requires a reason: {category}.{name}")
    else:
        if reason:
            raise Conflict(f"Only an unsupported component can have a reason: {category}.{name}")
        verification = verification or "pending"
        if verification not in VERIFICATION_VALUES:
            raise Conflict(f"Invalid verification state for {category}.{name}: {verification}")
        row["verification"] = verification
    if next_action:
        row["next_action"] = next_action
    if reason:
        row["reason"] = reason
    state["components"][category][name] = row


def _prior_evidence(row: dict) -> dict:
    """Translate outcomes, never arbitrary prose or old delivery claims.

    A schema-1 successful note may describe a proof, handoff, or historical
    attempt. Preserve the passed outcome, but do not reinterpret that free-form
    text as a current limitation. ``reason`` is reserved for an actual
    unsupported limitation; pending work uses ``next_action``.
    """
    if not isinstance(row, dict):
        return {}
    note = _text(row.get("note"))
    if row.get("status") == "installed":
        return {"verification": "passed"}
    if row.get("status") == "unsupported":
        return {"delivery": "unsupported", **({"reason": note} if note else {})}
    if row.get("status") == "pending":
        return {"next_action": note} if note else {}
    if row.get("delivery") == "unsupported" and _text(row.get("reason")):
        return {"delivery": "unsupported", "reason": _text(row["reason"])}
    evidence = {}
    if row.get("verification") == "passed":
        evidence["verification"] = "passed"
    if _text(row.get("next_action")):
        evidence["next_action"] = _text(row["next_action"])
    return evidence


def reconcile_state(
    source: dict,
    prior: dict,
    target: dict,
    *,
    unchanged: bool,
    delivered: Iterable[Component] = (),
    unsupported: Mapping[Component, str] | None = None,
    pending: Mapping[Component, str] | None = None,
    next_actions: Iterable[str] = (),
) -> dict:
    """Rebuild schema 2; callers establish delivery, prior state supplies evidence."""
    state = deepcopy(source)
    state["target"] = deepcopy(target)
    state.pop("mainframe_root", None)
    state.pop("status_values", None)
    actions = [_text(action) for action in next_actions]
    actions = list(dict.fromkeys(action for action in actions if action))

    keys = set(component_keys(state))
    delivered = set(delivered)
    unsupported = dict(unsupported or {})
    pending = dict(pending or {})
    supplied = delivered | set(unsupported) | set(pending)
    unknown = supplied - keys
    if unknown:
        category, name = sorted(unknown)[0]
        raise Conflict(f"Unknown adaptation component: {category}.{name}")
    if (delivered & set(unsupported)) or (delivered & set(pending)) or (set(unsupported) & set(pending)):
        raise Conflict("An adaptation component has conflicting delivery outcomes.")

    evidence = {}
    if unchanged and isinstance(prior, dict):
        for component in keys:
            category, name = component
            old = prior.get("components", {}).get(category, {}).get(name, {})
            current = state["components"][category][name]
            if old.get("source") == current["source"]:
                evidence[component] = _prior_evidence(old)

    repeated_actions = Counter(
        row.get("next_action") for row in evidence.values() if row.get("next_action")
    )
    for action, count in repeated_actions.items():
        if count > 1:
            if not actions:
                actions.append(action)
            for row in evidence.values():
                if row.get("next_action") == action:
                    row.pop("next_action")
    if actions:
        state["next_actions"] = actions
    else:
        state.pop("next_actions", None)

    for component in keys:
        old = evidence.get(component, {})
        if component in unsupported:
            set_component(state, component, delivery="unsupported", reason=unsupported[component])
        elif component in pending:
            set_component(state, component, delivery="pending", next_action=pending[component])
        elif component in delivered:
            set_component(
                state, component, delivery="installed",
                verification=old.get("verification", "pending"),
                next_action=old.get("next_action"),
            )
        elif old.get("delivery") == "unsupported" and old.get("reason"):
            set_component(state, component, delivery="unsupported", reason=old["reason"])
        else:
            set_component(
                state, component, delivery="pending",
                next_action=old.get("next_action"),
            )
    return state
