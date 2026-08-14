#!/usr/bin/env bash

set -euo pipefail

ADAPTER_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${ADAPTER_ROOT}/../.." && pwd)"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)-$$"
CODEX_DIR="${CODEX_HOME:-$HOME/.codex}"
GLOBAL_SKILLS_DIR="$HOME/.agents/skills"
SOURCE_AGENTS="${ADAPTER_ROOT}/export/AGENTS.md"
TARGET_AGENTS="${CODEX_DIR}/AGENTS.md"
AGENTS_STATE="${CODEX_DIR}/.mainframe-agents-state"
INDEX_SOURCE="${REPO_ROOT}/shared/credentials/credentials-index.md"
INDEX_TARGET="${CODEX_DIR}/credentials-index.md"
INDEX_STATE="${CODEX_DIR}/.mainframe-index-state"
RULES_SOURCE="${ADAPTER_ROOT}/rules/mainframe.rules"
RULES_TARGET="${CODEX_DIR}/rules/mainframe.rules"
RULES_STATE="${CODEX_DIR}/.mainframe-rules-state"
CONFIG_SOURCE="${ADAPTER_ROOT}/config/mainframe-permissions.toml"
CONFIG_TOOL="${ADAPTER_ROOT}/scripts/manage-config.py"
CONFIG_TARGET="${CODEX_DIR}/config.toml"
CONFIG_STATE="${CODEX_DIR}/.mainframe-config-state.json"
CONFIG_BACKUP="${CONFIG_TARGET}.backup-${TIMESTAMP}"
REQUIREMENTS_SOURCE="${ADAPTER_ROOT}/config/mainframe-requirements.toml"
REQUIREMENTS_TOOL="${ADAPTER_ROOT}/scripts/manage-requirements.py"
REQUIREMENTS_TARGET="${CODEX_REQUIREMENTS_FILE:-/etc/codex/requirements.toml}"
REQUIREMENTS_DIR="$(dirname "$REQUIREMENTS_TARGET")"
REQUIREMENTS_STATE="${REQUIREMENTS_DIR}/.mainframe-requirements-state.json"
REQUIREMENTS_BACKUP="${REQUIREMENTS_TARGET}.backup-${TIMESTAMP}"

DRY_RUN=0
ASSUME_YES=0
UNINSTALL=0
PREFLIGHT=0

usage() {
    cat <<'EOF'
MAINFRAME Codex adapter installer

Usage:
  install.sh [--dry-run] [--yes] [--uninstall]
  install.sh --preflight [--dry-run] [--yes]

The baseline is delivered directly so Desktop, CLI, and the IDE extension can
share AGENTS.md, standalone skills, command rules, and a bounded permission
profile. The system profile allowlist requires administrator access and keeps
the three built-in modes plus mainframe. Codex plugins, hooks, agents, and
development telemetry are not installed by this version.
EOF
}

log() { printf '%s\n' "$1"; }
error() { printf 'Error: %s\n' "$1" >&2; }

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --dry-run) DRY_RUN=1 ;;
            --yes) ASSUME_YES=1 ;;
            --uninstall) UNINSTALL=1 ;;
            --preflight) PREFLIGHT=1 ;;
            -h|--help) usage; exit 0 ;;
            --dev)
                error "Codex development delivery is not implemented yet."
                exit 2
                ;;
            *) error "Unknown Codex adapter option: $1"; exit 2 ;;
        esac
        shift
    done
}

require_python() {
    if ! command -v python3 >/dev/null 2>&1 || ! python3 -c 'import hashlib' >/dev/null 2>&1; then
        error "A working python3 is required; no Codex adapter files were changed."
        return 1
    fi
}

hash_file() {
    python3 -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1], "rb").read()).hexdigest())' "$1"
}

resolve_link() {
    python3 -c 'import os,sys; print(os.path.realpath(sys.argv[1]))' "$1"
}

state_value() {
    local key="$1"
    [[ -f "$AGENTS_STATE" ]] || return 1
    sed -n "s/^${key}=//p" "$AGENTS_STATE" | head -n 1
}

