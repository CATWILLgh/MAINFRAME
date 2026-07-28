#!/usr/bin/env python3
"""Tests for immutable release bundle publication modes."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))

import release_contract


def test_seal_bundle_seals_nested_file_named_bundle_json():
    bundle = Path(tempfile.mkdtemp())
    nested = bundle / "nested/bundle.json"
    nested.parent.mkdir()
    nested.write_text('{"payload":true}\n')
    release_contract.write_bundle_manifest(
        bundle,
        component="credential-tools",
        dependencies=[],
        install_units=[],
        resources=[],
    )

    release_contract.seal_bundle(bundle)

    assert nested.stat().st_mode & 0o222 == 0
    release_contract.validate_bundle(bundle)
