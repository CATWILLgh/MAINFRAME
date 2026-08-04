#!/usr/bin/env python3
"""Build the closed, unactivated ZCode Desktop release bundle."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import tempfile
from pathlib import Path


TOOLS = Path(__file__).resolve().parents[2] / "tools"
sys.path.insert(0, str(TOOLS))

from bundle_publication import publish_bundle
from bundle_sync import (
    copy_regular_file,
    prepare_output_root,
    sync_tree,
    write_text_file,
)
from detector_projection import project_hooklib_fallbacks
from release_contract import validate_bundle, write_bundle_manifest
from release_contract_fields import JSON_CLAIM_OWNERSHIP_SCHEMA_VERSION
from release_diagnostics import copy_diagnostics, diagnostics_resource


def _load_local_module(name: str, filename: str):
    path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValueError(f"cannot load ZCode module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


build_zcode = _load_local_module("mainframe_zcode_projection", "build_zcode.py")
compatibility = _load_local_module("mainframe_zcode_compatibility", "compatibility.py")
hook_config = _load_local_module("mainframe_zcode_hook_config", "hook_config.py")


DEFAULT_BUNDLE_PATH = Path("dist/zcode-desktop/bundle-v2")
BUNDLE_ENTRIES = {
    "AGENTS.md",
    "agents",
    "bundle.json",
    "diagnostics.json",
    "hook-config.json",
    "gates",
    "mainframe-agent-methods",
    "skills",
}
ZCODE_ROOT_EXPRESSION = (
    'os.environ.get("ZCODE_STORAGE_DIR") or os.path.expanduser("~/.zcode")'
)
DETECTOR_SUPPORT = frozenset({
    "_diagnostics.py",
    "_hooklib.py",
    "_markers.py",
    "comment_extract.py",
})


def _unit(identifier: str, kind: str, source: str, target: str) -> dict:
    return {
        "id": identifier,
        "kind": kind,
        "source": source,
        "target": {"root": "zcode-config", "path": target},
    }


def _install_units(files: dict[Path, bytes]) -> list[dict]:
    units = [_unit("zcode-desktop.instructions", "file", "AGENTS.md", "AGENTS.md")]
    for name in sorted(path.name for path in files if path.parent == Path("agents")):
        units.append(_unit(
            f"zcode-desktop.agents.{Path(name).stem}",
            "file", f"agents/{name}", f"agents/{name}",
        ))
    public = sorted({path.parts[1] for path in files if path.parts[0] == "skills"})
    private = sorted({
        path.parts[1]
        for path in files
        if path.parts[0] == build_zcode.PRIVATE_METHODS_DIR
    })
    units.extend(
        _unit(f"zcode-desktop.skills.{name}", "tree", f"skills/{name}", f"skills/{name}")
        for name in public
    )
    units.extend(
        _unit(
            f"zcode-desktop.private-methods.{name}", "tree",
            f"{build_zcode.PRIVATE_METHODS_DIR}/{name}",
            f"{build_zcode.PRIVATE_METHODS_DIR}/{name}",
        )
        for name in private
    )
    units.append(_unit(
        "zcode-desktop.gates", "tree", "gates", "mainframe/gates"
    ))
    return units


def _hook_document() -> dict:
    return {
        "hooks": {
            "enabled": True,
            "events": hook_config.render_cli_hook_events(),
        }
    }


def _hook_claims() -> list[dict]:
    claims = [{
        "id": "hooks-enabled",
        "kind": "exact-scalar",
        "pointer": "/hooks/enabled",
    }]
    for event in hook_config.CORE_EVENT_DETECTORS:
        claims.append({
            "id": f"hook-{_kebab(event)}",
            "kind": "array-entry",
            "pointer": f"/hooks/events/{event}",
            "selector": {
                "pointer": "/hooks/0/args/1",
                "value": event,
            },
        })
    return sorted(claims, key=lambda claim: claim["id"])


def _kebab(value: str) -> str:
    result = []
    for index, character in enumerate(value):
        if character.isupper() and index:
            result.append("-")
        result.append(character.lower())
    return "".join(result)


def _resources() -> list[dict]:
    return [
        diagnostics_resource("zcode-desktop"),
        {
            "id": "zcode-desktop.hooks",
            "strategy": "json-key-merge",
            "source": "hook-config.json",
            "target": {"root": "zcode-config", "path": "cli/config.json"},
            "observation": "supported",
            "apply": "supported",
            "json_ownership": {
                "kind": "json-claim-registry-v1",
                "registry": {
                    "target": {
                        "root": "zcode-config",
                        "path": "mainframe/config-ownership.json",
                    },
                    "schema_version": 1,
                },
                "claims": _hook_claims(),
            },
        },
    ]


def _write_projection(root: Path, output: Path) -> dict[Path, bytes]:
    files = build_zcode.render_projection(root)
    for relative, content in files.items():
        destination = output / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
    return files


def _project_gates(root: Path, output: Path) -> None:
    detectors = output / "detectors"
    detectors.mkdir(parents=True, exist_ok=True)
    detector_names = DETECTOR_SUPPORT | {
        name
        for names in hook_config.CORE_EVENT_DETECTORS.values()
        for name in names
    }
    for name in sorted(detector_names):
        copy_regular_file(
            root / "core/gates/detectors" / name,
            detectors / name,
        )
    sync_tree(root / "core/gates/rules", output / "rules")
    for name in ("__init__.py", "mainframe_hook.py", "mainframe_runtime.py"):
        copy_regular_file(
            root / "adapters/zcode-desktop/gates" / name,
            output / name,
        )
    feedback = f'os.path.join({ZCODE_ROOT_EXPRESSION}, "skills", "harness-feedback")'
    telemetry = (
        f'os.path.join({ZCODE_ROOT_EXPRESSION}, "mainframe", "telemetry", "telemetry.db")'
    )
    diagnostics = f'os.path.join({ZCODE_ROOT_EXPRESSION}, "mainframe", "diagnostics.json")'
    for detector in sorted(detectors.rglob("*.py")):
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
            "~/.zcode/mainframe/gates/detectors/path-validation.py",
        ).replace(
            "dist/claude-code/plugin/hooks/scripts/",
            "~/.zcode/mainframe/gates/detectors/",
        ).replace("~/.claude/", "~/.zcode/")
        if "~/.claude" in projected or "dist/claude-code" in projected:
            raise ValueError(f"projected ZCode detector retains a Claude path: {detector}")
        write_text_file(detector, projected)


def materialize(root: Path, output: Path) -> None:
    root = root.resolve(strict=True)
    prepare_output_root(output, BUNDLE_ENTRIES)
    files = _write_projection(root, output)
    _project_gates(root, output / "gates")
    write_text_file(
        output / "hook-config.json",
        json.dumps(_hook_document(), indent=2, sort_keys=True) + "\n",
    )
    copy_diagnostics(root, output)
    write_bundle_manifest(
        output,
        component="zcode-desktop",
        dependencies=["credential-tools", "mainframe-cli"],
        install_units=_install_units(files),
        resources=_resources(),
        runtime_profile={"config_root": "~/.zcode"},
        schema_version=JSON_CLAIM_OWNERSHIP_SCHEMA_VERSION,
        host_requirements=compatibility.managed_host_requirements(),
    )


def build(root: Path, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    publish_bundle(output, lambda staged: materialize(root, staged), validate_bundle)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    if args.dry_run:
        with tempfile.TemporaryDirectory() as temporary:
            build(root, Path(temporary) / "bundle-v2")
        print("validated ZCode Desktop bundle without publishing")
        return 0
    output = args.output or root / DEFAULT_BUNDLE_PATH
    build(root, output)
    print(f"wrote ZCode Desktop bundle to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
