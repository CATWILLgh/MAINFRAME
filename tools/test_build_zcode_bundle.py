#!/usr/bin/env python3
"""Tier-1 tests for the closed ZCode Desktop release bundle."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent
ADAPTER = REPO / "adapters" / "zcode-desktop"
sys.path.insert(0, str(ADAPTER))
sys.path.insert(0, str(REPO / "tools"))

from release_contract import validate_bundle


def _load_builder():
    path = ADAPTER / "build_bundle.py"
    spec = importlib.util.spec_from_file_location(
        "mainframe_zcode_bundle_test", path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


build_bundle = _load_builder()


def _materialized() -> tuple[Path, dict]:
    output = Path(tempfile.mkdtemp()) / "bundle-v2"
    build_bundle.materialize(REPO, output)
    return output, validate_bundle(output)


def test_bundle_is_closed_and_declares_every_core_surface() -> None:
    output, manifest = _materialized()
    assert manifest["schema_version"] == 8
    assert manifest["component"] == "zcode-desktop"
    assert manifest["dependencies"] == ["credential-tools", "mainframe-cli"]
    assert (output / "AGENTS.md").is_file()
    assert len(list((output / "agents").glob("*.md"))) == 7
    assert len(list((output / "skills").glob("*/SKILL.md"))) == 10
    assert not list((output / "mainframe-agent-methods").glob("*/SKILL.md"))
    assert (output / "gates/mainframe_hook.py").is_file()
    assert (output / "gates/mainframe_runtime.py").is_file()
    assert (output / "gates/detectors/_hooklib.py").is_file()
    assert (output / "gates/rules/frontend-token-storage.yml").is_file()
    agent_units = [
        unit for unit in manifest["install_units"]
        if unit["id"].startswith("zcode-desktop.agents.")
    ]
    assert len(agent_units) == 7
    assert {unit["materialization"] for unit in agent_units} == {"writable-file"}
    assert all(
        "materialization" not in unit
        for unit in manifest["install_units"]
        if not unit["id"].startswith("zcode-desktop.agents.")
    )


def test_hook_config_uses_hidden_cli_launcher_and_claim_scoped_ownership() -> None:
    output, manifest = _materialized()
    config = json.loads((output / "hook-config.json").read_text())
    assert config["hooks"]["enabled"] is True
    assert set(config["hooks"]["events"]) == {
        "SessionStart", "PreToolUse", "PostToolUse", "Stop"
    }
    for event, matchers in config["hooks"]["events"].items():
        hook = matchers[0]["hooks"][0]
        assert hook["command"] == "mainframe"
        assert hook["args"] == ["_zcode-hook", event]

    resource = next(item for item in manifest["resources"] if item["id"] == "zcode-desktop.hooks")
    assert resource["target"] == {"root": "zcode-config", "path": "cli/config.json"}
    ownership = resource["json_ownership"]
    assert ownership["kind"] == "json-claim-registry-v1"
    assert ownership["registry"]["target"] == {
        "root": "zcode-config", "path": "mainframe/config-ownership.json"
    }
    assert [claim["id"] for claim in ownership["claims"]] == sorted(
        claim["id"] for claim in ownership["claims"]
    )
    assert {claim["kind"] for claim in ownership["claims"]} == {
        "exact-scalar", "array-entry"
    }


def test_hook_config_module_ships_inside_gates_for_runtime_import() -> None:
    output, _ = _materialized()
    shipped = output / "gates" / "hook_config.py"
    assert shipped.is_file(), "hook_config.py must ship inside gates/ for mainframe_hook.py to import at runtime"
    bridge = output / "gates" / "mainframe_hook.py"
    bridge_text = bridge.read_text()
    assert "GATES_DIR" in bridge_text and "hook_config.py" in bridge_text, (
        "mainframe_hook.py must resolve hook_config.py via GATES_DIR so the runtime install (~/.zcode/mainframe/gates/) can find it"
    )


def test_projected_runtime_has_no_claude_paths_or_unsealed_links() -> None:
    output, _ = _materialized()
    for path in output.rglob("*"):
        assert not path.is_symlink(), path
        if path.is_file() and path.suffix in {".md", ".py", ".json"}:
            text = path.read_text()
            assert "~/.claude" not in text, path
            assert "dist/claude-code" not in text, path
