#!/usr/bin/env python3
"""Host MAINFRAME's local dev panel, OTLP receiver, and bounded model queue."""

from __future__ import annotations

import argparse
import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib
import json
import os
from pathlib import Path
import secrets
import sqlite3
import subprocess
import sys
import threading
import time
from urllib.parse import parse_qs, urlparse

import build_hub_page
import native_telemetry_receiver
import otlp_ingest_health
import telemetry_data

ROOT = Path(__file__).resolve().parent.parent
PROVIDERS = {"spark", "antigravity"}
ADAPTERS = {"claude-code", "codex", "pi"}
MODEL_ADAPTERS = {"claude-code", "codex"}
TERMINAL = {"completed", "retryable", "failed", "cancelled"}


def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def _valid_timestamp_boundary(value):
    if len(value) > 40:
        return False
    try:
        datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return "T" in value


def _parse_timestamp_boundary(value):
    parsed = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.timezone.utc)
    return parsed.astimezone(datetime.timezone.utc)


class JobStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    provider TEXT NOT NULL,
                    adapter TEXT NOT NULL,
                    status TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    detail TEXT NOT NULL DEFAULT '',
                    artifact TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status, id);
                CREATE TABLE IF NOT EXISTS providers (
                    provider TEXT PRIMARY KEY,
                    enabled INTEGER NOT NULL
                );
            """)
            for provider in sorted(PROVIDERS):
                db.execute(
                    "INSERT OR IGNORE INTO providers(provider, enabled) VALUES(?, 1)",
                    (provider,),
                )
        os.chmod(self.path, 0o600)

    def _connect(self):
        db = sqlite3.connect(self.path, timeout=2, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA busy_timeout=2000")
        return db

    @staticmethod
    def _row(row):
        return dict(row) if row is not None else None

    def enqueue(self, provider: str, adapter: str):
        if provider not in PROVIDERS or adapter not in MODEL_ADAPTERS:
            raise ValueError("unknown model-lab target")
        if provider == "antigravity" and adapter != "claude-code":
            raise ValueError("Antigravity audit currently supports Claude Code telemetry only")
        now = _now()
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT * FROM jobs WHERE provider=? AND adapter=? "
                "AND status IN ('queued','running') ORDER BY id DESC LIMIT 1",
                (provider, adapter),
            ).fetchone()
            if row is None:
                cursor = db.execute(
                    "INSERT INTO jobs(provider,adapter,status,created_at,updated_at) "
                    "VALUES(?,?, 'queued', ?, ?)",
                    (provider, adapter, now, now),
                )
                row = db.execute("SELECT * FROM jobs WHERE id=?", (cursor.lastrowid,)).fetchone()
            db.execute("COMMIT")
        return self._row(row)

    def list_jobs(self, limit=100):
        with self._connect() as db:
            rows = db.execute("SELECT * FROM jobs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [self._row(row) for row in rows]

    def providers(self):
        with self._connect() as db:
            rows = db.execute("SELECT provider, enabled FROM providers ORDER BY provider").fetchall()
        return {row["provider"]: bool(row["enabled"]) for row in rows}

    def counts(self):
        with self._connect() as db:
            rows = db.execute(
                "SELECT status, COUNT(*) AS total FROM jobs GROUP BY status"
            ).fetchall()
        return {row["status"]: row["total"] for row in rows}

    def set_provider(self, provider: str, enabled: bool):
        if provider not in PROVIDERS:
            raise ValueError("unknown provider")
        with self._connect() as db:
            db.execute("UPDATE providers SET enabled=? WHERE provider=?", (int(enabled), provider))
        return {"provider": provider, "enabled": bool(enabled)}

    def claim_next(self):
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT j.* FROM jobs j JOIN providers p ON p.provider=j.provider "
                "WHERE j.status='queued' AND p.enabled=1 ORDER BY j.id LIMIT 1"
            ).fetchone()
            if row is not None:
                db.execute(
                    "UPDATE jobs SET status='running', attempts=attempts+1, updated_at=? WHERE id=?",
                    (_now(), row["id"]),
                )
                row = db.execute("SELECT * FROM jobs WHERE id=?", (row["id"],)).fetchone()
            db.execute("COMMIT")
        return self._row(row)

    def finish(self, job_id: int, status: str, *, detail="", artifact=""):
        if status not in TERMINAL:
            raise ValueError("invalid terminal status")
        with self._connect() as db:
            db.execute(
                "UPDATE jobs SET status=?, detail=?, artifact=?, updated_at=? WHERE id=?",
                (status, str(detail)[:300], str(artifact)[:500], _now(), job_id),
            )
            row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        return self._row(row)

    def retry(self, job_id: int):
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            if row is None or row["status"] not in {"retryable", "failed", "cancelled"}:
                db.execute("ROLLBACK")
                raise ValueError("job cannot be retried")
            db.execute(
                "UPDATE jobs SET status='queued', detail='', artifact='', updated_at=? WHERE id=?",
                (_now(), job_id),
            )
            row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            db.execute("COMMIT")
        return self._row(row)

    def cancel(self, job_id: int):
        with self._connect() as db:
            row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            if row is None or row["status"] != "queued":
                raise ValueError("only queued jobs can be cancelled")
        return self.finish(job_id, "cancelled", detail="cancelled before execution")

    def recover_interrupted(self):
        with self._connect() as db:
            db.execute(
                "UPDATE jobs SET status='retryable', detail='service restarted during execution', "
                "updated_at=? WHERE status='running'", (_now(),)
            )


class ObservatoryApp:
    def __init__(self, root: Path, runtime: Path, *, snapshot_builder=None, token=None):
        self.root = Path(root).resolve()
        self.runtime = Path(runtime).resolve()
        self.runtime.mkdir(parents=True, exist_ok=True)
        self.token = token or secrets.token_urlsafe(32)
        self.ingest = native_telemetry_receiver.IngestHealth(
            self.runtime / "ingest.json")
        self.store = JobStore(self.runtime / "control.db")
        self.store.recover_interrupted()
        self.snapshot_builder = snapshot_builder or self._build_snapshot
        self._snapshot = None
        self._snapshot_at = 0.0
        self._snapshot_lock = threading.Lock()
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._worker = None

    def _build_snapshot(self, start_timestamp=None, end_timestamp=None):
        value = build_hub_page.build_manifest(
            str(self.root), start_timestamp=start_timestamp,
            end_timestamp=end_timestamp,
            include_sensitive=True,
        )
        enabled_dir = self.runtime / "enabled"
        active_adapters = sorted(
            adapter for adapter in ADAPTERS
            if (enabled_dir / adapter).is_file()
        )
        value["control"] = {
            "providers": self.store.providers(),
            "jobs": self.store.list_jobs(),
            "counts": self.store.counts(),
            "refresh_seconds": 5,
            "active_adapters": active_adapters,
        }
        ingest = self.ingest.snapshot()
        value["ingest"] = {
            "evidence": "observed",
            "healthy": otlp_ingest_health.is_healthy(ingest),
            **ingest,
        }
        return value

    def period_snapshot(self, start_timestamp=None, end_timestamp=None):
        if not start_timestamp and not end_timestamp:
            return self.snapshot()
        return self._build_snapshot(start_timestamp, end_timestamp)

    def snapshot(self, force=False):
        with self._snapshot_lock:
            if force or self._snapshot is None or time.monotonic() - self._snapshot_at >= 4:
                self._snapshot = self.snapshot_builder()
                self._snapshot_at = time.monotonic()
            return self._snapshot

    def live_snapshot(self, start_timestamp=None, end_timestamp=None):
        value = self.period_snapshot(start_timestamp, end_timestamp)
        return {
            key: value.get(key)
            for key in (
                "dev_state", "usage", "health", "control", "ingest", "analyses",
                "installation",
            )
            if key in value
        }

    def invalidate(self):
        with self._snapshot_lock:
            self._snapshot_at = 0
        self._wake.set()

    def start_worker(self):
        if self._worker and self._worker.is_alive():
            return
        self._worker = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker.start()

    def _worker_loop(self):
        while not self._stop.is_set():
            job = self.store.claim_next()
            if job is None:
                self._wake.wait(1)
                self._wake.clear()
                continue
            status, detail, artifact = self._run_job(job)
            self.store.finish(job["id"], status, detail=detail, artifact=artifact)
            self.invalidate()

    def _run_job(self, job):
        python = self.root / ".venv/bin/python3"
        if not python.is_file():
            return "retryable", "repository .venv is unavailable", ""
        status_file = self.runtime / f"job-{job['id']}-result.json"
        try:
            status_file.unlink()
        except FileNotFoundError:
            pass
        if job["provider"] == "spark":
            command = [
                str(python), str(self.root / "tools/spark_telemetry_triage.py"),
                "--adapter", job["adapter"], "--status-file", str(status_file),
            ]
            timeout = 240
        else:
            command = [
                str(python),
                str(self.root / "adapters/claude-code/dev/model-lab/gemini-telemetry-audit.py"),
                "--status-file", str(status_file),
            ]
            timeout = 420
        started = time.monotonic()
        try:
            proc = subprocess.run(
                command, cwd=self.root, text=True, stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE, timeout=timeout, check=False,
            )
        except subprocess.TimeoutExpired:
            return "retryable", f"timeout after {timeout}s", ""
        except OSError:
            return "retryable", "worker executable unavailable", ""
        if proc.returncode != 0:
            return "retryable", f"worker exit {proc.returncode}", ""
        try:
            outcome = json.loads(status_file.read_text(encoding="utf-8"))
            status = outcome["status"]
            if status not in TERMINAL:
                raise ValueError("invalid worker status")
            detail = outcome.get("detail", "")
            artifact = outcome.get("artifact", "")
        except (OSError, ValueError, KeyError, json.JSONDecodeError):
            return "retryable", "worker finished without a valid result contract", ""
        finally:
            try:
                status_file.unlink()
            except FileNotFoundError:
                pass
        elapsed = round(time.monotonic() - started, 1)
        return status, f"{detail} ({elapsed}s)", artifact

    def stop(self):
        self._stop.set()
        self._wake.set()

    def _json(self, value, status=200):
        body = json.dumps(value, ensure_ascii=False).encode()
        return status, {"Content-Type": "application/json; charset=utf-8"}, body

    def _authorized(self, headers):
        return headers.get("X-Mainframe-Token", headers.get("x-mainframe-token", "")) == self.token

    def handle(self, method, raw_path, headers, body):
        parsed = urlparse(raw_path)
        path = parsed.path
        query = parse_qs(parsed.query)
        start_timestamp = (query.get("from") or [""])[0]
        end_timestamp = (query.get("to") or [""])[0]
        for value in (start_timestamp, end_timestamp):
            if value and not _valid_timestamp_boundary(value):
                return self._json({"error": "invalid period boundary"}, 400)
        if (
            start_timestamp and end_timestamp
            and _parse_timestamp_boundary(start_timestamp)
            >= _parse_timestamp_boundary(end_timestamp)
        ):
            return self._json({"error": "period start must be before end"}, 400)
        if method == "GET" and path == "/api/snapshot":
            return self._json(self.period_snapshot(start_timestamp, end_timestamp))
        if method == "GET" and path == "/api/live":
            return self._json(self.live_snapshot(start_timestamp, end_timestamp))
        if method == "GET" and path == "/api/jobs":
            return self._json({
                "providers": self.store.providers(), "jobs": self.store.list_jobs(),
                "counts": self.store.counts(),
            })
        if method == "POST":
            if not self._authorized(headers):
                return self._json({"error": "forbidden"}, 403)
            if len(body) > 16 * 1024:
                return self._json({"error": "request too large"}, 413)
            try:
                payload = json.loads(body or b"{}")
                if not isinstance(payload, dict):
                    raise ValueError("request body must be an object")
                if path == "/api/jobs":
                    result = self.store.enqueue(payload.get("provider"), payload.get("adapter"))
                    status = 202
                elif path.startswith("/api/jobs/") and path.endswith("/retry"):
                    result = self.store.retry(int(path.split("/")[3])); status = 200
                elif path.startswith("/api/jobs/") and path.endswith("/cancel"):
                    result = self.store.cancel(int(path.split("/")[3])); status = 200
                elif path.startswith("/api/providers/"):
                    if not isinstance(payload.get("enabled"), bool):
                        raise ValueError("enabled must be a boolean")
                    result = self.store.set_provider(path.split("/")[3], payload["enabled"])
                    status = 200
                else:
                    return self._json({"error": "not found"}, 404)
            except (ValueError, TypeError, json.JSONDecodeError) as error:
                return self._json({"error": str(error)}, 400)
            self.invalidate()
            return self._json(result, status)
        return self._json({"error": "not found"}, 404)

    def html(self):
        return build_hub_page.render(
            self.snapshot(), _now(), auto_refresh_ms=10000,
            live=True, control_token=self.token,
        ).encode()


def _handler(app: ObservatoryApp):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, _format, *_args):
            return

        def _send(self, status, headers, body):
            self.send_response(status)
            for key, value in headers.items():
                self.send_header(key, value)
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Security-Policy", "default-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; object-src 'none'; frame-ancestors 'none'")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/health":
                self._send(200, {"X-Mainframe-Instance": app.token}, b"")
                return
            if self.path == "/" or self.path.startswith("/?"):
                self._send(200, {"Content-Type": "text/html; charset=utf-8"}, app.html())
                return
            status, headers, body = app.handle("GET", self.path, dict(self.headers), b"")
            self._send(status, headers, body)

        def do_POST(self):
            if self.path == "/v1/logs":
                try:
                    size = int(self.headers.get("Content-Length", "0"))
                    raw = self.rfile.read(size) if 0 < size <= native_telemetry_receiver.MAX_REQUEST_BYTES else b""
                    if raw:
                        native_telemetry_receiver.ingest_batch(
                            app.ingest, raw, self.headers.get("Content-Type", ""),
                            native_telemetry_receiver.Receiver.db_paths,
                        )
                except Exception:
                    pass
                self._send(200, {}, b"")
                return
            try:
                size = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                size = 0
            body = self.rfile.read(size) if 0 < size <= 16 * 1024 else b""
            status, headers, body = app.handle("POST", self.path, dict(self.headers), body)
            self._send(status, headers, body)

    return Handler


def create_server(host, port, *, root=ROOT, runtime=None, token=None):
    if host not in {"127.0.0.1", "::1", "localhost"}:
        raise ValueError("observatory may bind only to loopback")
    runtime = Path(runtime or Path(root) / "workspace/runtime/observatory")
    app = ObservatoryApp(Path(root), runtime, token=token)
    # The collector must write exactly where the reader looks; resolving both
    # through one helper keeps a sink from filling a database nobody reads.
    native_telemetry_receiver.Receiver.db_paths = {
        adapter_id: Path(path)
        for adapter_id, path in telemetry_data.default_db_paths().items()
    }
    native_telemetry_receiver.Receiver.ingest = app.ingest
    server = ThreadingHTTPServer((host, port), _handler(app))
    server.app = app
    return server


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=4318)
    parser.add_argument("--runtime", type=Path)
    parser.add_argument("--health-token", default="")
    parser.add_argument("--health-token-file", type=Path)
    args = parser.parse_args(argv)
    token = args.health_token
    if args.health_token_file:
        token = args.health_token_file.read_text(encoding="utf-8").strip()
    # A hand-started process bypasses the launcher's prerequisite check. Without
    # the protobuf decoder every binary batch — all Codex traffic — is dropped,
    # and the panel would report zero usage as if the harness had been idle.
    try:
        importlib.import_module(
            "opentelemetry.proto.collector.logs.v1.logs_service_pb2")
    except ImportError:
        print(
            "MAINFRAME observatory: OTLP protobuf decoding is unavailable; "
            "binary batches will be rejected and reported as a collector fault. "
            "Install tools/telemetry-requirements.txt into this interpreter.",
            file=sys.stderr, flush=True,
        )
    server = create_server(
        args.host, args.port, root=ROOT, runtime=args.runtime,
        token=token or None,
    )
    server.app.start_worker()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.app.stop()
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
