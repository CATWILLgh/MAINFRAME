"""Contract tests for the pinned ZCode Desktop adapter surface."""

import copy
import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT / "adapters" / "zcode-desktop"
COMPATIBILITY = ADAPTER / "compatibility.py"
CAPABILITIES = ADAPTER / "capabilities.json"
OWNERSHIP = ADAPTER / "config_ownership.json"
HOOK_EVENTS = {
    "SessionStart",
    "UserPromptSubmit",
    "PreToolUse",
    "PermissionRequest",
    "PostToolUse",
    "PostToolUseFailure",
    "Stop",
}
CORE_HOOK_EVENTS = {"SessionStart", "PreToolUse", "PostToolUse", "Stop"}


def _load_module():
    spec = importlib.util.spec_from_file_location("zcode_compatibility", COMPATIBILITY)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load ZCode compatibility module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ZCodeContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = _load_module()
        cls.capabilities = json.loads(CAPABILITIES.read_text(encoding="utf-8"))
        cls.ownership = json.loads(OWNERSHIP.read_text(encoding="utf-8"))

    def test_contracts_match_strict_schema(self):
        self.module.validate_capability_contract(self.capabilities)
        self.module.validate_ownership_manifest(self.ownership)

        invalid = copy.deepcopy(self.capabilities)
        invalid["unexpected"] = True
        with self.assertRaisesRegex(ValueError, "unknown fields"):
            self.module.validate_capability_contract(invalid)

    def test_host_and_user_roots_are_pinned(self):
        self.assertEqual(
            self.capabilities["host"],
            {
                "app_name": "ZCode Desktop",
                "app_version": "3.7.3",
                "app_build": "3.7.3.4573",
                "bundle_id": "dev.zcode.app",
                "cli_version": "0.16.1",
                "cli_path": "/Applications/ZCode.app/Contents/Resources/glm/zcode.cjs",
            },
        )

    def test_managed_host_requirement_matches_the_pinned_desktop(self):
        self.assertEqual(
            self.module.managed_host_requirements(),
            [
                {
                    "kind": "darwin-application-bundle-v1",
                    "bundle_identifier": "dev.zcode.app",
                    "exact_versions": ["3.7.3"],
                }
            ],
        )
        self.assertEqual(
            set(self.capabilities["user_roots"]),
            {
                "~/.zcode/AGENTS.md",
                "~/.zcode/skills",
                "~/.zcode/commands",
                "~/.zcode/agents",
                "~/.zcode/cli/config.json",
            },
        )

    def test_capabilities_classify_stable_beta_and_optional_surfaces(self):
        capabilities = self.capabilities["capabilities"]
        self.assertEqual(
            {item["status"] for item in capabilities.values()},
            {"stable", "beta", "optional"},
        )
        for capability_id, item in capabilities.items():
            self.assertEqual(
                set(item),
                {"status", "scope", "activation", "evidence", "required_for_core"},
                capability_id,
            )
        self.assertEqual(capabilities["mcp_servers"]["status"], "optional")
        self.assertEqual(capabilities["mcp_servers"]["activation"], "deferred-v1.1")
        self.assertEqual(capabilities["agents"]["status"], "beta")
        self.assertTrue(capabilities["agents"]["required_for_core"])
        self.assertIn("no safe native list command", capabilities["agents"]["evidence"])

    def test_hook_capability_lists_only_supported_events(self):
        hooks = self.capabilities["capabilities"]["hooks"]
        self.assertEqual(set(hooks["scope"]), HOOK_EVENTS)

    def test_ownership_claims_only_scalar_or_matching_entries(self):
        entries = self.ownership["entries"]
        self.assertEqual({entry["file"] for entry in entries}, {"~/.zcode/cli/config.json"})
        self.assertEqual(
            {entry["json_pointer"] for entry in entries if entry["claim_type"] == "scalar"},
            {"/hooks/enabled"},
        )
        hook_entries = [entry for entry in entries if entry["claim_type"] == "matching-array-entry"]
        self.assertEqual(
            {entry["json_pointer"] for entry in hook_entries},
            {f"/hooks/events/{event}" for event in CORE_HOOK_EVENTS},
        )
        for entry in hook_entries:
            event = entry["json_pointer"].rsplit("/", 1)[1]
            self.assertEqual(
                entry["selector"],
                {"pointer": "/hooks/0/args/1", "value": event},
            )
            self.assertEqual(entry["activation_class"], "core-required")

        claimed = {entry["json_pointer"] for entry in entries}
        self.assertTrue(
            claimed.isdisjoint({"", "/hooks", "/hooks/events", "/mcp", "/mcp/servers"})
        )

    def test_mcp_ownership_is_deferred_to_v1_1_and_name_scoped(self):
        entry = next(item for item in self.ownership["entries"] if item["id"] == "mcp_server")
        self.assertEqual(entry["json_pointer"], "/mcp/servers/mainframe-context7")
        self.assertEqual(entry["lifecycle"], "deferred-v1.1")
        self.assertEqual(entry["activation_class"], "selected-v1.1")


if __name__ == "__main__":
    unittest.main()
