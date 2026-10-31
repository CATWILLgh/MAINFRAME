from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from scanner_fixtures import scanner_path


ROOT = Path(__file__).resolve().parents[1]
HOOK_NAMES = (
    "mainframe-secret-access",
    "mainframe-rg-short-replace",
    "mainframe-destructive-operations",
    "mainframe-commit-secrets",
    "mainframe-code-quality",
    "mainframe-fallow-quality",
    "mainframe-todo-limits",
)


class ClineHookTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="mainframe-cline-hook-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.path_patch = mock.patch.dict(
            os.environ, {"PATH": scanner_path(self.root)}
        )
        self.path_patch.start()
        self.addCleanup(self.path_patch.stop)
        self.hooks = self.root / "hooks"
        self.detectors = self.hooks / "detectors"
        self.detectors.mkdir(parents=True)
        shutil.copy2(ROOT / "installer/cline_hook.py", self.hooks / "mainframe-cline-hook")
        for name in HOOK_NAMES:
            shutil.copy2(ROOT / "hooks" / (name + ".py"), self.detectors / (name + ".py"))
        self.state = self.root / "state"
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()
        self.git("init", "-q")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "user.name", "Test")
        (self.workspace / "base.txt").write_text("base\n")
        self.git("add", "base.txt")
        self.git("commit", "-qm", "base")

    def git(self, *args):
        return subprocess.run(
            ["git", *args], cwd=self.workspace, check=True, capture_output=True, timeout=10
        )

    def payload(self, command="printf clean", operation="operation"):
        return {
            "clineVersion": "0.0.46",
            "hookName": "PreToolUse",
            "taskId": "task",
            "workspaceRoots": [str(self.workspace)],
            "workspaceInfo": {"rootPath": str(self.workspace), "hint": "fixture"},
            "userId": "fixture",
            "agent_id": "agent",
            "parent_agent_id": None,
            "iteration": 1,
            "tool_call": {
                "id": operation,
                "name": "run_commands",
                "input": {"commands": [command]},
            },
            "preToolUse": {
                "toolName": "run_commands",
                "parameters": {"commands": json.dumps([command])},
            },
        }

    def edit_payload(self, event, path, operation="edit", success=True):
        tool_key = "tool_call" if event == "tool_call" else "tool_result"
        legacy_key = "preToolUse" if event == "tool_call" else "postToolUse"
        result = {
            "clineVersion": "0.0.46",
            "hookName": "PreToolUse" if event == "tool_call" else "PostToolUse",
            "taskId": "task",
            "workspaceRoots": [str(self.workspace)],
            "workspaceInfo": {"rootPath": str(self.workspace), "hint": "fixture"},
            "userId": "fixture",
            "agent_id": "agent",
            "parent_agent_id": None,
            "iteration": 1,
            tool_key: {"id": operation, "name": "editor", "input": {"path": str(path)}},
            legacy_key: {
                "toolName": "editor",
                "parameters": {"path": str(path)},
            },
        }
        if event == "tool_result":
            result[legacy_key].update(result="ok", success=success, executionTimeMs=1)
        return result

    def patch_payload(self, event, patch, operation="patch", success=True):
        tool_key = "tool_call" if event == "tool_call" else "tool_result"
        legacy_key = "preToolUse" if event == "tool_call" else "postToolUse"
        result = {
            "clineVersion": "0.0.46",
            "hookName": "PreToolUse" if event == "tool_call" else "PostToolUse",
            "taskId": "task",
            "workspaceRoots": [str(self.workspace)],
            "workspaceInfo": {"rootPath": str(self.workspace), "hint": "fixture"},
            "userId": "fixture",
            "agent_id": "agent",
            "parent_agent_id": None,
            "iteration": 1,
            tool_key: {"id": operation, "name": "apply_patch", "input": {"input": patch}},
            legacy_key: {"toolName": "apply_patch", "parameters": {"input": patch}},
        }
        if event == "tool_result":
            result[legacy_key].update(result="ok", success=success, executionTimeMs=1)
        return result

    def invoke(self, event, payload, *, raw=None):
        return subprocess.run(
            [sys.executable, "-B", str(self.hooks / "mainframe-cline-hook"), event, str(self.state)],
            input=raw if raw is not None else json.dumps(payload),
            text=True,
            capture_output=True,
            timeout=15,
        )

    def test_clean_unknown_and_malformed_events_are_silent(self):
        clean = self.invoke("tool_call", self.payload())
        self.assertEqual((clean.returncode, clean.stdout, clean.stderr), (0, "", ""))
        unknown = self.payload(operation="unknown")
        unknown["tool_call"] = {"id": "unknown", "name": "read_files", "input": {}}
        self.assertEqual(self.invoke("tool_call", unknown).stdout, "")
        self.assertEqual(self.invoke("tool_call", {}, raw="not json").stdout, "")
        self.assertEqual(self.invoke("agent_end", self.payload()).stdout, "")

    def test_shell_guards_advice_and_batching_preserve_fixed_effects(self):
        secret = json.loads(
            self.invoke("tool_call", self.payload("mainframe-secret get synthetic", "secret")).stdout
        )
        self.assertTrue(secret["cancel"])
        self.assertNotIn("synthetic", secret["errorMessage"])

        destructive = json.loads(
            self.invoke("tool_call", self.payload("git reset --hard", "destructive")).stdout
        )
        self.assertTrue(destructive["cancel"])

        advice = json.loads(
            self.invoke("tool_call", self.payload("rg -r replacement pattern .", "rg")).stdout
        )
        self.assertFalse(advice.get("cancel", False))
        self.assertIn("contextModification", advice)

        batched = self.payload(operation="batch")
        commands = ["printf clean", "git reset --hard"]
        batched["tool_call"]["input"]["commands"] = commands
        batched["preToolUse"]["parameters"]["commands"] = json.dumps(commands)
        self.assertTrue(json.loads(self.invoke("tool_call", batched).stdout)["cancel"])
        structured = self.payload(operation="native-argv")
        structured["tool_call"]["input"] = {"commands": [{"command": "git", "args": ["reset", "--hard"]}]}
        self.assertTrue(json.loads(self.invoke("tool_call", structured).stdout)["cancel"])

    def test_commit_guard_reads_the_exact_workspace_without_exposing_value(self):
        token = "ghp_0123456789abcdefghijklmnopqrstuvwxyz"
        (self.workspace / ".env").write_text("TOKEN=" + token + "\n")
        self.git("add", ".env")
        result = json.loads(
            self.invoke("tool_call", self.payload("git commit -m fixture", "commit")).stdout
        )
        self.assertTrue(result["cancel"])
        self.assertIn(".env:1", result["errorMessage"])
        self.assertNotIn(token, result["errorMessage"])

    def test_disable_markers_are_per_identity(self):
        (self.hooks / ".disabled-mainframe-rg-short-replace").touch()
        self.assertEqual(
            self.invoke("tool_call", self.payload("rg -r replacement pattern .", "disabled")).stdout,
            "",
        )
        result = json.loads(
            self.invoke("tool_call", self.payload("git reset --hard", "still-enabled")).stdout
        )
        self.assertTrue(result["cancel"])

    def test_quality_edit_snapshot_reports_once_and_repair_is_silent(self):
        target = self.workspace / "sample.go"
        target.write_text("package sample\n")
        self.assertEqual(
            self.invoke("tool_call", self.edit_payload("tool_call", target, "introduce")).stdout,
            "",
        )
        target.write_text("package sample\n// TODO: finish behavior\n")
        post = json.loads(
            self.invoke("tool_result", self.edit_payload("tool_result", target, "introduce")).stdout
        )
        self.assertIn("TODO/FIXME/HACK/XXX", post["contextModification"])
        self.assertEqual(
            self.invoke("tool_result", self.edit_payload("tool_result", target, "introduce")).stdout,
            "",
        )

        self.assertEqual(
            self.invoke("tool_call", self.edit_payload("tool_call", target, "repair")).stdout,
            "",
        )
        target.write_text("package sample\n")
        self.assertEqual(
            self.invoke("tool_result", self.edit_payload("tool_result", target, "repair")).stdout,
            "",
        )

    def test_concurrent_duplicate_post_delivery_is_at_most_once(self):
        target = self.workspace / "sample.go"
        target.write_text("package sample\n")
        self.invoke("tool_call", self.edit_payload("tool_call", target, "concurrent"))
        target.write_text("package sample\n// TODO: one finding\n")
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(
                pool.map(
                    lambda _: self.invoke(
                        "tool_result", self.edit_payload("tool_result", target, "concurrent")
                    ).stdout,
                    range(8),
                )
            )
        self.assertEqual(sum(bool(item) for item in results), 1)

    def test_apply_patch_captures_every_path_for_quality_and_fallow(self):
        first = self.workspace / "first.ts"
        second = self.workspace / "second.ts"
        first.write_text("export const first = 1;\n")
        second.write_text("export const second = 2;\n")
        patch = """*** Begin Patch
*** Update File: first.ts
@@
-export const first = 1;
+export const first = 1; // TODO: finish
*** Update File: second.ts
@@
-export const second = 2;
+export const second = 2; // FIXME: finish
*** End Patch"""
        self.assertEqual(self.invoke(
            "tool_call", self.patch_payload("tool_call", patch)
        ).stdout, "")
        with closing(sqlite3.connect(self.state / "events.sqlite3")) as connection:
            self.assertEqual(connection.execute(
                "SELECT count(*) FROM snapshot_files"
            ).fetchone()[0], 2)
        first.write_text("export const first = 1; // TODO: finish\n")
        second.write_text("export const second = 2; // FIXME: finish\n")
        post = json.loads(self.invoke(
            "tool_result", self.patch_payload("tool_result", patch)
        ).stdout)
        self.assertIn("first.ts", post["contextModification"])
        self.assertIn("second.ts", post["contextModification"])
        with closing(sqlite3.connect(self.state / "events.sqlite3")) as connection:
            self.assertEqual(connection.execute(
                "SELECT count(*) FROM snapshot_files"
            ).fetchone()[0], 0)
        self.assertEqual(self.invoke(
            "tool_result", self.patch_payload("tool_result", patch)
        ).stdout, "")

    def test_apply_patch_rejects_an_out_of_project_path_as_one_scope(self):
        patch = """*** Begin Patch
*** Update File: first.ts
*** Update File: ../outside.ts
*** End Patch"""
        self.assertEqual(self.invoke(
            "tool_call", self.patch_payload("tool_call", patch, "outside")
        ).stdout, "")
        self.assertFalse((self.state / "events.sqlite3").exists())

    def test_todo_guard_checks_native_patch_and_editor_changes_only(self):
        docs = self.workspace / ".docs"
        docs.mkdir()
        index = docs / "todo"
        before = "# TODO\n## Запланировано\n- existing unrelated malformed row\n## На рассмотрении\n## Отложено\n## Отказались\n"
        index.write_text(before)
        payload = self.edit_payload("tool_call", index)
        payload["tool_call"]["input"].update(old_text="existing unrelated malformed row", new_text="new invalid row")
        denied = json.loads(self.invoke("tool_call", payload).stdout)
        self.assertIn(".docs/todo", denied["errorMessage"])
        self.assertEqual(index.read_text(), before)
        clean = self.edit_payload("tool_call", self.workspace / "readme.md")
        clean["tool_call"]["input"].update(new_text="ordinary document")
        self.assertEqual(self.invoke("tool_call", clean).stdout, "")
        patch = "*** Begin Patch\n*** Add File: .docs/todos/new.md\n+missing sections\n*** End Patch"
        self.assertTrue(json.loads(self.invoke("tool_call", self.patch_payload("tool_call", patch)).stdout)["cancel"])
        self.assertEqual(self.invoke("tool_call", self.patch_payload("tool_call", "malformed")).stdout, "")
        insertion = self.edit_payload("tool_call", index, "insert")
        insertion["tool_call"]["input"].update(insert_line=3, new_text="invalid inserted row")
        self.assertTrue(json.loads(self.invoke("tool_call", insertion).stdout)["cancel"])
        insertion["tool_call"]["input"]["insert_line"] = 9999
        self.assertEqual(self.invoke("tool_call", insertion).stdout, "")
        payload["tool_call"]["input"].update(old_text="absent old text")
        self.assertEqual(self.invoke("tool_call", payload).stdout, "")

    def test_submit_revalidates_only_its_attributed_scope_and_repair(self):
        target = self.workspace / "sample.go"
        target.write_text("package sample\n")
        self.invoke("tool_call", self.edit_payload("tool_call", target, "introduce"))
        target.write_text("package sample\n// TODO: unfinished\n")
        self.invoke("tool_result", self.edit_payload("tool_result", target, "introduce"))
        submit = self.payload()
        submit["tool_call"] = {"id": "finish", "name": "submit_and_exit", "input": {}}
        self.assertTrue(json.loads(self.invoke("guard", submit).stdout)["cancel"])
        other = dict(submit, taskId="child-conversation", agent_id="child", parent_agent_id="agent")
        self.assertEqual(self.invoke("guard", other).stdout, "")
        target.write_text("package sample\n")
        self.assertEqual(self.invoke("guard", submit).stdout, "")

    def test_native_structured_failed_edit_stays_silent(self):
        target = self.workspace / "sample.go"
        target.write_text("package sample\n")
        self.invoke("tool_call", self.edit_payload("tool_call", target, "failed"))
        target.write_text("package sample\n// TODO: unrelated change\n")
        post = self.edit_payload("tool_result", target, "failed")
        post["tool_result"]["output"] = {"success": False, "error": "edit failed"}
        self.assertEqual(self.invoke("tool_result", post).stdout, "")

    def test_desktop_plugin_recovers_completion_denial_and_preserves_native_defaults(self):
        from installer.cline import desktop_plugin
        if shutil.which("node") is None:
            self.skipTest("Node runtime unavailable")
        target = self.workspace / "sample.go"
        target.write_text("package sample\n")
        self.invoke("tool_call", self.edit_payload("tool_call", target, "introduced"))
        target.write_text("package sample\n// TODO: finish\n")
        self.invoke("tool_result", self.edit_payload("tool_result", target, "introduced"))
        plugin = self.root / "mainframe.js"
        plugin.write_bytes(desktop_plugin(Path(sys.executable), self.hooks / "mainframe-cline-hook", self.state, Path(os.environ["PATH"].split(os.pathsep)[0])))
        script = r"""
const assert = require('node:assert/strict');
const fs = require('node:fs');
const plugin = require(process.argv[1]);
plugin.setup({}, {workspaceInfo:{rootPath:process.argv[2]}});
const snapshot={agentId:'agent',conversationId:'task'};
const call = (name,input) => plugin.hooks.beforeTool({snapshot,toolCall:{toolName:name,toolCallId:'finish'},input});
(async()=>{
  const denied=await call('submit_and_exit',{summary:'completion fixture',verified:true});
  assert.equal(denied.skip,true); assert.equal(denied.stop,undefined);
  assert.equal(await call('spawn_agent',{systemPrompt:'role',task:'task'}),undefined);
  assert.equal(await call('run_commands',{commands:['git reset --hard']}),undefined);
  fs.writeFileSync(process.argv[2]+'/sample.go','package sample\n');
  assert.equal(await call('submit_and_exit',{summary:'completion fixture',verified:true}),undefined);
})().catch(error=>{console.error(error);process.exitCode=1;});
"""
        result = subprocess.run(["node", "-e", script, str(plugin), str(self.workspace)], text=True, capture_output=True, timeout=10)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))


if __name__ == "__main__":
    unittest.main()
