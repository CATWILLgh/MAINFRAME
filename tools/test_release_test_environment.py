#!/usr/bin/env python3
"""Tests for the packaged-release subprocess environment boundary."""

from __future__ import annotations

import os

from release_test_environment import isolated_environment


def test_subprocess_environment_excludes_unrelated_user_values(monkeypatch) -> None:
    monkeypatch.setenv("MAINFRAME_TEST_SENSITIVE_VALUE", "must-not-propagate")

    environment = isolated_environment(HOME="/isolated-home")

    assert environment["HOME"] == "/isolated-home"
    assert environment["PATH"] == os.environ["PATH"]
    assert "MAINFRAME_TEST_SENSITIVE_VALUE" not in environment
