#!/usr/bin/env bash

set -euo pipefail

ADAPTER_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DIR="${MAINFRAME_BIN_DIR:-$HOME/.local/bin}"
TARGET="${TARGET_DIR}/mainframe-pi"
SOURCE="${ADAPTER_ROOT}/bin/mainframe-pi"
STAMP="${ADAPTER_ROOT}/node_modules/.mainframe-install-stamp"
EXPECTED_PI_VERSION="0.84.2"
DRY_RUN=0
UNINSTALL=0
PREFLIGHT=0
ASSUME_YES=0
DEV_MODE=0
REPO_ROOT="$(cd "${ADAPTER_ROOT}/../.." && pwd)"
TELEMETRY_DIR="${REPO_ROOT}/workspace/runtime/pi/telemetry"

usage() {
    cat <<'EOF'
MAINFRAME Pi adapter installer

Usage:
  install.sh [--dry-run] [--dev] [--yes] [--uninstall]
  install.sh --preflight [--dry-run] [--dev] [--yes]

Installs the project-scoped `mainframe-pi` launcher. Pi provider authorization
remains owned by the globally installed Pi CLI. The adapter installs only its
pinned local SDK dependencies and command link.
--dev enables privacy-safe Pi engineer telemetry and installs the local observatory command.
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run) DRY_RUN=1 ;;
        --uninstall) UNINSTALL=1 ;;
        --preflight) PREFLIGHT=1 ;;
        --yes) ASSUME_YES=1 ;;
        --dev) DEV_MODE=1 ;;
        -h|--help) usage; exit 0 ;;
        *) printf 'Error: Unknown Pi adapter option: %s\n' "$1" >&2; exit 2 ;;
    esac
    shift
done

