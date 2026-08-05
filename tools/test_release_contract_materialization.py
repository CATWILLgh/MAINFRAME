#!/usr/bin/env python3
"""Writable-file materialization tests for the release contract."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import release_contract
from test_release_contract import _bundle


def test_install_unit_materialization_accepts_symlink_and_writable_file():
    root = Path(tempfile.mkdtemp())
    bundle = _bundle(root, "credential-tools", "credentials-config")
    manifest_path = bundle / "bundle.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["schema_version"] = 8
    manifest["install_units"][0]["materialization"] = "writable-file"
    manifest["install_units"][1]["materialization"] = "symlink"
    manifest_path.write_text(json.dumps(manifest) + "\n")

    validated = release_contract.validate_bundle(bundle)

    assert validated["install_units"][0]["materialization"] == "writable-file"
    assert validated["install_units"][1]["materialization"] == "symlink"


def test_install_unit_materialization_rejects_invalid_and_writable_tree():
    for value, unit_index in (("copy", 0), ("writable-file", 1)):
        root = Path(tempfile.mkdtemp())
        bundle = _bundle(root, "credential-tools", "credentials-config")
        manifest_path = bundle / "bundle.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["schema_version"] = 8
        manifest["install_units"][unit_index]["materialization"] = value
        manifest_path.write_text(json.dumps(manifest) + "\n")

        try:
            release_contract.validate_bundle(bundle)
        except ValueError as error:
            assert "materialization" in str(error)
        else:
            raise AssertionError(f"materialization {value!r} was accepted")


def test_materialization_field_requires_schema_eight():
    for value in ("", "symlink", "writable-file"):
        root = Path(tempfile.mkdtemp())
        bundle = _bundle(root, "credential-tools", "credentials-config")
        manifest_path = bundle / "bundle.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["schema_version"] = 7
        manifest["install_units"][0]["materialization"] = value
        manifest_path.write_text(json.dumps(manifest) + "\n")

        try:
            release_contract.validate_bundle(bundle)
        except ValueError as error:
            assert "materialization" in str(error)
        else:
            raise AssertionError(f"schema 7 accepted materialization {value!r}")
