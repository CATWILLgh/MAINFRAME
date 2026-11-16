"""Runtime recovery preserves references and stops owned preparation processes."""
import os
from pathlib import Path
import signal
import tempfile
import unittest
from unittest import mock

from installer import core, runtime


class SyntheticCrash(BaseException):
    """Leave the ordinary recovery journal in place without exiting the test runner."""


class RuntimeRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="mainframe-runtime-recovery-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.home = self.root / "home"

    def prepare(self, root, names):
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

    def seed(self):
        with mock.patch.dict(os.environ, {"PATH": str(self.root / "no-tools")}), mock.patch.object(runtime, "_managed_python", side_effect=self.prepare):
            runtime.ensure(self.home, ("ruff",))
        return runtime.runtime_root(self.home)

    def test_generic_cleanup_preserves_external_aliases_in_executable_and_node_fields(self):
        for ecosystem in ("python", "node"):
            for field in ("executable", "node"):
                with self.subTest(ecosystem=ecosystem, field=field):
                    root = self.root / ecosystem / field
                    parent = root / "packages" / ecosystem
                    parent.mkdir(parents=True)
                    generation = Path(tempfile.mkdtemp(prefix=f"mainframe-{ecosystem}-", dir=parent))
                    executable = generation / "bin/tool"
                    executable.parent.mkdir()
                    executable.write_text("preserve referenced package")
                    alias = root / "external-alias"
                    alias.symlink_to(executable)
                    runtime._cleanup_generations(root, {"old": {"executable": str(executable)}},
                                                 {"other": {field: str(alias)}}, ecosystem)
                    self.assertEqual(alias.read_text(), "preserve referenced package")

    def test_preparation_interruption_stops_and_reaps_its_owned_group(self):
        process = mock.Mock(pid=12345)
        process.communicate.side_effect = KeyboardInterrupt
        events = []
        process.wait.side_effect = lambda **options: events.append("reaped")
        with (
            mock.patch.object(runtime.subprocess, "Popen", return_value=process) as spawn,
            mock.patch.object(runtime.os, "killpg", side_effect=lambda *arguments: events.append("killed")) as kill,
            self.assertRaises(KeyboardInterrupt),
        ):
            runtime._run(["synthetic-owned-preparation"], timeout=1)
        self.assertTrue(spawn.call_args.kwargs["start_new_session"])
        kill.assert_called_once_with(process.pid, signal.SIGKILL)
        self.assertEqual(events, ["killed", "reaped"])
        process.wait.assert_called_once_with(timeout=5)
        process.stdout.close.assert_called_once()
        process.stderr.close.assert_called_once()

    def test_activation_preserves_an_unregistered_launcher_and_discards_its_stage(self):
        root = self.seed()
        manifest = root / "installation.json"
        before = manifest.read_bytes(), (root / "bin/ruff").read_bytes()
        foreign = root / "bin/yamllint"
        foreign.write_text("user-owned launcher")
        foreign.chmod(0o750)
        with (
            mock.patch.dict(os.environ, {"PATH": str(self.root / "no-tools")}),
            mock.patch.object(runtime, "_managed_python", side_effect=self.prepare),
            self.assertRaisesRegex(core.Conflict, "no installer ownership"),
        ):
            runtime.ensure(self.home, ("yamllint",))
        self.assertEqual((manifest.read_bytes(), (root / "bin/ruff").read_bytes()), before)
        self.assertEqual(foreign.read_text(), "user-owned launcher")
        self.assertEqual(foreign.stat().st_mode & 0o777, 0o750)
        self.assertEqual(len(list((root / "packages/python").glob("mainframe-python-*"))), 1)

    def test_recovery_conflict_keeps_user_edits_journal_and_both_generations(self):
        root = self.seed()
        shim = root / "bin/ruff"
        manifest = root / "installation.json"
        previous_manifest = manifest.read_bytes()
        original = core.atomic_write

        def write(path, data, mode=0o600):
            if path == manifest:
                shim.write_text("user edit during activation")
                raise OSError("synthetic activation failure")
            original(path, data, mode)

        with (
            mock.patch.dict(os.environ, {"PATH": str(self.root / "no-tools")}),
            mock.patch.object(runtime, "_managed_python", side_effect=self.prepare),
            mock.patch.object(core, "atomic_write", side_effect=write),
            mock.patch.object(runtime, "atomic_write", side_effect=write),
            self.assertRaisesRegex(core.Conflict, "manual recovery"),
        ):
            runtime.ensure(self.home, ("yamllint",))
        journal = root / ".analyzers-recovery.json"
        self.assertTrue(journal.is_file())
        self.assertEqual(shim.read_text(), "user edit during activation")
        self.assertEqual(manifest.read_bytes(), previous_manifest)
        self.assertEqual(len(list((root / "packages/python").glob("mainframe-python-*"))), 2)
        with mock.patch.object(runtime, "_managed_python", side_effect=AssertionError("recovery conflict must stop preparation")):
            with self.assertRaisesRegex(core.Conflict, "manual recovery"):
                runtime.ensure(self.home, ("ruff",))
        self.assertTrue(journal.is_file())
        self.assertEqual(shim.read_text(), "user edit during activation")

    def test_cleanup_refusal_keeps_a_retryable_journal_after_files_are_restored(self):
        root = self.seed()
        shim = root / "bin/ruff"
        manifest = root / "installation.json"
        before = shim.read_bytes(), manifest.read_bytes()
        original = core.atomic_write

        def crash(path, data, mode=0o600):
            original(path, data, mode)
            if path == shim:
                raise SyntheticCrash

        with (
            mock.patch.dict(os.environ, {"PATH": str(self.root / "no-tools")}),
            mock.patch.object(runtime, "_managed_python", side_effect=self.prepare),
            mock.patch.object(core, "atomic_write", side_effect=crash),
            self.assertRaises(SyntheticCrash),
        ):
            runtime.ensure(self.home, ("yamllint",))
        journal = root / ".analyzers-recovery.json"
        recovery_before = journal.read_bytes()
        packages = root / "packages"
        relocated = self.root / "relocated-packages"
        packages.rename(relocated)
        packages.symlink_to(relocated, target_is_directory=True)
        with self.assertRaisesRegex(core.Conflict, "symlink"):
            runtime.ensure(self.home, ("ruff",))
        self.assertEqual((shim.read_bytes(), manifest.read_bytes()), before)
        self.assertEqual(journal.read_bytes(), recovery_before)
        self.assertEqual(len(list((relocated / "python").glob("mainframe-python-*"))), 2)
        packages.unlink()
        relocated.rename(packages)
        with mock.patch.object(runtime, "_managed_python", side_effect=AssertionError("restored tools need no install")):
            self.assertTrue(runtime.ensure(self.home, ("ruff",))["ready"])
        self.assertFalse(journal.exists())
        self.assertEqual(len(list((packages / "python").glob("mainframe-python-*"))), 1)

    def test_normal_rollback_retains_recovery_metadata_until_stage_cleanup_succeeds(self):
        root = self.seed()
        shim = root / "bin/ruff"
        manifest = root / "installation.json"
        before = shim.read_bytes(), manifest.read_bytes()
        original = core.atomic_write

        def fail(path, data, mode=0o600):
            if path.name == "yamllint":
                raise OSError("synthetic write failure")
            original(path, data, mode)

        with (
            mock.patch.dict(os.environ, {"PATH": str(self.root / "no-tools")}),
            mock.patch.object(runtime, "_managed_python", side_effect=self.prepare),
            mock.patch.object(core, "atomic_write", side_effect=fail),
            mock.patch.object(runtime, "_discard_generation", side_effect=OSError("synthetic cleanup refusal")),
            self.assertRaisesRegex(OSError, "synthetic cleanup refusal"),
        ):
            runtime.ensure(self.home, ("yamllint",))
        journal = root / ".analyzers-recovery.json"
        self.assertEqual((shim.read_bytes(), manifest.read_bytes()), before)
        self.assertTrue(journal.is_file())
        self.assertEqual(len(list((root / "packages/python").glob("mainframe-python-*"))), 2)
        with mock.patch.object(runtime, "_managed_python", side_effect=AssertionError("restored tools need no install")):
            self.assertTrue(runtime.ensure(self.home, ("ruff",))["ready"])
        self.assertFalse(journal.exists())
        self.assertEqual(len(list((root / "packages/python").glob("mainframe-python-*"))), 1)


if __name__ == "__main__":
    unittest.main()
