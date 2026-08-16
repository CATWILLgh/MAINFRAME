#!/usr/bin/env bash

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME="${ROOT}/workspace/runtime/observatory"
ACTIVE_DIR="${RUNTIME}/enabled"
PID_FILE="${RUNTIME}/service.pid"
LOG_FILE="${RUNTIME}/service.log"
TOKEN_FILE="${RUNTIME}/service.token"
LEGACY_PID_FILE="${RUNTIME}/receiver.pid"
LEGACY_TOKEN_FILE="${RUNTIME}/receiver.token"
PYTHON="${ROOT}/.venv/bin/python3"
SERVICE="${ROOT}/tools/observatory_service.py"
LABEL="com.mainframe.observatory"
PLIST="${HOME}/Library/LaunchAgents/${LABEL}.plist"
HEALTH="http://127.0.0.1:4318/health"

usage() {
    printf 'Usage: %s {enable ADAPTER|disable ADAPTER|start|stop|status|uninstall}\n' "$0"
}

valid_adapter() {
    [[ "${1:-}" == "claude-code" || "${1:-}" == "codex" ]]
}

check_prerequisites() {
    if [[ ! -x "$PYTHON" ]]; then
        printf 'MAINFRAME observatory is inactive: repository .venv is missing.\n' >&2
        printf 'Create it and install tools/telemetry-requirements.txt, then retry.\n' >&2
        return 2
    fi
    if ! "$PYTHON" -c 'import opentelemetry.proto.collector.logs.v1.logs_service_pb2' >/dev/null 2>&1; then
        printf 'MAINFRAME observatory is inactive: dev telemetry dependencies are missing.\n' >&2
        printf 'Run .venv/bin/pip install -r tools/telemetry-requirements.txt, then retry.\n' >&2
        return 2
    fi
}

ensure_runtime() {
    mkdir -p "$RUNTIME" "$ACTIVE_DIR"
    if [[ ! -s "$TOKEN_FILE" ]]; then
        "$PYTHON" -c 'import secrets; print(secrets.token_urlsafe(32))' > "$TOKEN_FILE"
    fi
    touch "$LOG_FILE"
    chmod 600 "$TOKEN_FILE" "$LOG_FILE"
}

health_ok() {
    [[ -x "$PYTHON" && -s "$TOKEN_FILE" ]] || return 1
    "$PYTHON" - "$HEALTH" "$TOKEN_FILE" <<'PY' >/dev/null 2>&1
import sys
import urllib.request

token = open(sys.argv[2], encoding="utf-8").read().strip()
with urllib.request.urlopen(sys.argv[1], timeout=1) as response:
    actual = response.headers.get("X-Mainframe-Instance", "")
    raise SystemExit(0 if response.status == 200 and actual == token else 1)
PY
}

health_matches_token_file() {
    local token_file="$1"
    [[ -x "$PYTHON" && -s "$token_file" ]] || return 1
    "$PYTHON" - "$HEALTH" "$token_file" <<'PY' >/dev/null 2>&1
import sys
import urllib.request

token = open(sys.argv[2], encoding="utf-8").read().strip()
with urllib.request.urlopen(sys.argv[1], timeout=1) as response:
    raise SystemExit(0 if response.headers.get("X-Mainframe-Instance", "") == token else 1)
PY
}

stop_legacy_receiver() {
    [[ -f "$LEGACY_PID_FILE" ]] || return 0
    local pid
    pid="$(tr -d '[:space:]' < "$LEGACY_PID_FILE")"
    if [[ "$pid" =~ ^[0-9]+$ ]] && kill -0 "$pid" 2>/dev/null; then
        if ! health_matches_token_file "$LEGACY_TOKEN_FILE"; then
            printf 'Legacy receiver pid exists but its ownership could not be verified: %s\n' "$pid" >&2
            return 1
        fi
        kill "$pid"
        local attempt
        for attempt in {1..20}; do
            kill -0 "$pid" 2>/dev/null || break
            sleep 0.1
        done
        if kill -0 "$pid" 2>/dev/null; then
            printf 'Legacy receiver did not stop within two seconds: %s\n' "$pid" >&2
            return 1
        fi
    fi
    rm -f "$LEGACY_PID_FILE" "$LEGACY_TOKEN_FILE"
}

managed_plist() {
    [[ -f "$PLIST" ]] || return 1
    "$PYTHON" - "$PLIST" "$LABEL" "$SERVICE" <<'PY' >/dev/null 2>&1
import plistlib
import sys

with open(sys.argv[1], "rb") as handle:
    value = plistlib.load(handle)
arguments = value.get("ProgramArguments") or []
raise SystemExit(0 if value.get("Label") == sys.argv[2] and sys.argv[3] in arguments else 1)
PY
}

write_plist() {
    mkdir -p "$(dirname "$PLIST")"
    if [[ -e "$PLIST" ]] && ! managed_plist; then
        printf 'Refusing to replace an unmanaged LaunchAgent: %s\n' "$PLIST" >&2
        return 1
    fi
    "$PYTHON" - "$PLIST" "$LABEL" "$PYTHON" "$SERVICE" "$ROOT" "$RUNTIME" "$TOKEN_FILE" "$LOG_FILE" <<'PY'
import os
import plistlib
import sys
import tempfile

target, label, python, service, root, runtime, token_path, log_path = sys.argv[1:]
payload = {
    "Label": label,
    "ProgramArguments": [python, "-B", service, "--health-token-file", token_path, "--runtime", runtime],
    "WorkingDirectory": root,
    "RunAtLoad": True,
    "KeepAlive": True,
    "ProcessType": "Background",
    "ThrottleInterval": 10,
    "StandardOutPath": log_path,
    "StandardErrorPath": log_path,
    "EnvironmentVariables": {"PYTHONUNBUFFERED": "1"},
}
fd, temporary = tempfile.mkstemp(prefix=".mainframe-observatory-", dir=os.path.dirname(target))
try:
    with os.fdopen(fd, "wb") as handle:
        plistlib.dump(payload, handle, sort_keys=True)
    os.chmod(temporary, 0o644)
    os.replace(temporary, target)
finally:
    if os.path.exists(temporary):
        os.unlink(temporary)
PY
}

