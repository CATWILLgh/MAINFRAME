#!/usr/bin/env python3
"""Field sets and strategy groups for the release contract."""

import re

IDENTIFIER = re.compile(r"^[a-z][a-z0-9]*(?:[.-][a-z0-9]+)*$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")

BUNDLE_FIELDS_V2 = {
    "schema_version", "kind", "component", "dependencies", "install_units",
    "legacy_artifacts", "resources", "payload_files", "runtime_profile",
    "mcp_projections",
}
HOST_REQUIREMENTS_SCHEMA_VERSION = 3
EXACT_JSON_DOCUMENT_SCHEMA_VERSION = 4
FEATURE_INSTALL_UNIT_SCHEMA_VERSION = 5
MANAGED_FILE_OWNERSHIP_SCHEMA_VERSION = 6
JSON_CLAIM_OWNERSHIP_SCHEMA_VERSION = 7
BUNDLE_REQUIRED_FIELDS = {
    2: BUNDLE_FIELDS_V2,
    HOST_REQUIREMENTS_SCHEMA_VERSION: BUNDLE_FIELDS_V2 | {"host_requirements"},
    EXACT_JSON_DOCUMENT_SCHEMA_VERSION: BUNDLE_FIELDS_V2,
    FEATURE_INSTALL_UNIT_SCHEMA_VERSION: BUNDLE_FIELDS_V2,
    MANAGED_FILE_OWNERSHIP_SCHEMA_VERSION: BUNDLE_FIELDS_V2,
    JSON_CLAIM_OWNERSHIP_SCHEMA_VERSION: BUNDLE_FIELDS_V2,
}
BUNDLE_FIELDS = {
    2: BUNDLE_FIELDS_V2,
    HOST_REQUIREMENTS_SCHEMA_VERSION: BUNDLE_FIELDS_V2 | {"host_requirements"},
    EXACT_JSON_DOCUMENT_SCHEMA_VERSION: BUNDLE_FIELDS_V2 | {"host_requirements"},
    FEATURE_INSTALL_UNIT_SCHEMA_VERSION: BUNDLE_FIELDS_V2 | {"host_requirements"},
    MANAGED_FILE_OWNERSHIP_SCHEMA_VERSION: BUNDLE_FIELDS_V2 | {"host_requirements"},
    JSON_CLAIM_OWNERSHIP_SCHEMA_VERSION: BUNDLE_FIELDS_V2 | {"host_requirements"},
}
INDEX_FIELDS = {"schema_version", "kind", "release_id", "mcp_catalog", "manifests"}
UNIT_REQUIRED_FIELDS = {"id", "kind", "source", "target"}
UNIT_OPTIONAL_FIELDS = {"legacy_source_suffixes"}
UNIT_FEATURE_FIELDS = UNIT_REQUIRED_FIELDS | UNIT_OPTIONAL_FIELDS | {"feature"}
LEGACY_FIELDS = {"target", "target_suffixes"}
RESOURCE_REQUIRED_FIELDS = {"id", "strategy", "target", "observation", "apply"}
RESOURCE_OPTIONAL_FIELDS = {
    "source", "legacy_source_suffixes", "owned_json_pointers", "ownership",
    "external_state",
    "file_ownership",
    "json_ownership",
}
PAYLOAD_FIELDS = {"path", "mode", "size", "sha256"}
ENTRY_FIELDS = {"component", "path", "sha256"}
EXACT_JSON_DOCUMENT_STRATEGY = "exact-json-document"
SOURCE_STRATEGIES = {
    EXACT_JSON_DOCUMENT_STRATEGY, "json-key-merge", "seed-if-absent",
    "shell-line", "shell-line-if-present",
}
SOURCELESS_STRATEGIES = {"ensure-directory", "manual-action"}
OBSERVABLE_STRATEGIES = {
    EXACT_JSON_DOCUMENT_STRATEGY, "ensure-directory", "seed-if-absent",
    "shell-line", "shell-line-if-present",
}
SHELL_STRATEGIES = {"shell-line", "shell-line-if-present"}
EXACT_JSON_DOCUMENT_FORBIDDEN_FIELDS = {
    "external_state", "legacy_source_suffixes", "owned_json_pointers", "ownership",
    "json_ownership",
}
