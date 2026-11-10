"""DSH-only source components must never become legacy native installations."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from installer import codex
from installer.core import Conflict, encode_json, transact
from installer.shared import inventory
from installer.zcode import ZCode

ROOT = Path(__file__).resolve().parents[1]
PLUGINS = {name: f"plugins/dsh/{name}" for name in
           ("activity-analytics", "message-time", "secrets-vault", "session-collaboration")}
ADAPTERS = (
    (codex.Codex, "0.153.4", "cli"),
    (codex.Codex, codex.CURRENT_DESKTOP_RUNTIME, "desktop"),
    (ZCode, "3.11.2.6792", "desktop"),
    (ZCode, "3.17.1.9553", "desktop"),
)


class DshLegacyCompatibilityTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="mainframe-dsh-legacy-")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.source = self.base / "source"
        self.source.mkdir()
        for name in ("instructions", "skills", "agents", "commands", "hooks"):
            shutil.copytree(ROOT / name, self.source / name,
                            ignore=shutil.ignore_patterns("__pycache__"))
        credentials = self.source / "shared/credentials"
        credentials.mkdir(parents=True)
        for name in ("mainframe-secret", "credentials-index.template.md"):
            shutil.copy2(ROOT / "shared/credentials" / name, credentials / name)
        shutil.copy2(ROOT / ".gitignore", self.source)
        manifest = json.loads((ROOT / "ADAPTATION.example.json").read_bytes())
        manifest["components"]["plugins"] = {
            name: {"source": source, "delivery": "pending", "verification": "pending"}
            for name, source in PLUGINS.items()
        }
        for source in PLUGINS.values():
            (self.source / source).mkdir(parents=True)
        self.manifest = self.source / "ADAPTATION.example.json"
        self.manifest.write_bytes(encode_json(manifest))

    def adapter(self, kind, version, surface):
        home = self.base / f"{kind.__name__}-{version}-{surface}"
        home.mkdir()
        adapter = kind(self.source, home, version=version, surface=surface)
        if hasattr(adapter, "clean_event_state"):
            self.addCleanup(adapter.clean_event_state)
        return adapter

    def assert_unsupported_plugins(self, state):
        self.assertEqual(set(state["components"]["plugins"]), set(PLUGINS))
        for name, row in state["components"]["plugins"].items():
            self.assertEqual(row["source"], PLUGINS[name])
            self.assertEqual(row["delivery"], "unsupported")
            self.assertNotIn("verification", row)
            self.assertIn("DSH", row["reason"])
            self.assertIn("not installed", row["reason"])

    def test_every_existing_surface_excludes_plugins_and_converges(self):
        for kind, version, surface in ADAPTERS:
            with self.subTest(product=kind.__name__, version=version, surface=surface):
                adapter = self.adapter(kind, version, surface)
                changes, report = adapter.plan(instructions_reviewed=True)
                self.assertEqual(list(adapter.home.iterdir()), [])
                state = json.loads(next(change.after for change in changes
                                        if change.path == adapter.state_path))
                self.assert_unsupported_plugins(state)
                self.assertFalse(any(change.component.startswith("plugins.") for change in changes))
                for name in PLUGINS:
                    self.assertIn(name, report["unsupported_full_contracts"])
                    self.assertNotIn(name, report["retained_partial_bindings"])
                transact(changes, adapter.journal, adapter.allowed)
                self.assertFalse(any(record["component"].startswith("plugins.")
                                     for record in adapter.receipt()["files"].values()))
                self.assertEqual(adapter.plan(instructions_reviewed=True)[1]["changes"], [])

    def test_old_state_upgrade_preserves_existing_acceptance_and_rejects_false_plugin_acceptance(self):
        for kind, version, surface in ADAPTERS:
            with self.subTest(product=kind.__name__, version=version, surface=surface):
                adapter = self.adapter(kind, version, surface)
                changes, _ = adapter.plan(instructions_reviewed=True)
                transact(changes, adapter.journal, adapter.allowed)
                state = json.loads(adapter.state_path.read_bytes())
                state["components"]["skills"]["mainframe-research"]["verification"] = "passed"
                del state["components"]["plugins"]
                adapter.state_path.write_bytes(encode_json(state))
                changes, _ = adapter.plan(instructions_reviewed=True)
                upgraded = json.loads(next(change.after for change in changes
                                           if change.path == adapter.state_path))
                self.assert_unsupported_plugins(upgraded)
                self.assertEqual(upgraded["components"]["skills"]["mainframe-research"]["verification"], "passed")
                transact(changes, adapter.journal, adapter.allowed)
                # Even a stale prior installed/passed claim cannot override an unsupported mapping.
                for row in upgraded["components"]["plugins"].values():
                    row.update(delivery="installed", verification="passed")
                adapter.state_path.write_bytes(encode_json(upgraded))
                changes, _ = adapter.plan(instructions_reviewed=True)
                corrected = json.loads(next(change.after for change in changes
                                            if change.path == adapter.state_path))
                self.assert_unsupported_plugins(corrected)

    def test_inventory_rejects_missing_unknown_or_redirected_plugins(self):
        source = inventory(self.source)
        self.assertEqual(sum(map(len, source["components"].values())), 56)
        for mutation in ("missing", "unknown", "redirected"):
            with self.subTest(mutation=mutation):
                changed = deepcopy(source)
                plugins = changed["components"]["plugins"]
                if mutation == "missing":
                    del plugins["message-time"]
                elif mutation == "unknown":
                    plugins["unknown-plugin"] = deepcopy(plugins["message-time"])
                else:
                    plugins["message-time"]["source"] = PLUGINS["secrets-vault"]
                self.manifest.write_bytes(encode_json(changed))
                with self.assertRaisesRegex(Conflict, "plugin"):
                    inventory(self.source)

    def test_codex_mapping_admits_only_known_dsh_plugin_sources(self):
        source = json.loads(self.manifest.read_bytes())
        codex._validate_mapping(source)
        for mutation in ("unknown", "unknown-without-source", "redirected"):
            with self.subTest(mutation=mutation):
                changed = deepcopy(source)
                plugins = changed["components"]["plugins"]
                if mutation == "unknown":
                    plugins["unknown-plugin"] = deepcopy(plugins["message-time"])
                elif mutation == "unknown-without-source":
                    plugins["unknown-plugin"] = {}
                else:
                    plugins["message-time"]["source"] = PLUGINS["secrets-vault"]
                with self.assertRaisesRegex(Conflict, "plugin"):
                    codex._validate_mapping(changed)
        for category in ("mcp", "runtime", "settings"):
            with self.subTest(category=category):
                changed = deepcopy(source)
                changed["components"][category]["unmapped"] = {}
                with self.assertRaisesRegex(Conflict, category):
                    codex._validate_mapping(changed)


if __name__ == "__main__":
    unittest.main()
