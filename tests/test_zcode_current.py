"""Current Desktop delivery and exact native post-edit attribution fixtures."""
from copy import deepcopy
import io
import importlib.util
import json
from pathlib import Path
import plistlib
import shutil
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from installer import zcode_hook
from installer.core import Conflict, encode_json, transact
from installer.runtime import CODE_QUALITY_TOOLS, FALLOW_TOOLS
from installer.zcode import ZCode, FULL_MAPPING_RUNTIMES

ROOT = Path(__file__).resolve().parents[1]
CURRENT = "3.17.1.9553"
FALLOW = "mainframe-fallow-quality"


class CurrentZCodeInstallationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="mainframe-zcode-current-")
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name).resolve()
        self.root, self.home = base / "source", base / "home"
        self.root.mkdir(); self.home.mkdir()
        for name in ("instructions", "skills", "agents", "commands", "hooks", "plugins", "installer"):
            shutil.copytree(ROOT / name, self.root / name, ignore=shutil.ignore_patterns("__pycache__"))
        credentials = self.root / "shared/credentials"
        credentials.mkdir(parents=True)
        for name in ("mainframe-secret", "credentials-index.template.md"):
            shutil.copyfile(ROOT / "shared/credentials" / name, credentials / name)
        for name in ("ADAPTATION.example.json", ".gitignore", "install.py"):
            shutil.copyfile(ROOT / name, self.root / name)
        self.adapter = ZCode(self.root, self.home, version=CURRENT)

    def test_current_full_delivery_maps_every_component_and_converges(self):
        self.assertIn(CURRENT, FULL_MAPPING_RUNTIMES)
        from installer.zcode import runtime_tools
        self.assertEqual(runtime_tools(CURRENT, "desktop"), CODE_QUALITY_TOOLS + FALLOW_TOOLS)
        self.assertEqual(runtime_tools("unknown", "desktop"), CODE_QUALITY_TOOLS)
        changes, report = self.adapter.plan()
        transact(changes, self.adapter.journal, self.adapter.allowed)
        self.assertEqual(self.adapter.plan()[0], [])
        self.assertTrue((self.adapter.hooks / "detectors" / (FALLOW + ".py")).is_file())
        cfg = json.loads(self.adapter.config.read_bytes())
        callbacks = [hook for group in cfg["hooks"]["events"]["PostToolUse"] for hook in group["hooks"]]
        self.assertEqual(sum(hook["args"][-2] == FALLOW for hook in callbacks), 1)
        self.assertNotIn("SubagentStop", cfg["hooks"]["events"])
        state = json.loads(self.adapter.state_path.read_bytes())
        rows = [row for group in state["components"].values() for row in group.values()]
        source = json.loads((self.root / "ADAPTATION.example.json").read_text())
        self.assertEqual(
            {category: set(entries) for category, entries in state["components"].items()},
            {category: set(entries) for category, entries in source["components"].items()},
        )
        self.assertFalse(any(row["delivery"] == "pending" for row in rows))
        selection = state["components"]["hooks"]["mainframe-subagent-selection"]
        self.assertEqual(selection["delivery"], "unsupported")
        self.assertIn("both", selection["reason"])
        self.assertIn(FALLOW, report["retained_partial_bindings"])
        self.assertIn("Primary", report["hook_scope"])

    def test_newer_desktop_is_admitted_only_for_the_selected_skill(self):
        changes, _ = self.adapter.plan()
        transact(changes, self.adapter.journal, self.adapter.allowed)
        target = self.adapter.skills / "mainframe-openspec/SKILL.md"
        target.unlink()
        config = self.adapter.config.read_bytes()
        self.adapter.version = "3.17.2.9661"
        changes, report = self.adapter.plan_skill("mainframe-openspec")
        self.assertEqual({row["path"] for row in report["changes"]},
                         {str(target), str(self.adapter.state_path)})
        transact(changes, self.adapter.journal, self.adapter.allowed)
        self.assertEqual(target.read_bytes(), (self.root / "skills/mainframe-openspec/SKILL.md").read_bytes())
        self.assertEqual(self.adapter.config.read_bytes(), config)
        self.assertEqual(self.adapter.plan_skill("mainframe-openspec")[1]["changes"], [])

    def test_current_upgrade_preserves_role_settings_and_native_disables(self):
        self.adapter.version = "3.14.4.7912"
        changes, _ = self.adapter.plan()
        transact(changes, self.adapter.journal, self.adapter.allowed)
        role = self.adapter.agents / "mainframe-researcher.md"
        role.write_bytes(role.read_bytes().replace(b"name: mainframe-researcher\n", b'name: mainframe-researcher\nmodel: "specific/provider-model"\nthoughtLevel: high\ncolor: blue\ninjectAgentsMd: false\n'))
        cfg = json.loads(self.adapter.config.read_bytes()); cfg["user"] = {"preserve": True}
        cfg["hooks"]["enabled"] = False
        cfg["hooks"]["events"]["PreToolUse"][0]["hooks"][0]["enabled"] = False
        self.adapter.config.write_bytes(encode_json(cfg))
        self.adapter.version = CURRENT
        changes, _ = self.adapter.plan()
        transact(changes, self.adapter.journal, self.adapter.allowed)
        current = json.loads(self.adapter.config.read_bytes())
        self.assertFalse(current["hooks"]["enabled"])
        self.assertFalse(current["hooks"]["events"]["PreToolUse"][0]["hooks"][0]["enabled"])
        self.assertEqual(current["user"], {"preserve": True})
        for value in (b"specific/provider-model", b"thoughtLevel: high", b"color: blue", b"injectAgentsMd: false"):
            self.assertIn(value, role.read_bytes())
        self.assertEqual(self.adapter.plan()[0], [])

    def test_entrypoint_full_routes_require_fallow_and_enable_infers_receipted_binding(self):
        specification = importlib.util.spec_from_file_location("mainframe_zcode_current_entrypoint", self.root / "install.py")
        entrypoint = importlib.util.module_from_spec(specification)
        specification.loader.exec_module(entrypoint)
        options = ["--home", str(self.home), "--surface", "desktop", "--runtime-version", CURRENT]
        required = CODE_QUALITY_TOOLS + FALLOW_TOOLS
        package_tools = (*required, "openspec")
        ready = {"ready": True, "required": list(package_tools), "missing": []}
        with (patch.object(Path, "cwd", return_value=self.root),
              patch.object(entrypoint, "ensure_runtime", return_value=ready) as ensure,
              patch.object(entrypoint, "runtime_status", return_value=ready) as status,
              patch("sys.stdout", new_callable=io.StringIO)):
            self.assertEqual(entrypoint.main(["zcode", "plan", *options]), 0)
            status.assert_called_once_with(self.home, package_tools)
            status.reset_mock()
            self.assertEqual(entrypoint.main(["zcode", "apply", *options]), 0)
            ensure.assert_called_once_with(self.home, package_tools)
            ensure.reset_mock()
            self.assertEqual(entrypoint.main(["zcode", "verify", *options]), 0)
            status.assert_called_once_with(self.home, package_tools)
            status.reset_mock()
            self.assertEqual(entrypoint.main(["zcode", "enable", "--home", str(self.home)]), 0)
            ensure.assert_called_once_with(self.home, required)
            ensure.reset_mock()
            for action in ("apply", "verify"):
                self.assertEqual(entrypoint.main(["zcode", action, *options, "--todo"]), 0)
            ensure.assert_not_called(); status.assert_not_called()


class CurrentZCodeFallowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="mainframe-zcode-fallow-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.path = self.root / "file.ts"
        self.state = self.root / "private-state"
        self.payload = {"hook_event_name": "PostToolUse", "tool_name": "Write",
                        "session_id": "session", "tool_use_id": "operation", "cwd": str(self.root),
                        "tool_input": {"file_path": str(self.path), "content": "const after = 2;\n"},
                        "tool_response": {"filePath": str(self.path), "type": "update", "originalFile": "const before = 1;\n", "content": "const after = 2;\n", "userModified": False}}
        self.path.write_text("const after = 2;\n")
        self.calls = []
        self.detector = SimpleNamespace(analyze=lambda *args, **kwargs: self.analyze(*args, **kwargs))

    def analyze(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return SimpleNamespace(advisory="bounded fallow finding", unavailable=None)

    def invoke(self, payload=None):
        with patch.object(zcode_hook, "_load_detector", return_value=self.detector):
            return zcode_hook.dispatch(FALLOW, self.state, io.BytesIO(json.dumps(payload or self.payload).encode()))

    def test_exact_write_and_edit_diffs_are_memory_only_and_deduplicated(self):
        result = self.invoke()
        self.assertEqual(result["hookSpecificOutput"]["additionalContext"], "bounded fallow finding")
        args, kwargs = self.calls[0]
        self.assertEqual(args[:2], (str(self.root), [str(self.path)]))
        self.assertIn("-const before = 1;", args[2]); self.assertIn("+const after = 2;", args[2])
        self.assertEqual(kwargs["wholly_owned_paths"], [str(self.path)])
        self.assertIsNone(self.invoke())
        edit = deepcopy(self.payload); edit["tool_name"] = "Edit"; edit["tool_use_id"] = "edit"
        edit["tool_input"] = {"file_path": str(self.path), "old_string": "before", "new_string": "after"}
        edit["tool_response"] = {"filePath": str(self.path), "originalFile": "const before = 2;\n", "oldString": "before", "newString": "after", "replaceAll": False, "userModified": False}
        self.assertIsNotNone(self.invoke(edit))
        self.assertEqual(self.calls[-1][1]["wholly_owned_paths"], [])
        for path in self.state.rglob("*"):
            if path.is_file():
                raw = path.read_bytes()
                self.assertNotIn(b"const before", raw); self.assertNotIn(b"const after", raw)

    def test_changed_postimage_or_unattributed_response_returns_bounded_unavailable(self):
        self.path.write_text("concurrent change\n")
        output = self.invoke()
        self.assertIn("unavailable", output["hookSpecificOutput"]["additionalContext"])
        self.assertEqual(self.calls, [])
        missing = deepcopy(self.payload); missing["tool_use_id"] = "missing"; missing.pop("tool_response")
        self.assertIn("unavailable", self.invoke(missing)["hookSpecificOutput"]["additionalContext"])

    def test_non_js_failed_or_unidentified_events_are_neutral(self):
        for update in ({"hook_event_name": "PostToolUseFailure"}, {"tool_name": "Bash"}, {"session_id": ""}):
            payload = {**self.payload, **update}
            self.assertIsNone(self.invoke(payload))
        payload = deepcopy(self.payload); payload["tool_input"]["file_path"] = str(self.root / "readme.md")
        self.assertIsNone(self.invoke(payload))
        self.assertEqual(self.calls, [])

    def test_deletion_uses_native_line_break_rule_and_path_conflicts_are_unavailable(self):
        payload = deepcopy(self.payload); payload["tool_name"] = "Edit"
        payload["tool_response"] = {"filePath": str(self.path), "originalFile": "remove\nkeep\n", "oldString": "remove", "newString": "", "replaceAll": False, "userModified": False}
        self.path.write_text("keep\n")
        self.assertIsNotNone(self.invoke(payload))
        self.assertIn("-remove\n", self.calls[-1][0][2])
        payload["tool_use_id"] = "conflict"; payload["tool_response"]["filePath"] = str(self.root / "other.ts")
        self.assertIn("unavailable", self.invoke(payload)["hookSpecificOutput"]["additionalContext"])
        self.assertEqual(len(self.calls), 1)


class CurrentZCodeBundleTests(unittest.TestCase):
    def test_installed_public_contract_with_pure_extracted_functions(self):
        contents = Path("/Applications/ZCode.app/Contents")
        bundle = contents / "Resources/glm/zcode.cjs"
        node = shutil.which("node")
        if not bundle.is_file() or not node:
            self.skipTest("Current macOS ZCode bundle and Node are needed for this source-only probe")
        with (contents / "Info.plist").open("rb") as plist:
            build = plistlib.load(plist)["CFBundleVersion"]
        probe = Path(__file__).with_name("probes") / "zcode_current_contract.cjs"
        result = subprocess.run([node, str(probe), str(bundle), build],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
