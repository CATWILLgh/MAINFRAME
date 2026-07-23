#!/usr/bin/env python3
"""Build the unlinked, self-contained Codex bundle-v2 projection."""

from __future__ import annotations

import argparse
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[2] / "tools"
sys.path.insert(0, str(TOOLS))

from adapter_profiles import load_profiles, project_text
from bundle_sync import (
    copy_regular_file,
    prepare_output_root,
    source_files,
    sync_tree,
    write_text_file,
)
from bundle_publication import publish_bundle
from detector_projection import project_hooklib_fallbacks
from feedback_projection import project_adapter_feedback_skill
import build_codex
from release_contract import validate_bundle, write_bundle_manifest
from release_contract_fields import FEATURE_INSTALL_UNIT_SCHEMA_VERSION
from release_diagnostics import copy_diagnostics, diagnostics_resource


CODEX_CONFIG_EXPRESSION = (
    'os.environ.get("CODEX_HOME") or os.path.expanduser("~/.codex")'
)
CODEX_BUNDLE_ENTRIES = {
    "AGENTS.md",
    "agents",
    "bundle.json",
    "credentials-index.md",
    "diagnostics.json",
    "gates",
    "hooks.json",
    "mainframe-hook.sh",
    "rules",
    "skills",
}


def _unit(
    identifier: str,
    kind: str,
    source: str,
    target: str,
    legacy: list[str] | None = None,
    feature: str | None = None,
) -> dict:
    unit = {
        "id": identifier,
        "kind": kind,
        "source": source,
        "target": {"root": "codex-config", "path": target},
    }
    if legacy:
        unit["legacy_source_suffixes"] = sorted(legacy)
    if feature is not None:
        unit["feature"] = feature
    return unit


def _gate_units(root: Path) -> list[dict]:
    units = []
    for group in ("detectors", "rules"):
        for relative in source_files(root / f"core/gates/{group}"):
            path = f"gates/{group}/{relative.as_posix()}"
            identifier = f"codex.gates.{group}.{relative.as_posix()}"
            units.append(_unit(identifier, "file", path, path))
    return units


def _install_units(root: Path, skills, agents) -> list[dict]:
    units = [
        _unit(
            "codex.dev.harness-feedback",
            "tree",
            "skills/harness-feedback",
            "skills/harness-feedback",
            feature="dev.harness-feedback",
        ),
        _unit(
            "codex.instructions",
            "file",
            "AGENTS.md",
            "AGENTS.md",
            ["dist/codex/AGENTS.md"],
        ),
        _unit(
            "codex.hooks",
            "file",
            "hooks.json",
            "hooks.json",
            ["dist/codex/hooks.json"],
        ),
        _unit(
            "codex.launcher",
            "file",
            "mainframe-hook.sh",
            "mainframe-hook.sh",
            ["dist/codex/mainframe-hook.sh"],
        ),
        _unit(
            "codex.rules",
            "file",
            "rules/mainframe.rules",
            "rules/mainframe.rules",
            ["dist/codex/rules/mainframe.rules"],
        ),
    ]
    units.extend(
        _unit(
            f"codex.skills.{name}",
            "tree",
            f"skills/{name}",
            f"skills/{name}",
            [f"dist/codex/skills/{name}"],
        )
        for name, _ in skills
    )
    units.extend(
        _unit(
            f"codex.agents.{name}",
            "file",
            f"agents/{name}.toml",
            f"agents/{name}.toml",
            [f"dist/codex/agents/{name}.toml"],
        )
        for name, _ in agents
    )
    units.extend(_gate_units(root))
    return units


def _resources() -> list[dict]:
    supported = {"observation": "supported", "apply": "unimplemented"}
    return [
        {
            "id": "codex.credentials-index",
            "strategy": "seed-if-absent",
            "source": "credentials-index.md",
            "target": {
                "root": "codex-config",
                "path": "credentials-index.md",
            },
            **supported,
        },
        diagnostics_resource("codex"),
        {
            "id": "codex.hook-trust",
            "strategy": "manual-action",
            "source": "hooks.json",
            "target": {"root": "codex-config", "path": "hooks.json"},
            "observation": "supported",
            "apply": "unimplemented",
            "external_state": {"kind": "codex-hook-trust-v1"},
        },
    ]


def _mcp_projections() -> list[dict]:
    return [{
        "id": "codex.mcp.context7",
        "codec": "codex-user-http-v1",
        "server": "context7",
        "profile": "remote-keyless",
        "target": {"root": "codex-config", "path": "config.toml"},
        "map_pointer": "/mcp_servers",
        "entry_key": "context7",
        "registry": {
            "target": {
                "root": "codex-config",
                "path": "mainframe/mcp-ownership.json",
            },
            "schema_version": 1,
            "entries_pointer": "/servers",
        },
    }]


