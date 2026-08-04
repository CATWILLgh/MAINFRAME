from __future__ import annotations

import importlib.util
import io
import json
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT / "adapters" / "zcode-desktop"


def load_module(name: str, relative: str):
    path = ADAPTER / relative
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


hook_config = load_module("zcode_hook_config", "hook_config.py")
runtime = load_module("zcode_mainframe_runtime", "gates/mainframe_runtime.py")
hook = load_module("zcode_mainframe_hook", "gates/mainframe_hook.py")


def detector(path: Path, body: str) -> str:
    script = path / "detector.py"
    script.write_text("#!/usr/bin/env python3\n" + textwrap.dedent(body))
    return script.name


class HookConfigTests(unittest.TestCase):
    def test_registers_only_events_with_v1_core_detectors(self):
        self.assertEqual(
            set(hook_config.CORE_EVENT_DETECTORS),
            {"SessionStart", "PreToolUse", "PostToolUse", "Stop"},
        )
        self.assertEqual(set(hook_config.SUPPORTED_EVENTS), {
            "SessionStart", "UserPromptSubmit", "PreToolUse",
            "PermissionRequest", "PostToolUse", "PostToolUseFailure", "Stop",
        })
        self.assertEqual(hook_config.CORE_EVENT_DETECTORS["SessionStart"], (
            "session-posture.py", "hooklib-smoke-check.py",
            "task-workflow-engagement.py", "concise-reminder.py",
        ))
        self.assertEqual(hook_config.CORE_EVENT_DETECTORS["PreToolUse"], (
            "path-validation.py", "secret-commit-gate.py",
            "bash-pattern-reminder.py", "commit-conventional-reminder.py",
        ))
        self.assertEqual(hook_config.CORE_EVENT_DETECTORS["Stop"], (
            "stop-gate-suppression-markers.py", "stop-gate-comment-discipline.py",
            "python-security-stop-gate.py", "nodejs-security-stop-gate.py",
            "frontend-fsd-gate.py",
        ))
        self.assertNotIn("telemetry.py", str(hook_config.CORE_EVENT_DETECTORS))

    def test_rendered_entries_are_process_hooks_with_stable_selectors(self):
        events = hook_config.render_hook_events(Path("/managed/mainframe_hook.py"))
        self.assertEqual(set(events), set(hook_config.CORE_EVENT_DETECTORS))
        for event, matchers in events.items():
            self.assertEqual(len(matchers), 1)
            process = matchers[0]["hooks"][0]
            self.assertEqual(process["type"], "process")
            self.assertEqual(process["command"], "python3")
            self.assertEqual(
                process["args"], ["/managed/mainframe_hook.py", event]
            )
            self.assertEqual(process["statusMessage"], f"mainframe:{event}")
            self.assertGreater(process["timeoutMs"], 0)


class PayloadNormalizationTests(unittest.TestCase):
    def test_normalizes_every_supported_event(self):
        for event in hook_config.SUPPORTED_EVENTS:
            with self.subTest(event=event):
                payload = runtime.normalize_payload(event, {
                    "hookEventName": event,
                    "sessionId": "session-1",
                    "cwd": "/work",
                    "toolName": "Bash",
                    "toolInput": {"command": "pwd"},
                    "toolCallId": "call-1",
                    "stopHookActive": True,
                })
                self.assertEqual(payload["hook_event_name"], event)
                self.assertEqual(payload["session_id"], "session-1")
                self.assertEqual(payload["project_dir"], "/work")
                self.assertEqual(payload["tool_name"], "Bash")
                self.assertEqual(payload["tool_input"], {"command": "pwd"})
                self.assertEqual(payload["tool_use_id"], "call-1")
                self.assertTrue(payload["stop_hook_active"])

    def test_rejects_wrong_event_and_invalid_boundary_types(self):
        with self.assertRaises(runtime.BridgeInputError):
            runtime.normalize_payload("PreToolUse", {"hookEventName": "Stop"})
        with self.assertRaises(runtime.BridgeInputError):
            runtime.normalize_payload("PreToolUse", {"toolInput": "not-an-object"})
        with self.assertRaises(runtime.BridgeInputError):
            runtime.normalize_payload("Unknown", {})


