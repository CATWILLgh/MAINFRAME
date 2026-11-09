"""Current Desktop delivery and exact-edit advisory boundaries, without services."""

from copy import deepcopy
import io
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from installer import codex, codex_hook
from installer.core import Conflict, encode_json, observed, transact
from installer.shared import inventory

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.165.0-alpha.1.2"


class CurrentCodexDeliveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary_source = tempfile.TemporaryDirectory(prefix="mainframe-current-source-")
        cls.source = Path(cls.temporary_source.name).resolve()
        for directory in ("instructions", "skills", "agents", "commands", "hooks", "plugins"):
            shutil.copytree(ROOT / directory, cls.source / directory, ignore=shutil.ignore_patterns("__pycache__"))
        for name in ("ADAPTATION.example.json", ".gitignore", "install.py"):
            shutil.copyfile(ROOT / name, cls.source / name)
        (cls.source / "shared/credentials").mkdir(parents=True)
        for name in ("mainframe-secret", "credentials-index.template.md"):
            shutil.copyfile(ROOT / "shared/credentials" / name, cls.source / "shared/credentials" / name)

    @classmethod
    def tearDownClass(cls):
        cls.temporary_source.cleanup()

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="mainframe-current-home-")
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name).resolve()
        self.adapter = codex.Codex(self.source, self.home, version=VERSION, surface="desktop")
        self.adapter.state_path.unlink(missing_ok=True)
        self.adapter.index.unlink(missing_ok=True)
        self.addCleanup(self.adapter.clean_event_state)

    def apply(self):
        changes, report = self.adapter.plan(instructions_reviewed=True)
        transact(changes, self.adapter.journal, self.adapter.allowed)
        return report

    def test_exact_current_desktop_mapping_keeps_other_surfaces_out(self):
        self.assertTrue(codex.mapping_supported(VERSION, "desktop"))
        self.assertFalse(codex.mapping_supported(VERSION, "cli"))
        self.assertFalse(codex.mapping_supported("0.165.0-alpha.1.3", "desktop"))
        self.assertEqual(codex.runtime_tools(VERSION, "desktop"), ("ruff", "oxlint", "semgrep", "fallow"))
        self.assertEqual(codex.runtime_tools("0.153.4", "cli"), ("ruff", "oxlint", "semgrep"))

    def test_every_canonical_component_has_a_truthful_private_delivery(self):
        source = inventory(self.source)
        report = self.apply()
        state = json.loads(self.adapter.state_path.read_bytes())
        self.assertEqual(
            {category: set(rows) for category, rows in state["components"].items()},
            {category: set(rows) for category, rows in source["components"].items()},
        )
        for category, rows in state["components"].items():
            for name, row in rows.items():
                with self.subTest(category=category, name=name):
                    self.assertIn(row["delivery"], {"installed", "unsupported"})
                    if row["delivery"] == "installed":
                        self.assertEqual(row["verification"], "pending")
        for name in source["components"]["hooks"]:
            self.assertTrue((self.adapter.hooks / "detectors" / (name + ".py")).is_file(), name)
        for name in (*source["components"]["skills"], *source["components"]["commands"]):
            self.assertTrue((self.adapter.skills / name / "SKILL.md").is_file(), name)
        self.assertFalse((self.home / ".agents").exists())
        self.assertIn("mainframe-fallow-quality", report["retained_partial_bindings"])
        self.assertIn("mainframe-subagent-selection", {
            name for name, row in state["components"]["hooks"].items() if row["delivery"] == "installed"})
        groups = json.loads((self.adapter.codex / "hooks.json").read_bytes())["hooks"]
        self.assertTrue(any("mainframe-subagent-selection" in handler["command"]
                            for group in groups["PreToolUse"] for handler in group["hooks"]))
        self.assertTrue(any("mainframe-fallow-quality" in handler["command"]
                            for group in groups["PostToolUse"] for handler in group["hooks"]))
        self.assertIn("SubagentStop", groups)
        self.assertEqual(self.adapter.plan()[1]["changes"], [])

    def test_full_upgrade_preserves_foreign_files_settings_disables_and_trust(self):
        self.adapter.version = "0.164.0-alpha.11.1"
        self.apply()
        config = self.adapter.codex / "config.toml"
        config.write_bytes(config.read_bytes() + b"\n# private preference\nmodel = 'user-model'\n")
        role = self.adapter.codex / "agents/user-role.toml"
        role.write_bytes(b"# user role\n")
        trust = self.adapter.codex / "hook-trust.fixture"
        trust.write_bytes(b"untouched native trust")
        disabled = self.adapter.hooks / ".disabled-mainframe-todo-limits"
        disabled.write_bytes(b"")
        protected = {path: observed(path) for path in (config, role, trust, disabled)}
        hooks_path = self.adapter.codex / "hooks.json"
        hooks = json.loads(hooks_path.read_bytes())
        user = {"matcher": "^Foreign$", "hooks": [{"type": "command", "command": "true"}]}
        hooks["hooks"]["PreToolUse"].insert(1, user)
        before_groups = deepcopy(hooks["hooks"]["PreToolUse"])
        hooks_path.write_bytes(encode_json(hooks))
        self.adapter.version = VERSION
        self.apply()
        self.assertEqual(json.loads(hooks_path.read_bytes())["hooks"]["PreToolUse"], before_groups)
        for path, snapshot in protected.items():
            self.assertEqual(observed(path), snapshot, str(path))
        self.assertEqual(self.adapter.plan()[1]["changes"], [])
        receipt = self.adapter.receipt()
        changes, _ = self.adapter.plan(remove=True)
        transact(changes, self.adapter.journal, self.adapter.allowed)
        self.adapter.clean_directories(receipt)
        self.assertTrue(role.exists())
        self.assertEqual(trust.read_bytes(), b"untouched native trust")
        self.assertEqual(json.loads(hooks_path.read_bytes())["hooks"]["PreToolUse"], [user])

    def test_entrypoint_full_apply_requests_fallow_and_scoped_routes_skip_dependencies(self):
        specification = importlib.util.spec_from_file_location("mainframe_current_entrypoint", self.source / "install.py")
        entrypoint = importlib.util.module_from_spec(specification)
        specification.loader.exec_module(entrypoint)
        options = ["--home", str(self.home), "--surface", "desktop", "--runtime-version", VERSION]
        required = ("ruff", "oxlint", "semgrep", "fallow", "openspec")
        ready = {"ready": True, "required": list(required), "missing": []}
        with (patch.object(Path, "cwd", return_value=self.source),
              patch.object(entrypoint, "ensure_runtime", return_value=ready) as ensure,
              patch.object(entrypoint, "runtime_status", return_value=ready) as status,
              patch("sys.stdout", new_callable=io.StringIO)):
            self.assertEqual(entrypoint.main(["codex", "apply", *options, "--instructions-reviewed"]), 0)
            ensure.assert_called_once_with(self.home, required)
            ensure.reset_mock()
            self.assertEqual(entrypoint.main(["codex", "verify", *options]), 0)
            status.assert_called_once_with(self.home, required)
            status.reset_mock()
            for selector in (["--skill", "mainframe-sentry"], ["--todo"]):
                self.assertEqual(entrypoint.main(["codex", "apply", *options, *selector]), 0)
                self.assertEqual(entrypoint.main(["codex", "verify", *options, *selector]), 0)
            ensure.assert_not_called()
            status.assert_not_called()

    def test_scoped_openspec_checks_and_provisions_only_its_cli(self):
        self.apply()
        specification = importlib.util.spec_from_file_location("mainframe_openspec_entrypoint", self.source / "install.py")
        entrypoint = importlib.util.module_from_spec(specification)
        specification.loader.exec_module(entrypoint)
        options = ["--home", str(self.home), "--surface", "desktop", "--runtime-version", VERSION,
                   "--skill", "mainframe-openspec"]
        missing = {"ready": False, "required": ["openspec"], "missing": ["openspec"]}
        ready = {"ready": True, "required": ["openspec"], "missing": []}
        installed = self.adapter.skills / "mainframe-openspec/SKILL.md"
        before = observed(installed)
        receipt = observed(self.adapter.receipt_path)
        with (patch.object(Path, "cwd", return_value=self.source),
              patch.object(entrypoint, "runtime_status", return_value=missing) as status,
              patch.object(entrypoint, "ensure_runtime", side_effect=Conflict("OpenSpec unavailable")) as ensure,
              patch("sys.stdout", new_callable=io.StringIO)):
            self.assertEqual(entrypoint.main(["codex", "verify", *options]), 1)
            status.assert_called_once_with(self.home, ("openspec",))
            ensure.assert_not_called()

            source = self.source / "skills/mainframe-openspec/SKILL.md"
            original = source.read_bytes()
            self.addCleanup(source.write_bytes, original)
            source.write_bytes(original + b"\nTest revision.\n")
            with self.assertRaisesRegex(Conflict, "OpenSpec unavailable"):
                entrypoint.main(["codex", "apply", *options])
            ensure.assert_called_once_with(self.home, ("openspec",))
            self.assertEqual(observed(installed), before)
            self.assertEqual(observed(self.adapter.receipt_path), receipt)

            ensure.side_effect = None
            ensure.return_value = ready
            status.return_value = ready
            self.assertEqual(entrypoint.main(["codex", "apply", *options]), 0)
            self.assertEqual(installed.read_bytes(), source.read_bytes())
            self.assertEqual(entrypoint.main(["codex", "verify", *options]), 0)


class CurrentCodexAdvisoryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="mainframe-current-advisory-")
        self.addCleanup(temporary.cleanup)
        self.workspace = Path(temporary.name).resolve() / "workspace"
        self.workspace.mkdir()
        self.state = self.workspace.parent / "state"
        self.support = self.workspace.parent / "support"
        self.support.mkdir()
        self.root_patch = patch.object(codex_hook, "ROOT", self.support)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)

    def payload(self, patch_text, operation="edit"):
        return {"hook_event_name": "PostToolUse", "tool_name": "apply_patch", "cwd": str(self.workspace),
                "session_id": "session", "tool_use_id": operation, "tool_input": {"command": patch_text},
                "tool_response": {"ok": True}}

    def invoke(self, name, data):
        return codex_hook.dispatch(name, self.state, io.BytesIO(json.dumps(data).encode()))

    def test_exact_post_patch_diff_excludes_unrelated_changes_and_retains_no_source(self):
        target = self.workspace / "file.ts"
        target.write_text("unrelated user line\nconst newValue = 2;\nanchor\n")
        patch_text = "*** Begin Patch\n*** Update File: file.ts\n@@\n-const oldValue = 1;\n+const newValue = 2;\n anchor\n*** End Patch\n"
        calls = []
        def analyze(root, paths, diff, **options):
            calls.append((root, paths, diff, options))
            return SimpleNamespace(advisory="bounded structural finding", unavailable=None)
        detector = SimpleNamespace(analyze=analyze)
        with patch.object(codex_hook, "_load_detector", return_value=detector):
            result = self.invoke("mainframe-fallow-quality", self.payload(patch_text))
            self.assertIn("bounded structural finding", result["hookSpecificOutput"]["additionalContext"])
            self.assertNotIn("permissionDecision", result["hookSpecificOutput"])
            self.assertIsNone(self.invoke("mainframe-fallow-quality", self.payload(patch_text)))
        self.assertEqual(calls[0][1], [str(target)])
        self.assertIn("-const oldValue = 1;", calls[0][2])
        self.assertIn("+const newValue = 2;", calls[0][2])
        self.assertNotIn("+unrelated user line", calls[0][2])
        self.assertEqual(calls[0][3]["wholly_owned_paths"], [])
        for path in self.state.rglob("*"):
            if path.is_file():
                self.assertNotIn(b"const oldValue", path.read_bytes())
                self.assertNotIn(b"unrelated user line", path.read_bytes())

    def test_add_whole_ownership_ambiguity_and_failure_are_bounded(self):
        target = self.workspace / "new.ts"
        target.write_text("export const value = 2;\n")
        patch_text = "*** Begin Patch\n*** Add File: new.ts\n+export const value = 2;\n*** End Patch\n"
        analyze = unittest.mock.Mock(return_value=SimpleNamespace(advisory=None, unavailable=None))
        with patch.object(codex_hook, "_load_detector", return_value=SimpleNamespace(analyze=analyze)):
            self.assertIsNone(self.invoke("mainframe-fallow-quality", self.payload(patch_text)))
            self.assertEqual(analyze.call_args.kwargs["wholly_owned_paths"], [str(target)])
            analyze.reset_mock()
            target.write_text("duplicate\nduplicate\n")
            ambiguous = "*** Begin Patch\n*** Update File: new.ts\n@@\n-before\n+duplicate\n*** End Patch\n"
            data = self.payload(ambiguous, "ambiguous")
            output = self.invoke("mainframe-fallow-quality", data)
            self.assertIn("unavailable", output["hookSpecificOutput"]["additionalContext"])
            self.assertIsNone(self.invoke("mainframe-fallow-quality", data))
            analyze.assert_not_called()
            self.assertIsNone(self.invoke("mainframe-fallow-quality", {**data, "tool_use_id": "failure", "tool_response": {"isError": True}}))
        (self.support / ".disabled-mainframe-fallow-quality").write_bytes(b"")
        self.assertIsNone(self.invoke("mainframe-fallow-quality", self.payload(patch_text, "disabled")))

    def test_subagent_completion_uses_its_scope_and_reports_unresolved_retry_without_loop(self):
        seen = []
        def completion(scope, workspace, **options):
            seen.append((scope, workspace))
            return SimpleNamespace(block_reason="attributed unresolved finding", advisory=None)
        detector = SimpleNamespace(check_completion=completion)
        data = {"hook_event_name": "SubagentStop", "session_id": "shared-parent", "agent_id": "child",
                "cwd": str(self.workspace)}
        with patch.object(codex_hook, "_load_detector", return_value=detector):
            first = self.invoke("mainframe-code-quality", data)
            self.assertEqual(first["decision"], "block")
            terminal = self.invoke("mainframe-code-quality", {**data, "stop_hook_active": True})
            self.assertFalse(terminal["continue"])
            self.assertIn("unresolved", terminal["stopReason"])
        self.assertNotEqual(seen[0][0], "shared-parent")
        self.assertEqual(seen[0], seen[1])

    def test_quality_resolves_native_relative_paths_from_environment_cwd(self):
        subprocess.run(["git", "-C", str(self.workspace), "init", "-q"], check=True)
        subdirectory = self.workspace / "subdirectory"
        subdirectory.mkdir()
        capture = unittest.mock.Mock(return_value=SimpleNamespace(advisory=None))
        detector = SimpleNamespace(capture_before=capture)
        data = self.payload("*** Begin Patch\n*** Add File: edited.py\n+print('work')\n*** End Patch\n")
        data.update(hook_event_name="PreToolUse", cwd=str(subdirectory))
        with patch.object(codex_hook, "_load_detector", return_value=detector):
            self.assertIsNone(self.invoke("mainframe-code-quality", data))
        self.assertEqual(capture.call_args.args[3], [str(subdirectory / "edited.py")])

    def test_fallow_handles_multifile_edits_and_reports_unsupported_moves_without_reading_foreign_files(self):
        first = self.workspace / "first.ts"
        second = self.workspace / "second.ts"
        first.write_text("first new\nanchor one\n")
        second.write_text("second new\nanchor two\n")
        text = ("*** Begin Patch\n*** Update File: first.ts\n@@\n-first old\n+first new\n anchor one\n"
                "*** Update File: second.ts\n@@\n-second old\n+second new\n anchor two\n*** End Patch\n")
        analyze = unittest.mock.Mock(return_value=SimpleNamespace(advisory=None, unavailable="Fallow unavailable"))
        with patch.object(codex_hook, "_load_detector", return_value=SimpleNamespace(analyze=analyze)):
            output = self.invoke("mainframe-fallow-quality", self.payload(text))
            self.assertNotIn("decision", output)
            self.assertEqual(analyze.call_args.args[1], [str(first), str(second)])
            self.assertIn("--- a/first.ts", analyze.call_args.args[2])
            self.assertIn("--- a/second.ts", analyze.call_args.args[2])
            analyze.reset_mock()
            moved = "*** Begin Patch\n*** Update File: first.ts\n*** Move to: renamed.ts\n@@\n-first old\n+first new\n*** End Patch\n"
            result = self.invoke("mainframe-fallow-quality", self.payload(moved, "move"))
            self.assertIn("unavailable", result["hookSpecificOutput"]["additionalContext"])
            analyze.assert_not_called()

    def test_parent_and_child_completion_state_are_isolated_and_clean_retry_is_silent(self):
        checked = []
        def completion(scope, workspace, **options):
            checked.append(scope)
            return SimpleNamespace(block_reason=None, advisory="unavailable")
        with patch.object(codex_hook, "_load_detector", return_value=SimpleNamespace(check_completion=completion)):
            for data in [{"hook_event_name": "Stop", "session_id": "parent", "cwd": str(self.workspace)},
                         {"hook_event_name": "SubagentStop", "session_id": "parent", "agent_id": "child", "cwd": str(self.workspace), "stop_hook_active": True}]:
                self.assertIsNone(self.invoke("mainframe-code-quality", data))
            missing_child = {"hook_event_name": "SubagentStop", "session_id": "parent", "cwd": str(self.workspace)}
            self.assertIsNone(self.invoke("mainframe-code-quality", missing_child))
        self.assertEqual(checked[0], "parent")
        self.assertEqual(len(checked), 2)
        self.assertNotEqual(checked[0], checked[1])
        self.assertFalse(self.state.exists())

    def test_plain_native_spawn_with_unverified_selectable_schema_is_neutral(self):
        detector = SimpleNamespace(decision_reason=lambda model, effort: "Choose both controls" if not model or not effort else None)
        data = {"hook_event_name": "PreToolUse", "tool_name": "spawn_agent", "tool_input": {}}
        with patch.object(codex_hook, "_load_detector", return_value=detector):
            self.assertIsNone(self.invoke("mainframe-subagent-selection", data))
            data["tool_input"] = {"model": "selected", "reasoning_effort": "high", "fork_context": False}
            self.assertIsNone(self.invoke("mainframe-subagent-selection", data))


if __name__ == "__main__":
    unittest.main()
