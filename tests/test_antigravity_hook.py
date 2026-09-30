import json
from pathlib import Path
import shutil
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

from installer import antigravity_hook as BRIDGE

ROOT = Path(__file__).resolve().parents[1]


class AntigravityHookTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="mainframe-antigravity-hook-")
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.workspace = self.base / "workspace"
        self.workspace.mkdir()
        self.support = self.base / "support"
        detectors = self.support / "detectors"
        detectors.mkdir(parents=True)
        for name in (
            "mainframe-secret-access", "mainframe-rg-short-replace", "mainframe-destructive-operations",
            "mainframe-commit-secrets", "mainframe-code-quality", "mainframe-fallow-quality",
        ):
            shutil.copyfile(ROOT / "hooks" / (name + ".py"), detectors / (name + ".py"))
        self.previous_root = BRIDGE.ROOT
        BRIDGE.ROOT = self.support
        self.addCleanup(setattr, BRIDGE, "ROOT", self.previous_root)
        self.state = self.base / "state"
        self.transcript = (
            self.base / "antigravity" / "brain" / "conversation-fixture"
            / ".system_generated" / "logs" / "transcript.jsonl"
        )
        self.transcript.parent.mkdir(parents=True)

    def payload(self):
        return {
            "conversationId": "conversation-fixture",
            "workspacePaths": [str(self.workspace)],
            "transcriptPath": str(self.transcript),
            "invocationNum": 2,
            "executionNum": 1,
        }

    def call(self, name, args, *, created="2026-09-15T10:00:00Z"):
        self.transcript.write_text(json.dumps({
            "step_index": 7,
            "source": "MODEL",
            "type": "PLANNER_RESPONSE",
            "status": "DONE",
            "created_at": created,
            "tool_calls": [{"name": name, "args": args}],
        }) + "\n")

    def test_clean_post_invocation_is_valid_and_silent(self):
        self.call("run_command", {"CommandLine": "printf clean", "Cwd": str(self.workspace)})
        self.assertEqual(BRIDGE.post_invocation(self.payload(), self.state), {})

    def test_shell_advice_is_contextual_and_deduplicated(self):
        self.call("run_command", {
            "CommandLine": "rg -r replacement pattern .",
            "Cwd": str(self.workspace),
        })
        first = BRIDGE.post_invocation(self.payload(), self.state)
        self.assertIn("ripgrep", first["injectSteps"][0]["ephemeralMessage"])
        self.assertEqual(BRIDGE.post_invocation(self.payload(), self.state), {})

    def test_inserted_quality_finding_blocks_stop_until_repaired(self):
        target = self.workspace / "sample.py"
        target.write_text("# TODO: finish\n")
        self.call("write_to_file", {
            "TargetFile": str(target),
            "CodeContent": target.read_text(),
            "Overwrite": False,
        })
        result = BRIDGE.post_invocation(self.payload(), self.state)
        self.assertIn("Code-quality finding", result["injectSteps"][0]["ephemeralMessage"])
        stopped = BRIDGE.stop(self.payload(), self.state)
        self.assertEqual(stopped["decision"], "continue")
        self.assertIn("sample.py", stopped["reason"])
        self.assertEqual(BRIDGE.stop(self.payload(), self.state), {"decision": "stop"})
        next_execution = self.payload()
        next_execution["executionNum"] = 2
        self.assertEqual(BRIDGE.stop(next_execution, self.state)["decision"], "continue")
        target.write_text("value = 1\n")
        self.assertEqual(BRIDGE.stop(self.payload(), self.state), {"decision": "stop"})

    def test_fallow_advice_is_injected_from_the_exact_edit_diff(self):
        target = self.workspace / "sample.ts"
        target.write_text("export const value = 1;\n")
        self.call("write_to_file", {
            "TargetFile": str(target),
            "CodeContent": target.read_text(),
            "Overwrite": False,
        })
        real_load = BRIDGE._load_detector
        fake = SimpleNamespace(
            JS_EXTENSIONS={".ts"},
            analyze=lambda *args, **kwargs: SimpleNamespace(
                advisory="Fallow exact-scope finding", unavailable=None
            ),
        )
        with mock.patch.object(
            BRIDGE, "_load_detector",
            side_effect=lambda name: fake if name == "mainframe-fallow-quality" else real_load(name),
        ):
            result = BRIDGE.post_invocation(self.payload(), self.state)
        self.assertIn("Fallow exact-scope finding", result["injectSteps"][0]["ephemeralMessage"])

    def test_missing_transcript_and_state_are_neutral(self):
        self.assertEqual(BRIDGE.post_invocation(self.payload(), self.state), {})
        self.assertEqual(BRIDGE.stop(self.payload(), self.state), {"decision": "stop"})

    def test_cli_and_ide_transcripts_are_outside_desktop_transport(self):
        for surface in ("antigravity-cli", "antigravity-ide"):
            with self.subTest(surface=surface):
                transcript = self.base / surface / "brain" / "fixture" / "transcript.jsonl"
                transcript.parent.mkdir(parents=True)
                transcript.write_text(json.dumps({
                    "step_index": 7,
                    "source": "MODEL",
                    "type": "PLANNER_RESPONSE",
                    "status": "DONE",
                    "created_at": "2026-09-15T10:00:00Z",
                    "tool_calls": [{
                        "name": "run_command",
                        "args": {"CommandLine": "rg -r replacement pattern ."},
                    }],
                }) + "\n")
                payload = self.payload()
                payload["transcriptPath"] = str(transcript)
                self.assertEqual(BRIDGE.post_invocation(payload, self.state), {})


if __name__ == "__main__":
    unittest.main()