class RuntimeTests(unittest.TestCase):
    def run_scripts(self, event: str, scripts: list[str], directory: Path):
        payload = runtime.normalize_payload(event, {
            "hookEventName": event,
            "cwd": str(directory),
            "toolName": "Bash",
            "toolInput": {"command": "pwd"},
        })
        return runtime.run_detectors(
            event,
            payload,
            scripts,
            directory,
            timeout_seconds=0.2,
            max_output_bytes=512,
        )

    def test_aggregates_strongest_pretool_verdict_and_context(self):
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            scripts = []
            for index, (decision, reason, context) in enumerate((
                ("allow", "safe", "first note"),
                ("ask", "uncertain", "second note"),
                ("deny", "unsafe", "third note"),
            )):
                name = f"detector-{index}.py"
                (directory / name).write_text(textwrap.dedent(f"""
                    import json, sys
                    json.load(sys.stdin)
                    print(json.dumps({{
                        "hookSpecificOutput": {{
                            "hookEventName": "PreToolUse",
                            "permissionDecision": "{decision}",
                            "permissionDecisionReason": "{reason}",
                            "additionalContext": "{context}"
                        }}
                    }}))
                """))
                scripts.append(name)
            result = self.run_scripts("PreToolUse", scripts, directory)
        self.assertEqual(result.exit_code, 0)
        specific = result.output["hookSpecificOutput"]
        self.assertEqual(specific["permissionDecision"], "deny")
        self.assertEqual(specific["permissionDecisionReason"], "unsafe")
        self.assertEqual(
            specific["additionalContext"],
            "first note\n\nsecond note\n\nthird note",
        )

    def test_aggregates_stop_blocks_deterministically(self):
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            scripts = []
            for name, reason in (("a.py", "first"), ("b.py", "second")):
                (directory / name).write_text(
                    f'import json; print(json.dumps({{"decision":"block","reason":"{reason}"}}))\n'
                )
                scripts.append(name)
            result = self.run_scripts("Stop", scripts, directory)
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.output, {
            "decision": "block",
            "reason": "first\n\nsecond",
        })

    def test_no_op_detectors_produce_no_output(self):
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            script = detector(directory, "import sys\nsys.stdin.read()\n")
            result = self.run_scripts("PostToolUse", [script], directory)
        self.assertEqual(result.exit_code, 0)
        self.assertIsNone(result.output)

    def test_malformed_timeout_failure_and_oversize_fail_open_visibly(self):
        cases = {
            "malformed.py": "print('not-json')\n",
            "timeout.py": "import time\ntime.sleep(2)\n",
            "failure.py": "import sys\nsys.exit(7)\n",
            "oversize.py": "print('x' * 2000)\n",
        }
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            for name, body in cases.items():
                (directory / name).write_text(body)
            result = self.run_scripts("PostToolUse", list(cases), directory)
        self.assertEqual(result.exit_code, 0)
        context = result.output["hookSpecificOutput"]["additionalContext"]
        for name in cases:
            self.assertIn(name, context)
        self.assertIn("degraded", context.lower())

    def test_exit_two_is_preserved_as_a_deliberate_block(self):
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            script = detector(directory, "import sys\nsys.exit(2)\n")
            result = self.run_scripts("PreToolUse", [script], directory)
        self.assertEqual(result.exit_code, 2)
        self.assertEqual(
            result.output["hookSpecificOutput"]["permissionDecision"], "deny"
        )


class EntrypointTests(unittest.TestCase):
    def test_oversized_and_malformed_input_fail_open_with_valid_event_output(self):
        for payload in (b"{", b"x" * (hook.MAX_INPUT_BYTES + 1)):
            with self.subTest(size=len(payload)):
                stdout = io.StringIO()
                stderr = io.StringIO()
                code = hook.run(
                    ["PreToolUse"],
                    stdin=io.BytesIO(payload),
                    stdout=stdout,
                    stderr=stderr,
                )
                self.assertEqual(code, 0)
                parsed = json.loads(stdout.getvalue())
                self.assertEqual(
                    parsed["hookSpecificOutput"]["hookEventName"], "PreToolUse"
                )
                self.assertIn("degraded", parsed["hookSpecificOutput"]["additionalContext"].lower())
                self.assertTrue(stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
