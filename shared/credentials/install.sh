#!/usr/bin/env bash

set -euo pipefail

COMPONENT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPOSITORY_ROOT="$(cd "$COMPONENT_ROOT/../.." && pwd)"
SOURCE="$COMPONENT_ROOT/mainframe-secret"
TARGET="$HOME/.local/bin/mainframe-secret"
LEGACY_TARGET="$HOME/.local/bin/secret"
INDEX="$COMPONENT_ROOT/credentials-index.md"
TEMPLATE="$COMPONENT_ROOT/credentials-index.template.md"
STORE_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/credentials"
DRY_RUN=0

usage() {
    printf '%s\n' 'Usage: install.sh [--dry-run]'
}

log() {
    printf '%s\n' "$1"
}

fail() {
    printf 'error: %s\n' "$1" >&2
    exit 1
}

parse_args() {
    while [[ "$#" -gt 0 ]]; do
        case "$1" in
            --dry-run) DRY_RUN=1 ;;
            -h|--help) usage; exit 0 ;;
            *) fail "unknown option: $1" ;;
        esac
        shift
    done
}

validate_command() {
    local command_path="$1" output
    output=$("$command_path" help 2>&1) || return 1
    [[ "$output" == *'mainframe-secret run NAME'* ]] \
        && [[ "$output" == *'mainframe-secret get NAME'* ]] \
        && [[ "$output" == *'mainframe-secret set NAME --clipboard'* ]] \
        && [[ "$output" == *'mainframe-secret copy NAME'* ]]
}

is_legacy_mainframe_command() {
    local command_path="$1"
    [[ -f "$command_path" ]] \
        && [[ ! -L "$command_path" ]] \
        && { grep -Fq 'Personal file-based secret command for macOS and Linux.' "$command_path" \
            || grep -Fq 'secret — personal secrets manager.' "$command_path"; } \
        && grep -Fq 'SECRETS_FILE="$SECRETS_DIR/secrets.env"' "$command_path"
}

install_command_file() {
    mkdir -p "$(dirname "$TARGET")"
    local temporary="$TARGET.tmp.$$"
    install -m 0755 "$SOURCE" "$temporary"
    mv "$temporary" "$TARGET"
}

retire_legacy_command() {
    if [[ ! -e "$LEGACY_TARGET" && ! -L "$LEGACY_TARGET" ]]; then
        return
    fi
    if ! is_legacy_mainframe_command "$LEGACY_TARGET"; then
        fail "the legacy path is not a recognized MAINFRAME helper: $LEGACY_TARGET"
    fi
    if [[ "$DRY_RUN" -eq 1 ]]; then
        log "would remove legacy MAINFRAME command: $LEGACY_TARGET"
    else
        rm -- "$LEGACY_TARGET"
        log "removed legacy MAINFRAME command: $LEGACY_TARGET"
    fi
}

install_command_if_missing() {
    local existing
    existing=$(command -v mainframe-secret 2>/dev/null || true)
    if [[ -n "$existing" ]]; then
        if validate_command "$existing"; then
            log "preserved existing compatible command: $existing"
            retire_legacy_command
            return
        fi
        if [[ "$existing" == "$TARGET" ]] && is_legacy_mainframe_command "$existing"; then
            if [[ "$DRY_RUN" -eq 1 ]]; then
                log "would update legacy MAINFRAME command: $TARGET"
            else
                install_command_file
                log "updated legacy MAINFRAME command: $TARGET"
            fi
            return
        fi
        fail "an incompatible command named 'mainframe-secret' already exists at $existing"
    fi
    if [[ -e "$TARGET" || -L "$TARGET" ]]; then
        validate_command "$TARGET" \
            || fail "an incompatible file already exists at $TARGET"
        log "preserved compatible command outside PATH: $TARGET"
        log "ensure $HOME/.local/bin is present in PATH"
        retire_legacy_command
        return
    fi
    if [[ "$DRY_RUN" -eq 1 ]]; then
        log "would install command: $TARGET"
        return
    fi
    install_command_file
    log "installed command: $TARGET"
    retire_legacy_command
}

ensure_store_directory() {
    if [[ -d "$STORE_DIR" ]]; then
        log "preserved existing store directory: $STORE_DIR"
        return
    fi
    if [[ -e "$STORE_DIR" ]]; then
        fail "credential store path exists but is not a directory: $STORE_DIR"
    fi
    if [[ "$DRY_RUN" -eq 1 ]]; then
        log "would create store directory: $STORE_DIR (0700)"
        return
    fi
    mkdir -p "$STORE_DIR"
    chmod 700 "$STORE_DIR"
    log "created store directory: $STORE_DIR"
}

ensure_index() {
    if [[ -e "$INDEX" ]]; then
        log "preserved existing central index: $INDEX"
        return
    fi
    if [[ "$DRY_RUN" -eq 1 ]]; then
        log "would seed central index from template: $INDEX"
        return
    fi
    install -m 0600 "$TEMPLATE" "$INDEX"
    log "seeded central index: $INDEX"
}

verify_index_is_ignored() (
    local owner ignore_check
    owner=$(git -C "$REPOSITORY_ROOT" rev-parse --show-toplevel 2>/dev/null || true)
    if [[ "$owner" == "$REPOSITORY_ROOT" ]]; then
        git -C "$REPOSITORY_ROOT" check-ignore -q \
            'shared/credentials/credentials-index.md' \
            || fail "shared/credentials/credentials-index.md is not ignored by Git"
    else
        # Downloaded archives have ignore rules but no Git metadata. Evaluate
        # those rules with disposable metadata, without initializing the source.
        ignore_check=$(mktemp -d "${TMPDIR:-/tmp}/mainframe-ignore.XXXXXX")
        trap 'rm -rf -- "$ignore_check"' EXIT
        git init --bare --template= -q "$ignore_check"
        git -C "$REPOSITORY_ROOT" --git-dir="$ignore_check" \
            --work-tree="$REPOSITORY_ROOT" -c core.excludesFile=/dev/null \
            check-ignore -q 'shared/credentials/credentials-index.md' \
            || fail "shared/credentials/credentials-index.md is not ignored by shipped rules"
    fi
    log "verified central index is ignored by Git"
)

main() {
    parse_args "$@"
    [[ -x "$SOURCE" ]] || fail "canonical command is not executable: $SOURCE"
    [[ -f "$TEMPLATE" ]] || fail "missing index template: $TEMPLATE"
    verify_index_is_ignored
    install_command_if_missing
    ensure_store_directory
    ensure_index
    log "legacy index migration remains the adapting agent's scoped task"
}

main "$@"
