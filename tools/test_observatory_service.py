#!/usr/bin/env python3

import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
MODULE_PATH = ROOT / "tools/observatory_service.py"


def _load():
    spec = importlib.util.spec_from_file_location("mainframe_observatory_service", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_queue_is_persistent_deduplicated_and_adapter_owned():
    module = _load()
    work = Path(tempfile.mkdtemp())
    db = work / "control.db"
    store = module.JobStore(db)
    first = store.enqueue("spark", "codex")
    duplicate = store.enqueue("spark", "codex")
    other = store.enqueue("spark", "claude-code")
    assert first["id"] == duplicate["id"]
    assert other["id"] != first["id"]
    reopened = module.JobStore(db)
    assert [row["adapter"] for row in reopened.list_jobs()] == [
        "claude-code", "codex"
    ]
    assert reopened.counts() == {"queued": 2}


def test_queue_rejects_unknown_actions_and_supports_retry():
    module = _load()
    store = module.JobStore(Path(tempfile.mkdtemp()) / "control.db")
    for provider, adapter in (("shell", "codex"), ("spark", "unknown")):
        try:
            store.enqueue(provider, adapter)
        except ValueError:
            pass
        else:
            raise AssertionError("unknown queue target was accepted")
    job = store.enqueue("antigravity", "claude-code")
    claimed = store.claim_next()
    assert claimed["id"] == job["id"] and claimed["status"] == "running"
    store.finish(job["id"], "retryable", detail="quota")
    retried = store.retry(job["id"])
    assert retried["status"] == "queued" and retried["attempts"] == 1


def test_provider_probe_distinguishes_ready_and_auth_required():
    module = _load()
    original_which = module.shutil.which
    original_run = module.subprocess.run
    try:
        module.shutil.which = lambda command: "/tmp/fake-" + command
        class Result:
            returncode = 0
            stdout = "gemini-3.7-flash-high\tGemini 3.7 Flash (High)\n"
            stderr = ""

        module.subprocess.run = lambda *_args, **_kwargs: Result()
        assert module._probe_provider("antigravity")["state"] == "ready"

        Result.returncode = 1
        Result.stdout = ""
        Result.stderr = "Please sign in to view available models."
        assert module._probe_provider("antigravity")["state"] == "auth-required"
    finally:
        module.shutil.which = original_which
        module.subprocess.run = original_run


def test_provider_status_prefers_latest_job_outcome():
    module = _load()
    app = module.ObservatoryApp(
        ROOT, Path(tempfile.mkdtemp()), snapshot_builder=lambda: {}
    )
    job = app.store.enqueue("spark", "codex")
    app.store.claim_next()
    app.store.finish(job["id"], "completed", detail="stored")
    status = app.provider_status()["spark"]
    assert status["state"] == "ready"
    assert "completed" in status["detail"]
    with app._provider_lock:
        app._provider_status["spark"] = {
            "state": "unavailable", "detail": "not available", "checked_at": "now"
        }
    assert app.provider_status()["spark"]["state"] == "unavailable"


def test_service_rejects_non_loopback_bind_and_has_csrf_boundary():
    module = _load()
    try:
        module.create_server("0.0.0.0", 0, root=ROOT)
    except ValueError:
        pass
    else:
        raise AssertionError("non-loopback bind was accepted")
    app = module.ObservatoryApp(
        ROOT, Path(tempfile.mkdtemp()), snapshot_builder=lambda: {"safe": True}
    )
    status, _headers, body = app.handle("GET", "/api/snapshot", {}, b"")
    assert status == 200 and json.loads(body) == {"safe": True}
    status, _headers, body = app.handle("GET", "/api/live", {}, b"")
    assert status == 200 and json.loads(body) == {}
    status, _headers, body = app.handle(
        "GET", "/api/live?from=not-a-date", {}, b""
    )
    assert status == 400 and "period" in json.loads(body)["error"]
    status, _headers, body = app.handle(
        "GET", "/api/live?from=2026-08-20T00:00:00Z&to=2026-08-19T00:00:00Z",
        {}, b"",
    )
    assert status == 400 and "before" in json.loads(body)["error"]
    status, _headers, _body = app.handle(
        "POST", "/api/jobs", {"Content-Type": "application/json"},
        b'{"provider":"spark","adapter":"codex"}',
    )
    assert status == 403
    status, _headers, body = app.handle(
        "POST", "/api/jobs",
        {"Content-Type": "application/json", "X-Mainframe-Token": app.token},
        b'{"provider":"spark","adapter":"codex"}',
    )
    assert status == 202 and json.loads(body)["status"] == "queued"
    status, _headers, body = app.handle(
        "POST", "/api/providers/spark",
        {"Content-Type": "application/json", "X-Mainframe-Token": app.token},
        b'{"enabled":"false"}',
    )
    assert status == 400 and "boolean" in json.loads(body)["error"]


def test_panel_keeps_language_locally_and_exposes_both_catalogs():
    app = (ROOT / "tools/hub_page_assets/app.js").read_text(encoding="utf-8")
    assert "mainframe-language" in app
    assert "localStorage" in app
    assert '"en"' in app and '"ru"' in app
    assert 'fetch("/api/live" + periodQuery()' in app
    assert 'type: "date"' in app and 'mainframe-period' in app
    assert "setCustomValidity" in app
    # Scroll position must not gate the refresh: treating any scroll as "busy"
    # froze a scrolled page forever. It is saved and restored around the
    # re-render instead, and an active filter is what defers the update.
    assert 'window.scrollY > 0' not in app
    assert "const scrollTop = window.scrollY;" in app
    assert "window.scrollTo(0, scrollTop)" in app
    assert "Boolean(filterQuery)" in app
    assert app.count("window.location.reload()") == 1


def test_panel_uses_adapter_telemetry_for_shared_overview_and_usage():
    app = (ROOT / "tools/hub_page_assets/app.js").read_text(encoding="utf-8")
    assert 'overviewMetric(t("Observed sessions")' in app
    assert 'overviewMetric(t("Spend")' in app
    assert '"Claude sessions"' not in app
    assert 'function renderUsage' in app
    assert 'function renderTranscriptHistory' in app
    assert 'Claude transcript history' in app
    assert 'usage.by_model' in app
    assert 't("Token share by adapter")' in app
    assert 't("Token share by model")' in app


def test_live_server_serves_panel_and_health_on_loopback():
    module = _load()
    runtime = Path(tempfile.mkdtemp())
    (runtime / "enabled").mkdir()
    (runtime / "enabled" / "codex").touch()
    server = module.create_server("127.0.0.1", 0, root=ROOT, runtime=runtime, token="probe")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        with urllib.request.urlopen(f"http://{host}:{port}/health", timeout=2) as response:
            assert response.status == 200
            assert response.headers["X-Mainframe-Instance"] == "probe"
        with urllib.request.urlopen(f"http://{host}:{port}/", timeout=2) as response:
            page = response.read().decode()
            assert response.status == 200
            assert "window.HUB_LIVE = true" in page
            assert "mainframe-language" in page
            assert "Analysis queue" in page
        with urllib.request.urlopen(f"http://{host}:{port}/api/live", timeout=2) as response:
            live = json.loads(response.read())
            assert live["control"]["active_adapters"] == ["codex"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_dev_lifecycle_is_adapter_scoped_and_keeps_token_out_of_plist():
    manager = (ROOT / "tools/mainframe-observatory.sh").read_text(encoding="utf-8")
    claude_installer = (ROOT / "adapters/claude-code/install.sh").read_text(encoding="utf-8")
    codex_installer = (ROOT / "adapters/codex/install.sh").read_text(encoding="utf-8")
    assert 'case "${1:-help}"' in manager
    assert "--health-token-file" in manager
    assert '"KeepAlive": True' in manager and '"RunAtLoad": True' in manager
    assert "mainframe-observatory.service" in manager
    assert "autostart install" in manager
    assert "exec \"$PYTHON\"" in manager
    assert "nohup" not in manager
    assert '"MainframeManaged"' not in manager
    assert 'mainframe-observatory.sh" enable claude-code' in claude_installer
    assert 'mainframe-observatory.sh" disable claude-code' in claude_installer
    assert 'mainframe-observatory.sh" enable codex' in codex_installer
    assert 'mainframe-observatory.sh" disable codex' in codex_installer


if __name__ == "__main__":
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
        print("  ok", test.__name__)
    print(f"OK observatory service - {len(tests)} tests passed")
