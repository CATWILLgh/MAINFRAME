#!/usr/bin/env python3
"""Field sets and strategy groups for the release contract."""

BUNDLE_FIELDS_V2 = {
    "schema_version", "kind", "component", "dependencies", "install_units",
    "legacy_artifacts", "resources", "payload_files", "runtime_profile",
    "mcp_projections",
}
HOST_REQUIREMENTS_SCHEMA_VERSION = 3
BUNDLE_FIELDS = {
    2: BUNDLE_FIELDS_V2,
    HOST_REQUIREMENTS_SCHEMA_VERSION: BUNDLE_FIELDS_V2 | {"host_requirements"},
}
INDEX_FIELDS = {"schema_version", "kind", "release_id", "mcp_catalog", "manifests"}
UNIT_REQUIRED_FIELDS = {"id", "kind", "source", "target"}
UNIT_OPTIONAL_FIELDS = {"legacy_source_suffixes"}
LEGACY_FIELDS = {"target", "target_suffixes"}
RESOURCE_REQUIRED_FIELDS = {"id", "strategy", "target", "observation", "apply"}
RESOURCE_OPTIONAL_FIELDS = {
    "source", "legacy_source_suffixes", "owned_json_pointers", "ownership",
    "external_state",
}
PAYLOAD_FIELDS = {"path", "mode", "size", "sha256"}
ENTRY_FIELDS = {"component", "path", "sha256"}
SOURCE_STRATEGIES = {"json-key-merge", "seed-if-absent", "shell-line", "shell-line-if-present"}
SOURCELESS_STRATEGIES = {"ensure-directory", "manual-action"}
OBSERVABLE_STRATEGIES = {
    "ensure-directory", "seed-if-absent", "shell-line", "shell-line-if-present",
}
SHELL_STRATEGIES = {"shell-line", "shell-line-if-present"}
