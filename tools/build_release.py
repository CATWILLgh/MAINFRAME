#!/usr/bin/env python3
"""Build one immutable, indexed MAINFRAME release directory."""

from __future__ import annotations

import argparse
import importlib.util
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

from bundle_sync import copy_regular_file, write_text_file
from mcp_catalog_contract import CATALOG_RELEASE_PATH
from release_contract import (
    seal_bundle,
    validate_bundle,
    validate_release,
    write_bundle_manifest,
    write_release_index,
)
from release_contract_io import seal_release_files
from release_secret_projection import project_release_secret_guidance


def _load_builder(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValueError(f"cannot load bundle builder: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(path.parent))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    return module


def _credential_resources() -> list[dict]:
    lifecycle = {"observation": "supported", "apply": "supported"}
    return [
        {
            "id": "credential-tools.secrets-store",
            "strategy": "seed-if-absent",
            "source": "secrets.env",
            "target": {"root": "credentials-config", "path": "secrets.env"},
            "file_ownership": {
                "kind": "managed-file-registry-v1",
                "registry": {
                    "target": {
                        "root": "credentials-config",
                        "path": "mainframe/file-ownership.json",
                    },
                    "schema_version": 1,
                },
            },
            **lifecycle,
        },
    ]


def _build_credential_tools(root: Path, output: Path) -> None:
    output.mkdir(parents=True)
    copy_regular_file(
        root / "core/resources/credential-tools/secret-release",
        output / "secret",
        executable=True,
    )
    write_text_file(output / "secrets.env", "")
    (output / "secrets.env").chmod(0o600)
    write_bundle_manifest(
        output,
        component="credential-tools",
        dependencies=["mainframe-cli"],
        install_units=[
            {
                "id": "credential-tools.secret",
                "kind": "file",
                "source": "secret",
                "target": {"root": "user-bin", "path": "secret"},
                "legacy_source_suffixes": [
                    "dist/claude-code/scripts/secret",
                    "export/scripts/secret",
                ],
            }
        ],
        resources=_credential_resources(),
    )


def _build_cli(root: Path, output: Path) -> None:
    output.mkdir(parents=True)
    binary = output / "mainframe"
    _build_go_binary(root, binary, "./cmd/mainframe")
    write_bundle_manifest(
        output,
        component="mainframe-cli",
        dependencies=[],
        install_units=[
            {
                "id": "mainframe-cli.binary",
                "kind": "file",
                "source": "mainframe",
                "target": {"root": "user-bin", "path": "mainframe"},
            }
        ],
        resources=[],
    )


def _build_go_binary(root: Path, binary: Path, package: str) -> None:
    result = subprocess.run(
        [
            "go",
            "build",
            "-trimpath",
            "-buildvcs=false",
            "-o",
            str(binary),
            package,
        ],
        cwd=root,
        text=True,
        capture_output=True,
        timeout=180,
    )
    if result.returncode != 0:
        raise ValueError(f"build {package} binary: {result.stderr.strip()}")
    binary.chmod(0o755)


def _build_staged(root: Path, staging: Path, release_id: str) -> None:
    builders = {
        "antigravity-2": _load_builder(
            "mainframe_antigravity_bundle",
            root / "adapters/antigravity-2/build_bundle.py",
        ),
        "claude-code": _load_builder(
            "mainframe_claude_bundle",
            root / "adapters/claude-code/build_bundle.py",
        ),
        "codex": _load_builder(
            "mainframe_codex_bundle", root / "adapters/codex/build_bundle.py"
        ),
        "opencode": _load_builder(
            "mainframe_opencode_bundle",
            root / "adapters/opencode/build_bundle.py",
        ),
    }
    manifests = []
    for component, builder in builders.items():
        bundle = staging / "bundles" / component
        builder.materialize(root, bundle)
        manifests.append(bundle / "bundle.json")
    credentials = staging / "common/credential-tools"
    _build_credential_tools(root, credentials)
    manifests.append(credentials / "bundle.json")
    cli = staging / "bin"
    _build_cli(root, cli)
    manifests.append(cli / "bundle.json")
    for manifest in manifests:
        validate_bundle(manifest.parent)
    project_release_secret_guidance(staging)
    for manifest in manifests:
        seal_bundle(manifest.parent)
        validate_bundle(manifest.parent)
    mcp_catalog = staging / CATALOG_RELEASE_PATH
    copy_regular_file(root / "internal/mcpcatalog/catalog.json", mcp_catalog)
    write_release_index(
        staging,
        release_id=release_id,
        mcp_catalog=mcp_catalog,
        manifests=manifests,
    )
    validate_release(staging)


def _make_tree_removable(root: Path) -> None:
    if not root.exists():
        return
    for path in [root, *root.rglob("*")]:
        if path.is_dir():
            path.chmod(stat.S_IMODE(path.stat().st_mode) | 0o700)


def build(root: Path, output: Path, *, release_id: str) -> None:
    """Stage, validate, and publish a new immutable release directory."""
    root = root.resolve()
    output = output.absolute()
    if output.exists() or output.is_symlink():
        raise ValueError(f"release destination must not already exist: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=f".{output.name}.staging-", dir=output.parent)
    )
    try:
        _build_staged(root, staging, release_id)
        seal_release_files(staging)
        os.replace(staging, output)
    finally:
        if staging.exists():
            _make_tree_removable(staging)
            shutil.rmtree(staging)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parent.parent
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--release-id", required=True)
    args = parser.parse_args(argv)
    build(args.root, args.output, release_id=args.release_id)
    print(f"wrote MAINFRAME release to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
