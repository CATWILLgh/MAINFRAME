"""Decision-useful hook text survives the maintained native context boundaries."""
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from installer import codex_hook, zcode_hook

ROOT = Path(__file__).resolve().parents[1]


def detector(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "hooks" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class HookContextTests(unittest.TestCase):
    def test_fallow_guidance_and_locus_survive_three_channel_delivery(self):
        fallow = detector("mainframe-fallow-quality")
        with tempfile.TemporaryDirectory(prefix="mainframe-fallow-context-") as temporary:
            root = Path(temporary)
            path = "/".join(["feature_segment" * 5] * 4 + ["worker.ts"])
            report = {"kind": "audit", "complexity": {"findings": [
                {"path": path, "line": line, "name": "handler", "cyclomatic": 32, "introduced": True}
                for line in range(15, 21)
            ]}}
            note = fallow.build_advisory(report, root, [path])
            self.assertIsNotNone(note)
            messages = ("Code quality\n" + "q" * 450, note,
                        detector("mainframe-commit-checkpoint").MESSAGE)
            data = {"hook_event_name": "PostToolUse", "tool_name": "apply_patch"}
            with (
                patch.object(codex_hook, "_dispatch_quality", return_value=codex_hook._context("PostToolUse", messages[0])),
                patch.object(codex_hook, "_dispatch_fallow", return_value=codex_hook._context("PostToolUse", messages[1])),
                patch.object(codex_hook, "_dispatch_checkpoint", return_value=codex_hook._context("PostToolUse", messages[2])),
            ):
                output = codex_hook.dispatch(codex_hook.POST_EDIT_TRANSPORT, root / "state",
                                             io.BytesIO(json.dumps(data).encode()))
            native = zcode_hook._combine_post_edit([
                zcode_hook._native_output("PostToolUse", "additionalContext", message) for message in messages
            ])
            for output in (output, native):
                context = output["hookSpecificOutput"]["additionalContext"]
                for required in ("non-blocking", "Verify findings before acting", "in-scope", "configured issue route",
                                 "worker.ts:15", "handler", "cyclomatic 32", "Commit checkpoint"):
                    self.assertIn(required, context)
                self.assertLessEqual(len(context), 1600)
                self.assertLessEqual(len(json.dumps(output, ensure_ascii=True, separators=(",", ":")).encode()) + 1, 8192)
                self.assertNotIn("decision", output)

    def test_completion_keeps_repair_protection_through_native_encoding(self):
        quality = detector("mainframe-code-quality")
        with tempfile.TemporaryDirectory(prefix="mainframe-hook-context-") as temporary:
            root = Path(temporary)
            workspace, state = root / "workspace", root / "state"
            for directory in ("feature_segment" * 5, "каталог" * 10):
                with self.subTest(directory=directory), patch.object(quality, "_python_findings", return_value=[]):
                    parent = workspace.joinpath(*([directory] * 3))
                    parent.mkdir(parents=True)
                    paths = [parent / f"worker_{index}.py" for index in range(6)]
                    for path in paths:
                        path.write_text("value = 1\n")
                    quality.capture_before(directory, workspace, "edit", paths, state_root=state)
                    for path in paths:
                        path.write_text("# TODO: finish the implementation\nvalue = 1\n")
                    quality.record_after(directory, workspace, "edit", state_root=state)
                    result = quality.check_completion(directory, workspace, state_root=state)
                    self.assertIsNotNone(result.block_reason)
                    outputs = (
                        codex_hook._bound_output({"decision": "block", "reason": result.block_reason}),
                        zcode_hook._stop_block(result.block_reason),
                    )
                    for output in outputs:
                        message = output["reason"]
                        for required in ("introduced in this execution scope", "underlying implementation",
                                         "verification", "Do not remove a marker", "suppress a diagnostic"):
                            self.assertIn(required, message)
                        self.assertIn("worker_0.py:1", message)
                        self.assertLessEqual(len(message), 1600)
                        self.assertLessEqual(len(json.dumps(output, ensure_ascii=True, separators=(",", ":")).encode()) + 1, 8192)


if __name__ == "__main__":
    unittest.main()
