#!/usr/bin/env python3
"""Hermetic owned-JSON tests for the MAINFRAME release contract."""

from __future__ import annotations

import hashlib
import sys
import tempfile
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

import release_contract
import release_contract_io


def _json_resource(
    identifier: str,
    target_root: str,
    *,
    observation: str = "supported",
    pointers: object = ("/owned",),
) -> dict:
    resource = {
        "id": identifier,
        "strategy": "json-key-merge",
        "source": "config.json",
        "target": {"root": target_root, "path": "config.json"},
        "observation": observation,
        "apply": "unimplemented",
    }
    if pointers is not None:
        resource["owned_json_pointers"] = (
            list(pointers) if isinstance(pointers, tuple) else pointers
        )
    return resource


def _write_json_bundle(
    root: Path,
    component: str,
    target_root: str,
    pointers: list[str],
) -> Path:
    bundle = root / "bundles" / component
    bundle.mkdir(parents=True)
    (bundle / "config.json").write_text('{"owned":{"child":true},"peer":true}\n')
    release_contract.write_bundle_manifest(
        bundle,
        component=component,
        dependencies=[],
        install_units=[],
        resources=[_json_resource(component + ".configuration", target_root, pointers=pointers)],
    )

    return bundle


def test_supported_json_observation_requires_valid_owned_pointers():
    bundle = Path(tempfile.mkdtemp())
    (bundle / "config.json").write_text(
        '{"":0,"a/b":{"~key":1},"permissions":{"allow":[],"deny":[]}}\n'
    )
    resource = _json_resource(
        "alpha.configuration",
        "codex-config",
        pointers=["/", "/a~1b/~0key", "/permissions/allow", "/permissions/deny"],
    )

    manifest = release_contract.write_bundle_manifest(
        bundle,
        component="codex",
        dependencies=[],
        install_units=[],
        resources=[resource],
    )

    assert manifest["resources"][0]["owned_json_pointers"] == resource[
        "owned_json_pointers"
    ]


def test_owned_json_pointers_are_forbidden_outside_supported_json_observation():
    cases = [
        _json_resource("alpha.missing", "codex-config", pointers=None),
        _json_resource(
            "alpha.unimplemented",
            "codex-config",
            observation="unimplemented",
        ),
        _json_resource(
            "alpha.unimplemented-empty",
            "codex-config",
            observation="unimplemented",
            pointers=[],
        ),
        {
            "id": "alpha.seed",
            "strategy": "seed-if-absent",
            "source": "config.json",
            "target": {"root": "codex-config", "path": "seed.json"},
            "observation": "supported",
            "apply": "unimplemented",
            "owned_json_pointers": ["/owned"],
        },
        {
            "id": "alpha.seed-empty",
            "strategy": "seed-if-absent",
            "source": "config.json",
            "target": {"root": "codex-config", "path": "seed-empty.json"},
            "observation": "supported",
            "apply": "unimplemented",
            "owned_json_pointers": [],
        },
    ]
    for resource in cases:
        bundle = Path(tempfile.mkdtemp())
        (bundle / "config.json").write_text('{"owned":true}\n')
        try:
            release_contract.write_bundle_manifest(
                bundle,
                component="codex",
                dependencies=[],
                install_units=[],
                resources=[resource],
            )
        except ValueError as exc:
            assert "owned_json_pointers" in str(exc) or "lifecycle support" in str(exc)
        else:
            raise AssertionError(f"invalid owned JSON metadata was accepted: {resource}")