runtime_preflight() {
    local found=0
    if command -v codex >/dev/null 2>&1; then
        log "Codex CLI: $(codex --version 2>/dev/null || printf 'detected')"
        found=1
    fi
    if [[ -x /Applications/ChatGPT.app/Contents/Resources/codex ]]; then
        log "Codex Desktop runtime: $(/Applications/ChatGPT.app/Contents/Resources/codex --version 2>/dev/null || printf 'detected')"
        found=1
    fi
    if [[ $found -eq 0 ]]; then
        error "No Codex CLI or Codex Desktop runtime was detected."
        return 1
    fi
}

link_conflicts() {
    local target="$1" source="$2"
    if [[ -L "$target" ]] && [[ "$(resolve_link "$target")" == "$source" ]]; then
        return 1
    fi
    [[ -e "$target" || -L "$target" ]]
}

delivery_preflight() {
    local target source managed_sha current_sha
    for source in "${ADAPTER_ROOT}/skills/mainframe-init" "${ADAPTER_ROOT}/skills/mainframe-secrets"; do
        target="${GLOBAL_SKILLS_DIR}/$(basename "$source")"
        if link_conflicts "$target" "$source"; then
            error "Refusing to replace existing skill path without a separate migration: $target"
            return 1
        fi
    done
    if link_conflicts "$INDEX_TARGET" "$INDEX_SOURCE" && [[ $ASSUME_YES -ne 1 ]]; then
        error "A Codex credentials index already exists. Rerun with --yes to back it up before linking the repository index."
        return 1
    fi
    if link_conflicts "$RULES_TARGET" "$RULES_SOURCE" && [[ $ASSUME_YES -ne 1 ]]; then
        error "A Codex MAINFRAME rules file already exists. Rerun with --yes to back it up before linking the adapter rules."
        return 1
    fi

    if [[ -f "$AGENTS_STATE" ]]; then
        managed_sha="$(state_value managed_sha || true)"
        if [[ ! -f "$TARGET_AGENTS" || -L "$TARGET_AGENTS" ]]; then
            if [[ $ASSUME_YES -ne 1 ]]; then
                error "The managed AGENTS.md installation is incomplete; inspect it or rerun with --yes."
                return 1
            fi
        elif [[ -n "$managed_sha" ]]; then
            current_sha="$(hash_file "$TARGET_AGENTS")"
            if [[ "$current_sha" != "$managed_sha" && $ASSUME_YES -ne 1 ]]; then
                error "The installed AGENTS.md has user changes; rerun with --yes to back them up and replace it."
                return 1
            fi
        fi
    elif [[ -e "$TARGET_AGENTS" || -L "$TARGET_AGENTS" ]]; then
        if [[ $ASSUME_YES -ne 1 ]]; then
            error "An unmanaged global AGENTS.md already exists. Rerun with --yes to back it up before replacement."
            return 1
        fi
    fi
}

check_sources() {
    local path
    for path in "$SOURCE_AGENTS" \
        "${ADAPTER_ROOT}/skills/mainframe-init/SKILL.md" \
        "${ADAPTER_ROOT}/skills/mainframe-secrets/SKILL.md" \
        "$RULES_SOURCE" \
        "$CONFIG_SOURCE" \
        "$CONFIG_TOOL" \
        "$REQUIREMENTS_SOURCE" \
        "$REQUIREMENTS_TOOL"; do
        if [[ ! -f "$path" ]]; then
            error "Codex adapter source is missing: $path"
            return 1
        fi
    done
}

manage_config() {
    local action="$1"
    shift
    python3 "$CONFIG_TOOL" "$action" \
        --config "$CONFIG_TARGET" \
        --source "$CONFIG_SOURCE" \
        --repo-root "$REPO_ROOT" \
        --state "$CONFIG_STATE" \
        --backup "$CONFIG_BACKUP" \
        "$@"
}

requirements_command() {
    local action="$1"
    shift
    python3 "$REQUIREMENTS_TOOL" "$action" \
        --requirements "$REQUIREMENTS_TARGET" \
        --source "$REQUIREMENTS_SOURCE" \
        --state "$REQUIREMENTS_STATE" \
        --backup "$REQUIREMENTS_BACKUP" \
        "$@"
}

