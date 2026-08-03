#!/usr/bin/env python3
"""Tests for the read-only local agent-surface preflight."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from check_local_agent_surfaces import check_layout


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _source_skill(root: Path, name: str, restricted: bool) -> None:
    marker = "true" if restricted else "false"
    _write(
        root / f"core/skills/{name}/SKILL.md",
        f"---\nname: {name}\ndisable-model-invocation: {marker}\n---\n",
    )


def _fixture() -> tuple[Path, Path, Path]:
    root = Path(tempfile.mkdtemp())
    claude = root / "claude"
    codex = root / "codex"
    _source_skill(root, "public-method", False)
    _source_skill(root, "private-method", True)
    _source_skill(root, "codex-exec", False)
    _write(
        root / "core/agents/worker.md",
        "---\nname: worker\nmethod-skills:\n  - private-method\n---\n",
    )
    for name in ("public-method", "private-method", "codex-exec"):
        _write(claude / f"skills/mainframe/skills/{name}/SKILL.md", "method\n")
    _write(codex / "skills/public-method/SKILL.md", "method\n")
    _write(codex / "mainframe-agent-methods/private-method/SKILL.md", "method\n")
    _write(
        codex / "agents/worker.toml",
        'developer_instructions = "Private method: private-method"\n',
    )
    return root, claude, codex


def test_complete_isolated_layout_passes() -> None:
    root, claude, codex = _fixture()
    assert check_layout(root, claude, codex, check_binaries=False) == []


def test_global_private_skill_and_missing_agent_method_fail() -> None:
    root, claude, codex = _fixture()
    _write(codex / "skills/private-method/SKILL.md", "leaked\n")
    _write(codex / "agents/worker.toml", 'developer_instructions = "plain"\n')
    failures = check_layout(root, claude, codex, check_binaries=False)
    assert any("globally visible" in failure for failure in failures)
    assert any("lacks private method" in failure for failure in failures)


def test_malformed_agent_definition_fails_cleanly() -> None:
    root, claude, codex = _fixture()
    _write(codex / "agents/worker.toml", "not = [valid\n")
    failures = check_layout(root, claude, codex, check_binaries=False)
    assert failures == ["codex agent worker has invalid TOML"]


def main() -> int:
    tests = [
        value for key, value in sorted(globals().items())
        if key.startswith("test_") and callable(value)
    ]
    for test in tests:
        test()
        print(f"  ok   {test.__name__}")
    print(f"{len(tests)}/{len(tests)} passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
