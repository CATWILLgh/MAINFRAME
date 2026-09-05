"""Regression checks for source templates, using isolated files and fake inputs."""

from concurrent.futures import ThreadPoolExecutor
import importlib.util
import io
from contextlib import redirect_stdout
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


SOURCES = Path(__file__).resolve().parents[1] / "templates/hooks/scripts"
sys.path.insert(0, str(SOURCES))


def load(name):
    spec = importlib.util.spec_from_file_location(name, SOURCES / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class HookSources(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="mainframe-hook-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.environment = patch.dict(os.environ, {
            "MAINFRAME_NOTICE_STATE_DIR": str(self.root / "notices"),
            "MAINFRAME_MARKER_STATE_DIR": str(self.root / "findings"),
            "MAINFRAME_SNAPSHOT_DIR": str(self.root / "snapshots"),
        })
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def run_hook(self, name, payload):
        return subprocess.run(
            [sys.executable, str(SOURCES / (name + ".py"))],
            input=json.dumps(payload), text=True, capture_output=True, timeout=20,
        )

    def shell_payload(self, command):
        return {"tool_name": "Bash", "tool_input": {"command": command},
                "cwd": str(self.root), "session_id": "probe", "agent_id": "worker"}

    def test_every_module_imports_without_runtime_services(self):
        for source in SOURCES.glob("*.py"):
            with self.subTest(source=source.name):
                load(source.stem)

    def test_literal_catastrophic_paths_and_narrow_cleanup(self):
        detector = load("_path_validation")
        for command in ("rm -rf /", "rm -rf .", 'rm -rf "$HOME"'):
            self.assertTrue(detector.decision_reason(command, str(self.root), str(self.root)))
        self.assertIsNone(detector.decision_reason("rm -rf cache", str(self.root), str(self.root)))
        self.assertIsNone(detector.decision_reason("printf 'rm -rf /'", str(self.root), str(self.root)))

    def test_git_classification_has_no_writer_role_gate(self):
        detector = load("_git_authority")
        for command in ("git status", "git add file", "git commit -m result"):
            self.assertEqual(detector.authority_decision(command), (None, None))
        self.assertEqual(detector.authority_decision("git push origin main")[0], "ask")
        self.assertEqual(detector.authority_decision("git reset --hard")[0], "ask")

    def test_standalone_secret_inspection_boundary(self):
        detector = load("_secret_read")
        self.assertTrue(detector.decision_reason("secret get SYNTHETIC_NAME"))
        self.assertIsNone(detector.decision_reason('consumer --token "$(secret get SYNTHETIC_NAME)"'))

    def test_exact_staged_secret_content_and_redaction(self):
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        file = self.root / "sample.txt"
        token = "ghp_" + "aB3cD5eF7" * 4
        file.write_text(token + "\n")
        subprocess.run(["git", "-C", str(self.root), "add", "sample.txt"], check=True)
        file.write_text("clean working copy\n")
        result = self.run_hook("_secret_commit", self.shell_payload("git commit -m test"))
        self.assertEqual(result.returncode, 0, result.stderr)
        decision = json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"]
        self.assertEqual(decision, "deny")
        self.assertNotIn(token, result.stdout + result.stderr)
        subprocess.run(["git", "-C", str(self.root), "add", "sample.txt"], check=True)
        file.write_text(token + "\n")
        result = self.run_hook("_secret_commit", self.shell_payload("git commit -m test"))
        self.assertEqual((result.returncode, result.stdout), (0, ""))

    def test_invalid_payload_is_failure_not_clean_scan(self):
        result = self.run_hook("_secret_commit", [])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unavailable", result.stderr)

    def test_notice_claim_is_atomic_and_writer_scoped(self):
        notice = load("_notice_state")
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: notice.claim_once("finding", "task", "writer"), range(12)))
        self.assertEqual(sum(results), 1)
        self.assertTrue(notice.claim_once("finding", "task", "another-writer"))

    def test_marker_revalidation_and_session_isolation(self):
        markers = load("_markers")
        state = load("_marker_state")
        file = self.root / "module.py"
        file.write_text("# TODO: finish behavior\n")
        deltas = markers.marker_counts(file.read_text(), ".py")
        self.assertTrue(state.update("task", "writer", str(file), deltas)[0])
        self.assertFalse(state.unresolved("other-task", "writer"))
        file.write_text("value = 1\n")
        self.assertFalse(state.unresolved("task", "writer"))
        self.assertFalse(markers.marker_counts('value = "TODO"\n', ".py"))

    def test_snapshots_are_private_consumed_and_call_scoped(self):
        snapshots = load("_edit_snapshot")
        payload = {"session_id": "task", "tool_use_id": "call"}
        snapshots.atomic_write(payload, [{"path": "fixture.py", "text": "value = 1"}])
        path = snapshots.snapshot_path(payload)
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertNotEqual(path, snapshots.snapshot_path(dict(payload, tool_use_id="another")))
        self.assertEqual(snapshots.consume(payload)[0]["text"], "value = 1")
        self.assertFalse(path.exists())

    def test_growth_ignores_inherited_size(self):
        growth = load("length-quality-note")
        change = {"path": str(self.root / "module.py"), "before": "x = 1\n" * 400,
                  "after": "x = 1\n" * 401}
        self.assertTrue(growth.note_for_changes(str(self.root), [change])[1])
        change["before"] = change["after"]
        self.assertEqual(growth.note_for_changes(str(self.root), [change]), (None, 0))

    def test_shell_reminder_is_bounded_and_explicit_replace_is_quiet(self):
        payload = self.shell_payload("rg -rn needle .")
        first = self.run_hook("_bash_patterns", payload)
        self.assertTrue(first.stdout)
        self.assertEqual(self.run_hook("_bash_patterns", payload).stdout, "")
        self.assertEqual(self.run_hook("_bash_patterns", self.shell_payload("rg --replace value needle .")).stdout, "")

    def test_missing_security_tools_are_not_empty_findings(self):
        for name, extension in (("_python_findings", ".py"), ("_node_findings", ".js")):
            with self.subTest(name=name), patch("shutil.which", return_value=None):
                with self.assertRaises(RuntimeError):
                    load(name).findings("value = 1", extension, str(self.root / ("file" + extension)))

    def test_scanner_empty_or_wrong_schema_is_not_a_clean_scan(self):
        for name, extension, bad_outputs in (
            ("_python_findings", ".py", ("", "{}", "null")),
            ("_node_findings", ".js", ("", "[]", "{}", "null")),
        ):
            module = load(name)
            for output in bad_outputs:
                with self.subTest(scanner=name, output=output), \
                     patch("shutil.which", return_value="scanner"), \
                     patch("subprocess.run", return_value=subprocess.CompletedProcess([], 0, output, "")):
                    with self.assertRaises(RuntimeError):
                        module.findings("value = 1", extension, str(self.root / ("sample" + extension)))

    def test_marker_event_lifecycle_and_other_session(self):
        file = self.root / "sample.py"
        file.write_text("# TODO: implement real behavior\n")
        payload = {"tool_name": "Edit", "tool_input": {"file_path": str(file),
                   "old_string": "", "new_string": file.read_text()},
                   "cwd": str(self.root), "session_id": "first"}
        self.assertTrue(self.run_hook("scan-suppression-markers", payload).stdout)
        self.assertEqual(self.run_hook("scan-suppression-markers", payload).stdout, "")
        stop = {"cwd": str(self.root), "session_id": "first"}
        self.assertTrue(self.run_hook("stop-gate-suppression-markers", stop).stdout)
        self.assertEqual(self.run_hook("stop-gate-suppression-markers", dict(stop, session_id="other")).stdout, "")
        self.assertEqual(self.run_hook("stop-gate-suppression-markers", dict(stop, stop_hook_active=True)).stdout, "")
        file.write_text("value = 1\n")
        self.assertEqual(self.run_hook("stop-gate-suppression-markers", stop).stdout, "")

    def test_targeted_comment_repeat_is_quiet(self):
        file = self.root / "sample.py"
        file.write_text("# Step 1: implement the plan\nvalue = 1\n")
        payload = {"tool_name": "Edit", "tool_input": {"file_path": str(file),
                   "old_string": "value = 1\n", "new_string": file.read_text()},
                   "cwd": str(self.root), "session_id": "first"}
        self.assertTrue(self.run_hook("comment-discipline-reminder", payload).stdout)
        self.assertEqual(self.run_hook("comment-discipline-reminder", payload).stdout, "")

    def test_scanner_failures_and_timeouts_remain_visible(self):
        for name, extension in (("_python_findings", ".py"), ("_node_findings", ".js")):
            module = load(name)
            with self.subTest(scanner=name), patch("shutil.which", return_value="scanner"):
                with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("scanner", 10)):
                    with self.assertRaises((RuntimeError, subprocess.TimeoutExpired)):
                        module.findings("value = 1", extension, str(self.root / ("sample" + extension)))
                with patch("subprocess.run", return_value=subprocess.CompletedProcess([], 2, "", "failure")):
                    with self.assertRaises(RuntimeError):
                        module.findings("value = 1", extension, str(self.root / ("sample" + extension)))

    def test_semgrep_invalid_results_and_bounded_failure_recovery(self):
        module = load("semgrep-informational")
        file = self.root / "sample.js"
        file.write_text("const value = 1;\n")
        targets = {file: {1}}
        for output in ("", "{}", "[]", '{"results": [], "errors": [{"type": "timeout"}]}'):
            with self.subTest(output=output), patch("shutil.which", return_value="semgrep"), \
                 patch("subprocess.run", return_value=subprocess.CompletedProcess([], 0, output, "")):
                with self.assertRaises((ValueError, RuntimeError)):
                    module._run_semgrep(targets)
        payload = {"session_id": "probe", "cwd": str(self.root)}
        with patch.object(module, "load_payload", return_value=payload), \
             patch.object(module, "_targets", return_value=targets):
            for failure in (FileNotFoundError("semgrep"), subprocess.TimeoutExpired("semgrep", 12)):
                with patch.object(module, "_run_semgrep", side_effect=failure):
                    first, repeated = io.StringIO(), io.StringIO()
                    with redirect_stdout(first):
                        module.main()
                    with redirect_stdout(repeated):
                        module.main()
                    self.assertTrue(first.getvalue())
                    self.assertEqual(repeated.getvalue(), "")
            with patch.object(module, "_run_semgrep", return_value=([], 0)):
                recovered = io.StringIO()
                with redirect_stdout(recovered):
                    module.main()
                self.assertEqual(recovered.getvalue(), "")

    def test_comment_extraction_does_not_flag_strings_or_domain_docstrings(self):
        comments = load("_comment_findings")
        for source in ('message = "Step 1: execute plan"\n',
                       '"""Phase 2 of the compiler: type checking."""\n',
                       '# Cache avoids a second network round trip.\n'):
            self.assertEqual(comments.findings(source, ".py"), [])

    def test_semgrep_attribution_excludes_unchanged_lines_and_ambiguous_edits(self):
        module = load("semgrep-informational")
        file = self.root / "sample.js"
        file.write_text("oldRisk();\nsafe();\nsafe();\nnewRisk();\n")
        payload = {"tool_name": "Edit", "cwd": str(self.root),
                   "tool_input": {"file_path": str(file), "new_string": "newRisk();"}}
        self.assertEqual(module._targets(payload), {file: {4}})
        payload["tool_input"]["new_string"] = "safe();"
        self.assertEqual(module._targets(payload), {})


if __name__ == "__main__":
    unittest.main()
