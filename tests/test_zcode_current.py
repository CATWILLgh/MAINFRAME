"""Current Desktop delivery and exact native post-edit attribution fixtures."""
from copy import deepcopy
import io
import importlib.util
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from installer import zcode_hook
from installer.core import Conflict, encode_json, transact
from installer.runtime import CODE_QUALITY_TOOLS, FALLOW_TOOLS
from installer.zcode import ZCode, FULL_MAPPING_RUNTIMES, hook_registration
from installer.runtime import runtime_bin

ROOT = Path(__file__).resolve().parents[1]
CURRENT = "3.18.0.10300"
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
        self.assertEqual(sum(hook["args"][-2] == "mainframe-post-edit" for hook in callbacks), 1)
        self.assertEqual(next(hook["timeoutMs"] for hook in callbacks if hook["args"][-2] == "mainframe-post-edit"), 20000)
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
        cfg["hooks"]["events"]["PreToolUse"][1]["hooks"][0]["enabled"] = False
        cfg["hooks"]["events"]["Stop"][0]["hooks"][0]["enabled"] = False
        old_matcher = "startup|clear|compact|resume"
        cfg["hooks"]["events"]["SessionStart"][0]["matcher"] = old_matcher
        receipt = self.adapter.receipt()
        receipt["hook_groups"]["SessionStart"][0]["matcher"] = old_matcher
        self.adapter.receipt_path.write_bytes(encode_json(receipt))
        user_hook = {"matcher": "Write", "hooks": [{"type": "process", "command": "user-check", "enabled": True}]}
        cfg["hooks"]["events"]["PreToolUse"].append(user_hook)
        self.adapter.config.write_bytes(encode_json(cfg))
        self.adapter.version = CURRENT
        changes, _ = self.adapter.plan()
        transact(changes, self.adapter.journal, self.adapter.allowed)
        current = json.loads(self.adapter.config.read_bytes())
        self.assertFalse(current["hooks"]["enabled"])
        self.assertFalse(current["hooks"]["events"]["PreToolUse"][0]["hooks"][0]["enabled"])
        self.assertFalse(current["hooks"]["events"]["PreToolUse"][1]["hooks"][0]["enabled"])
        self.assertTrue(current["hooks"]["events"]["PostToolUseFailure"][0]["hooks"][0]["enabled"])
        self.assertFalse(current["hooks"]["events"]["Stop"][0]["hooks"][0]["enabled"])
        self.assertTrue(current["hooks"]["events"]["PostToolUse"][0]["hooks"][0]["enabled"])
        self.assertEqual(current["hooks"]["events"]["PreToolUse"][-1], user_hook)
        self.assertEqual([group["matcher"] for group in current["hooks"]["events"]["SessionStart"]],
                         ["startup|clear|resume|fork"])
        self.assertEqual(current["user"], {"preserve": True})
        for value in (b"specific/provider-model", b"thoughtLevel: high", b"color: blue", b"injectAgentsMd: false"):
            self.assertIn(value, role.read_bytes())
        self.assertEqual(self.adapter.plan()[0], [])

    def test_split_post_callbacks_migrate_only_when_all_are_enabled(self):
        for toggles in ((True, True, True), (False, True, True), (False, False, False)):
            with self.subTest(toggles=toggles):
                # Install once, then emulate the previous owned split registration.
                if not self.adapter.receipt_path.exists():
                    changes, _ = self.adapter.plan()
                    transact(changes, self.adapter.journal, self.adapter.allowed)
                cfg = json.loads(self.adapter.config.read_bytes())
                receipt = self.adapter.receipt()
                callbacks = [hook_registration(self.adapter.hooks, name, self.adapter.event_state, timeout, runtime_bin(self.home))
                             for name, timeout in (("mainframe-code-quality", 60000),
                                                   ("mainframe-commit-checkpoint", 5000),
                                                   (FALLOW, 10000))]
                for callback, enabled in zip(callbacks, toggles):
                    callback["enabled"] = enabled
                groups = [{"matcher": "Write|Edit", "hooks": callbacks[:2]},
                          {"matcher": "Write|Edit", "hooks": callbacks[2:]}]
                for target in (cfg["hooks"]["events"], receipt["hook_groups"]):
                    target["PostToolUse"] = groups + [group for group in target["PostToolUse"]
                                                      if group.get("matcher") != "Write|Edit"]
                self.adapter.config.write_bytes(encode_json(cfg))
                self.adapter.receipt_path.write_bytes(encode_json(receipt))
                changes, _ = self.adapter.plan()
                transact(changes, self.adapter.journal, self.adapter.allowed)
                result = json.loads(self.adapter.config.read_bytes())["hooks"]["events"]["PostToolUse"]
                actual = [hook for group in result if group.get("matcher") == "Write|Edit" for hook in group["hooks"]]
                if all(toggles):
                    self.assertEqual([hook["args"][-2] for hook in actual], ["mainframe-post-edit"])
                else:
                    self.assertEqual([hook["enabled"] for hook in actual], list(toggles))
                self.assertEqual(self.adapter.plan()[0], [])

    def test_combined_post_native_disable_survives_update(self):
        changes, _ = self.adapter.plan()
        transact(changes, self.adapter.journal, self.adapter.allowed)
        cfg = json.loads(self.adapter.config.read_bytes())
        receipt = self.adapter.receipt()
        for events in (cfg["hooks"]["events"], receipt["hook_groups"]):
            callback = events["PostToolUse"][0]["hooks"][0]
            callback["timeoutMs"] = 75000
            callback["enabled"] = False
        self.adapter.config.write_bytes(encode_json(cfg))
        self.adapter.receipt_path.write_bytes(encode_json(receipt))
        changes, _ = self.adapter.plan()
        transact(changes, self.adapter.journal, self.adapter.allowed)
        groups = json.loads(self.adapter.config.read_bytes())["hooks"]["events"]["PostToolUse"]
        post = next(group["hooks"][0] for group in groups if group.get("matcher") == "Write|Edit")
        self.assertFalse(post["enabled"])
        self.assertEqual(post["timeoutMs"], 20000)

    def test_split_pre_callbacks_preserve_native_disables_or_consolidate(self):
        changes, _ = self.adapter.plan()
        transact(changes, self.adapter.journal, self.adapter.allowed)
        for toggles in ((True, True), (False, True), (True, False), (False, False)):
            with self.subTest(toggles=toggles):
                cfg = json.loads(self.adapter.config.read_bytes())
                receipt = self.adapter.receipt()
                callbacks = [hook_registration(self.adapter.hooks, name, self.adapter.event_state, timeout, runtime_bin(self.home))
                             for name, timeout in (("mainframe-pre-shell", 5000), ("mainframe-skill-reminder", 2000))]
                groups = [{"matcher": "Bash", "hooks": [callback]} for callback in callbacks]
                for group, enabled in zip(groups, toggles):
                    group["hooks"][0]["enabled"] = enabled
                for events in (cfg["hooks"]["events"], receipt["hook_groups"]):
                    events["PreToolUse"] = groups + [group for group in events["PreToolUse"] if group.get("matcher") != "Bash"]
                self.adapter.config.write_bytes(encode_json(cfg))
                self.adapter.receipt_path.write_bytes(encode_json(receipt))
                changes, _ = self.adapter.plan()
                transact(changes, self.adapter.journal, self.adapter.allowed)
                result = json.loads(self.adapter.config.read_bytes())["hooks"]["events"]["PreToolUse"]
                actual = [hook for group in result if group.get("matcher") == "Bash" for hook in group["hooks"]]
                if all(toggles):
                    self.assertEqual([hook["args"][-2] for hook in actual], ["mainframe-before-shell"])
                else:
                    self.assertEqual([hook["enabled"] for hook in actual], list(toggles))
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

    def test_post_transport_combines_and_deduplicates_independent_advice(self):
        messages = {"mainframe-code-quality": "quality", FALLOW: "fallow",
                    "mainframe-commit-checkpoint": "checkpoint"}
        def dispatch(name, state, data):
            return zcode_hook._native_output("PostToolUse", "additionalContext", messages[name])
        original = zcode_hook._dispatch_data
        def nested(name, state, data):
            return original(name, state, data) if name == "mainframe-post-edit" else dispatch(name, state, data)
        with patch.object(zcode_hook, "_dispatch_data", side_effect=nested):
            output = zcode_hook.dispatch("mainframe-post-edit", self.state, io.BytesIO(json.dumps(self.payload).encode()))
        self.assertEqual(output["hookSpecificOutput"]["additionalContext"], "quality\n\nfallow\n\ncheckpoint")

    def test_post_transport_claims_each_advice_once_for_same_event(self):
        seen = set()
        quality = SimpleNamespace(record_after=lambda *args, **kwargs: SimpleNamespace(advisory="quality"))
        def observe(scope, cwd, operation, size, **kwargs):
            if operation in seen:
                return None
            seen.add(operation)
            return "checkpoint"
        checkpoint = SimpleNamespace(text_lines=lambda *args: 1, observe=observe)
        detectors = {"mainframe-code-quality": quality, FALLOW: self.detector,
                     "mainframe-commit-checkpoint": checkpoint}
        with patch.object(zcode_hook, "_load_detector", side_effect=detectors.get):
            raw = json.dumps(self.payload).encode()
            first = zcode_hook.dispatch("mainframe-post-edit", self.state, io.BytesIO(raw))
            second = zcode_hook.dispatch("mainframe-post-edit", self.state, io.BytesIO(raw))
        self.assertEqual(first["hookSpecificOutput"]["additionalContext"],
                         "quality\n\nbounded fallow finding\n\ncheckpoint")
        self.assertIsNone(second)

    def test_post_transport_isolates_failures_and_bounds_serialized_context(self):
        original = zcode_hook._dispatch_data
        def nested(name, state, data):
            if name == "mainframe-post-edit":
                return original(name, state, data)
            if name == "mainframe-code-quality":
                raise RuntimeError("synthetic failure")
            return zcode_hook._native_output("PostToolUse", "additionalContext", "😀" * 6000)
        with patch.object(zcode_hook, "_dispatch_data", side_effect=nested):
            output = zcode_hook.dispatch("mainframe-post-edit", self.state, io.BytesIO(json.dumps(self.payload).encode()))
        context = output["hookSpecificOutput"]["additionalContext"]
        self.assertLessEqual(len(context), 1600)
        self.assertLessEqual(len(zcode_hook._serialize(output).encode()) + 1, 8192)
        self.assertTrue(context)

    def test_post_transport_preserves_all_long_diagnostic_channels(self):
        outputs = [zcode_hook._native_output("PostToolUse", "additionalContext", label + ":" + "x" * 3000)
                   for label in ("quality", "fallow", "checkpoint")]
        result = zcode_hook._combine_post_edit(outputs)
        context = result["hookSpecificOutput"]["additionalContext"]
        for label in ("quality:", "fallow:", "checkpoint:"):
            self.assertIn(label, context)
        self.assertLessEqual(len(context), 1600)

    def test_post_transport_accepts_large_payload_and_enforces_own_limit(self):
        payload = deepcopy(self.payload)
        payload["tool_response"]["originalFile"] = "x" * (zcode_hook.MAX_INPUT_BYTES + 1)
        calls = []
        with patch.object(zcode_hook, "_quality_dispatch", side_effect=lambda *args: calls.append(1)):
            zcode_hook.dispatch("mainframe-post-edit", self.state, io.BytesIO(json.dumps(payload).encode()))
            self.assertEqual(calls, [1])
            raw = b" " * (zcode_hook.MAX_POST_INPUT_BYTES + 1)
            self.assertIsNone(zcode_hook.dispatch("mainframe-post-edit", self.state, io.BytesIO(raw)))
            self.assertEqual(calls, [1])

    def test_fifo_postimage_returns_unavailable_without_waiting(self):
        self.path.unlink()
        os.mkfifo(self.path)
        script = """import json, sys
from installer import zcode_hook
data = json.loads(sys.stdin.read())
try:
    zcode_hook._fallow_diff(data, data['cwd'], data['cwd'], 'Write')
except (ValueError, OSError):
    pass
else:
    raise AssertionError('FIFO must be unavailable')
"""
        subprocess.run([sys.executable, "-c", script], input=json.dumps(self.payload), text=True,
                       cwd=ROOT, check=True, timeout=3)

    def test_large_replace_all_is_rejected_before_materializing(self):
        class Tracked(str):
            def replace(self, *args):
                raise AssertionError("oversized replacement was materialized")
        payload = deepcopy(self.payload)
        payload["tool_name"] = "Edit"
        payload["tool_response"] = {"filePath": str(self.path), "originalFile": Tracked("a" * 800_000),
                                    "oldString": "a", "newString": "x" * 64, "replaceAll": True}
        with self.assertRaises(ValueError):
            zcode_hook._fallow_diff(payload, str(self.root), str(self.root), "Edit")

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
        create = deepcopy(self.payload)
        create["tool_use_id"] = "create"
        create["tool_response"].update(type="create", originalFile=None)
        self.assertIsNotNone(self.invoke(create))
        self.assertTrue(self.calls[-1][0][2].startswith("--- /dev/null\n+++ b/"))
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
        self.assertIsNone(self.invoke(missing))
        other = deepcopy(missing); other["session_id"] = "other"
        self.assertIn("unavailable", self.invoke(other)["hookSpecificOutput"]["additionalContext"])
        with patch.object(zcode_hook, "_project_root", return_value=str(self.root / "another-workspace")):
            self.assertIn("unavailable", self.invoke(missing)["hookSpecificOutput"]["additionalContext"])
        self.path.write_text("const after = 2;\n")
        recovered = deepcopy(self.payload); recovered["tool_use_id"] = "recovered"
        self.assertEqual(self.invoke(recovered)["hookSpecificOutput"]["additionalContext"], "bounded fallow finding")

    def test_empty_old_edit_uses_the_exact_new_file_or_blank_replacement(self):
        payload = {**self.payload, "tool_name": "Edit", "tool_input": {
            "file_path": str(self.path), "old_string": "", "new_string": "const after = 2;\n"}}
        for operation, original in (("create", ""), ("blank", " \n\t"), ("unicode", "\u00a0\ufeff\u2028")):
            with self.subTest(operation=operation):
                payload["tool_use_id"] = operation
                payload["tool_response"] = {"filePath": str(self.path), "originalFile": original,
                    "oldString": "", "newString": "const after = 2;\n", "replaceAll": False, "userModified": False}
                output = self.invoke(payload)
                self.assertEqual(output["hookSpecificOutput"]["additionalContext"], "bounded fallow finding")
                self.assertIn("+const after = 2;\n", self.calls[-1][0][2])
                self.assertEqual(self.calls[-1][1]["wholly_owned_paths"], [str(self.path)])
        payload["tool_use_id"] = "nonblank"
        payload["tool_response"]["originalFile"] = "const unrelated = 1;\n"
        self.assertIn("unavailable", self.invoke(payload)["hookSpecificOutput"]["additionalContext"])
        self.assertEqual(len(self.calls), 3)

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
