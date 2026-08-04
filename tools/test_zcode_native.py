"""Hermetic tests for the ZCode native probe and discovery assertions."""

import importlib.util
import json
import stat
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROBE_PATH = ROOT / "tools" / "probe_zcode_native.py"


def _load_probe():
    spec = importlib.util.spec_from_file_location("probe_zcode_native", PROBE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load ZCode native probe")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ZCodeNativeProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.probe = _load_probe()

    def _fake_cli(self, root: Path, version: str = "0.16.1") -> Path:
        target = root / "fake-zcode"
        target.write_text(
            "#!/usr/bin/env python3\n"
            "import json, os, pathlib, sys\n"
            f"VERSION = {version!r}\n"
            "args = sys.argv[1:]\n"
            "if args == ['--version']:\n"
            "    print('zcode ' + VERSION)\n"
            "    raise SystemExit(0)\n"
            "kind = args[0]\n"
            "root = pathlib.Path(os.environ['HOME']) / '.zcode' / kind\n"
            "suffix = 'SKILL.md' if kind == 'skills' else '*.md'\n"
            "paths = root.glob('*/' + suffix) if kind == 'skills' else root.glob(suffix)\n"
            "items = [{'name': p.parent.name if kind == 'skills' else p.stem} for p in paths]\n"
            "print(json.dumps({kind: items, 'diagnostics': []}))\n",
            encoding="utf-8",
        )
        target.chmod(target.stat().st_mode | stat.S_IXUSR)
        return target

    def test_probe_accepts_pinned_version_and_checks_negative_visibility(self):
        with tempfile.TemporaryDirectory() as directory:
            cli = self._fake_cli(Path(directory))
            result = self.probe.probe(cli)
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["version"], "0.16.1")
        self.assertEqual(result["skills"], {"visible": True, "hidden": False})
        self.assertEqual(result["commands"], {"visible": True, "hidden": False})

    def test_probe_distinguishes_unavailable_and_incompatible_cli(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            unavailable = self.probe.probe(root / "missing")
            incompatible = self.probe.probe(self._fake_cli(root, version="9.9.9"))
        self.assertEqual(unavailable["status"], "unavailable")
        self.assertEqual(incompatible["status"], "incompatible")

    def test_result_is_json_serializable_without_host_paths_on_success(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.probe.probe(self._fake_cli(Path(directory)))
        encoded = json.dumps(result, sort_keys=True)
        self.assertNotIn(directory, encoded)


if __name__ == "__main__":
    unittest.main()
