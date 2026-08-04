"""Cross-adapter Python import isolation contracts."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent


def test_zcode_and_antigravity_builders_are_order_independent() -> None:
    script = """
import importlib.util
import sys
import tempfile
from pathlib import Path

repo = Path(sys.argv[1])
order = sys.argv[2].split(',')
sys.path.insert(0, str(repo / 'tools'))

def load(name):
    path = repo / 'adapters' / name / 'build_bundle.py'
    spec = importlib.util.spec_from_file_location('test_' + name, path)
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(path.parent))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    return module

modules = {name: load(name) for name in order}
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    zcode = root / 'zcode'
    antigravity = root / 'antigravity'
    modules['zcode-desktop'].materialize(repo, zcode)
    modules['antigravity-2'].materialize(repo, antigravity)
    assert (zcode / 'hook-config.json').is_file()
    assert (antigravity / 'plugin/plugin.json').is_file()
"""
    for order in (
        "zcode-desktop,antigravity-2",
        "antigravity-2,zcode-desktop",
    ):
        result = subprocess.run(
            [sys.executable, "-c", script, str(REPO), order],
            text=True,
            capture_output=True,
            timeout=30,
        )
        assert result.returncode == 0, (order, result.stdout, result.stderr)