manage_requirements() {
    local action="$1"
    local probe privileged_dir result
    shift
    if [[ $DRY_RUN -eq 1 ]]; then
        requirements_command "$action" --dry-run "$@"
        return
    fi
    probe="$(requirements_command "$action" --dry-run "$@")"
    if [[ "$action" == "install" && "$probe" == "would keep existing profile allowlist" ]]; then
        log "profile allowlist already installed"
        return
    fi
    if [[ "$action" == "uninstall" && "$probe" == "profile allowlist is not managed by MAINFRAME" ]]; then
        log "$probe"
        return
    fi
    if [[ "$REQUIREMENTS_TARGET" != /etc/* || $EUID -eq 0 ]]; then
        requirements_command "$action" "$@"
        return
    fi
    if ! command -v sudo >/dev/null 2>&1; then
        error "Administrator access is required to manage $REQUIREMENTS_TARGET."
        return 1
    fi
    privileged_dir="$(mktemp -d "${TMPDIR:-/tmp}/mainframe-codex-requirements.XXXXXX")"
    cp "$REQUIREMENTS_TOOL" "${privileged_dir}/manage-requirements.py"
    cp "$REQUIREMENTS_SOURCE" "${privileged_dir}/mainframe-requirements.toml"
    result=0
    sudo python3 "${privileged_dir}/manage-requirements.py" "$action" \
        --requirements "$REQUIREMENTS_TARGET" \
        --source "${privileged_dir}/mainframe-requirements.toml" \
        --state "$REQUIREMENTS_STATE" \
        --backup "$REQUIREMENTS_BACKUP" \
        "$@" || result=$?
    rm -r "$privileged_dir"
    return "$result"
}

validate_rules() {
    local runtime=""
    if command -v codex >/dev/null 2>&1; then
        runtime="$(command -v codex)"
    elif [[ -x /Applications/ChatGPT.app/Contents/Resources/codex ]]; then
        runtime="/Applications/ChatGPT.app/Contents/Resources/codex"
    fi
    if [[ -n "$runtime" ]] && ! "$runtime" execpolicy check --rules "$RULES_SOURCE" -- git push >/dev/null 2>&1; then
        error "Codex rejected the MAINFRAME rules file; no adapter files were changed."
        return 1
    fi
}

preflight() {
    local managed_sha current_sha
    require_python
    check_sources
    if [[ $UNINSTALL -eq 1 ]]; then
        if [[ -f "$AGENTS_STATE" ]]; then
            managed_sha="$(state_value managed_sha || true)"
            if [[ ! -f "$TARGET_AGENTS" || -L "$TARGET_AGENTS" || -z "$managed_sha" ]]; then
                error "Cannot safely uninstall AGENTS.md because the managed target or state is incomplete."
                return 1
            fi
            current_sha="$(hash_file "$TARGET_AGENTS")"
            if [[ "$current_sha" != "$managed_sha" ]]; then
                error "AGENTS.md changed after installation. It was preserved; reconcile it before uninstalling."
                return 1
            fi
        fi
        if [[ -f "$INDEX_STATE" ]] && { [[ ! -L "$INDEX_TARGET" ]] || [[ "$(resolve_link "$INDEX_TARGET")" != "$INDEX_SOURCE" ]]; }; then
            error "The Codex credentials index changed after installation. It was preserved."
            return 1
        fi
        if [[ -f "$RULES_STATE" ]] && { [[ ! -L "$RULES_TARGET" ]] || [[ "$(resolve_link "$RULES_TARGET")" != "$RULES_SOURCE" ]]; }; then
            error "The Codex MAINFRAME rules installation changed after installation. It was preserved."
            return 1
        fi
        manage_config uninstall --dry-run >/dev/null
        requirements_command uninstall --dry-run >/dev/null
    else
        runtime_preflight
        validate_rules
        delivery_preflight
        manage_config install --dry-run >/dev/null
        requirements_command install --dry-run >/dev/null
    fi
}

write_agents_state() {
    local managed_sha="$1" backup_path="$2"
    if [[ $DRY_RUN -eq 1 ]]; then return; fi
    printf 'managed_sha=%s\nbackup_path=%s\n' "$managed_sha" "$backup_path" > "$AGENTS_STATE"
    chmod 600 "$AGENTS_STATE"
}

install_agents() {
    local managed_sha current_sha old_managed backup_path
    managed_sha="$(hash_file "$SOURCE_AGENTS")"
    backup_path="-"

    if [[ -f "$AGENTS_STATE" ]]; then
        old_managed="$(state_value managed_sha || true)"
        backup_path="$(state_value backup_path || printf '-')"
        if [[ -L "$TARGET_AGENTS" ]]; then
            backup_path="${TARGET_AGENTS}.backup-${TIMESTAMP}"
            if [[ $DRY_RUN -eq 1 ]]; then
                log "would back up changed $TARGET_AGENTS to $backup_path"
            else
                mv "$TARGET_AGENTS" "$backup_path"
            fi
        elif [[ -f "$TARGET_AGENTS" ]]; then
            current_sha="$(hash_file "$TARGET_AGENTS")"
            if [[ -n "$old_managed" && "$current_sha" != "$old_managed" ]]; then
                backup_path="${TARGET_AGENTS}.backup-${TIMESTAMP}"
                if [[ $DRY_RUN -eq 1 ]]; then
                    log "would back up changed $TARGET_AGENTS to $backup_path"
                else
                    mv "$TARGET_AGENTS" "$backup_path"
                fi
            fi
        fi
    elif [[ -e "$TARGET_AGENTS" || -L "$TARGET_AGENTS" ]]; then
        backup_path="${TARGET_AGENTS}.backup-${TIMESTAMP}"
        if [[ $DRY_RUN -eq 1 ]]; then
            log "would back up existing $TARGET_AGENTS to $backup_path"
        else
            mv "$TARGET_AGENTS" "$backup_path"
        fi
    fi

    if [[ $DRY_RUN -eq 1 ]]; then
        log "would install regular file $TARGET_AGENTS from $SOURCE_AGENTS"
        return
    fi
    mkdir -p "$CODEX_DIR"
    cp "$SOURCE_AGENTS" "$TARGET_AGENTS"
    chmod 600 "$TARGET_AGENTS"
    write_agents_state "$managed_sha" "$backup_path"
    log "installed regular global instructions: $TARGET_AGENTS"
}

install_link() {
    local source="$1" target="$2" label="$3"
    if [[ ! -e "$source" ]]; then
        error "$label source is missing: $source"
        return 1
    fi
    if [[ -L "$target" ]] && [[ "$(resolve_link "$target")" == "$source" ]]; then
        log "$label already linked: $target"
        return
    fi
    if [[ $DRY_RUN -eq 1 ]]; then
        log "would link $target -> $source"
        return
    fi
    mkdir -p "$(dirname "$target")"
    ln -s "$source" "$target"
    log "linked $label: $target"
}

index_state_value() {
    [[ -f "$INDEX_STATE" ]] || return 1
    sed -n 's/^backup_path=//p' "$INDEX_STATE" | head -n 1
}

install_index() {
    local backup_path="-"
    if [[ -L "$INDEX_TARGET" ]] && [[ "$(resolve_link "$INDEX_TARGET")" == "$INDEX_SOURCE" ]]; then
        log "credentials index already linked: $INDEX_TARGET"
        return
    fi
    if [[ -f "$INDEX_STATE" ]]; then
        backup_path="$(index_state_value || printf '-')"
    fi
    if [[ -e "$INDEX_TARGET" || -L "$INDEX_TARGET" ]]; then
        backup_path="${INDEX_TARGET}.backup-${TIMESTAMP}"
        if [[ $DRY_RUN -eq 1 ]]; then
            log "would back up existing $INDEX_TARGET to $backup_path"
        else
            mv "$INDEX_TARGET" "$backup_path"
        fi
    fi
    if [[ $DRY_RUN -eq 1 ]]; then
        log "would link $INDEX_TARGET -> $INDEX_SOURCE"
        return
    fi
    if [[ ! -e "$INDEX_SOURCE" ]]; then
        error "credentials index source is missing: $INDEX_SOURCE"
        return 1
    fi
    mkdir -p "$CODEX_DIR"
    ln -s "$INDEX_SOURCE" "$INDEX_TARGET"
    printf 'backup_path=%s\n' "$backup_path" > "$INDEX_STATE"
    chmod 600 "$INDEX_STATE"
    log "linked credentials index: $INDEX_TARGET"
}

rules_state_value() {
    [[ -f "$RULES_STATE" ]] || return 1
    sed -n 's/^backup_path=//p' "$RULES_STATE" | head -n 1
}

install_rules() {
    local backup_path="-"
    if [[ -L "$RULES_TARGET" ]] && [[ "$(resolve_link "$RULES_TARGET")" == "$RULES_SOURCE" ]]; then
        log "Codex rules already linked: $RULES_TARGET"
        return
    fi
    if [[ -f "$RULES_STATE" ]]; then
        backup_path="$(rules_state_value || printf '-')"
    fi
    if [[ -e "$RULES_TARGET" || -L "$RULES_TARGET" ]]; then
        backup_path="${RULES_TARGET}.backup-${TIMESTAMP}"
        if [[ $DRY_RUN -eq 1 ]]; then
            log "would back up existing $RULES_TARGET to $backup_path"
        else
            mv "$RULES_TARGET" "$backup_path"
        fi
    fi
    if [[ $DRY_RUN -eq 1 ]]; then
        log "would link $RULES_TARGET -> $RULES_SOURCE"
        return
    fi
    mkdir -p "$(dirname "$RULES_TARGET")"
    ln -s "$RULES_SOURCE" "$RULES_TARGET"
    printf 'backup_path=%s\n' "$backup_path" > "$RULES_STATE"
    chmod 600 "$RULES_STATE"
    log "linked Codex command rules: $RULES_TARGET"
}

install_config() {
    if [[ $DRY_RUN -eq 1 ]]; then
        manage_config install --dry-run
    else
        manage_config install
    fi
}

install_adapter() {
    manage_requirements install
    install_agents
    install_link "${ADAPTER_ROOT}/skills/mainframe-init" "${GLOBAL_SKILLS_DIR}/mainframe-init" "manual init skill"
    install_link "${ADAPTER_ROOT}/skills/mainframe-secrets" "${GLOBAL_SKILLS_DIR}/mainframe-secrets" "secrets skill"
    install_index
    install_rules
    install_config
    if [[ $DRY_RUN -eq 1 ]]; then
        log "Codex baseline plan verified; no files were changed."
    else
        log "Codex baseline installed. Start a new task before relying on updated global instructions or skill discovery."
    fi
}

uninstall_rules() {
    local backup_path="-"
    if [[ ! -L "$RULES_TARGET" ]] || [[ "$(resolve_link "$RULES_TARGET")" != "$RULES_SOURCE" ]]; then
        if [[ -f "$RULES_STATE" ]]; then
            error "The Codex MAINFRAME rules installation changed after installation. It was preserved."
            return 1
        fi
        log "Codex rules are not an adapter-owned link: $RULES_TARGET"
        return
    fi
    if [[ -f "$RULES_STATE" ]]; then
        backup_path="$(rules_state_value || printf '-')"
    fi
    if [[ $DRY_RUN -eq 1 ]]; then
        log "would remove $RULES_TARGET"
        if [[ "$backup_path" != "-" ]]; then log "would restore $backup_path"; fi
        return
    fi
    rm "$RULES_TARGET"
    if [[ "$backup_path" != "-" && -e "$backup_path" ]]; then
        mv "$backup_path" "$RULES_TARGET"
        log "restored previous Codex rules: $RULES_TARGET"
    else
        log "removed Codex rules: $RULES_TARGET"
    fi
    if [[ -f "$RULES_STATE" ]]; then rm "$RULES_STATE"; fi
}

remove_owned_link() {
    local source="$1" target="$2" label="$3"
    if [[ ! -L "$target" ]] || [[ "$(resolve_link "$target")" != "$source" ]]; then
        log "$label is not an adapter-owned link: $target"
        return
    fi
    if [[ $DRY_RUN -eq 1 ]]; then
        log "would remove $target"
    else
        rm "$target"
        log "removed $label: $target"
    fi
}

uninstall_index() {
    local backup_path="-"
    if [[ ! -L "$INDEX_TARGET" ]] || [[ "$(resolve_link "$INDEX_TARGET")" != "$INDEX_SOURCE" ]]; then
        if [[ -f "$INDEX_STATE" ]]; then
            error "The Codex credentials index changed after installation. It was preserved."
            return 1
        fi
        log "credentials index is not an adapter-owned link: $INDEX_TARGET"
        return
    fi
    if [[ -f "$INDEX_STATE" ]]; then
        backup_path="$(index_state_value || printf '-')"
    fi
    if [[ $DRY_RUN -eq 1 ]]; then
        log "would remove $INDEX_TARGET"
        if [[ "$backup_path" != "-" ]]; then log "would restore $backup_path"; fi
        return
    fi
    rm "$INDEX_TARGET"
    if [[ "$backup_path" != "-" && -e "$backup_path" ]]; then
        mv "$backup_path" "$INDEX_TARGET"
        log "restored previous credentials index: $INDEX_TARGET"
    else
        log "removed credentials index link: $INDEX_TARGET"
    fi
    if [[ -f "$INDEX_STATE" ]]; then rm "$INDEX_STATE"; fi
}

uninstall_agents() {
    local managed_sha current_sha backup_path
    if [[ ! -f "$AGENTS_STATE" ]]; then
        log "global AGENTS.md is not managed by this adapter"
        return
    fi
    managed_sha="$(state_value managed_sha || true)"
    backup_path="$(state_value backup_path || printf '-')"
    if [[ ! -f "$TARGET_AGENTS" || -L "$TARGET_AGENTS" || -z "$managed_sha" ]]; then
        error "Cannot safely uninstall AGENTS.md because the managed target or state is incomplete."
        return 1
    fi
    current_sha="$(hash_file "$TARGET_AGENTS")"
    if [[ "$current_sha" != "$managed_sha" ]]; then
        error "AGENTS.md changed after installation. It was preserved; reconcile it before uninstalling."
        return 1
    fi
    if [[ $DRY_RUN -eq 1 ]]; then
        log "would remove managed $TARGET_AGENTS"
        if [[ "$backup_path" != "-" ]]; then log "would restore $backup_path"; fi
        return
    fi
    rm "$TARGET_AGENTS"
    if [[ "$backup_path" != "-" && -e "$backup_path" ]]; then
        mv "$backup_path" "$TARGET_AGENTS"
        log "restored previous global instructions: $TARGET_AGENTS"
    else
        log "removed managed global instructions: $TARGET_AGENTS"
    fi
    rm "$AGENTS_STATE"
}

uninstall_adapter() {
    manage_requirements uninstall
    uninstall_agents
    remove_owned_link "${ADAPTER_ROOT}/skills/mainframe-init" "${GLOBAL_SKILLS_DIR}/mainframe-init" "manual init skill"
    remove_owned_link "${ADAPTER_ROOT}/skills/mainframe-secrets" "${GLOBAL_SKILLS_DIR}/mainframe-secrets" "secrets skill"
    uninstall_index
    uninstall_rules
    if [[ $DRY_RUN -eq 1 ]]; then
        manage_config uninstall --dry-run
    else
        manage_config uninstall
    fi
    log "Credentials, the repository index, and unrelated Codex configuration were preserved."
}

main() {
    parse_args "$@"
    preflight
    if [[ $PREFLIGHT -eq 1 ]]; then
        log "Codex adapter preflight passed."
        return
    fi
    if [[ $UNINSTALL -eq 1 ]]; then
        uninstall_adapter
    else
        install_adapter
    fi
}

main "$@"
