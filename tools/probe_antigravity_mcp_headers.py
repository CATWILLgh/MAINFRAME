#!/usr/bin/env python3

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


HEADER_NAME = "X-Mainframe-Probe"
DEFAULT_HOST = "127.0.0.1"


class ProbeHandler(BaseHTTPRequestHandler):
    request_count = 0

    def do_POST(self):
        request = self._read_request()
        type(self).request_count += 1
        value = self.headers.get(HEADER_NAME)
        print(
            f"REQUEST_{type(self).request_count}_{HEADER_NAME}={value}",
            flush=True,
        )

        request_id = request.get("id")
        if request_id is None:
            self.send_response(202)
            self.end_headers()
            return
        self._write_json(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": self._result_for(request),
            }
        )

    def do_DELETE(self):
        self.send_response(200)
        self.end_headers()

    def log_message(self, format, *args):
        return

    def _read_request(self):
        length = int(self.headers.get("Content-Length", "0"))
        return json.loads(self.rfile.read(length) or b"{}")

    def _result_for(self, request):
        if request.get("method") == "initialize":
            return {
                "protocolVersion": request.get("params", {}).get(
                    "protocolVersion", "2024-11-05"
                ),
                "capabilities": {},
                "serverInfo": {
                    "name": "mainframe-antigravity-header-probe",
                    "version": "1",
                },
            }
        if request.get("method") == "tools/list":
            return {"tools": []}
        return {}

    def _write_json(self, payload):
        response = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Capture Antigravity MCP probe headers on loopback."
    )
    parser.add_argument("--port", type=int, required=True)
    return parser.parse_args()


def main():
    args = parse_args()
    server = ThreadingHTTPServer((DEFAULT_HOST, args.port), ProbeHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
