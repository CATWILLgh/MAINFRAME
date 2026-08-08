#!/usr/bin/env python3
"""Unit tests for python-backend-patterns recon — type_checker detection.

Detection is by CONFIG presence (pyproject `[tool.*]` sections + standalone
config files), not by folding dev-dep strings into the shared deps blob — that
would perturb the other substring detectors. Run: `python3 tools/test_recon.py`
(exit 0 = pass). Stdlib only.
"""

import contextlib
import importlib.util
import io
import sys
import tempfile
from pathlib import Path

_RECON_PATH = (Path(__file__).resolve().parent.parent
               / "adapters/claude-code/plugin" / "skills" / "python-backend-patterns" / "recon.py")
_spec = importlib.util.spec_from_file_location("recon", _RECON_PATH)
recon = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(recon)


def _project(files):
    """Create a temp project dir from {relpath: content}; return its Path."""
    d = Path(tempfile.mkdtemp())
    for rel, content in files.items():
        p = d / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
    return d


def test_detect_pyright_via_tool_section():
    root = _project({"pyproject.toml": '[tool.pyright]\ntypeCheckingMode = "standard"\n'})
    assert recon.detect_type_checker(root) == "pyright"


def test_detect_mypy_via_tool_section():
    root = _project({"pyproject.toml": "[tool.mypy]\nstrict = true\n"})
    assert recon.detect_type_checker(root) == "mypy"


def test_detect_pyright_via_config_file():
    root = _project({"pyrightconfig.json": "{}\n"})
    assert recon.detect_type_checker(root) == "pyright"


def test_detect_mypy_via_ini_and_setupcfg():
    assert recon.detect_type_checker(_project({"mypy.ini": "[mypy]\n"})) == "mypy"
    assert recon.detect_type_checker(_project({"setup.cfg": "[mypy]\nstrict = True\n"})) == "mypy"


def test_detect_none_when_absent():
    root = _project({"pyproject.toml": '[project]\nname = "x"\n'})
    assert recon.detect_type_checker(root) == "none"


def test_detect_both_sorted_join():
    root = _project({"pyproject.toml": "[tool.pyright]\n[tool.mypy]\n"})
    assert recon.detect_type_checker(root) == "mypy+pyright"


def test_malformed_pyproject_is_safe():
    root = _project({"pyproject.toml": "this is not valid toml ::: ["})
    assert recon.detect_type_checker(root) == "none"


def test_main_output_includes_type_checker_line():
    root = _project({"pyproject.toml": "[tool.pyright]\n"})
    buf, argv = io.StringIO(), sys.argv
    sys.argv = ["recon.py", str(root)]
    try:
        with contextlib.redirect_stdout(buf):
            recon.main()
    finally:
        sys.argv = argv
    assert "type_checker: pyright" in buf.getvalue()


def test_type_checker_does_not_perturb_other_detectors():
    # Detecting the checker via tool-sections must not shift the dep-blob detectors:
    # fastapi/sqlalchemy must still resolve alongside a [tool.pyright] section.
    root = _project({"pyproject.toml": (
        '[project]\nname = "x"\ndependencies = ["fastapi", "sqlalchemy"]\n'
        '[tool.pyright]\ntypeCheckingMode = "standard"\n')})
    buf, argv = io.StringIO(), sys.argv
    sys.argv = ["recon.py", str(root)]
    try:
        with contextlib.redirect_stdout(buf):
            recon.main()
    finally:
        sys.argv = argv
    out = buf.getvalue()
    assert "framework: fastapi" in out
    assert "orm: sqlalchemy-2" in out
    assert "type_checker: pyright" in out


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"  ok {t.__name__}")
    print(f"OK recon — {len(tests)} tests passed")


if __name__ == "__main__":
    main()