def _validate_sources(root: Path) -> None:
    for relative in (
        "core/skills",
        "core/agents",
        "core/gates/detectors",
        "core/gates/rules",
        "dev/harness-feedback-plugin/skills/harness-feedback",
    ):
        source_files(root / relative)
    for relative in (
        "core/permissions/rules.json",
        "dist/codex/AGENTS.md",
        "adapters/codex/gates/bundle-hook.sh",
        "core/resources/credentials-index.md",
    ):
        source = root / relative
        if source.is_symlink() or not source.is_file():
            raise ValueError(f"bundle source must be a regular file: {source}")


def _render_inputs(root: Path, profile, validate_native: bool):
    skills, _ = build_codex.collect_skills(root, profile)
    agents = build_codex.collect_agents(root)
    projected, _ = build_codex.project_permissions(build_codex._load_rules(root))
    rules_text = build_codex.render_rules(projected)
    build_codex._validate_gate_detectors(root)
    if validate_native:
        build_codex.validate_rules_native(rules_text)
    return skills, agents, rules_text, build_codex.render_hooks_json()


def _project_gates(root: Path, output: Path, profile) -> None:
    sync_tree(root / "core/gates/detectors", output / "detectors")
    sync_tree(root / "core/gates/rules", output / "rules")
    feedback = f'os.path.join({CODEX_CONFIG_EXPRESSION}, "skills", "harness-feedback")'
    telemetry = (
        f'os.path.join({CODEX_CONFIG_EXPRESSION}, "mainframe", '
        '"telemetry", "telemetry.db")'
    )
    diagnostics = (
        f'os.path.join({CODEX_CONFIG_EXPRESSION}, "mainframe", '
        '"diagnostics.json")'
    )
    for detector in sorted((output / "detectors").rglob("*.py")):
        projected = detector.read_text()
        if detector.name == "_hooklib.py":
            projected = project_hooklib_fallbacks(
                projected,
                detector,
                feedback=feedback,
                telemetry=telemetry,
                diagnostics=diagnostics,
            )
        projected = projected.replace(
            "~/.claude/hooks/path-validation.py",
            f"{profile.detectors_root}/path-validation.py",
        ).replace("~/.claude/", f"{profile.config_root}/")
        if "~/.claude/" in projected:
            raise ValueError(
                f"projected Codex detector retains a Claude path: {detector}"
            )
        write_text_file(detector, projected)


def _stage_bundle(
    root: Path,
    staged: Path,
    profile,
    skills,
    agents,
    rules_text: str,
    hooks_text: str,
) -> None:
    _project_gates(root, staged / "gates", profile)
    build_codex.write_skills(staged / "skills", skills)
    project_adapter_feedback_skill(
        root / "dev/harness-feedback-plugin/skills/harness-feedback",
        staged / "skills/harness-feedback",
        "codex",
    )
    build_codex._write_agents(staged / "agents", agents)
    write_text_file(staged / "rules/mainframe.rules", rules_text)
    write_text_file(staged / "hooks.json", hooks_text)
    copy_regular_file(root / "dist/codex/AGENTS.md", staged / "AGENTS.md")
    copy_regular_file(
        root / "adapters/codex/gates/bundle-hook.sh",
        staged / "mainframe-hook.sh",
        executable=True,
    )
    write_text_file(
        staged / "credentials-index.md",
        project_text(
            (root / "core/resources/credentials-index.md").read_text(), profile
        ),
    )
    copy_diagnostics(root, staged)
    write_bundle_manifest(
        staged,
        component="codex",
        dependencies=["credential-tools", "mainframe-cli"],
        install_units=_install_units(root, skills, agents),
        resources=_resources(),
        runtime_profile=asdict(profile),
        mcp_projections=_mcp_projections(),
        schema_version=FEATURE_INSTALL_UNIT_SCHEMA_VERSION,
    )


def materialize(
    root: Path,
    output: Path,
    *,
    validate_native: bool = False,
) -> None:
    """Materialize all immutable Codex delivery without user-state I/O."""
    if output.is_symlink() or (output.exists() and not output.is_dir()):
        raise ValueError(f"bundle output must be a real directory: {output}")
    _validate_sources(root)
    profile = load_profiles(root)["codex"]
    inputs = _render_inputs(root, profile, validate_native)
    prepare_output_root(output, CODEX_BUNDLE_ENTRIES)
    _stage_bundle(root, output, profile, *inputs)


def build(root: Path, output: Path, *, validate_native: bool = False) -> None:
    """Atomically publish a validated Codex bundle."""
    if output.is_symlink() or (output.exists() and not output.is_dir()):
        raise ValueError(f"bundle output must be a real directory: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    publish_bundle(
        output,
        lambda staged: materialize(
            root,
            staged,
            validate_native=validate_native,
        ),
        validate_bundle,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--validate-native", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    if args.dry_run:
        with tempfile.TemporaryDirectory() as temporary:
            build(
                root,
                Path(temporary) / "bundle-v2",
                validate_native=args.validate_native,
            )
        print("validated Codex bundle without publishing")
        return 0
    output = args.output or root / "dist/codex/bundle-v2"
    build(root, output, validate_native=args.validate_native)
    print(f"wrote Codex bundle to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
