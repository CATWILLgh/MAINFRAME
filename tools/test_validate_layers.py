#!/usr/bin/env python3
"""Tests for structural boundaries between Claude agents and skills."""

import importlib.util
import pathlib
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
MODULE_PATH = ROOT / "tools" / "validate-layers.py"
SPEC = importlib.util.spec_from_file_location("validate_layers", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def fixture(agent_skills, skill_name="ticket", skill_extra=""):
    root = pathlib.Path(tempfile.mkdtemp())
    agents = root / "agents"
    skills = root / "skills"
    agents.mkdir()
    skill = skills / skill_name
    skill.mkdir(parents=True)
    skill.joinpath("SKILL.md").write_text(
        f"---\nname: {skill_name}\ndescription: Test skill.\n{skill_extra}---\n\nBody.\n",
        encoding="utf-8",
    )
    rendered = "\n".join(f"  - {name}" for name in agent_skills)
    agents.joinpath("worker.md").write_text(
        "---\nname: worker\ndescription: Test worker.\n"
        f"skills:\n{rendered}\n---\n\nBody.\n",
        encoding="utf-8",
    )
    return agents, skills


def test_repository_layers_satisfy_contract():
    assert MODULE.validate() == []


def test_accepts_existing_namespaced_preload():
    agents, skills = fixture(["mainframe:ticket"])
    assert MODULE.validate(agents, skills) == []


def test_rejects_missing_or_unnamespaced_preload():
    agents, skills = fixture(["mainframe:missing", "ticket"])
    messages = [message for _, message in MODULE.validate(agents, skills)]
    assert any("does not exist" in message for message in messages)
    assert any("must use the `mainframe:` namespace" in message for message in messages)


def test_rejects_preload_of_manual_only_skill():
    agents, skills = fixture(
        ["mainframe:init"],
        skill_name="init",
        skill_extra="disable-model-invocation: true\n",
    )
    issues = MODULE.validate(agents, skills)
    assert issues == [(
        "error",
        "worker.md: `mainframe:init` cannot be preloaded because it disables model invocation",
    )]


def test_rejects_duplicate_preload():
    agents, skills = fixture(["mainframe:ticket", "mainframe:ticket"])
    issues = MODULE.validate(agents, skills)
    assert issues == [("error", "worker.md: duplicate preloaded skill `mainframe:ticket`")]


if __name__ == "__main__":
    tests = sorted(name for name in globals() if name.startswith("test_"))
    for name in tests:
        globals()[name]()
        print(f"  ok  {name}")
    print(f"\n{len(tests)}/{len(tests)} passed")
