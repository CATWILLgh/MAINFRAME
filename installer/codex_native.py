"""Bounded native discovery. Does not start model turns or claim behavior proof."""

import json
from pathlib import Path
import queue
import subprocess
import tempfile
import threading
import time

from .codex import HOOK_NAMES, PRE_SHELL_TRANSPORT, SHELL_HOOK_NAMES, hook_command, inventory
from .core import Conflict
from .runtime import runtime_bin


class Native:
    def __init__(self, executable):
        self.process = subprocess.Popen([executable, "app-server"], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1)
        self.messages = queue.Queue(maxsize=256)
        self.counter = 0
        self.finished = threading.Event()

        def pump():
            try:
                for line in self.process.stdout:
                    if self.finished.is_set():
                        break
                    try:
                        self.messages.put(json.loads(line), timeout=1)
                    except (ValueError, queue.Full):
                        continue
            finally:
                self.finished.set()

        self.reader = threading.Thread(target=pump, daemon=True)
        self.reader.start()
        try:
            self.rpc("initialize", {"clientInfo": {"name": "mainframe_installer", "version": "1"},
                                    "capabilities": {"experimentalApi": True}})
            self.send({"method": "initialized", "params": {}})
        except Exception:
            self.close()
            raise

    def send(self, value):
        self.process.stdin.write(json.dumps(value) + "\n")
        self.process.stdin.flush()

    def rpc(self, method, params):
        self.counter += 1
        identifier = self.counter
        self.send({"id": identifier, "method": method, "params": params})
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            try:
                value = self.messages.get(timeout=min(0.5, max(0.01, deadline - time.monotonic())))
            except queue.Empty:
                if self.finished.is_set():
                    break
                continue
            if value.get("id") != identifier:
                continue
            if "error" in value:
                raise Conflict(f"Native {method} rejected the request; discovery remains pending.")
            return value["result"]
        raise Conflict(f"Native {method} did not complete within its bound.")

    def close(self):
        self.finished.set()
        self.process.terminate()
        try:
            self.process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()
        self.process.stdin.close()
        self.reader.join(timeout=1)
        self.process.stdout.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def discover(adapter, executable, native_class=Native):
    # app-server discovers the real process environment. Never mislabel a
    # fixture's file tree as that environment or override a home behind its back.
    import os
    actual_home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))).resolve()
    if adapter.home != Path.home().resolve() or adapter.codex != actual_home:
        raise Conflict("Native discovery requires the process's actual home and CODEX_HOME; fixture tests use a fake client.")
    source = inventory(adapter.root)
    with tempfile.TemporaryDirectory(prefix="mainframe-discovery-") as temporary:
        with native_class(executable) as native:
            skill_result = native.rpc("skills/list", {"cwds": [temporary], "forceReload": True})
            hook_result = native.rpc("hooks/list", {"cwds": [temporary]})
        return summarize(adapter, source, skill_result, hook_result, Path(temporary))


def summarize(adapter, source, skill_result, hook_result, cwd):
    for result in (skill_result, hook_result):
        groups = result.get("data", [])
        if len(groups) != 1 or Path(groups[0].get("cwd", "")).resolve() != cwd.resolve():
            raise Conflict("Native discovery did not inspect the requested isolated scope.")
    skills = [skill for group in skill_result["data"] for skill in group["skills"]]
    hooks = [hook for group in hook_result["data"] for hook in group["hooks"]]
    result = {"skills": {}, "commands": {}, "hooks": {}, "scope": "CLI/app-server discovery only; no Desktop reload or behavior claim"}
    for category in ("skills", "commands"):
        for name in source["components"][category]:
            found = [s for s in skills if s.get("name") == name]
            valid = len(found) == 1 and found[0].get("enabled") is True and found[0].get("path") == str(adapter.skills / name / "SKILL.md")
            result[category][name] = {"discovered": valid}
    for name in HOOK_NAMES:
        transport = PRE_SHELL_TRANSPORT if name in SHELL_HOOK_NAMES else name
        command = hook_command(
            adapter.hooks, transport, adapter.event_state,
            runtime_bin(adapter.home) if name not in ("mainframe-skill-reminder", "mainframe-commit-checkpoint") else None
        )
        found = [h for h in hooks if h.get("command") == command]
        expected = (
            [
                {"eventName": "preToolUse", "matcher": "^apply_patch$", "timeoutSec": 180,
                 "additionalContextLimit": 6000},
                {"eventName": "postToolUse", "matcher": "^apply_patch$", "timeoutSec": 180,
                 "additionalContextLimit": 6000},
                {"eventName": "stop", "matcher": None, "timeoutSec": 180,
                 "additionalContextLimit": None},
            ]
            if name == "mainframe-code-quality"
            else [{"eventName": "postToolUse", "matcher": "^Bash$", "timeoutSec": 2,
                   "additionalContextLimit": 300}] if name == "mainframe-skill-reminder"
            else [{"eventName": "postToolUse", "matcher": "^apply_patch$", "timeoutSec": 5,
                   "additionalContextLimit": 1000}] if name == "mainframe-commit-checkpoint"
            else [{"eventName": "preToolUse", "matcher": "^Bash$", "timeoutSec": 5,
                   "additionalContextLimit": 6000}]
        )
        common = {
            "enabled": True, "sourcePath": str(adapter.codex / "hooks.json"),
            "source": "user", "handlerType": "command",
        }
        remaining = list(found)
        # The four shell identities intentionally share one native process and
        # registration. Discovery of that registration establishes transport
        # availability for each identity; behavior remains a separate probe.
        valid = len(remaining) == len(expected)
        for registration in expected:
            matches = [hook for hook in remaining if all(
                hook.get(key) == value for key, value in {**common, **registration}.items()
            )]
            if len(matches) != 1:
                valid = False
                continue
            remaining.remove(matches[0])
        result["hooks"][name] = {"discovered": valid, "trusted": valid and all(h.get("trustStatus") == "trusted" for h in found),
                               "disabled": (adapter.hooks / (".disabled-" + name)).exists()}
    result["diagnostic_errors"] = sum(len(group.get("errors", [])) for group in skill_result["data"] + hook_result["data"])
    return result
