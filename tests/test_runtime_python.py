"""Real pip writes remain inside an allocated runtime despite ambient destinations."""
import io
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from unittest import mock
import zipfile

from installer import core, runtime


class PythonRuntimeDestinationTests(unittest.TestCase):
    def test_timed_out_source_build_leaves_the_ambient_temporary_directory_unchanged(self):
        with tempfile.TemporaryDirectory(prefix="mainframe-pip-timeout-") as temporary:
            base = Path(temporary).resolve()
            ambient = base / "ambient"
            ambient.mkdir()
            sentinel = ambient / "user-note"
            sentinel.write_text("preserve")
            marker = base / "backend-entered"
            files = {
                "pyproject.toml": '[build-system]\nrequires=[]\nbuild-backend="backend"\nbackend-path=["."]\n',
                "backend.py": (
                    "import os, time\nfrom pathlib import Path\n"
                    "def get_requires_for_build_wheel(config_settings=None):\n"
                    "    Path(os.environ['MAINFRAME_PIP_BUILD_ENTERED']).touch()\n"
                    "    time.sleep(30)\n    return []\n"
                ),
            }
            with tarfile.open(base / "yamllint-1.38.0.tar.gz", "w:gz") as archive:
                for name, value in files.items():
                    data = value.encode()
                    member = tarfile.TarInfo("yamllint-1.38.0/" + name)
                    member.size = len(data)
                    archive.addfile(member, io.BytesIO(data))
            environment = {
                "PATH": os.defpath, "TMPDIR": str(ambient), "TMP": str(ambient), "TEMP": str(ambient),
                "PIP_CONFIG_FILE": os.devnull, "PIP_NO_INDEX": "1", "PIP_FIND_LINKS": str(base),
                "PIP_DISABLE_PIP_VERSION_CHECK": "1", "MAINFRAME_PIP_BUILD_ENTERED": str(marker),
            }
            original = runtime._run

            def bounded(command, **options):
                if "pip" in command:
                    options["timeout"] = 3
                return original(command, **options)

            with (
                mock.patch.dict(os.environ, environment, clear=True),
                mock.patch.object(runtime, "_run", side_effect=bounded),
                self.assertRaises(core.Conflict),
            ):
                runtime._managed_python(base / "runtime", ["yamllint"])
            self.assertTrue(marker.is_file(), "source-build fixture did not enter its slow hook")
            self.assertEqual(list(ambient.iterdir()), [sentinel])
            self.assertEqual(sentinel.read_text(), "preserve")

    def test_pip_destination_and_output_overrides_cannot_escape_the_generation(self):
        with tempfile.TemporaryDirectory(prefix="mainframe-pip-destination-") as temporary:
            base = Path(temporary).resolve()
            wheel = base / "yamllint-1.38.0-py3-none-any.whl"
            info = "yamllint-1.38.0.dist-info"
            files = {
                "mainframe_synthetic_yamllint.py": "def main():\n    print('yamllint 1.38.0')\n",
                info + "/METADATA": "Metadata-Version: 2.1\nName: yamllint\nVersion: 1.38.0\n",
                info + "/WHEEL": "Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
                info + "/entry_points.txt": "[console_scripts]\nyamllint = mainframe_synthetic_yamllint:main\n",
            }
            files[info + "/RECORD"] = "".join(name + ",,\n" for name in files) + info + "/RECORD,,\n"
            with zipfile.ZipFile(wheel, "w") as archive:
                for name, value in files.items():
                    archive.writestr(name, value)

            for scenario in ("environment", "configuration", "combined"):
                with self.subTest(scenario=scenario):
                    work = base / scenario
                    work.mkdir()
                    scratch = work / "tmp"
                    scratch.mkdir()
                    outside = work / "outside"
                    environment = {
                        "PATH": os.defpath, "TMPDIR": str(scratch),
                        "PIP_CONFIG_FILE": os.devnull, "PIP_NO_INDEX": "1",
                        "PIP_FIND_LINKS": str(base), "PIP_DISABLE_PIP_VERSION_CHECK": "1",
                    }
                    if scenario in ("environment", "combined"):
                        environment["PIP_TARGET"] = str(outside / "env-target")
                    if scenario in ("configuration", "combined"):
                        config = work / "pip.conf"
                        config.write_text(
                            "[global]\nindex-url = https://example.invalid/simple\n"
                            f"log = {outside / 'install.log'}\n[install]\n"
                            f"target = {outside / 'config-target'}\nreport = {outside / 'report.json'}\n"
                        )
                        environment["PIP_CONFIG_FILE"] = str(config)
                    if scenario == "combined":
                        environment.update(PIP_PREFIX=str(outside / "prefix"),
                                           PIP_ROOT=str(outside / "root"), PIP_USER="1")
                    result, failure = None, None
                    with mock.patch.dict(os.environ, environment, clear=True):
                        try:
                            result = runtime._managed_python(work / "runtime", ["yamllint"])
                        except core.Conflict as error:
                            failure = error
                    self.assertFalse(outside.exists(), "pip wrote outside its allocated generation")
                    self.assertIsNone(failure, f"bounded preparation failed: {failure}")
                    executable = result["yamllint"]
                    self.assertTrue(executable.is_relative_to(work / "runtime/packages/python"))
                    version = subprocess.run([str(executable), "--version"], capture_output=True,
                                             text=True, timeout=5, check=True)
                    self.assertEqual(version.stdout.strip(), "yamllint 1.38.0")


if __name__ == "__main__":
    unittest.main()
