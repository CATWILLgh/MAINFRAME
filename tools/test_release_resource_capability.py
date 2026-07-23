#!/usr/bin/env python3
"""Parity and integration tests for release apply capability."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

import release_contract
from release_diagnostics import diagnostics_resource
from release_resource_capability import valid_apply_declaration


def test_apply_capability_predicate_matrix():
    cases = {
        "supported": ("opencode", lambda item: None, True),
        "unsupported apply": ("opencode", lambda item: item.update(apply="future"), False),
        "wrong component": ("codex", lambda item: None, False),
        "wrong strategy": ("opencode", lambda item: item.update(strategy="seed-if-absent"), False),
        "wrong observation": ("opencode", lambda item: item.update(observation="unimplemented"), False),
        "wrong target root": ("opencode", _wrong_target_root, False),
        "static ownership": ("opencode", _add_static_ownership, False),
        "missing ownership": ("opencode", lambda item: item.pop("ownership"), False),
        "wrong entry schema": ("opencode", _wrong_entry_schema, False),
        "wrong registry root": ("opencode", _wrong_registry_root, False),
        "wrong registry version": ("opencode", _wrong_registry_version, False),
        "wrong entries pointer": ("opencode", _wrong_entries_pointer, False),
        "external state": ("opencode", _add_external_state, False),
    }
    for name, (component, mutate, expected) in cases.items():
        resource = _supported_resource()
        mutate(resource)
        actual = valid_apply_declaration(component, resource)
        assert actual == expected, f"{name}: {actual} != {expected}"


def test_bundle_contract_preserves_supported_opencode_apply():
    bundle = Path(tempfile.mkdtemp())
    (bundle / "config.json").write_text(
        '{"permission":{"bash":{"*":"deny"}}}\n'
    )
    release_contract.write_bundle_manifest(
        bundle,
        component="opencode",
        dependencies=[],
        install_units=[],
        resources=[_supported_resource()],
    )
    manifest = release_contract.validate_bundle(bundle)
    assert manifest["resources"][0]["apply"] == "supported"


def test_exact_json_document_apply_capability_is_adapter_local():
    valid_pairs = {
        ("claude-code", "claude-config"),
        ("codex", "codex-config"),
        ("opencode", "opencode-config"),
        ("antigravity-2", "antigravity-data"),
    }
    for component, root in valid_pairs:
        resource = _exact_document_resource(root)
        assert valid_apply_declaration(component, resource)

    invalid_cases = (
        ("credential-tools", "credentials-config", "mainframe/diagnostics.json"),
        ("codex", "claude-config", "mainframe/diagnostics.json"),
        ("codex", "codex-config", "diagnostics.json"),
    )
    for component, root, path in invalid_cases:
        resource = _exact_document_resource(root)
        resource["target"]["path"] = path
        assert not valid_apply_declaration(component, resource)


def test_diagnostics_resource_mapping_is_exact_and_copy_safe():
    roots = {
        "antigravity-2": "antigravity-data",
        "claude-code": "claude-config",
        "codex": "codex-config",
        "opencode": "opencode-config",
    }
    for component, root in roots.items():
        resource = diagnostics_resource(component)
        assert resource == {
            "id": f"{component}.diagnostics",
            "strategy": "exact-json-document",
            "source": "diagnostics.json",
            "target": {"root": root, "path": "mainframe/diagnostics.json"},
            "observation": "supported",
            "apply": "supported",
        }
        resource["target"]["root"] = "mutated"
        assert diagnostics_resource(component)["target"]["root"] == root


def test_exact_json_document_capability_has_no_foreign_ownership_state():
    for field, value in (
        ("legacy_source_suffixes", []),
        ("owned_json_pointers", ["/events"]),
        ("ownership", {}),
        ("external_state", {}),
    ):
        resource = _exact_document_resource("codex-config")
        resource[field] = value
        assert not valid_apply_declaration("codex", resource)


def test_exact_json_document_capability_requires_supported_lifecycle():
    for field in ("observation", "apply"):
        resource = _exact_document_resource("codex-config")
        resource[field] = "unimplemented"
        assert not valid_apply_declaration("codex", resource)


def _supported_resource() -> dict:
    return {
        "id": "opencode.permissions",
        "strategy": "json-key-merge",
        "source": "config.json",
        "target": {"root": "opencode-config", "path": "opencode.json"},
        "observation": "supported",
        "apply": "supported",
        "ownership": {
            "kind": "json-map-entry-registry-v1",
            "map_pointer": "/permission",
            "entry_schema": "decision-rule-v1",
            "registry": {
                "target": {
                    "root": "opencode-config",
                    "path": "opencode.json.mainframe-permissions.json",
                },
                "schema_version": 1,
                "entries_pointer": "/actions",
            },
        },
    }


def _exact_document_resource(root: str) -> dict:
    return {
        "id": "adapter.diagnostics",
        "strategy": "exact-json-document",
        "source": "diagnostics.json",
        "target": {"root": root, "path": "mainframe/diagnostics.json"},
        "observation": "supported",
        "apply": "supported",
    }


def _wrong_target_root(item: dict) -> None:
    item["target"]["root"] = "codex-config"


def _add_static_ownership(item: dict) -> None:
    item["owned_json_pointers"] = ["/permission"]


def _wrong_entry_schema(item: dict) -> None:
    item["ownership"]["entry_schema"] = "future"


def _wrong_registry_root(item: dict) -> None:
    item["ownership"]["registry"]["target"]["root"] = "codex-config"


def _wrong_registry_version(item: dict) -> None:
    item["ownership"]["registry"]["schema_version"] = 2


def _wrong_entries_pointer(item: dict) -> None:
    item["ownership"]["registry"]["entries_pointer"] = "/servers"


def _add_external_state(item: dict) -> None:
    item["external_state"] = {"kind": "future"}


def _run_all() -> None:
    failures = 0
    tests = [
        (name, function)
        for name, function in sorted(globals().items())
        if name.startswith("test_") and callable(function)
    ]
    for name, function in tests:
        try:
            function()
            print(f"  ok  {name}")
        except Exception as exc:
            failures += 1
            print(f"FAIL  {name}: {exc!r}")
    print(f"\n{len(tests) - failures}/{len(tests)} passed")
    raise SystemExit(1 if failures else 0)


if __name__ == "__main__":
    _run_all()