def test_owned_json_pointers_reject_invalid_shape_escape_order_and_overlap():
    invalid_pointers = (
        "/owned",
        [],
        [""],
        ["owned"],
        [1],
        [[]],
        ["/bad~"],
        ["/bad~2escape"],
        ["/peer", "/owned"],
        ["/owned", "/owned"],
        ["/owned", "/owned/child"],
        [f"/field-{index:04d}" for index in range(1025)],
    )
    for pointers in invalid_pointers:
        bundle = Path(tempfile.mkdtemp())
        (bundle / "config.json").write_text('{"owned":{"child":true},"peer":true}\n')
        try:
            release_contract.write_bundle_manifest(
                bundle,
                component="codex",
                dependencies=[],
                install_units=[],
                resources=[_json_resource("alpha.configuration", "codex-config", pointers=pointers)],
            )
        except ValueError as exc:
            assert "owned_json_pointers" in str(exc)
        else:
            raise AssertionError(f"invalid JSON pointers were accepted: {pointers!r}")


def test_owned_json_pointers_resolve_only_through_existing_object_members():
    cases = [
        ('{"items":[{"name":"value"}]}\n', ["/items/0/name"]),
        ('{"scalar":true}\n', ["/scalar/child"]),
        ('{"owned":true}\n', ["/missing"]),
    ]
    for payload, pointers in cases:
        bundle = Path(tempfile.mkdtemp())
        (bundle / "config.json").write_text(payload)
        try:
            release_contract.write_bundle_manifest(
                bundle,
                component="codex",
                dependencies=[],
                install_units=[],
                resources=[_json_resource("alpha.configuration", "codex-config", pointers=pointers)],
            )
        except ValueError as exc:
            assert "owned_json_pointers" in str(exc)
        else:
            raise AssertionError(f"unresolvable JSON pointer was accepted: {pointers!r}")


def test_supported_json_source_requires_strict_bounded_json():
    invalid_payloads = (
        b'{"owned":true,"owned":false}\n',
        b'{"owned":"\\ud800"}\n',
        b'{"owned":NaN}\n',
        b"\xff",
        b'{"owned":"' + b"x" * (1024 * 1024) + b'"}',
    )
    for payload in invalid_payloads:
        bundle = Path(tempfile.mkdtemp())
        (bundle / "config.json").write_bytes(payload)
        try:
            release_contract.write_bundle_manifest(
                bundle,
                component="codex",
                dependencies=[],
                install_units=[],
                resources=[_json_resource("alpha.configuration", "codex-config")],
            )
        except ValueError as exc:
            assert "JSON" in str(exc) or "json" in str(exc)
        else:
            raise AssertionError("invalid supported JSON source was accepted")


def test_supported_json_source_accepts_exactly_one_mibibyte():
    bundle = Path(tempfile.mkdtemp())
    prefix = b'{"owned":"'
    suffix = b'"}'
    payload = prefix + b"x" * (1024 * 1024 - len(prefix) - len(suffix)) + suffix
    (bundle / "config.json").write_bytes(payload)

    release_contract.write_bundle_manifest(
        bundle,
        component="codex",
        dependencies=[],
        install_units=[],
        resources=[_json_resource("alpha.configuration", "codex-config")],
    )


def test_verified_json_source_reads_one_authenticated_no_follow_snapshot():
    root = Path(tempfile.mkdtemp())
    bundle = root / "bundle"
    bundle.mkdir()
    source = bundle / "config.json"
    original = b'{"owned":true}'
    source.write_bytes(original)
    expected = {
        "path": "config.json",
        "mode": "0644",
        "size": len(original),
        "sha256": hashlib.sha256(original).hexdigest(),
    }
    source.write_bytes(b'{"owned":false}')
    try:
        release_contract_io.read_verified_bytes(
            bundle.resolve(),
            "config.json",
            expected,
            max_bytes=1024 * 1024,
        )
    except ValueError as exc:
        assert "integrity" in str(exc)
    else:
        raise AssertionError("changed JSON source passed payload authentication")

    source.unlink()
    source.symlink_to(root / "outside.json")
    (root / "outside.json").write_bytes(original)
    try:
        release_contract_io.read_verified_bytes(
            bundle.resolve(),
            "config.json",
            expected,
            max_bytes=1024 * 1024,
        )
    except (OSError, ValueError):
        pass
    else:
        raise AssertionError("verified JSON source reader followed a symlink")


def _run_all():
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
