#!/usr/bin/env bash
set -euo pipefail

SOURCE="${BASH_SOURCE[0]}"
while [[ -L "$SOURCE" ]]; do
    SOURCE_DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"
    SOURCE="$(readlink "$SOURCE")"
    [[ "$SOURCE" = /* ]] || SOURCE="${SOURCE_DIR}/${SOURCE}"
done
SOURCE="$(cd -P "$(dirname "$SOURCE")" && pwd)/$(basename "$SOURCE")"
ROOT="$(cd "$(dirname "$SOURCE")/.." && pwd)"
RUNTIME="${MAINFRAME_OBSERVATORY_RUNTIME:-${ROOT}/workspace/runtime/observatory}"
ACTIVE_DIR="${RUNTIME}/enabled"
LOG_FILE="${RUNTIME}/service.log"
AUTOSTART_LOG_FILE="${MAINFRAME_OBSERVATORY_AUTOSTART_LOG:-${HOME}/Library/Logs/MAINFRAME Observatory/service.log}"
TOKEN_FILE="${RUNTIME}/service.token"
PYTHON="${ROOT}/.venv/bin/python3"
CONTROL_PYTHON="$(command -v python3 || true)"
SERVICE="${ROOT}/tools/observatory_service.py"
PORT="${MAINFRAME_OBSERVATORY_PORT:-4318}"
URL="http://127.0.0.1:${PORT}/"
HEALTH="${URL}health"
BIN_DIR="${MAINFRAME_BIN_DIR:-${HOME}/.local/bin}"
COMMAND_TARGET="${BIN_DIR}/mainframe-observatory"
LABEL="com.mainframe.observatory"
PLIST="${MAINFRAME_LAUNCH_AGENTS_DIR:-${HOME}/Library/LaunchAgents}/${LABEL}.plist"
SYSTEMD_DIR="${MAINFRAME_SYSTEMD_USER_DIR:-${HOME}/.config/systemd/user}"
SYSTEMD_UNIT="${SYSTEMD_DIR}/mainframe-observatory.service"
TESTING="${MAINFRAME_OBSERVATORY_TESTING:-0}"

usage() {
    cat <<'EOF'
MAINFRAME Observatory — local development telemetry panel

Usage:
  mainframe-observatory                 Run in this terminal (Ctrl+C stops it)
  mainframe-observatory status          Show server and autostart status
  mainframe-observatory open            Open the panel in a browser
  mainframe-observatory autostart install
  mainframe-observatory autostart status
  mainframe-observatory autostart remove

The command is delivered only by a MAINFRAME adapter installed with --dev.
The server listens only on 127.0.0.1 and starts automatically only after the
explicit `mainframe-observatory autostart install` command.
EOF
}

platform_name() {
    if [[ "$TESTING" == "1" && -n "${MAINFRAME_OBSERVATORY_TEST_PLATFORM:-}" ]]; then
        printf '%s\n' "$MAINFRAME_OBSERVATORY_TEST_PLATFORM"
    else
        uname -s
    fi
}

valid_adapter() {
    [[ "${1:-}" == "claude-code" || "${1:-}" == "codex" || "${1:-}" == "pi" ]]
}

check_prerequisites() {
    if [[ ! -x "$PYTHON" ]]; then
        printf 'MAINFRAME Observatory cannot start: %s is missing.\n' "$PYTHON" >&2
        printf 'Create the repository .venv and install tools/telemetry-requirements.txt.\n' >&2
        return 2
    fi
    if ! "$PYTHON" -c 'import opentelemetry.proto.collector.logs.v1.logs_service_pb2' >/dev/null 2>&1; then
        printf 'MAINFRAME Observatory cannot start: dev telemetry dependencies are missing.\n' >&2
        printf 'Run .venv/bin/pip install -r tools/telemetry-requirements.txt.\n' >&2
        return 2
    fi
}

ensure_runtime() {
    [[ -n "$CONTROL_PYTHON" ]] || { printf 'python3 is required.\n' >&2; return 2; }
    mkdir -p "$RUNTIME" "$ACTIVE_DIR"
    if [[ ! -s "$TOKEN_FILE" ]]; then
        "$CONTROL_PYTHON" -c 'import secrets; print(secrets.token_urlsafe(32))' > "$TOKEN_FILE"
    fi
    touch "$LOG_FILE"
    chmod 600 "$TOKEN_FILE" "$LOG_FILE"
    rm -f "${RUNTIME}/service.pid"
}

health_ok() {
    [[ -n "$CONTROL_PYTHON" && -s "$TOKEN_FILE" ]] || return 1
    "$CONTROL_PYTHON" - "$HEALTH" "$TOKEN_FILE" <<'PY' >/dev/null 2>&1
import sys
import urllib.request
token = open(sys.argv[2], encoding="utf-8").read().strip()
with urllib.request.urlopen(sys.argv[1], timeout=1) as response:
    actual = response.headers.get("X-Mainframe-Instance", "")
    raise SystemExit(0 if response.status == 200 and actual == token else 1)
PY
}

wait_healthy() {
    local attempt
    for attempt in {1..40}; do health_ok && return 0; sleep 0.25; done
    return 1
}

resolve_link() {
    local target="$1" directory
    while [[ -L "$target" ]]; do
        directory="$(cd -P "$(dirname "$target")" && pwd)"
        target="$(readlink "$target")"
        [[ "$target" = /* ]] || target="${directory}/${target}"
    done
    [[ -e "$target" ]] || return 1
    printf '%s/%s\n' "$(cd -P "$(dirname "$target")" && pwd)" "$(basename "$target")"
}

install_command() {
    mkdir -p "$BIN_DIR"
    if [[ -e "$COMMAND_TARGET" || -L "$COMMAND_TARGET" ]]; then
        if [[ "$(resolve_link "$COMMAND_TARGET" 2>/dev/null || true)" != "$SOURCE" ]]; then
            printf 'Refusing to replace an unmanaged command: %s\n' "$COMMAND_TARGET" >&2
            return 1
        fi
        return 0
    fi
    ln -s "$SOURCE" "$COMMAND_TARGET"
}

remove_command() {
    if [[ -L "$COMMAND_TARGET" && "$(resolve_link "$COMMAND_TARGET" 2>/dev/null || true)" == "$SOURCE" ]]; then
        rm -f "$COMMAND_TARGET"
    fi
}

managed_plist() {
    [[ -f "$PLIST" && -n "$CONTROL_PYTHON" ]] || return 1
    "$CONTROL_PYTHON" - "$PLIST" "$LABEL" "$SERVICE" <<'PY' >/dev/null 2>&1
import plistlib, sys
with open(sys.argv[1], "rb") as handle: value = plistlib.load(handle)
raise SystemExit(0 if value.get("Label") == sys.argv[2] and sys.argv[3] in (value.get("ProgramArguments") or []) else 1)
PY
}

write_plist() {
    local system_python="/usr/bin/python3" site_packages
    [[ -x "$system_python" ]] || {
        printf 'macOS autostart requires /usr/bin/python3 (Apple Command Line Tools).\n' >&2
        return 2
    }
    site_packages="$("$PYTHON" -c 'import site; print(site.getsitepackages()[0])')"
    mkdir -p "$(dirname "$PLIST")"
    mkdir -p "$(dirname "$AUTOSTART_LOG_FILE")"
    touch "$AUTOSTART_LOG_FILE"
    chmod 600 "$AUTOSTART_LOG_FILE"
    if [[ -e "$PLIST" ]] && ! managed_plist; then
        printf 'Refusing to replace an unmanaged LaunchAgent: %s\n' "$PLIST" >&2; return 1
    fi
    "$CONTROL_PYTHON" - "$PLIST" "$LABEL" "$system_python" "$SERVICE" "$ROOT" "$RUNTIME" "$TOKEN_FILE" "$AUTOSTART_LOG_FILE" "$PORT" "$site_packages" <<'PY'
import os, plistlib, sys, tempfile
target, label, python, service, root, runtime, token, log, port, site_packages = sys.argv[1:]
payload = {
    "Label": label,
    "ProgramArguments": [python, "-B", service, "--health-token-file", token, "--runtime", runtime, "--port", port],
    "RunAtLoad": True, "KeepAlive": True,
    "ProcessType": "Background", "ThrottleInterval": 10,
    "StandardOutPath": log, "StandardErrorPath": log,
    "EnvironmentVariables": {
        "PYTHONUNBUFFERED": "1",
        "PYTHONPATH": site_packages,
        "PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION": "python",
    },
}
fd, temporary = tempfile.mkstemp(prefix=".mainframe-observatory-", dir=os.path.dirname(target))
try:
    with os.fdopen(fd, "wb") as handle: plistlib.dump(payload, handle, sort_keys=True)
    os.chmod(temporary, 0o644); os.replace(temporary, target)
finally:
    if os.path.exists(temporary): os.unlink(temporary)
PY
}

managed_systemd_unit() {
    [[ -f "$SYSTEMD_UNIT" ]] || return 1
    grep -Fq '# Managed by MAINFRAME Observatory' "$SYSTEMD_UNIT" && grep -Fq "$SERVICE" "$SYSTEMD_UNIT"
}

write_systemd_unit() {
    mkdir -p "$SYSTEMD_DIR"
    if [[ -e "$SYSTEMD_UNIT" ]] && ! managed_systemd_unit; then
        printf 'Refusing to replace an unmanaged user service: %s\n' "$SYSTEMD_UNIT" >&2; return 1
    fi
    "$CONTROL_PYTHON" - "$SYSTEMD_UNIT" "$PYTHON" "$SERVICE" "$ROOT" "$RUNTIME" "$TOKEN_FILE" "$LOG_FILE" "$PORT" <<'PY'
import os, sys, tempfile
target, python, service, root, runtime, token, log, port = sys.argv[1:]
def quote(value): return '"' + value.replace('\\', '\\\\').replace('"', '\\"') + '"'
payload = "\n".join([
    "# Managed by MAINFRAME Observatory", "[Unit]",
    "Description=MAINFRAME Observatory local development telemetry panel", "After=network.target", "",
    "[Service]", "Type=simple", f"WorkingDirectory={quote(root)}",
    f"ExecStart={quote(python)} -B {quote(service)} --health-token-file {quote(token)} --runtime {quote(runtime)} --port {port}",
    "Restart=on-failure", "RestartSec=10", "",
    "[Install]", "WantedBy=default.target", "",
])
fd, temporary = tempfile.mkstemp(prefix=".mainframe-observatory-", dir=os.path.dirname(target), text=True)
try:
    with os.fdopen(fd, "w", encoding="utf-8") as handle: handle.write(payload)
    os.chmod(temporary, 0o644); os.replace(temporary, target)
finally:
    if os.path.exists(temporary): os.unlink(temporary)
PY
}

launch_domain() { printf 'gui/%s\n' "$(id -u)"; }

autostart_install() {
    check_prerequisites; ensure_runtime; install_command
    case "$(platform_name)" in
        Darwin)
            write_plist
            if [[ "$TESTING" == "1" ]]; then printf 'Prepared MAINFRAME Observatory LaunchAgent.\n'; return 0; fi
            command -v launchctl >/dev/null 2>&1 || { printf 'launchctl is unavailable.\n' >&2; return 2; }
            launchctl bootout "$(launch_domain)" "$PLIST" >/dev/null 2>&1 || true
            launchctl bootstrap "$(launch_domain)" "$PLIST" || { printf 'Could not register MAINFRAME Observatory with launchd.\n' >&2; return 1; }
            ;;
        Linux)
            write_systemd_unit
            if [[ "$TESTING" == "1" ]]; then printf 'Prepared MAINFRAME Observatory systemd user service.\n'; return 0; fi
            command -v systemctl >/dev/null 2>&1 || { printf 'systemctl is unavailable.\n' >&2; return 2; }
            systemctl --user daemon-reload
            systemctl --user enable --now mainframe-observatory.service
            ;;
        *) printf 'Autostart is supported on macOS and systemd-based Linux.\n' >&2; return 2 ;;
    esac
    if ! wait_healthy; then
        autostart_remove 1
        if [[ "$(platform_name)" == "Darwin" ]] && grep -Fq "Operation not permitted" "$AUTOSTART_LOG_FILE" 2>/dev/null; then
            printf 'macOS denied the background process access to this repository. Autostart was rolled back.\n' >&2
            printf 'Run mainframe-observatory in a terminal, or move the repository outside Desktop, Documents, and Downloads.\n' >&2
        else
            printf 'Autostart did not become healthy and was rolled back; run mainframe-observatory in a terminal to inspect the failure.\n' >&2
        fi
        return 1
    fi
    printf 'MAINFRAME Observatory autostart is active at %s\n' "$URL"
}

autostart_remove() {
    local quiet="${1:-0}"
    case "$(platform_name)" in
        Darwin)
            if managed_plist; then
                [[ "$TESTING" == "1" ]] || launchctl bootout "$(launch_domain)" "$PLIST" >/dev/null 2>&1 || true
                rm -f "$PLIST"
            fi ;;
        Linux)
            if managed_systemd_unit; then
                if [[ "$TESTING" != "1" ]] && command -v systemctl >/dev/null 2>&1; then
                    systemctl --user disable --now mainframe-observatory.service >/dev/null 2>&1 || true
                fi
                rm -f "$SYSTEMD_UNIT"
                if [[ "$TESTING" != "1" ]] && command -v systemctl >/dev/null 2>&1; then systemctl --user daemon-reload >/dev/null 2>&1 || true; fi
            fi ;;
    esac
    [[ "$quiet" == "1" ]] || printf 'MAINFRAME Observatory autostart is removed; telemetry data was preserved.\n'
}

autostart_status() {
    local installed="no"
    case "$(platform_name)" in Darwin) managed_plist && installed="yes" ;; Linux) managed_systemd_unit && installed="yes" ;; esac
    printf 'Autostart installed: %s\n' "$installed"
    health_ok && printf 'Panel running: yes (%s)\n' "$URL" || printf 'Panel running: no\n'
    [[ "$installed" == "yes" ]]
}

serve_foreground() {
    check_prerequisites; ensure_runtime
    if health_ok; then printf 'MAINFRAME Observatory is already running at %s\n' "$URL"; return 0; fi
    printf 'MAINFRAME Observatory: %s\nRunning in this terminal. Press Ctrl+C to stop.\n' "$URL"
    exec "$PYTHON" -B "$SERVICE" --health-token-file "$TOKEN_FILE" --runtime "$RUNTIME" --port "$PORT"
}

open_panel() {
    health_ok || { printf 'MAINFRAME Observatory is not running. Start it first.\n' >&2; return 1; }
    case "$(platform_name)" in Darwin) open "$URL" ;; Linux) xdg-open "$URL" ;; *) printf '%s\n' "$URL" ;; esac
}

status_service() {
    autostart_status || true
    if [[ -d "$ACTIVE_DIR" ]]; then find "$ACTIVE_DIR" -maxdepth 1 -type f -exec basename {} \; | sort | sed 's/^/Dev adapter: /'; fi
}

has_enabled_adapters() {
    [[ -d "$ACTIVE_DIR" ]] && find "$ACTIVE_DIR" -maxdepth 1 -type f -print -quit | grep -q .
}

enable_adapter() {
    local adapter="${1:-}"
    valid_adapter "$adapter" || { printf 'Unknown adapter: %s\n' "$adapter" >&2; return 2; }
    ensure_runtime; install_command; touch "${ACTIVE_DIR}/${adapter}"; chmod 600 "${ACTIVE_DIR}/${adapter}"
    printf 'MAINFRAME Observatory command installed: %s\n' "$COMMAND_TARGET"
    printf 'Run `mainframe-observatory` when you want the panel, or install optional autostart.\n'
}

disable_adapter() {
    local adapter="${1:-}"
    valid_adapter "$adapter" || { printf 'Unknown adapter: %s\n' "$adapter" >&2; return 2; }
    rm -f "${ACTIVE_DIR}/${adapter}"
    if has_enabled_adapters; then printf 'Disabled %s observatory input; another dev adapter still uses the command.\n' "$adapter"; return 0; fi
    autostart_remove 1; remove_command
    printf 'Removed the MAINFRAME Observatory command and autostart; telemetry data was preserved.\n'
}

case "${1:-serve}" in
    serve|start) serve_foreground ;;
    status) status_service ;;
    open) open_panel ;;
    autostart)
        case "${2:-status}" in install) autostart_install ;; status) autostart_status ;; remove) autostart_remove ;; *) usage >&2; exit 2 ;; esac ;;
    enable) enable_adapter "${2:-}" ;;
    disable) disable_adapter "${2:-}" ;;
    help|-h|--help) usage ;;
    *) usage >&2; exit 2 ;;
esac
