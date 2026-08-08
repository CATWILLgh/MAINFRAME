#!/usr/bin/env bash

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
    cat <<'EOF'
MAINFRAME installer

Usage:
  ./install.sh --claude [--dry-run] [--dev] [--uninstall]
  ./install.sh --help

With no arguments, this help is shown and no changes are made.

Targets:
  --claude     Install or remove the Claude Code adapter.

Adapter options are forwarded unchanged to its installer.
EOF
}

main() {
    if [[ $# -eq 0 ]]; then
        usage
        return 0
    fi

    case "$1" in
        -h|--help)
            usage
            return 0
            ;;
        --claude)
            shift
            ;;
        *)
            echo "Unknown target: $1" >&2
            usage >&2
            return 2
            ;;
    esac

    local uninstall=0
    local argument
    for argument in "$@"; do
        if [[ "$argument" == "--uninstall" ]]; then
            uninstall=1
        fi
    done

    if [[ $uninstall -eq 0 ]]; then
        echo "[mainframe] shared secrets"
        "${ROOT}/shared/credentials/install.sh" "$@"
        echo
    fi

    echo "[mainframe] Claude Code adapter"
    "${ROOT}/adapters/claude-code/install.sh" "$@"
}

main "$@"
