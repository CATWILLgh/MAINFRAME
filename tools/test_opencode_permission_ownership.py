#!/usr/bin/env python3
"""Test order-aware OpenCode permission ownership reconciliation."""

import os
import sys


_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "adapters", "opencode"))

from permission_config import merge_permissions


def test_nested_rule_order_controls_ownership():
    old = {"*": "allow", "rm -rf /": "deny"}
    reversed_rule = {"rm -rf /": "deny", "*": "allow"}

    merged, owned = merge_permissions(
        {"bash": reversed_rule}, {"bash": old}, {"bash": old})
    assert list(merged["bash"]) == ["rm -rf /", "*"]
    assert owned == {"bash": None}

    merged, owned = merge_permissions(
        {"bash": old}, {"bash": old}, {"bash": old})
    assert list(merged["bash"]) == ["*", "rm -rf /"]
    assert list(owned["bash"]) == ["*", "rm -rf /"]

    merged, owned = merge_permissions(
        {"bash": old}, {"bash": reversed_rule}, {"bash": old})
    assert list(merged["bash"]) == ["rm -rf /", "*"]
    assert list(owned["bash"]) == ["rm -rf /", "*"]


def test_empty_nested_rule_is_invalid_but_empty_generated_map_is_valid():
    try:
        merge_permissions({}, {"bash": {}}, {})
    except SystemExit:
        pass
    else:
        raise AssertionError("empty nested permission rule was accepted")

    merged, owned = merge_permissions({}, {}, {})
    assert merged == {}
    assert owned == {}


def test_top_level_action_order_matches_reconciliation_contract():
    merged, owned = merge_permissions(
        {"custom_*": "deny", "bash": "ask"},
        {"edit": "deny", "bash": "allow"},
        {"bash": "ask"},
    )
    assert list(merged) == ["custom_*", "bash", "edit"]
    assert list(owned) == ["bash", "custom_*", "edit"]


def _run_all():
    tests = [value for name, value in sorted(globals().items())
             if name.startswith("test_") and callable(value)]
    for test in tests:
        test()
        print(f"  ok   {test.__name__}")
    print(f"{len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    _run_all()
