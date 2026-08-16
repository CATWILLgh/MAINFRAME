#!/usr/bin/env bash

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME="${ROOT}/workspace/runtime/observatory"
PID_FILE="${RUNTIME}/receiver.pid"
LOG_FILE="${RUNTIME}/receiver.log"
TOKEN_FILE="${RUNTIME}/receiver.token"
PYTHON="${ROOT}/.venv/bin/python3"
RECEIVER="${ROOT}/tools/native_telemetry_receiver.py"
CODEX_DB="${CODEX_HOME:-${HOME}/.codex}/mainframe/codex/telemetry/telemetry.db"
HEALTH="http://127.0.0.1:4318/health"

usage() {
    printf 'Usage: %s {start|stop|status}\n' "$0"
}

pid_value() {
    [[ -f "$PID_FILE" ]] || return 1
    local pid
    pid="$(tr -d '[:space:]' < "$PID_FILE")"
    [[ "$pid" =~ ^[0-9]+$ ]] || return 1
    printf '%s\n' "$pid"
}

owns_pid() {
    local pid="$1"
    kill -0 "$pid" 2>/dev/null || return 1
}

health_ok() {
    [[ -f "$TOKEN_FILE" ]] || return 1
    "$PYTHON" - "$HEALTH" "$TOKEN_FILE" <<'PY' >/dev/null 2>&1
import sys
import urllib.request

token = open(sys.argv[2], encoding="utf-8").read().strip()
with urllib.request.urlopen(sys.argv[1], timeout=1) as response:
    actual = response.headers.get("X-Mainframe-Instance", "")
    raise SystemExit(0 if response.status == 200 and actual == token else 1)
PY
}

start_service() {
    if [[ ! -x "$PYTHON" ]]; then
        printf 'MAINFRAME observatory is inactive: repository .venv is missing.\n' >&2
        printf 'Create it and install tools/telemetry-requirements.txt, then retry.\n' >&2
        return 2
    fi
    if ! "$PYTHON" -c 'import opentelemetry.proto.collector.logs.v1.logs_service_pb2' \
            >/dev/null 2>&1; then
        printf 'MAINFRAME observatory is inactive: dev telemetry dependencies are missing.\n' >&2
        printf 'Run .venv/bin/pip install -r tools/telemetry-requirements.txt, then retry.\n' >&2
        return 2
    fi

    local pid=""
    pid="$(pid_value || true)"
    if [[ -n "$pid" ]] && health_ok; then
        printf 'MAINFRAME observatory is already running (pid %s).\n' "$pid"
        return 0
    fi
    if [[ -n "$pid" ]] && owns_pid "$pid"; then
        printf 'MAINFRAME observatory process exists but is unhealthy (pid %s).\n' "$pid" >&2
        return 1
    fi

    mkdir -p "$RUNTIME"
    : > "$LOG_FILE"
    "$PYTHON" -c 'import uuid; print(uuid.uuid4().hex)' > "$TOKEN_FILE"
    local token
    token="$(cat "$TOKEN_FILE")"
    nohup "$PYTHON" -B "$RECEIVER" --health-token "$token" \
        --codex-db "$CODEX_DB" >>"$LOG_FILE" 2>&1 &
    pid=$!
    printf '%s\n' "$pid" > "$PID_FILE"
    chmod 600 "$PID_FILE" "$TOKEN_FILE" "$LOG_FILE"
    local attempt
    for attempt in {1..20}; do
        if health_ok; then
            printf 'MAINFRAME observatory started (pid %s).\n' "$pid"
            return 0
        fi
        if ! owns_pid "$pid"; then
            break
        fi
        sleep 0.1
    done
    if owns_pid "$pid"; then
        kill "$pid" 2>/dev/null || true
    fi
    rm -f "$PID_FILE" "$TOKEN_FILE"
    printf 'MAINFRAME observatory failed to start; see %s.\n' "$LOG_FILE" >&2
    return 1
}

stop_service() {
    local pid=""
    pid="$(pid_value || true)"
    if [[ -z "$pid" ]]; then
        printf 'MAINFRAME observatory is not running.\n'
        return 0
    fi
    if ! health_ok; then
        rm -f "$PID_FILE" "$TOKEN_FILE"
        printf 'Removed a stale MAINFRAME observatory pid file.\n'
        return 0
    fi
    kill "$pid"
    local attempt
    for attempt in {1..20}; do
        if ! kill -0 "$pid" 2>/dev/null; then
            rm -f "$PID_FILE" "$TOKEN_FILE"
            printf 'MAINFRAME observatory stopped.\n'
            return 0
        fi
        sleep 0.1
    done
    printf 'MAINFRAME observatory did not stop within two seconds (pid %s).\n' "$pid" >&2
    return 1
}

status_service() {
    local pid=""
    pid="$(pid_value || true)"
    if [[ -n "$pid" ]] && health_ok; then
        printf 'MAINFRAME observatory is running (pid %s).\n' "$pid"
        return 0
    fi
    printf 'MAINFRAME observatory is not running.\n'
    return 1
}

case "${1:-}" in
    start) start_service ;;
    stop) stop_service ;;
    status) status_service ;;
    *) usage >&2; exit 2 ;;
esac
