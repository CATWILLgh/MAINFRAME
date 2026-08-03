#!/usr/bin/env python3
"""Tier-1 contracts for central-first credential discovery guidance."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))

import build_release


SKILLS = {
    "Antigravity": "antigravity-2/plugin/skills/secrets-handling/SKILL.md",
    "Claude Code": "claude-code/plugin/skills/secrets-handling/SKILL.md",
    "Codex": "codex/skills/secrets-handling/SKILL.md",
    "OpenCode": "opencode/skills/secrets-handling/SKILL.md",
}
INSTRUCTIONS = {
    "Antigravity": (
        "antigravity-2/plugin/rules/core-50-engineering-practices.md"
    ),
    "Claude Code": "claude-code/CLAUDE.md",
    "Codex": "codex/AGENTS.md",
    "OpenCode": "opencode/AGENTS.md",
}


def normalized(path: Path) -> str:
    return " ".join(path.read_text(encoding="utf-8").split())


class SecretDiscoveryContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sandbox = Path(tempfile.mkdtemp()).resolve(strict=True)
        cls.release = cls.sandbox / "release"
        build_release.build(REPO, cls.release, release_id="secret-discovery-test")
        cls.skills = {
            name: normalized(cls.release / "bundles" / relative)
            for name, relative in SKILLS.items()
        }
        cls.instructions = {
            name: normalized(cls.release / "bundles" / relative)
            for name, relative in INSTRUCTIONS.items()
        }

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.sandbox)

    def test_every_projection_prefers_the_central_catalog(self) -> None:
        for name, text in self.skills.items():
            with self.subTest(adapter=name):
                self.assertIn("Run `mainframe credentials` first", text)
                self.assertIn(
                    "Check `command -v mainframe` and `command -v secret`",
                    text,
                )
                self.assertIn(
                    "`schema_version` equal to `1`",
                    text,
                )
                self.assertIn(
                    "`kind` equal to `mainframe-credential-catalog`",
                    text,
                )
                self.assertIn(
                    "`secret_availability` equal to `unchecked`",
                    text,
                )
                self.assertIn(
                    "`services` and `instances` as non-null arrays",
                    text,
                )
                self.assertIn(
                    "unique non-empty service and instance IDs",
                    text,
                )
                self.assertIn(
                    "every instance's `service_id` to name one listed service",
                    text,
                )
                self.assertIn(
                    "every credential binding to use a role listed by that "
                    "service plus a valid `secret-env` reference name",
                    text,
                )
                self.assertIn(
                    "Any missing, mistyped, duplicate, or inconsistent field "
                    "makes the response schema-invalid.",
                    text,
                )
                self.assertIn("`$NAME`", text)
                self.assertIn("`$(secret get NAME)`", text)

    def test_instance_selection_never_guesses_a_default(self) -> None:
        expected = (
            "Never choose an implicit default; if more than one instance is "
            "plausible, ask the user."
        )
        for name, text in self.skills.items():
            with self.subTest(adapter=name):
                self.assertIn(expected, text)

    def test_legacy_fallback_is_limited_to_two_safe_conditions(self) -> None:
        expected = (
            "`credentials-index.md` is a fallback only when `mainframe` is "
            "unavailable or a successful, schema-valid catalog has no exact "
            "instance match."
        )
        for name, text in self.skills.items():
            with self.subTest(adapter=name):
                self.assertIn(expected, text)

    def test_catalog_errors_stop_without_legacy_fallback(self) -> None:
        expected = (
            "Do not fall back after a non-zero exit, malformed JSON, an "
            "unsupported schema, or a permission failure; stop and report "
            "the error."
        )
        for name, text in self.skills.items():
            with self.subTest(adapter=name):
                self.assertIn(expected, text)

    def test_codex_shared_legacy_fallback_requires_both_missing_dependencies(
        self,
    ) -> None:
        codex = self.skills["Codex"]
        self.assertIn(
            "if `mainframe` is unavailable and "
            "`${CODEX_HOME:-$HOME/.codex}/credentials-index.md` does not "
            "exist, read `~/.claude/credentials-index.md` as the final "
            "read-only shared legacy fallback.",
            codex,
        )
        self.assertIn(
            "Do not use this shared fallback after any `mainframe` "
            "response, when the Codex-local index exists, or when a "
            "successful catalog has no exact instance match.",
            codex,
        )
        for name in ("Antigravity", "Claude Code", "OpenCode"):
            with self.subTest(adapter=name):
                self.assertNotIn("shared legacy fallback", self.skills[name])

    def test_guidance_is_honest_about_transcript_and_command_leakage(self) -> None:
        expected = (
            "The runtime does not guarantee transcript redaction. Never echo "
            "secret values, enable shell tracing, or use verbose modes that "
            "may expose credentials."
        )
        for name, text in self.skills.items():
            with self.subTest(adapter=name):
                self.assertIn(expected, text)
        umbrella_expected = (
            "The authenticated process still receives the expanded value, "
            "and the runtime may expose arguments or output; never promise "
            "transcript redaction."
        )
        forbidden = "so the value reaches the subprocess but not the transcript"
        for name, text in self.instructions.items():
            with self.subTest(instructions=name):
                self.assertIn(umbrella_expected, text)
                self.assertNotIn(forbidden, text)

    def test_guidance_is_local_only(self) -> None:
        expected = (
            "This workflow applies only to local terminal sessions; do not "
            "assume Chat, Cowork, web, or remote runs can access local tools."
        )
        for name, text in self.skills.items():
            with self.subTest(adapter=name):
                self.assertIn(expected, text)

    def test_secret_helper_points_to_central_discovery(self) -> None:
        result = subprocess.run(
            [str(self.release / "common/credential-tools/secret"), "--help"],
            text=True,
            capture_output=True,
            check=True,
            timeout=10,
        )
        help_text = " ".join(result.stdout.split())
        self.assertIn(
            "For credential discovery, run `mainframe credentials` first.",
            help_text,
        )


if __name__ == "__main__":
    unittest.main()
