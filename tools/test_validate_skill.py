#!/usr/bin/env python3
"""Tests for tools/validate-skill.py (needs the validators' .venv: tiktoken,
pyyaml). Pins every rule id and the root-split behaviour (LIVE_ROOTS vs
SUMMARY_ROOTS) that per-edit hook validation and the SessionStart summary
depend on."""

import importlib.util
import shutil
import sys
import tempfile
from pathlib import Path

TOOLS = Path(__file__).resolve().parent

_spec = importlib.util.spec_from_file_location(
    "validate_skill_mod", TOOLS / "validate-skill.py")
vs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vs)


def make_skill(name="sample-skill", description="A sample skill.",
               extra_fm="", body="Body text.\n", files=None):
    root = Path(tempfile.mkdtemp(prefix="vs-test-"))
    skill = root / name
    skill.mkdir()
    fm = f"---\nname: {name}\ndescription: {description}\n{extra_fm}---\n\n"
    (skill / "SKILL.md").write_text(fm + body)
    for rel, content in (files or {}).items():
        p = skill / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            p.write_bytes(content)
        else:
            p.write_text(content)
    return skill


def rules_of(skill_dir):
    return {i["rule"] for i in vs.validate_skill(skill_dir)}


def cleanup(skill_dir):
    shutil.rmtree(skill_dir.parent)


def test_valid_skill_has_no_issues():
    s = make_skill()
    assert vs.validate_skill(s) == []
    cleanup(s)


def test_fm_required_and_parse():
    s = make_skill()
    (s / "SKILL.md").write_text("---\nname: sample-skill\n---\n\nBody.\n")
    assert "FM-REQUIRED" in rules_of(s)
    (s / "SKILL.md").write_text("---\n: [broken\n---\n\nBody.\n")
    assert "FM-PARSE" in rules_of(s)
    cleanup(s)


def test_name_format_and_dir_mismatch():
    s = make_skill(description="d")
    (s / "SKILL.md").write_text(
        "---\nname: Bad Name!\ndescription: d\n---\n\nBody.\n")
    assert "NAME-FMT" in rules_of(s)
    (s / "SKILL.md").write_text(
        "---\nname: other-name\ndescription: d\n---\n\nBody.\n")
    assert "NAME-DIR" in rules_of(s)
    cleanup(s)


def test_description_caps():
    s = make_skill(description='"' + "x" * 1100 + '"')
    assert "DESC-LEN" in rules_of(s)
    cleanup(s)
    s = make_skill(description='"' + "x" * 900 + '"',
                   extra_fm='when_to_use: "' + "y" * 700 + '"\n')
    assert "DESC-WHEN-LEN" in rules_of(s)
    cleanup(s)


def test_body_budget_caps():
    s = make_skill(body="x\n" * 501)
    assert "BODY-LINES" in rules_of(s)
    cleanup(s)
    s = make_skill(body="word " * 9000 + "\n")
    assert "BODY-TOKENS" in rules_of(s)
    cleanup(s)


def test_depth_flags_nested_reference():
    s = make_skill(body="See [deep](a/b/c.md).\n",
                   files={"a/b/c.md": "deep\n"})
    assert "DEPTH" in rules_of(s)
    cleanup(s)


def test_dead_supp_and_referenced_supp():
    s = make_skill(files={"extra.md": "unreferenced\n"})
    assert "DEAD-SUPP" in rules_of(s)
    cleanup(s)
    s = make_skill(body="See [extra](extra.md).\n",
                   files={"extra.md": "referenced\n"})
    assert "DEAD-SUPP" not in rules_of(s)
    cleanup(s)


def test_dead_supp_ignores_bytecode_caches():
    s = make_skill(files={"__pycache__/recon.cpython-313.pyc": b"\x00junk"})
    assert "DEAD-SUPP" not in rules_of(s)
    cleanup(s)


def test_supp_line_cap_and_format():
    s = make_skill(body="See [big](big.md).\n",
                   files={"big.md": "line\n" * 61})
    assert "SUPP-LINES" in rules_of(s)
    cleanup(s)
    s = make_skill(files={"bad.md": b"\xff\xfe broken"})
    assert "FORMAT" in rules_of(s)
    cleanup(s)


def test_live_roots_accept_three_and_reject_outside():
    base = Path(tempfile.mkdtemp(prefix="vs-roots-"))
    roots = [base / n for n in (
        "core/skills", "dist/claude-code/plugin/skills", "dev/skills")]
    for r in roots:
        (r / "sk").mkdir(parents=True)
    old_live, old_summary = vs.LIVE_ROOTS, vs.SUMMARY_ROOTS
    vs.LIVE_ROOTS = tuple(roots)
    vs.SUMMARY_ROOTS = (roots[0], roots[2])
    try:
        for r in roots:
            found = vs.find_skill_dir_for_file(r / "sk/SKILL.md")
            assert found == r / "sk", (r, found)
        assert vs.find_skill_dir_for_file(base / "elsewhere/x.md") is None
        listed = vs.all_skill_dirs()
        assert listed == sorted([roots[0] / "sk", roots[2] / "sk"]), listed
    finally:
        vs.LIVE_ROOTS, vs.SUMMARY_ROOTS = old_live, old_summary
    shutil.rmtree(base)


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
