"""Runtime recovery preserves references and stops owned preparation processes."""
import json
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
        for ecosystem in ("python", "node", "release", "openspec"):
            for field in ("executable", "node"):
                with self.subTest(ecosystem=ecosystem, field=field):
                    root = self.root / ecosystem / field
                    parent = root / "packages" if ecosystem == "openspec" else root / "packages" / ecosystem
                    parent.mkdir(parents=True)
                    prefix = "openspec" if ecosystem == "openspec" else f"mainframe-{ecosystem}"
                    generation = Path(tempfile.mkdtemp(prefix=prefix + "-", dir=parent))
                    name = {"python": "ruff", "node": "oxlint", "release": "squawk", "openspec": "openspec"}[ecosystem]
                    executable = generation / "bin" / name
                    if ecosystem == "release":
                        executable = generation / name
                    elif ecosystem == "openspec":
                        executable = generation / "node_modules" / runtime.OPENSPEC_PACKAGE / "bin/openspec.js"
                    executable.parent.mkdir(parents=True, exist_ok=True)
                    executable.write_text("preserve referenced package")
                    alias = root / "external-alias"
                    alias.symlink_to(executable)
                    runtime._cleanup_generations(root, {name: {"executable": str(executable),
                                                              "managed_generation": str(generation)}},
                                                 {"other": {field: str(alias)}}, ecosystem)
                    self.assertEqual(alias.read_text(), "preserve referenced package")

    def test_reusing_a_different_candidate_does_not_transfer_generation_ownership(self):
        root = self.seed()
        manifest = root / "installation.json"
        before = json.loads(manifest.read_text())["tools"]["ruff"]
        owned = Path(before["managed_generation"])
        Path(before["executable"]).write_text("#!/bin/sh\nprintf 'ruff 0.0.1\\n'\n")
        foreign = root / "packages/python/mainframe-python-foreign1"
        replacement = foreign / "bin/ruff"
        replacement.parent.mkdir(parents=True)
        replacement.write_text(f"#!/bin/sh\nprintf 'ruff {runtime.TOOL_SPECS['ruff'][2]}\\n'\n")
        replacement.chmod(0o755)
        note = foreign / "user-note"
        note.write_text("preserve")
        with (
            mock.patch.dict(os.environ, {"PATH": str(replacement.parent)}),
            mock.patch.object(runtime, "_managed_python", side_effect=AssertionError("compatible replacement needs no install")),
        ):
            self.assertTrue(runtime.ensure(self.home, ("ruff",))["ready"])
        current = json.loads(manifest.read_text())["tools"]["ruff"]
        self.assertEqual(current["executable"], str(replacement))
        self.assertNotIn("managed_generation", current)
        self.assertFalse(owned.exists())
        self.assertEqual(note.read_text(), "preserve")

    def native_fixture(self):
        binaries = {name: f"#!/bin/sh\nprintf '{name} {runtime.TOOL_SPECS[name][2]}\\n'\n".encode()
                    for name in ("squawk", "actionlint")}

        def release(name):
            return "synthetic/release", "v" + runtime.TOOL_SPECS[name][2], name, None, core.digest(binaries[name])

        return release, lambda repo, tag, asset: binaries[asset]

    def test_native_replacement_removes_only_its_previously_allocated_generation(self):
        release, download = self.native_fixture()
        root = runtime.runtime_root(self.home)
        manifest = root / "installation.json"
        with (
            mock.patch.dict(os.environ, {"PATH": str(self.root / "no-tools")}),
            mock.patch.object(runtime, "_native_release", side_effect=release),
            mock.patch.object(runtime, "_download_release", side_effect=download) as fetch,
        ):
            runtime.ensure(self.home, ("squawk",))
            old = json.loads(manifest.read_text())["tools"]["squawk"]
            generation = Path(old["managed_generation"])
            Path(old["executable"]).write_text("#!/bin/sh\nprintf 'squawk 0.0.1\\n'\n")
            foreign = root / "packages/release/mainframe-release-foreign1/user-note"
            foreign.parent.mkdir()
            foreign.write_text("preserve unregistered directory")
            legacy = root / "packages/release/squawk/legacy/squawk"
            legacy.parent.mkdir(parents=True)
            legacy.write_text("preserve path-only legacy file")
            self.assertTrue(runtime.ensure(self.home, ("squawk",))["ready"])
            self.assertTrue(runtime.ensure(self.home, ("squawk",))["ready"])
            self.assertEqual(fetch.call_count, 2)
        current = json.loads(manifest.read_text())["tools"]["squawk"]
        self.assertNotEqual(current["managed_generation"], old["managed_generation"])
        self.assertEqual(Path(current["executable"]).parent, Path(current["managed_generation"]))
        self.assertFalse(generation.exists())
        self.assertEqual(foreign.read_text(), "preserve unregistered directory")
        self.assertEqual(legacy.read_text(), "preserve path-only legacy file")

    def test_native_stages_follow_normal_rollback_and_interrupted_activation_recovery(self):
        release, download = self.native_fixture()
        for abrupt in (False, True):
            with self.subTest(abrupt=abrupt):
                home = self.home / str(abrupt)
                root = runtime.runtime_root(home)
                manifest = root / "installation.json"
                with (
                    mock.patch.dict(os.environ, {"PATH": str(self.root / "no-tools")}),
                    mock.patch.object(runtime, "_native_release", side_effect=release),
                    mock.patch.object(runtime, "_download_release", side_effect=download),
                ):
                    runtime.ensure(home, ("squawk",))
                    shim = root / "bin/squawk"
                    before = shim.read_bytes(), manifest.read_bytes()
                    original = core.atomic_write

                    def interrupt(path, data, mode=0o600):
                        if not abrupt and path == manifest:
                            raise OSError("synthetic native activation failure")
                        original(path, data, mode)
                        if abrupt and path.name == "actionlint":
                            raise SyntheticCrash

                    with mock.patch.object(core, "atomic_write", side_effect=interrupt):
                        with self.assertRaises(SyntheticCrash if abrupt else OSError):
                            runtime.ensure(home, ("actionlint",))
                    journal = root / ".analyzers-recovery.json"
                    self.assertEqual(journal.exists(), abrupt)
                    self.assertTrue(runtime.ensure(home, ("squawk",))["ready"])
                self.assertEqual((shim.read_bytes(), manifest.read_bytes()), before)
                self.assertFalse(journal.exists())
                self.assertFalse((root / "bin/actionlint").exists())
                self.assertEqual(len(list((root / "packages/release").glob("mainframe-release-*"))), 1)

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

    def test_activation_refuses_a_launcher_edit_made_during_preparation(self):
        root = self.seed()
        shim = root / "bin/ruff"
        manifest = root / "installation.json"
        before = manifest.read_bytes()
        private = "SYNTHETIC_PRIVATE_MARKER"

        def prepare(root, names):
            result = self.prepare(root, names)
            shim.write_text(private)
            return result

        with (
            mock.patch.dict(os.environ, {"PATH": str(self.root / "no-tools")}),
            mock.patch.object(runtime, "_managed_python", side_effect=prepare),
            self.assertRaisesRegex(core.Conflict, "changed after planning") as refused,
        ):
            runtime.ensure(self.home, ("yamllint",))
        self.assertEqual(shim.read_text(), private)
        self.assertNotIn(private, str(refused.exception))
        self.assertEqual(manifest.read_bytes(), before)
        self.assertFalse((root / "bin/yamllint").exists())
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

    def test_pending_retirements_retain_alias_proof_and_merge_without_duplicate_generations(self):
        root = self.seed()
        manifest = root / "installation.json"
        record = json.loads(manifest.read_text())
        first = Path(record["tools"]["ruff"]["managed_generation"])
        first_alias = self.root / "first-alias"
        first_alias.symlink_to(Path(record["tools"]["ruff"]["executable"]))
        record["tools"]["first-external"] = {"executable": str(first_alias)}
        manifest.write_text(json.dumps(record))
        with mock.patch.dict(os.environ, {"PATH": str(self.root / "no-tools")}), mock.patch.object(runtime, "_managed_python", side_effect=self.prepare):
            runtime.ensure(self.home, ("yamllint",))
            record = json.loads(manifest.read_text())
            self.assertEqual(len(record["pending_retirements"]), 1)
            second = Path(record["tools"]["ruff"]["managed_generation"])
            second_alias = self.root / "second-alias"
            second_alias.symlink_to(Path(record["tools"]["ruff"]["executable"]))
            record["tools"]["second-external"] = {"node": str(second_alias)}
            record["pending_retirements"].append(dict(record["pending_retirements"][0]))
            manifest.write_text(json.dumps(record))
            runtime.ensure(self.home, ("semgrep",))
        record = json.loads(manifest.read_text())
        pending = record["pending_retirements"]
        self.assertEqual(len(pending), 2)
        self.assertEqual({Path(row["managed_generation"]) for row in pending}, {first, second})
        self.assertTrue(first_alias.is_file() and second_alias.is_file())
        foreign = root / "packages/python/mainframe-python-foreign1/user-note"
        foreign.parent.mkdir()
        foreign.write_text("preserve unregistered data")
        del record["tools"]["first-external"], record["tools"]["second-external"]
        manifest.write_text(json.dumps(record))
        with mock.patch.object(runtime, "_managed_python", side_effect=AssertionError("ready tools need no preparation")):
            self.assertTrue(runtime.ensure(self.home, ("ruff", "yamllint", "semgrep"))["ready"])
        self.assertFalse(first.exists() or second.exists())
        self.assertEqual(json.loads(manifest.read_text()).get("pending_retirements", []), [])
        self.assertEqual(foreign.read_text(), "preserve unregistered data")

    def test_retirement_receipt_write_failure_is_idempotently_retried_after_deletion(self):
        root = self.seed()
        manifest = root / "installation.json"
        old = Path(json.loads(manifest.read_text())["tools"]["ruff"]["managed_generation"])
        write = runtime.atomic_write

        def fail_clear(path, data, mode=0o600):
            if path == manifest and not old.exists():
                raise OSError("synthetic receipt update failure")
            write(path, data, mode)

        with (
            mock.patch.dict(os.environ, {"PATH": str(self.root / "no-tools")}),
            mock.patch.object(runtime, "_managed_python", side_effect=self.prepare),
            mock.patch.object(runtime, "atomic_write", side_effect=fail_clear),
            self.assertRaisesRegex(OSError, "synthetic receipt update failure"),
        ):
            runtime.ensure(self.home, ("yamllint",))
        self.assertFalse(old.exists())
        record = json.loads(manifest.read_text())
        self.assertEqual(record["pending_retirements"][0]["managed_generation"], str(old))
        active = record["tools"]
        self.assertFalse(list(root.glob("*-recovery.json")))
        with mock.patch.object(runtime, "_managed_python", side_effect=AssertionError("ready tools need no preparation")):
            self.assertTrue(runtime.ensure(self.home, ("ruff", "yamllint"))["ready"])
        record = json.loads(manifest.read_text())
        self.assertEqual(record["tools"], active)
        self.assertEqual(record.get("pending_retirements", []), [])

    def test_retirement_preserves_a_concurrent_manifest_edit(self):
        root = self.seed()
        manifest = root / "installation.json"
        discard = runtime._discard_generation

        def edit_after_deletion(path, owner):
            discard(path, owner)
            record = json.loads(manifest.read_text())
            record["user_annotation"] = "preserve concurrent update"
            manifest.write_text(json.dumps(record))

        with (
            mock.patch.dict(os.environ, {"PATH": str(self.root / "no-tools")}),
            mock.patch.object(runtime, "_managed_python", side_effect=self.prepare),
            mock.patch.object(runtime, "_discard_generation", side_effect=edit_after_deletion),
            self.assertRaisesRegex(core.Conflict, "changed during retirement"),
        ):
            runtime.ensure(self.home, ("yamllint",))
        self.assertEqual(json.loads(manifest.read_text())["user_annotation"], "preserve concurrent update")
        with mock.patch.object(runtime, "_managed_python", side_effect=AssertionError("ready tools need no preparation")):
            self.assertTrue(runtime.ensure(self.home, ("ruff", "yamllint"))["ready"])
        self.assertEqual(json.loads(manifest.read_text())["user_annotation"], "preserve concurrent update")


if __name__ == "__main__":
    unittest.main()
