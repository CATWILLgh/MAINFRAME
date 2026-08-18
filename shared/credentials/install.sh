#!/usr/bin/env bash

set -euo pipefail

COMPONENT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DRY_RUN=0
UNINSTALL=0
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"

usage() {
    cat <<'EOF'
MAINFRAME shared secrets installer

Usage:
  install.sh [--dry-run] [--yes] [--uninstall]
EOF
}

log() {
    printf '%s\n' "$1"
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --dry-run) DRY_RUN=1 ;;
            --uninstall) UNINSTALL=1 ;;
            --dev|--yes|--replace-modified) ;;
            -h|--help) usage; exit 0 ;;
            *) echo "Unknown shared-secrets option: $1" >&2; exit 2 ;;
        esac
        shift
    done
}

resolve_link() {
    python3 -c 'import os,sys; print(os.path.realpath(sys.argv[1]))' "$1"
}

install_helper() {
    local bin_dir="$HOME/.local/bin"
    local target="$bin_dir/secret"
    local source="$COMPONENT_ROOT/secret"

    if [[ -L "$target" ]] && [[ "$(resolve_link "$target")" == "$source" ]]; then
        log "secret helper already linked: $target"
        return
    fi
    if [[ $DRY_RUN -eq 1 ]]; then
        log "would link $target -> $source"
        return
    fi

    mkdir -p "$bin_dir"
    if [[ -e "$target" || -L "$target" ]]; then
        mv "$target" "${target}.backup-${TIMESTAMP}"
        log "backed up existing helper: ${target}.backup-${TIMESTAMP}"
    fi
    ln -s "$source" "$target"
    log "linked $target -> $source"
}

ensure_index() {
    local index="$COMPONENT_ROOT/credentials-index.md"
    local template="$COMPONENT_ROOT/credentials-index.template.md"
    if [[ -e "$index" ]]; then
        log "credentials index already present: $index"
        return
    fi
    if [[ $DRY_RUN -eq 1 ]]; then
        log "would seed $index from adjacent template"
        return
    fi
    cp "$template" "$index"
    chmod 600 "$index"
    log "seeded credentials index: $index"
}

ensure_store() {
    local store="${XDG_CONFIG_HOME:-$HOME/.config}/credentials"
    if [[ -d "$store" ]]; then
        log "credentials store already present: $store"
        return
    fi
    if [[ $DRY_RUN -eq 1 ]]; then
        log "would create $store with mode 0700"
        return
    fi
    mkdir -p "$store"
    chmod 700 "$store"
    log "created credentials store: $store"
}

append_source_line() {
    local rcfile="$1"
    local source_line='[ -f ~/.config/credentials/secrets.env ] && set -a && . ~/.config/credentials/secrets.env && set +a'
    if grep -Fqs "$source_line" "$rcfile" 2>/dev/null; then
        log "$(basename "$rcfile") already sources the credentials store"
        return
    fi
    if [[ $DRY_RUN -eq 1 ]]; then
        log "would append credentials source line to $rcfile"
        return
    fi
    printf '\n%s\n' "$source_line" >> "$rcfile"
    log "updated $rcfile"
}

uninstall_helper() {
    local target="$HOME/.local/bin/secret"
    local source="$COMPONENT_ROOT/secret"
    if [[ ! -L "$target" ]] || [[ "$(resolve_link "$target")" != "$source" ]]; then
        log "shared secret helper is not installed by this component"
        return
    fi
    if [[ $DRY_RUN -eq 1 ]]; then
        log "would remove $target"
    else
        rm "$target"
        log "removed $target; credentials and index were preserved"
    fi
}

main() {
    parse_args "$@"
    if [[ $UNINSTALL -eq 1 ]]; then
        uninstall_helper
        return
    fi
    install_helper
    ensure_index
    ensure_store
    append_source_line "$HOME/.zshenv"
    if [[ -f "$HOME/.bashrc" ]]; then append_source_line "$HOME/.bashrc"; fi
    if [[ -f "$HOME/.profile" ]]; then append_source_line "$HOME/.profile"; fi
}

main "$@"
