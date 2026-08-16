#!/usr/bin/env python3
"""Initialize the adapter-owned Codex development telemetry sink."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _hooklib import initialize_telemetry_db  # noqa: E402


def main():
    if len(sys.argv) != 3 or sys.argv[1] != "--initialize":
        return 2
    initialize_telemetry_db(sys.argv[2])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
