#!/usr/bin/env python3
"""Hermetic tests for external-state release resources."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

import release_contract


def test_codex_external_state_must_match_its_install_unit():
    bundle = Path(tempfile.mkdtemp())
    hooks = '{"hooks":{"Stop":[{"hooks":[{"type":"command","command":"true"}]}]}}\n'
    (bundle / "hooks.json").write_text(hooks)
    (bundle / "other-hooks.json").write_text(hooks)
    unit = {
        "id": "codex.hooks",
        "kind": "file",
        "source": "hooks.json",
        "target": {"root": "codex-config", "path": "hooks.json"},
    }
    resource = {
        "id": "codex.hook-trust",
        "strategy": "manual-action",
        "source": "hooks.json",
        "target": {"root": "codex-config", "path": "hooks.json"},
        "observation": "supported",
        "apply": "unimplemented",
        "external_state": {"kind": "codex-hook-trust-v1"},
    }
    manifest = release_contract.write_bundle_manifest(
        bundle,
        component="codex",
        dependencies=[],
        install_units=[unit],
        resources=[resource],
    )
    assert manifest["resources"][0]["external_state"] == {
        "kind": "codex-hook-trust-v1"
    }

    resource["source"] = "other-hooks.json"
    try:
        release_contract.write_bundle_manifest(
            bundle,
            component="codex",
            dependencies=[],
            install_units=[unit],
            resources=[resource],
        )
    except ValueError as exc:
        assert "does not match an install unit" in str(exc)
    else:
        raise AssertionError("detached Codex trust resource was accepted")


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