resolve_link() {
    local source="$1" directory target
    while [[ -L "$source" ]]; do
        directory="$(cd -P "$(dirname "$source")" && pwd)"
        target="$(readlink "$source")"
        if [[ "$target" == /* ]]; then source="$target"; else source="${directory}/${target}"; fi
    done
    printf '%s/%s\n' "$(cd -P "$(dirname "$source")" && pwd)" "$(basename "$source")"
}

preflight() {
    local actual node_major
    [[ -x "$SOURCE" ]] || { printf 'Error: Missing executable Pi launcher: %s\n' "$SOURCE" >&2; return 1; }
    [[ -f "${ADAPTER_ROOT}/package-lock.json" ]] || { printf 'Error: Missing Pi package lock.\n' >&2; return 1; }
    [[ -f "${ADAPTER_ROOT}/config/profiles.example.json" ]] || { printf 'Error: Missing Pi profile example.\n' >&2; return 1; }
    command -v pi >/dev/null 2>&1 || { printf 'Error: Global Pi CLI is unavailable.\n' >&2; return 1; }
    actual="$(pi --version 2>/dev/null | sed -nE 's/.*(^|[[:space:]])([0-9]+\.[0-9]+\.[0-9]+)([[:space:]]|$).*/\2/p' | head -n 1)"
    [[ "$actual" == "$EXPECTED_PI_VERSION" ]] || {
        printf 'Error: Pi CLI %s is incompatible with the pinned adapter SDK %s.\n' "${actual:-unknown}" "$EXPECTED_PI_VERSION" >&2
        return 1
    }
    command -v node >/dev/null 2>&1 || { printf 'Error: Node.js 24 or newer is required.\n' >&2; return 1; }
    node_major="$(node -p 'process.versions.node.split(".")[0]')"
    [[ "$node_major" =~ ^[0-9]+$ && "$node_major" -ge 24 ]] || {
        printf 'Error: Node.js 24 or newer is required.\n' >&2
        return 1
    }
    command -v npm >/dev/null 2>&1 || { printf 'Error: npm is required.\n' >&2; return 1; }
}

if [[ $UNINSTALL -eq 1 ]]; then
    if [[ -L "$TARGET" && "$(resolve_link "$TARGET")" == "$(resolve_link "$SOURCE")" ]]; then
        if [[ $DRY_RUN -eq 1 ]]; then printf 'would remove owned Pi launcher %s\n' "$TARGET"; else rm "$TARGET"; printf 'removed owned Pi launcher %s\n' "$TARGET"; fi
    elif [[ -e "$TARGET" || -L "$TARGET" ]]; then
        printf 'preserved non-owned Pi launcher %s\n' "$TARGET"
    else
        printf 'Pi launcher is not installed.\n'
    fi
    if [[ $DRY_RUN -eq 1 ]]; then
        printf 'would disable the Pi observatory input; telemetry data would be preserved\n'
    else
        rm -f "${TELEMETRY_DIR}/enabled"
        "${REPO_ROOT}/tools/mainframe-observatory.sh" disable pi >/dev/null 2>&1 || true
    fi
    exit 0
fi

preflight
if [[ $PREFLIGHT -eq 1 ]]; then
    printf 'Pi adapter preflight passed.\n'
    exit 0
fi

if [[ ! -f "${ADAPTER_ROOT}/config/profiles.local.json" ]]; then
    if [[ $DRY_RUN -eq 1 ]]; then
        printf 'would create machine-local Pi routing from profiles.example.json\n'
    else
        cp "${ADAPTER_ROOT}/config/profiles.example.json" "${ADAPTER_ROOT}/config/profiles.local.json"
        chmod 600 "${ADAPTER_ROOT}/config/profiles.local.json"
        printf 'created machine-local Pi routing; verify model aliases before the first run\n'
    fi
fi

if [[ ! -x "${ADAPTER_ROOT}/node_modules/.bin/tsx" || ! -f "$STAMP" || "${ADAPTER_ROOT}/package-lock.json" -nt "$STAMP" ]]; then
    if [[ $DRY_RUN -eq 1 ]]; then
        printf 'would install pinned Pi adapter dependencies with npm ci\n'
    else
        (cd "$ADAPTER_ROOT" && npm ci)
        touch "$STAMP"
        printf 'installed pinned Pi adapter dependencies\n'
    fi
else
    printf 'Pi adapter dependencies are current.\n'
fi

if [[ -L "$TARGET" && "$(resolve_link "$TARGET")" == "$(resolve_link "$SOURCE")" ]]; then
    printf 'Pi launcher is already installed: %s\n' "$TARGET"
elif [[ -e "$TARGET" || -L "$TARGET" ]]; then
    if [[ $ASSUME_YES -ne 1 ]]; then
        printf 'Error: A launcher already exists at %s. Rerun with --yes to back it up.\n' "$TARGET" >&2
        exit 1
    fi
    backup="${TARGET}.backup-$(date +%Y%m%d-%H%M%S)-$$"
    if [[ $DRY_RUN -eq 1 ]]; then
        printf 'would back up %s to %s\n' "$TARGET" "$backup"
        printf 'would link %s -> %s\n' "$TARGET" "$SOURCE"
    else
        mv "$TARGET" "$backup"
        printf 'backed up existing launcher to %s\n' "$backup"
        mkdir -p "$TARGET_DIR"
        ln -s "$SOURCE" "$TARGET"
        printf 'installed Pi launcher: %s\n' "$TARGET"
    fi
elif [[ $DRY_RUN -eq 1 ]]; then
    printf 'would link %s -> %s\n' "$TARGET" "$SOURCE"
else
    mkdir -p "$TARGET_DIR"
    ln -s "$SOURCE" "$TARGET"
    printf 'installed Pi launcher: %s\n' "$TARGET"
fi

if [[ $DEV_MODE -eq 1 ]]; then
    if [[ $DRY_RUN -eq 1 ]]; then
        printf 'would enable privacy-safe Pi engineer telemetry and install the observatory command without starting it\n'
    else
        mkdir -p "$TELEMETRY_DIR"
        touch "${TELEMETRY_DIR}/enabled"
        chmod 700 "$TELEMETRY_DIR"
        chmod 600 "${TELEMETRY_DIR}/enabled"
        if ! "${REPO_ROOT}/tools/mainframe-observatory.sh" enable pi; then
            rm -f "${TELEMETRY_DIR}/enabled"
            printf 'Error: Pi dev telemetry was not enabled because the observatory command could not be installed.\n' >&2
            exit 1
        fi
        printf 'enabled Pi engineer telemetry and installed the MAINFRAME Observatory command\n'
    fi
elif [[ $DRY_RUN -eq 0 ]]; then
    rm -f "${TELEMETRY_DIR}/enabled"
    "${REPO_ROOT}/tools/mainframe-observatory.sh" disable pi >/dev/null 2>&1 || true
fi
