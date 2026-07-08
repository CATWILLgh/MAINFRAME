#!/usr/bin/env python3
"""Regression test for ticket 3cd20dc8: the hub semgrep rules directory must
resolve to the shipped location (`hooks/rules`, sibling of `scripts/`), so the
custom rules actually reach semgrep. Stdlib-only."""

import importlib.util
import os
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parent
DETECTORS = REPO / "core/gates/detectors"
sys.path.insert(0, str(DETECTORS))

_spec = importlib.util.spec_from_file_location(
    "nodejs_security_stop_gate", DETECTORS / "nodejs-security-stop-gate.py")
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)


def test_rules_dir_exists_in_source_layout():
    assert os.path.isdir(gate._HUB_RULES_DIR), gate._HUB_RULES_DIR


def test_shipped_rule_reaches_semgrep_config_list():
    configs = gate._hub_rule_configs()
    assert any(c.endswith("frontend-token-storage.yml") for c in configs), configs


def test_render_layout_resolves_too():
    """The deployed tree (`hooks/scripts` + sibling `hooks/rules`) mirrors the
    core layout (`gates/detectors` + sibling `gates/rules`); pin the rendered
    copy's derivation as well."""
    spec = importlib.util.spec_from_file_location(
        "rendered_gate",
        REPO / "plugin-dist/hooks/scripts/nodejs-security-stop-gate.py")
    rendered = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rendered)
    assert os.path.isdir(rendered._HUB_RULES_DIR), rendered._HUB_RULES_DIR
    assert any(c.endswith("frontend-token-storage.yml")
               for c in rendered._hub_rule_configs())


def _run_all():
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    failures = 0
    for t in tests:
        try:
            t()
            print(f"ok   {t.__name__}")
        except AssertionError as e:
            failures += 1
            print(f"FAIL {t.__name__}: {e}")
    print(f"{len(tests) - failures}/{len(tests)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(_run_all())
