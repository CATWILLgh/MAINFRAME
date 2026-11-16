"""Native dependency preparation preserves foreign files and leaves no failed payload."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from installer import core, runtime


class NativeRuntimePreparationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="mainframe-native-runtime-")
        self.addCleanup(self.temporary.cleanup)
        self.home = Path(self.temporary.name).resolve() / "home"
        self.root = runtime.runtime_root(self.home)

    def download(self, version=None):
        version = version or runtime.TOOL_SPECS["squawk"][2]
        binary = f"#!/bin/sh\nprintf 'squawk {version}\\n'\n".encode()
        release = ("sbdchd/squawk", "v" + runtime.TOOL_SPECS["squawk"][2],
                   "synthetic-squawk", None, core.digest(binary))
        return binary, release

    def test_rejected_native_binary_does_not_leave_a_package_payload(self):
        binary, release = self.download("0.0.1")
        with (
            mock.patch.object(runtime, "_native_release", return_value=release),
            mock.patch.object(runtime, "_download_release", return_value=binary),
            self.assertRaisesRegex(core.Conflict, "version probe"),
        ):
            runtime._managed_release(self.root, "squawk")
        self.assertFalse([path for path in self.root.rglob("*") if path.is_file()])

    def test_later_preparation_failure_discards_the_new_native_payload(self):
        binary, release = self.download()
        with (
            mock.patch.dict(os.environ, {"PATH": str(self.home / "no-tools")}),
            mock.patch.object(runtime, "_native_release", return_value=release),
            mock.patch.object(runtime, "_download_release", return_value=binary),
            mock.patch.object(runtime, "_managed_python", side_effect=core.Conflict("synthetic Python failure")),
            self.assertRaisesRegex(core.Conflict, "synthetic Python failure"),
        ):
            runtime.ensure(self.home, ("squawk", "yamllint"))
        packages = self.root / "packages"
        self.assertFalse([path for path in packages.rglob("*") if path.is_file()])
        self.assertFalse((self.root / "installation.json").exists())

    def test_failure_of_a_second_native_download_discards_the_first_payload(self):
        version = runtime.TOOL_SPECS["actionlint"][2]
        binary = f"#!/bin/sh\nprintf 'actionlint {version}\\n'\n".encode()

        def release(name):
            return ("synthetic/release", "v" + runtime.TOOL_SPECS[name][2], name, None,
                    core.digest(binary))

        def download(repo, tag, asset):
            if asset == "squawk":
                raise OSError("synthetic download failure")
            return binary

        with (
            mock.patch.dict(os.environ, {"PATH": str(self.home / "no-tools")}),
            mock.patch.object(runtime, "_native_release", side_effect=release),
            mock.patch.object(runtime, "_download_release", side_effect=download),
            self.assertRaises(core.Conflict),
        ):
            runtime.ensure(self.home, ("actionlint", "squawk"))
        self.assertFalse([path for path in (self.root / "packages").rglob("*") if path.is_file()])

    def test_preparation_preserves_an_unregistered_file_at_the_legacy_release_path(self):
        binary, release = self.download()
        existing = self.root / "packages/release/squawk" / release[1] / "squawk"
        existing.parent.mkdir(parents=True)
        existing.write_text("user-owned file without a MAINFRAME receipt\n")
        before = existing.read_bytes()
        with (
            mock.patch.object(runtime, "_native_release", return_value=release),
            mock.patch.object(runtime, "_download_release", return_value=binary),
        ):
            prepared = runtime._managed_release(self.root, "squawk")
        self.assertEqual(existing.read_bytes(), before)
        self.assertNotEqual(prepared, existing)
        self.assertEqual(prepared.read_bytes(), binary)


if __name__ == "__main__":
    unittest.main()
