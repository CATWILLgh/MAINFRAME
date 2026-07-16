"""Validated permission-source loading and ownership-aware OpenCode merging."""

import copy
import json
import os
import re
import tempfile


DECISIONS = frozenset({"allow", "ask", "deny"})
RULE_KEYS = frozenset({"allow", "ask", "deny"})
STATE_VERSION = 1
REGEX_META = frozenset(".+^${}()|[]\\")


class _DuplicateKey(ValueError):
    pass


def _object_without_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKey(f"duplicate key: {key}")
        result[key] = value
    return result


def _load_json_file(path, *, required, label):
    if not os.path.isfile(path):
        if required:
            raise SystemExit(f"error: required {label} not found: {path}")
        return None
    try:
        with open(path) as stream:
            return json.load(stream, object_pairs_hook=_object_without_duplicates)
    except (OSError, UnicodeError, json.JSONDecodeError, _DuplicateKey) as exc:
        raise SystemExit(f"error: cannot load {label} {path}: {exc}") from exc


def load_permission_rules(path):
    rules = _load_json_file(path, required=True, label="permission rules")
    if not isinstance(rules, dict) or set(rules) != RULE_KEYS:
        raise SystemExit(
            "error: permission rules must contain exactly allow, ask, and deny")
    for key in ("allow", "ask", "deny"):
        entries = rules[key]
        if (not isinstance(entries, list)
                or any(not isinstance(entry, str) for entry in entries)):
            raise SystemExit(f"error: permission rules `{key}` must be list[str]")
    if not any(rules.values()):
        raise SystemExit("error: permission rules cannot be empty")
    return rules


def require_restrictive_projection(permission):
    for rule in permission.values():
        if rule in ("ask", "deny"):
            return
        if isinstance(rule, dict) and any(
                decision in ("ask", "deny") for decision in rule.values()):
            return
    raise SystemExit(
        "error: permission rules project no effective ask or deny policy")


def _is_rule(value):
    if isinstance(value, str):
        return value in DECISIONS
    return (isinstance(value, dict) and bool(value)
            and all(isinstance(pattern, str) and pattern
                    and isinstance(decision, str) and decision in DECISIONS
                    for pattern, decision in value.items()))


def _rules_equal(actual, previous):
    if actual != previous:
        return False
    if isinstance(actual, dict):
        return list(actual.items()) == list(previous.items())
    return True


def validate_permission(value, *, label="permission"):
    if isinstance(value, str):
        if value not in DECISIONS:
            raise SystemExit(f"error: invalid {label} decision: {value}")
        return
    if (not isinstance(value, dict)
            or any(not isinstance(action, str) or not action or not _is_rule(rule)
                   for action, rule in value.items())):
        raise SystemExit(f"error: {label} must be a decision or action rule map")


def load_permission_state(path):
    state = _load_json_file(path, required=False, label="permission state")
    if state is None:
        return {}
    if (not isinstance(state, dict) or set(state) != {"version", "actions"}
            or state.get("version") != STATE_VERSION
            or isinstance(state.get("version"), bool)
            or not isinstance(state.get("actions"), dict)):
        raise SystemExit("error: invalid permission state schema")
    actions = state["actions"]
    if any(not isinstance(action, str) or not action
           or (rule is not None and not _is_rule(rule))
           for action, rule in actions.items()):
        raise SystemExit("error: invalid permission state action")
    return actions


def _tombstone_all(owned, generated):
    result = {action: None for action in owned}
    for action in generated:
        result[action] = None
    return result


def _matches_action(action, pattern):
    expression = []
    for character in pattern.replace("\\", "/"):
        if character == "*":
            expression.append(".*")
        elif character == "?":
            expression.append(".")
        else:
            expression.append("\\" + character
                              if character in REGEX_META else character)
    regex = "".join(expression)
    if regex.endswith(" .*"):
        regex = regex[:-3] + "( .*)?"
    flags = re.DOTALL | (re.IGNORECASE if os.name == "nt" else 0)
    normalized = action.replace("\\", "/")
    return re.fullmatch(regex, normalized, flags=flags) is not None


def merge_permissions(existing, generated, owned):
    validate_permission(existing)
    validate_permission(generated, label="generated permission")
    if not isinstance(owned, dict):
        raise SystemExit("error: permission ownership must be an action map")
    if isinstance(existing, str):
        return existing, _tombstone_all(owned, generated)

    merged = copy.deepcopy(existing)
    next_owned = {}
    for action, previous in owned.items():
        if previous is None:
            next_owned[action] = None
        elif (action not in existing
              or not _rules_equal(existing[action], previous)):
            next_owned[action] = None
        elif action in generated:
            merged[action] = copy.deepcopy(generated[action])
            next_owned[action] = copy.deepcopy(generated[action])
        else:
            del merged[action]

    for action in existing:
        if action not in owned:
            next_owned[action] = None
    for action, rule in generated.items():
        if action in next_owned or action in merged:
            continue
        if any(_matches_action(action, pattern) for pattern in merged):
            next_owned[action] = None
            continue
        merged[action] = copy.deepcopy(rule)
        next_owned[action] = copy.deepcopy(rule)
    return merged, next_owned


def write_permission_state(path, actions):
    parent = os.path.dirname(path) or "."
    os.makedirs(parent, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{os.path.basename(path)}.", dir=parent)
    published = False
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w") as stream:
            json.dump({"version": STATE_VERSION, "actions": actions},
                      stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        published = True
    finally:
        if not published:
            try:
                os.close(descriptor)
            except OSError:
                pass
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
