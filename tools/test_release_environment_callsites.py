#!/usr/bin/env python3
"""Secret-isolation tests for packaged release subprocess call sites."""

from __future__ import annotations

from test_build_release import _assert_secret_help
from test_release_cli_lifecycle import _environment


def test_release_cli_environment_excludes_unrelated_user_values(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("MAINFRAME_TEST_SENSITIVE_VALUE", "must-not-propagate")

    environment = _environment(tmp_path)

    if "MAINFRAME_TEST_SENSITIVE_VALUE" in environment:
        raise AssertionError("unrelated user environment reached release CLI")


def test_secret_help_subprocess_excludes_unrelated_user_values(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("MAINFRAME_TEST_SENSITIVE_VALUE", "must-not-propagate")
    secret = tmp_path / "common/credential-tools/secret"
    secret.parent.mkdir(parents=True)
    secret.write_text(
        """#!/bin/sh
if [ "${MAINFRAME_TEST_SENSITIVE_VALUE+x}" = x ]; then exit 9; fi
printf '%s\n' \\
  'For credential discovery, run `mainframe credentials` first.' \\
  'Adapter-local credentials indexes are read-only migration fallbacks.' \\
  '${XDG_CONFIG_HOME:-$HOME/.config}/credentials/secrets.env' \\
  '$(secret get NAME)'
"""
    )
    secret.chmod(0o755)

    _assert_secret_help(tmp_path)
