"""Shared analyzer bindings survive failed or interrupted activation."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

from installer import core, runtime

ROOT = Path(__file__).resolve().parents[1]


def prepare_python(root, names):
    parent = root / "packages/python"
    parent.mkdir(parents=True, exist_ok=True)
    generation = Path(tempfile.mkdtemp(prefix="mainframe-python-", dir=parent))
    result = {}
    for name in names:
        executable = generation / "bin" / name
        executable.parent.mkdir(exist_ok=True)
        executable.write_text(f"#!/bin/sh\nprintf '{name} {runtime.TOOL_SPECS[name][2]}\\n'\n")
        executable.chmod(0o755)
        result[name] = executable
    return result


class RuntimeActivationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="mainframe-activation-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()

    def seed(self, home):
        root = runtime.runtime_root(home)
        tools = prepare_python(root, ["ruff"])
        executable = tools["ruff"]
        shim = runtime.runtime_bin(home) / "ruff"
        shim.parent.mkdir()
        shim.write_bytes(runtime._analyzer_shim("ruff", executable))
        shim.chmod(0o755)
        manifest = root / "installation.json"
        manifest.write_text(json.dumps({"schema": 1, "tools": {"ruff": {
            "executable": str(executable), "version": runtime.TOOL_SPECS["ruff"][2],
            "managed_generation": str(executable.parents[1]),
        }}}))
        return root, shim, manifest

    def test_failed_activation_restores_bindings_and_discards_new_generation(self):
        for boundary in ("yamllint", "installation.json"):
            with self.subTest(boundary=boundary):
                home = self.root / boundary
                root, shim, manifest = self.seed(home)
                before = shim.read_bytes(), manifest.read_bytes()
                original = core.atomic_write
                failed = False

                def write(path, data, mode=0o600):
                    nonlocal failed
                    if path.name == boundary and not failed:
                        failed = True
                        raise OSError("synthetic activation failure")
                    original(path, data, mode)

                with (
                    mock.patch.dict(os.environ, {"PATH": str(self.root / "no-tools")}),
                    mock.patch.object(runtime, "_managed_python", side_effect=prepare_python),
                    mock.patch.object(runtime, "atomic_write", side_effect=write),
                    mock.patch.object(core, "atomic_write", side_effect=write),
                    self.assertRaisesRegex(OSError, "synthetic activation failure"),
                ):
                    runtime.ensure(home, ("yamllint",))
                self.assertEqual((shim.read_bytes(), manifest.read_bytes()), before)
                self.assertFalse((shim.parent / "yamllint").exists())
                self.assertEqual(len(list((root / "packages/python").glob("mainframe-python-*"))), 1)
                self.assertTrue(runtime.status(home, ("ruff",))["ready"])

    def test_next_ensure_recovers_abrupt_activation_and_removes_abandoned_generation(self):
        home = self.root / "crash"
        root, shim, manifest = self.seed(home)
        seed = Path(__file__).resolve()
        program = '''
import importlib.util, os, sys
from pathlib import Path
from unittest import mock
from installer import core, runtime
spec = importlib.util.spec_from_file_location("activation_fixtures", sys.argv[2])
fixtures = importlib.util.module_from_spec(spec); spec.loader.exec_module(fixtures)
original = core.atomic_write
def write(path, data, mode=0o600):
    original(path, data, mode)
    if path.name == "ruff":
        os._exit(79)
with mock.patch.object(runtime, "_managed_python", side_effect=fixtures.prepare_python), \\
     mock.patch.object(runtime, "atomic_write", side_effect=write), \\
     mock.patch.object(core, "atomic_write", side_effect=write):
    runtime.ensure(Path(sys.argv[1]), ("yamllint",))
'''
        environment = {**os.environ, "PATH": str(self.root / "no-tools")}
        child = subprocess.run([sys.executable, "-B", "-c", program, str(home), str(seed)],
                               cwd=ROOT, env=environment, capture_output=True, text=True, timeout=10)
        self.assertEqual(child.returncode, 79, child.stderr)
        with (
            mock.patch.dict(os.environ, {"PATH": environment["PATH"]}),
            mock.patch.object(runtime, "_managed_python", side_effect=prepare_python),
        ):
            self.assertTrue(runtime.ensure(home, ("ruff", "yamllint"))["ready"])
        generations = list((root / "packages/python").glob("mainframe-python-*"))
        self.assertEqual(len(generations), 1, "interrupted activation retained an unused generation")
        rows = json.loads(manifest.read_text())["tools"]
        for name in ("ruff", "yamllint"):
            self.assertTrue(Path(rows[name]["executable"]).is_file())
        self.assertFalse(list(root.glob("*-recovery.json")))

    def test_preparation_timeout_stops_owned_descendants_before_cleanup(self):
        pid_file = self.root / "child.pid"
        heartbeat, stop, done = (self.root / name for name in ("heartbeat", "stop", "done"))
        program = '''
import subprocess, sys, time
from pathlib import Path
child_code = """
import sys, time
from pathlib import Path
heartbeat, stop, done = map(Path, sys.argv[1:])
deadline = time.monotonic() + 10
while not stop.exists() and time.monotonic() < deadline:
    heartbeat.write_text(str(time.monotonic_ns()))
    time.sleep(0.02)
done.touch()
"""
child = subprocess.Popen([sys.executable, "-B", "-c", child_code, *sys.argv[2:]],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
Path(sys.argv[1]).write_text(str(child.pid))
time.sleep(15)
'''
        running = False
        try:
            with self.assertRaises(core.Conflict):
                runtime._run([sys.executable, "-B", "-c", program, str(pid_file),
                              str(heartbeat), str(stop), str(done)], timeout=1)
            self.assertTrue(pid_file.is_file() and heartbeat.is_file(), "fixture child did not start")
            before = heartbeat.read_bytes()
            deadline = time.monotonic() + 1
            while time.monotonic() < deadline:
                if heartbeat.read_bytes() != before:
                    running = True
                    break
                time.sleep(0.02)
            self.assertFalse(running, "timed-out preparation left its child writing after cleanup")
        finally:
            stop.touch()
            deadline = time.monotonic() + 2
            while running and not done.exists() and time.monotonic() < deadline:
                time.sleep(0.02)

    def test_next_ensure_removes_an_openspec_generation_abandoned_during_activation(self):
        import test_runtime as runtime_fixtures

        fixture = runtime_fixtures.RuntimeSupportTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        environment = {**os.environ, **fixture.openspec_fixture()}
        program = '''
import os, sys
from pathlib import Path
from unittest import mock
from installer import core, runtime
original = core.atomic_write
def write(path, data, mode=0o600):
    original(path, data, mode)
    if path.name == "openspec":
        os._exit(79)
with mock.patch.object(core, "atomic_write", side_effect=write):
    runtime.ensure(Path(sys.argv[1]), ("openspec",))
'''
        child = subprocess.run([sys.executable, "-B", "-c", program, str(fixture.home)],
                               cwd=ROOT, env=environment, capture_output=True, text=True, timeout=10)
        self.assertEqual(child.returncode, 79, child.stderr)
        with mock.patch.dict(os.environ, environment):
            self.assertTrue(runtime.ensure(fixture.home, ("openspec",))["ready"])
        root = runtime.runtime_root(fixture.home)
        self.assertEqual(len(list((root / "packages").glob("openspec-*"))), 1)
        self.assertFalse((root / ".openspec-recovery.json").exists())


if __name__ == "__main__":
    unittest.main()
