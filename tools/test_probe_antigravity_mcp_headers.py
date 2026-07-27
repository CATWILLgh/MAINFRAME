#!/usr/bin/env python3

import json
import socket
import subprocess
import sys
import time
import unittest
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PROBE = ROOT / "tools" / "probe_antigravity_mcp_headers.py"
HEADER_NAME = "X-Mainframe-Probe"
HEADER_VALUE = "${MAINFRAME_ANTIGRAVITY_PROBE}"


class ProbeServerTests(unittest.TestCase):
    def test_captures_headers_and_speaks_minimal_mcp(self):
        port = available_port()
        process = subprocess.Popen(
            [sys.executable, str(PROBE), "--port", str(port)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            wait_until_listening(port)
            initialize = post(
                port,
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {"protocolVersion": "2025-03-26"},
                },
            )
            tools = post(
                port,
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            )
        finally:
            process.terminate()
            stdout, stderr = process.communicate(timeout=5)

        self.assertEqual(initialize["result"]["protocolVersion"], "2025-03-26")
        self.assertEqual(tools["result"], {"tools": []})
        self.assertEqual(
            stdout.splitlines(),
            [
                f"REQUEST_1_{HEADER_NAME}={HEADER_VALUE}",
                f"REQUEST_2_{HEADER_NAME}={HEADER_VALUE}",
            ],
        )
        self.assertEqual(stderr, "")


def available_port():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def wait_until_listening(port):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                return
        except OSError:
            time.sleep(0.02)
    raise AssertionError("probe server did not start")


def post(port, payload):
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}/mcp",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", HEADER_NAME: HEADER_VALUE},
    )
    with urllib.request.urlopen(request, timeout=2) as response:
        return json.load(response)


if __name__ == "__main__":
    unittest.main()
