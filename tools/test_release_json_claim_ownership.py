#!/usr/bin/env python3
"""Hermetic contract tests for generic JSON claim ownership."""

from __future__ import annotations

import copy
import sys
import tempfile
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

import release_contract


SCALAR = {"id": "hooks-enabled", "kind": "exact-scalar", "pointer": "/hooks/enabled"}
ARRAY = {
    "id": "session-start",
    "kind": "array-entry",
    "pointer": "/hooks/events/SessionStart",
    "selector": {"pointer": "/hooks/0/args/1", "value": "mainframe:SessionStart"},
}


def _resource(ownership: object) -> dict:
    return {
        "id": "zcode.hooks",
        "strategy": "json-key-merge",
        "source": "config.json",
        "target": {"root": "zcode-config", "path": "cli/config.json"},
        "observation": "supported",
        "apply": "supported",
        "json_ownership": ownership,
    }


def _ownership() -> dict:
    return {
        "kind": "json-claim-registry-v1",
        "registry": {
            "target": {"root": "zcode-config", "path": "mainframe/config-ownership.json"},
            "schema_version": 1,
        },
        "claims": [SCALAR, ARRAY],
    }


def _write(resource: dict, payload: str | None = None, schema_version: int = 7) -> dict:
    root = Path(tempfile.mkdtemp())
    (root / "config.json").write_text(
        payload
        or '{"hooks":{"enabled":true,"events":{"SessionStart":[{"hooks":[{"type":"process","executable":"python3","args":["bridge.py","mainframe:SessionStart"]}]}]}}}\n'
    )
    return release_contract.write_bundle_manifest(
        root,
        component="zcode-desktop",
        dependencies=["credential-tools", "mainframe-cli"],
        install_units=[],
        resources=[resource],
        schema_version=schema_version,
    )


def test_accepts_strict_scalar_and_selector_array_claims():
    ownership = _ownership()
    manifest = _write(_resource(ownership))
    assert manifest["schema_version"] == 7
    assert manifest["resources"][0]["json_ownership"] == ownership


def test_accepts_a_root_selector_for_an_array_of_scalars():
    ownership = _ownership()
    ownership["claims"] = [{
        "id": "permission-allow-one",
        "kind": "array-entry",
        "pointer": "/permissions/allow",
        "selector": {"pointer": "", "value": "Bash(ls:*)"},
    }]
    payload = '{"permissions":{"allow":["Bash(ls:*)","Read"]}}\n'

    manifest = _write(_resource(ownership), payload=payload)

    assert manifest["resources"][0]["json_ownership"] == ownership


def test_rejects_a_root_selector_that_matches_more_than_one_entry():
    ownership = _ownership()
    ownership["claims"] = [{
        "id": "permission-allow-one",
        "kind": "array-entry",
        "pointer": "/permissions/allow",
        "selector": {"pointer": "", "value": "Bash(ls:*)"},
    }]
    payload = '{"permissions":{"allow":["Bash(ls:*)","Bash(ls:*)"]}}\n'

    try:
        _write(_resource(ownership), payload=payload)
    except ValueError:
        return
    raise AssertionError("duplicate source entries accepted for one claim")


def test_requires_schema_v7_and_adapter_local_nonoverlapping_registry():
    for schema in (5, 6):
        try:
            _write(_resource(_ownership()), schema_version=schema)
        except ValueError:
            pass
        else:
            raise AssertionError("pre-v7 bundle accepted JSON claim ownership")
    for target in (
        {"root": "codex-config", "path": "owned.json"},
        {"root": "zcode-config", "path": "cli/config.json"},
    ):
        ownership = _ownership()
        ownership["registry"]["target"] = target
        try:
            _write(_resource(ownership))
        except ValueError:
            pass
        else:
            raise AssertionError("unsafe registry target was accepted")


def test_rejects_unknown_fields_invalid_selectors_and_ambiguous_source():
    invalid = []
    ownership = _ownership()
    ownership["extra"] = True
    invalid.append((ownership, None))
    ownership = _ownership()
    ownership["claims"] = list(reversed(ownership["claims"]))
    invalid.append((ownership, None))
    ownership = _ownership()
    ownership["claims"][1]["selector"]["pointer"] = "/bad~2escape"
    invalid.append((ownership, None))
    ownership = _ownership()
    ownership["claims"][0]["pointer"] = ""
    ownership["claims"] = [ownership["claims"][0]]
    invalid.append((ownership, None))
    ownership = _ownership()
    ownership["claims"][0]["pointer"] = "/hooks/events/SessionStart/0/hooks/0/args/1"
    ownership["claims"] = [ownership["claims"][0]]
    invalid.append((ownership, None))
    ownership = _ownership()
    ownership["claims"][0]["selector"] = {"pointer": "/x", "value": 1}
    invalid.append((ownership, None))
    ownership = _ownership()
    invalid.append((ownership, '{"hooks":{"enabled":{},"events":{"SessionStart":[]}}}\n'))
    duplicate = '{"hooks":{"enabled":true,"events":{"SessionStart":[{"hooks":[{"args":["x","mainframe:SessionStart"]}]},{"hooks":[{"args":["x","mainframe:SessionStart"]}]}]}}}\n'
    invalid.append((_ownership(), duplicate))
    for descriptor, payload in invalid:
        try:
            _write(_resource(copy.deepcopy(descriptor)), payload)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid JSON ownership contract was accepted")


if __name__ == "__main__":
    for name, value in sorted(globals().items()):
        if name.startswith("test_") and callable(value):
            value()