manual_pid() {
    [[ -f "$PID_FILE" ]] || return 1
    local pid
    pid="$(tr -d '[:space:]' < "$PID_FILE")"
    [[ "$pid" =~ ^[0-9]+$ ]] || return 1
    printf '%s\n' "$pid"
}

stop_manual() {
    local pid=""
    pid="$(manual_pid || true)"
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null && health_ok; then
        kill "$pid"
        local attempt
        for attempt in {1..20}; do
            kill -0 "$pid" 2>/dev/null || break
            sleep 0.1
        done
        if kill -0 "$pid" 2>/dev/null; then
            printf 'Manual observatory did not stop within two seconds: %s\n' "$pid" >&2
            return 1
        fi
    fi
    rm -f "$PID_FILE"
}

launch_domain() {
    printf 'gui/%s\n' "$(id -u)"
}

start_manual() {
    local token
    token="$(tr -d '[:space:]' < "$TOKEN_FILE")"
    nohup "$PYTHON" -B "$SERVICE" --health-token "$token" --runtime "$RUNTIME" >>"$LOG_FILE" 2>&1 &
    printf '%s\n' "$!" > "$PID_FILE"
    chmod 600 "$PID_FILE"
}

start_service() {
    check_prerequisites
    ensure_runtime
    if health_ok; then
        printf 'MAINFRAME observatory is already running at http://127.0.0.1:4318/.\n'
        return 0
    fi
    stop_legacy_receiver
    stop_manual
    if [[ "$(uname -s)" == "Darwin" && -x "$(command -v launchctl || true)" ]]; then
        write_plist
        launchctl bootout "$(launch_domain)" "$PLIST" >/dev/null 2>&1 || true
        if ! launchctl bootstrap "$(launch_domain)" "$PLIST"; then
            printf 'LaunchAgent registration was unavailable; using a manual background process for this login.\n' >&2
            start_manual
        fi
    else
        start_manual
    fi
    local attempt
    for attempt in {1..40}; do
        if health_ok; then
            printf 'MAINFRAME observatory started at http://127.0.0.1:4318/.\n'
            return 0
        fi
        sleep 0.1
    done
    printf 'MAINFRAME observatory failed to start; see %s.\n' "$LOG_FILE" >&2
    return 1
}

stop_service() {
    if [[ "$(uname -s)" == "Darwin" ]] && managed_plist; then
        launchctl bootout "$(launch_domain)" "$PLIST" >/dev/null 2>&1 || true
    fi
    stop_legacy_receiver
    stop_manual
    if health_ok; then
        printf 'MAINFRAME observatory did not stop.\n' >&2
        return 1
    fi
    printf 'MAINFRAME observatory stopped.\n'
}

uninstall_service() {
    stop_service
    if managed_plist; then
        rm -f "$PLIST"
        printf 'Removed the MAINFRAME LaunchAgent; runtime data was preserved.\n'
    else
        printf 'No managed MAINFRAME LaunchAgent was installed; runtime data was preserved.\n'
    fi
}

enable_adapter() {
    local adapter="${1:-}"
    valid_adapter "$adapter" || { printf 'Unknown adapter: %s\n' "$adapter" >&2; return 2; }
    check_prerequisites
    ensure_runtime
    touch "${ACTIVE_DIR}/${adapter}"
    chmod 600 "${ACTIVE_DIR}/${adapter}"
    if ! start_service; then
        rm -f "${ACTIVE_DIR}/${adapter}"
        return 1
    fi
}

disable_adapter() {
    local adapter="${1:-}"
    valid_adapter "$adapter" || { printf 'Unknown adapter: %s\n' "$adapter" >&2; return 2; }
    rm -f "${ACTIVE_DIR}/${adapter}"
    if [[ ! -d "$ACTIVE_DIR" ]] || ! find "$ACTIVE_DIR" -maxdepth 1 -type f -print -quit | grep -q .; then
        uninstall_service
    else
        printf 'Disabled %s observatory input; another dev adapter still uses the service.\n' "$adapter"
    fi
}

status_service() {
    if health_ok; then
        printf 'MAINFRAME observatory is running at http://127.0.0.1:4318/.\n'
        if [[ -d "$ACTIVE_DIR" ]]; then
            find "$ACTIVE_DIR" -maxdepth 1 -type f -exec basename {} \; | sort | sed 's/^/  dev adapter: /'
        fi
        return 0
    fi
    printf 'MAINFRAME observatory is not running.\n'
    return 1
}

case "${1:-}" in
    enable) enable_adapter "${2:-}" ;;
    disable) disable_adapter "${2:-}" ;;
    start) start_service ;;
    stop) stop_service ;;
    status) status_service ;;
    uninstall) uninstall_service ;;
    *) usage >&2; exit 2 ;;
esac
