#!/usr/bin/env bash

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
    cat <<'EOF'
MAINFRAME installer

Usage:
  ./install.sh --claude [--dry-run] [--dev] [--yes] [--replace-modified] [--uninstall]
  ./install.sh --codex [--dry-run] [--dev] [--yes] [--replace-modified] [--uninstall]
  ./install.sh --pi [--dry-run] [--yes] [--uninstall]
  ./install.sh --help

With no arguments, this help is shown and no changes are made.

Targets:
  --claude     Install or remove the Claude Code adapter.
  --codex      Install or remove the Codex adapter.
  --pi         Install or remove the Pi execution adapter.

Adapter options are forwarded unchanged to its installer.
Use --yes to approve a required Claude Code update without an interactive prompt.
Use --replace-modified only to back up and replace/remove locally customized
managed artifacts; otherwise they are preserved and the operation stops.
For Codex, --yes can back up and replace a conflicting credentials-index link;
it never authorizes loss of a locally changed managed copy.
EOF
}

main() {
    if [[ $# -eq 0 ]]; then
        usage
        return 0
    fi

    local adapter adapter_label
    case "$1" in
        -h|--help)
            usage
            return 0
            ;;
        --claude)
            adapter="claude-code"
            adapter_label="Claude Code"
            shift
            ;;
        --codex)
            adapter="codex"
            adapter_label="Codex"
            shift
            ;;
        --pi)
            adapter="pi"
            adapter_label="Pi"
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
        "${ROOT}/adapters/${adapter}/install.sh" --preflight "$@"
        if [[ "$adapter" != "pi" ]]; then
            echo "[mainframe] shared secrets"
            "${ROOT}/shared/credentials/install.sh" "$@"
            echo
        fi
    fi

    echo "[mainframe] ${adapter_label} adapter"
    "${ROOT}/adapters/${adapter}/install.sh" "$@"
}

main "$@"
