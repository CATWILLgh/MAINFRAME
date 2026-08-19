#!/usr/bin/env bash

set -euo pipefail

ADAPTER_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${ADAPTER_ROOT}/../.." && pwd)"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)-$$"
CODEX_DIR="${CODEX_HOME:-$HOME/.codex}"
GLOBAL_SKILLS_DIR="$HOME/.agents/skills"
SKILL_NAMES=(
    mainframe-init
    mainframe-pi-business-analysis
    mainframe-pi-engineer
    mainframe-secrets
    mainframe-ticket
    mainframe-tickets-find
    mainframe-tickets-refine
    mainframe-tickets-implement
    mainframe-tickets-verify
    mainframe-python-backend
    mainframe-typescript-backend
    mainframe-frontend
    mainframe-testing-strategy
    mainframe-infrastructure
    mainframe-curl-requests
    mainframe-ops-app-server-safety
)
PRIVATE_SKILL_NAMES=(
    mainframe-research-method
    mainframe-decision-review
    mainframe-readiness-review
)
PRIVATE_SKILLS_DIR="${CODEX_HOME:-$HOME/.codex}/mainframe/private-skills"
TEMPLATED_AGENT_NAMES=(
    mainframe_researcher
    mainframe_python_backend_engineer
    mainframe_typescript_backend_engineer
    mainframe_react_frontend_engineer
    mainframe_test_auditor
    mainframe_decision_reviewer
    mainframe_advisor
)
SOURCE_AGENTS="${ADAPTER_ROOT}/export/AGENTS.md"
TARGET_AGENTS="${CODEX_DIR}/AGENTS.md"
AGENTS_STATE="${CODEX_DIR}/.mainframe-agents-state"
INDEX_SOURCE="${REPO_ROOT}/shared/credentials/credentials-index.md"
INDEX_TARGET="${CODEX_DIR}/credentials-index.md"
INDEX_STATE="${CODEX_DIR}/.mainframe-index-state"
RULES_SOURCE="${ADAPTER_ROOT}/rules/mainframe.rules"
RULES_TARGET="${CODEX_DIR}/rules/mainframe.rules"
RULES_STATE="${CODEX_DIR}/.mainframe-rules-state"
CONFIG_TOOL="${ADAPTER_ROOT}/scripts/manage-config.py"
CONFIG_TARGET="${CODEX_DIR}/config.toml"
CONFIG_STATE="${CODEX_DIR}/.mainframe-config-state.json"
CONFIG_BACKUP="${CONFIG_TARGET}.backup-${TIMESTAMP}"
HOOKS_SOURCE="${ADAPTER_ROOT}/hooks/hooks.json"
HOOKS_SCRIPT="${ADAPTER_ROOT}/hooks/scripts/mainframe-hook.py"
HOOKS_TOOL="${ADAPTER_ROOT}/scripts/manage-hooks.py"
HOOKS_TARGET="${CODEX_DIR}/hooks.json"
HOOKS_STATE="${CODEX_DIR}/.mainframe-hooks-state.json"
CODEX_DESKTOP_RUNTIME="${MAINFRAME_CODEX_DESKTOP_RUNTIME:-/Applications/ChatGPT.app/Contents/Resources/codex}"
TELEMETRY_SCRIPT="${ADAPTER_ROOT}/hooks/scripts/telemetry.py"
TELEMETRY_CONTRACT="${ADAPTER_ROOT}/hooks/scripts/_telemetry_contract.py"
TELEMETRY_DIR="${CODEX_DIR}/mainframe/codex/telemetry"
TELEMETRY_DB="${TELEMETRY_DIR}/telemetry.db"
TELEMETRY_MARKER="${TELEMETRY_DIR}/enabled"
DEV_FEEDBACK_SOURCE="${ADAPTER_ROOT}/dev/skills/harness-feedback"
DEV_FEEDBACK_TARGET="${GLOBAL_SKILLS_DIR}/harness-feedback"
OPENCODE_LAUNCHER_SOURCE="${ADAPTER_ROOT}/bin/mainframe-opencode"
OPENCODE_LAUNCHER_TARGET="$HOME/.local/bin/mainframe-opencode"
PEER_ADVISOR_SOURCE="${ADAPTER_ROOT}/optional/skills/mainframe-peer-review"
PEER_ADVISOR_TARGET="${GLOBAL_SKILLS_DIR}/mainframe-peer-review"
MANAGED_DELIVERY="${REPO_ROOT}/shared/managed-delivery/manage-artifact.py"
MANAGED_STATE_DIR="${CODEX_DIR}/.mainframe-managed-artifacts"
MANAGED_BACKUP_ROOT="${CODEX_DIR}/.mainframe-backups/${TIMESTAMP}"

DRY_RUN=0
ASSUME_YES=0
UNINSTALL=0
PREFLIGHT=0
DEV_MODE=0
REPLACE_MODIFIED=0
WITH_PEER_ADVISOR=0

usage() {
    cat <<'EOF'
MAINFRAME Codex adapter installer

Usage:
  install.sh [--dry-run] [--dev] [--with-peer-advisor] [--yes] [--replace-modified] [--uninstall]
  install.sh --preflight [--dry-run] [--yes] [--replace-modified]

The baseline is delivered directly so Desktop, CLI, and the IDE extension can
share AGENTS.md, standalone skills, command rules, native specialist agents,
and reviewed native hooks. Permission selection remains entirely user-owned.
--dev additionally enables
the adapter-owned local telemetry sink and harness-feedback receiver; normal
installation keeps both inactive.
--with-peer-advisor verifies an authenticated Claude Code CLI and installs the
optional Claude review skill. Reinstalling without it removes only that managed
optional skill.

Adapter artifacts are managed regular copies. Local changes block update or
uninstall unless confirmed interactively or with --replace-modified; changed
content is backed up before replacement.
EOF
}

log() { printf '%s\n' "$1"; }
error() { printf 'Error: %s\n' "$1" >&2; }

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --dry-run) DRY_RUN=1 ;;
            --yes) ASSUME_YES=1 ;;
            --replace-modified) REPLACE_MODIFIED=1 ;;
            --with-peer-advisor) WITH_PEER_ADVISOR=1 ;;
            --uninstall) UNINSTALL=1 ;;
            --preflight) PREFLIGHT=1 ;;
            -h|--help) usage; exit 0 ;;
            --dev) DEV_MODE=1 ;;
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

managed_delivery() {
    local action="$1" source="$2" target="$3" state_id="$4"
    local legacy_backup="${5:-}" legacy_digest="${6:-}" legacy_link_source="${7:-}"
    local args=(
        "$action"
        --source "$source"
        --target "$target"
        --state "${MANAGED_STATE_DIR}/${state_id}.json"
        --backup-root "$MANAGED_BACKUP_ROOT"
    )
    if [[ $DRY_RUN -eq 1 && "$action" != check-* ]]; then args+=(--dry-run); fi
    if [[ $REPLACE_MODIFIED -eq 1 ]]; then args+=(--replace-modified); fi
    if [[ -t 0 && -t 1 ]]; then args+=(--interactive); fi
    if [[ -n "$legacy_backup" && "$legacy_backup" != "-" ]]; then
        args+=(--legacy-backup "$legacy_backup")
    fi
    if [[ -n "$legacy_digest" ]]; then args+=(--legacy-managed-digest "$legacy_digest"); fi
    if [[ -n "$legacy_link_source" ]]; then args+=(--legacy-link-source "$legacy_link_source"); fi
    python3 "$MANAGED_DELIVERY" "${args[@]}"
}

install_managed() { managed_delivery install "$@"; }
uninstall_managed() { managed_delivery uninstall "$@"; }
check_managed() {
    local action="$1"
    shift
    managed_delivery "check-${action}" "$@" >/dev/null
}

managed_state_is_current() {
    local state_id="$1" name
    case "$state_id" in
        global-agents|rules|opencode-launcher|peer-advisor|dev-harness-feedback) return 0 ;;
    esac
    for name in "${SKILL_NAMES[@]}"; do
        [[ "$state_id" == "skill-${name}" ]] && return 0
    done
    for name in "${PRIVATE_SKILL_NAMES[@]}"; do
        [[ "$state_id" == "private-skill-${name}" ]] && return 0
    done
    for name in "${TEMPLATED_AGENT_NAMES[@]}"; do
        [[ "$state_id" == "agent-${name}" ]] && return 0
    done
    return 1
}

process_stale_managed_states() {
    local action="$1" state_file state_id source target
    [[ -d "$MANAGED_STATE_DIR" ]] || return 0
    for state_file in "$MANAGED_STATE_DIR"/*.json; do
        [[ -f "$state_file" ]] || continue
        state_id="$(basename "$state_file" .json)"
        managed_state_is_current "$state_id" && continue
        IFS=$'\t' read -r source target < <(
            python3 -c 'import json,sys; value=json.load(open(sys.argv[1])); print(value["source"]+"\t"+value["target"])' "$state_file"
        )
        managed_delivery "$action" "$source" "$target" "$state_id"
    done
}

agent_target() { printf '%s/agents/%s.toml\n' "$CODEX_DIR" "$1"; }
agent_state() { printf '%s/.mainframe-agent-%s-state\n' "$CODEX_DIR" "$1"; }
templated_agent_source() { printf '%s/agents/%s.toml.template\n' "$ADAPTER_ROOT" "$1"; }
legacy_agent_source() { printf '%s/agents/%s.toml\n' "$ADAPTER_ROOT" "$1"; }

state_value() {
    local key="$1"
    [[ -f "$AGENTS_STATE" ]] || return 1
    sed -n "s/^${key}=//p" "$AGENTS_STATE" | head -n 1
}

run_runtime() {
    local runtime="$1" probe result=0
    shift
    if [[ -d "$CODEX_DIR" ]]; then
        "$runtime" "$@"
        return
    fi
    probe="$(mktemp -d "${TMPDIR:-/tmp}/mainframe-codex-preflight.XXXXXX")"
    if CODEX_HOME="$probe" "$runtime" "$@"; then
        result=0
    else
        result=$?
    fi
    rmdir "$probe" 2>/dev/null || true
    return "$result"
}

runtime_preflight() {
    local found=0 features
    if command -v codex >/dev/null 2>&1; then
        log "Codex CLI: $(run_runtime codex --version 2>/dev/null || printf 'detected')"
        features="$(run_runtime codex features list 2>/dev/null)"
        if ! grep -E '^hooks[[:space:]]+stable[[:space:]]+true$' <<<"$features" >/dev/null; then
            error "The installed Codex CLI does not expose stable native hooks. Update Codex before installation."
            return 1
        fi
        found=1
    fi
    if [[ -x "$CODEX_DESKTOP_RUNTIME" ]]; then
        log "Codex Desktop runtime: $(run_runtime "$CODEX_DESKTOP_RUNTIME" --version 2>/dev/null || printf 'detected')"
        features="$(run_runtime "$CODEX_DESKTOP_RUNTIME" features list 2>/dev/null)"
        if ! grep -E '^hooks[[:space:]]+stable[[:space:]]+true$' <<<"$features" >/dev/null; then
            error "The installed Codex Desktop runtime does not expose stable native hooks. Update the app before installation."
            return 1
        fi
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
    local name target source state managed_sha current_sha
    for name in "${SKILL_NAMES[@]}"; do
        source="${ADAPTER_ROOT}/skills/${name}"
        target="${GLOBAL_SKILLS_DIR}/$(basename "$source")"
        check_managed install "$source" "$target" "skill-${name}"
    done
    for name in "${PRIVATE_SKILL_NAMES[@]}"; do
        check_managed install "${ADAPTER_ROOT}/skills/${name}" \
            "${PRIVATE_SKILLS_DIR}/${name}" "private-skill-${name}"
    done
    if [[ $DEV_MODE -eq 1 ]]; then
        check_managed install "$DEV_FEEDBACK_SOURCE" "$DEV_FEEDBACK_TARGET" "dev-harness-feedback"
    else
        check_managed uninstall "$DEV_FEEDBACK_SOURCE" "$DEV_FEEDBACK_TARGET" "dev-harness-feedback"
    fi
    if [[ $WITH_PEER_ADVISOR -eq 1 ]]; then
        check_managed install "$PEER_ADVISOR_SOURCE" "$PEER_ADVISOR_TARGET" "peer-advisor"
    else
        check_managed uninstall "$PEER_ADVISOR_SOURCE" "$PEER_ADVISOR_TARGET" "peer-advisor"
    fi
    check_managed install "$OPENCODE_LAUNCHER_SOURCE" "$OPENCODE_LAUNCHER_TARGET" "opencode-launcher"
    if link_conflicts "$INDEX_TARGET" "$INDEX_SOURCE" && [[ $ASSUME_YES -ne 1 ]]; then
        error "A Codex credentials index already exists. Rerun with --yes to back it up before linking the repository index."
        return 1
    fi
    check_managed install "$RULES_SOURCE" "$RULES_TARGET" "rules" "$(rules_state_value || printf '-')"
    for name in "${TEMPLATED_AGENT_NAMES[@]}"; do
        local rendered legacy_backup legacy_digest legacy_link=""
        rendered="$(mktemp "${TMPDIR:-/tmp}/mainframe-codex-agent-check.XXXXXX")"
        render_templated_agent "$name" "$rendered"
        state="$(agent_state "$name")"
        legacy_backup="$(agent_state_field "$state" backup_path || printf '-')"
        legacy_digest="$(agent_state_field "$state" managed_sha || true)"
        [[ -f "$state" ]] && legacy_link="$(legacy_agent_source "$name")"
        if ! check_managed install "$rendered" "$(agent_target "$name")" "agent-${name}" \
            "$legacy_backup" "$legacy_digest" "$legacy_link"; then
            rm -f "$rendered"
            return 1
        fi
        rm "$rendered"
    done

    check_managed install "$SOURCE_AGENTS" "$TARGET_AGENTS" "global-agents" \
        "$(state_value backup_path || printf '-')" "$(state_value managed_sha || true)"
    process_stale_managed_states check-uninstall >/dev/null
}

check_sources() {
    local name path
    for path in "$SOURCE_AGENTS" \
        "${ADAPTER_ROOT}/skills/mainframe-init/SKILL.md" \
        "${ADAPTER_ROOT}/skills/mainframe-init/references/ticket-decision.md" \
        "${ADAPTER_ROOT}/skills/mainframe-secrets/SKILL.md" \
        "${ADAPTER_ROOT}/skills/mainframe-ticket/SKILL.md" \
        "${ADAPTER_ROOT}/skills/mainframe-ticket/agents/openai.yaml" \
        "${ADAPTER_ROOT}/skills/mainframe-ticket/references/record-observation.md" \
        "${ADAPTER_ROOT}/skills/mainframe-ticket/references/record-confirmed-problem.md" \
        "${ADAPTER_ROOT}/skills/mainframe-ticket/references/ticket-format.md" \
        "$RULES_SOURCE" \
        "$CONFIG_TOOL" \
        "$HOOKS_SOURCE" \
        "$HOOKS_SCRIPT" \
        "$TELEMETRY_SCRIPT" \
        "$TELEMETRY_CONTRACT" \
        "$DEV_FEEDBACK_SOURCE/SKILL.md" \
        "$DEV_FEEDBACK_SOURCE/feedback.py" \
        "$DEV_FEEDBACK_SOURCE/agents/openai.yaml" \
        "${REPO_ROOT}/dev/harness-feedback/receiver.py" \
        "$OPENCODE_LAUNCHER_SOURCE" \
        "$PEER_ADVISOR_SOURCE/SKILL.md" \
        "$PEER_ADVISOR_SOURCE/agents/openai.yaml" \
        "$MANAGED_DELIVERY" \
        "$HOOKS_TOOL"; do
        if [[ ! -f "$path" ]]; then
            error "Codex adapter source is missing: $path"
            return 1
        fi
    done
    for name in "${SKILL_NAMES[@]}"; do
        for path in \
            "${ADAPTER_ROOT}/skills/${name}/SKILL.md" \
            "${ADAPTER_ROOT}/skills/${name}/agents/openai.yaml"; do
            if [[ ! -f "$path" ]]; then
                error "Codex adapter skill source is missing: $path"
                return 1
            fi
        done
    done
    for name in "${TEMPLATED_AGENT_NAMES[@]}"; do
        path="$(templated_agent_source "$name")"
        if [[ ! -f "$path" ]]; then
            error "Codex adapter agent template is missing: $path"
            return 1
        fi
    done
    for name in "${PRIVATE_SKILL_NAMES[@]}"; do
        path="${ADAPTER_ROOT}/skills/${name}/SKILL.md"
        if [[ ! -f "$path" ]]; then
            error "Codex adapter private skill source is missing: $path"
            return 1
        fi
    done
}

check_peer_advisor() {
    [[ $WITH_PEER_ADVISOR -eq 1 ]] || return 0
    if ! command -v claude >/dev/null 2>&1; then
        error "--with-peer-advisor requires the Claude Code CLI on PATH; no Codex adapter files were changed."
        return 1
    fi
    if ! claude auth status >/dev/null 2>&1; then
        error "--with-peer-advisor requires an authenticated Claude Code CLI; run 'claude auth login' and retry."
        return 1
    fi
}

manage_config() {
    local action="$1"
    shift
    local args=("$action" \
        --config "$CONFIG_TARGET" \
        --state "$CONFIG_STATE" \
        --backup "$CONFIG_BACKUP")
    if [[ "$action" == "install" && $DEV_MODE -eq 1 ]]; then
        args+=(--dev-telemetry-endpoint "http://127.0.0.1:4318/v1/logs")
    fi
    args+=("$@")
    python3 "$CONFIG_TOOL" "${args[@]}"
}

manage_hooks() {
    local action="$1"
    shift
    python3 "$HOOKS_TOOL" "$action" \
        --target "$HOOKS_TARGET" \
        --source "$HOOKS_SOURCE" \
        --script "$HOOKS_SCRIPT" \
        --state "$HOOKS_STATE" \
        "$@"
}

validate_rules() {
    local runtime=""
    if command -v codex >/dev/null 2>&1; then
        runtime="$(command -v codex)"
    elif [[ -x "$CODEX_DESKTOP_RUNTIME" ]]; then
        runtime="$CODEX_DESKTOP_RUNTIME"
    fi
    if [[ -n "$runtime" ]]; then
        if ! run_runtime "$runtime" execpolicy check --rules "$RULES_SOURCE" -- git push >/dev/null 2>&1; then
            error "Codex rejected the MAINFRAME rules file; no adapter files were changed."
            return 1
        fi
    fi
}

preflight() {
    local name source target state managed_sha current_sha
    require_python
    if [[ $UNINSTALL -eq 1 ]]; then
        check_managed uninstall "$SOURCE_AGENTS" "$TARGET_AGENTS" "global-agents" \
            "$(state_value backup_path || printf '-')" "$(state_value managed_sha || true)"
        if [[ -f "$INDEX_STATE" ]] && { [[ ! -L "$INDEX_TARGET" ]] || [[ "$(resolve_link "$INDEX_TARGET")" != "$INDEX_SOURCE" ]]; }; then
            error "The Codex credentials index changed after installation. It was preserved."
            return 1
        fi
        for name in "${SKILL_NAMES[@]}"; do
            check_managed uninstall "${ADAPTER_ROOT}/skills/${name}" \
                "${GLOBAL_SKILLS_DIR}/${name}" "skill-${name}"
        done
        for name in "${PRIVATE_SKILL_NAMES[@]}"; do
            check_managed uninstall "${ADAPTER_ROOT}/skills/${name}" \
                "${PRIVATE_SKILLS_DIR}/${name}" "private-skill-${name}"
        done
        check_managed uninstall "$DEV_FEEDBACK_SOURCE" "$DEV_FEEDBACK_TARGET" "dev-harness-feedback"
        check_managed uninstall "$PEER_ADVISOR_SOURCE" "$PEER_ADVISOR_TARGET" "peer-advisor"
        check_managed uninstall "$OPENCODE_LAUNCHER_SOURCE" "$OPENCODE_LAUNCHER_TARGET" "opencode-launcher"
        check_managed uninstall "$RULES_SOURCE" "$RULES_TARGET" "rules" "$(rules_state_value || printf '-')"
        for name in "${TEMPLATED_AGENT_NAMES[@]}"; do
            state="$(agent_state "$name")"
            local legacy_link=""
            [[ -f "$state" ]] && legacy_link="$(legacy_agent_source "$name")"
            check_managed uninstall "$(templated_agent_source "$name")" "$(agent_target "$name")" \
                "agent-${name}" "$(agent_state_field "$state" backup_path || printf '-')" \
                "$(agent_state_field "$state" managed_sha || true)" "$legacy_link"
        done
        manage_config uninstall --dry-run >/dev/null
        manage_hooks uninstall --dry-run >/dev/null
        process_stale_managed_states check-uninstall >/dev/null
    else
        check_sources
        runtime_preflight
        check_peer_advisor
        validate_rules
        delivery_preflight
        manage_config install --dry-run >/dev/null
        manage_hooks install --dry-run >/dev/null
    fi
}

install_agents() {
    install_managed "$SOURCE_AGENTS" "$TARGET_AGENTS" "global-agents" \
        "$(state_value backup_path || printf '-')" "$(state_value managed_sha || true)"
    if [[ $DRY_RUN -eq 0 ]]; then chmod 600 "$TARGET_AGENTS"; fi
    if [[ $DRY_RUN -eq 0 && -f "$AGENTS_STATE" ]]; then rm "$AGENTS_STATE"; fi
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

agent_state_field() {
    local state="$1" key="$2"
    [[ -f "$state" ]] || return 1
    sed -n "s/^${key}=//p" "$state" | head -n 1
}

render_templated_agent() {
    local name="$1" destination="$2"
    local source
    source="$(templated_agent_source "$name")"
    python3 -c '
from pathlib import Path
import re
import sys

source, destination, adapter_root, global_skills, private_skills = map(Path, sys.argv[1:6])
replacements = {
    "__MAINFRAME_RESEARCH_METHOD_SKILL__": private_skills / "mainframe-research-method" / "SKILL.md",
    "__MAINFRAME_DECISION_REVIEW_SKILL__": private_skills / "mainframe-decision-review" / "SKILL.md",
    "__MAINFRAME_READINESS_REVIEW_SKILL__": private_skills / "mainframe-readiness-review" / "SKILL.md",
    "__MAINFRAME_PYTHON_BACKEND_SKILL__": global_skills / "mainframe-python-backend" / "SKILL.md",
    "__MAINFRAME_TYPESCRIPT_BACKEND_SKILL__": global_skills / "mainframe-typescript-backend" / "SKILL.md",
    "__MAINFRAME_FRONTEND_SKILL__": global_skills / "mainframe-frontend" / "SKILL.md",
    "__MAINFRAME_TESTING_STRATEGY_SKILL__": global_skills / "mainframe-testing-strategy" / "SKILL.md",
    "__MAINFRAME_TICKET_SKILL__": global_skills / "mainframe-ticket" / "SKILL.md",
}
body = source.read_text(encoding="utf-8")
markers = set(re.findall(r"__MAINFRAME_[A-Z_]+_SKILL__", body))
if not markers:
    raise SystemExit(f"no skill marker found in {source}")
unknown = markers - replacements.keys()
if unknown:
    raise SystemExit(f"unknown skill markers in {source}: {sorted(unknown)}")
for marker in markers:
    if body.count(marker) != 1:
        raise SystemExit(f"expected exactly one {marker} marker in {source}")
    body = body.replace(marker, str(replacements[marker].absolute()))
destination.write_text(body, encoding="utf-8")
' "$source" "$destination" "$ADAPTER_ROOT" "$GLOBAL_SKILLS_DIR" "$PRIVATE_SKILLS_DIR"
}

install_templated_agent() {
    local name="$1" target state backup_path managed_sha rendered legacy_link=""
    target="$(agent_target "$name")"
    state="$(agent_state "$name")"
    rendered="$(mktemp "${TMPDIR:-/tmp}/mainframe-codex-agent.XXXXXX")"
    render_templated_agent "$name" "$rendered"
    backup_path="$(agent_state_field "$state" backup_path || printf '-')"
    managed_sha="$(agent_state_field "$state" managed_sha || true)"
    [[ -f "$state" ]] && legacy_link="$(legacy_agent_source "$name")"
    if ! install_managed "$rendered" "$target" "agent-${name}" "$backup_path" "$managed_sha" \
        "$legacy_link"; then
        rm -f "$rendered"
        return 1
    fi
    rm "$rendered"
    if [[ $DRY_RUN -eq 0 ]]; then chmod 600 "$target"; fi
    if [[ $DRY_RUN -eq 0 && -f "$state" ]]; then rm "$state"; fi
}

install_rules() {
    install_managed "$RULES_SOURCE" "$RULES_TARGET" "rules" "$(rules_state_value || printf '-')"
    if [[ $DRY_RUN -eq 0 && -f "$RULES_STATE" ]]; then rm "$RULES_STATE"; fi
}

install_config() {
    if [[ $DRY_RUN -eq 1 ]]; then
        manage_config install --dry-run
    else
        manage_config install
    fi
}

install_hooks() {
    if [[ $DRY_RUN -eq 1 ]]; then
        manage_hooks install --dry-run
    else
        manage_hooks install
    fi
}

configure_dev_telemetry() {
    if [[ $DEV_MODE -eq 1 ]]; then
        if [[ $DRY_RUN -eq 1 ]]; then
            log "would initialize Codex development telemetry: $TELEMETRY_DB"
            log "would install the mainframe-observatory command without starting its server"
            return
        fi
        python3 -B "$TELEMETRY_SCRIPT" --initialize "$TELEMETRY_DB"
        : > "$TELEMETRY_MARKER"
        chmod 600 "$TELEMETRY_DB" "$TELEMETRY_MARKER"
        log "enabled Codex development telemetry: $TELEMETRY_DB"
        if [[ "${MAINFRAME_INSTALL_TESTING:-0}" != "1" ]]; then
            if "${REPO_ROOT}/tools/mainframe-observatory.sh" enable codex; then
                log "installed the MAINFRAME Observatory command; run mainframe-observatory start when needed"
            else
                log "could not install the MAINFRAME Observatory command; hook telemetry remains available"
            fi
        fi
        if [[ -x "${REPO_ROOT}/.venv/bin/python3" ]]; then
            if "${REPO_ROOT}/.venv/bin/python3" \
                    "${REPO_ROOT}/tools/build_hub_page.py" \
                    --root "$REPO_ROOT" \
                    --codex-db "$TELEMETRY_DB" >/dev/null 2>&1; then
                log "generated local hub page: ${REPO_ROOT}/workspace/runtime/hub.html"
            else
                log "Codex telemetry is active; hub page generation was skipped after a non-critical build failure."
            fi
        else
            log "Codex telemetry is active; hub page generation requires the repository .venv."
        fi
    else
        if [[ -f "$TELEMETRY_MARKER" ]]; then
            if [[ $DRY_RUN -eq 1 ]]; then
                log "would disable Codex development telemetry and preserve its database"
            else
                rm "$TELEMETRY_MARKER"
                log "disabled Codex development telemetry; preserved $TELEMETRY_DB"
            fi
        fi
        if [[ $DRY_RUN -eq 1 ]]; then
            log "would disable the Codex observatory input"
        elif [[ "${MAINFRAME_INSTALL_TESTING:-0}" != "1" ]]; then
            "${REPO_ROOT}/tools/mainframe-observatory.sh" disable codex || \
                log "could not disable the Codex observatory input"
        fi
    fi
}

configure_dev_feedback() {
    if [[ $DEV_MODE -eq 1 ]]; then
        install_managed "$DEV_FEEDBACK_SOURCE" "$DEV_FEEDBACK_TARGET" "dev-harness-feedback"
    else
        uninstall_managed "$DEV_FEEDBACK_SOURCE" "$DEV_FEEDBACK_TARGET" "dev-harness-feedback"
    fi
}

configure_peer_advisor() {
    if [[ $WITH_PEER_ADVISOR -eq 1 ]]; then
        install_managed "$PEER_ADVISOR_SOURCE" "$PEER_ADVISOR_TARGET" "peer-advisor"
    else
        uninstall_managed "$PEER_ADVISOR_SOURCE" "$PEER_ADVISOR_TARGET" "peer-advisor"
    fi
}

install_adapter() {
    local name
    install_agents
    for name in "${SKILL_NAMES[@]}"; do
        install_managed "${ADAPTER_ROOT}/skills/${name}" "${GLOBAL_SKILLS_DIR}/${name}" "skill-${name}"
    done
    for name in "${PRIVATE_SKILL_NAMES[@]}"; do
        install_managed "${ADAPTER_ROOT}/skills/${name}" "${PRIVATE_SKILLS_DIR}/${name}" "private-skill-${name}"
    done
    install_managed "$OPENCODE_LAUNCHER_SOURCE" "$OPENCODE_LAUNCHER_TARGET" "opencode-launcher"
    install_index
    install_rules
    for name in "${TEMPLATED_AGENT_NAMES[@]}"; do install_templated_agent "$name"; done
    install_config
    install_hooks
    configure_dev_feedback
    configure_peer_advisor
    process_stale_managed_states uninstall
    configure_dev_telemetry
    if [[ $DRY_RUN -eq 1 ]]; then
        log "Codex baseline plan verified; no files were changed."
    else
        log "Codex baseline installed. Review new or changed hook definitions with /hooks, then start a new task before relying on updated instructions, skills, agents, or hooks."
    fi
}

uninstall_rules() {
    uninstall_managed "$RULES_SOURCE" "$RULES_TARGET" "rules" "$(rules_state_value || printf '-')"
    if [[ $DRY_RUN -eq 0 && -f "$RULES_STATE" ]]; then rm "$RULES_STATE"; fi
}

uninstall_templated_agent() {
    local name="$1" target state backup_path managed_sha legacy_link=""
    target="$(agent_target "$name")"
    state="$(agent_state "$name")"
    backup_path="$(agent_state_field "$state" backup_path || printf '-')"
    managed_sha="$(agent_state_field "$state" managed_sha || true)"
    [[ -f "$state" ]] && legacy_link="$(legacy_agent_source "$name")"
    uninstall_managed "$(templated_agent_source "$name")" "$target" "agent-${name}" \
        "$backup_path" "$managed_sha" "$legacy_link"
    if [[ $DRY_RUN -eq 0 && -f "$state" ]]; then rm "$state"; fi
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
    uninstall_managed "$SOURCE_AGENTS" "$TARGET_AGENTS" "global-agents" \
        "$(state_value backup_path || printf '-')" "$(state_value managed_sha || true)"
    if [[ $DRY_RUN -eq 0 && -f "$AGENTS_STATE" ]]; then rm "$AGENTS_STATE"; fi
}

uninstall_adapter() {
    local name
    if [[ $DRY_RUN -eq 1 ]]; then
        manage_hooks uninstall --dry-run
    else
        manage_hooks uninstall
    fi
    if [[ -f "$TELEMETRY_MARKER" ]]; then
        if [[ $DRY_RUN -eq 1 ]]; then
            log "would disable Codex development telemetry and preserve its database"
        else
            rm "$TELEMETRY_MARKER"
            log "disabled Codex development telemetry; preserved $TELEMETRY_DB"
        fi
    fi
    if [[ $DRY_RUN -eq 1 ]]; then
        log "would disable the Codex observatory input"
    elif [[ "${MAINFRAME_INSTALL_TESTING:-0}" != "1" ]]; then
        "${REPO_ROOT}/tools/mainframe-observatory.sh" disable codex || \
            log "could not disable the Codex observatory input"
    fi
    uninstall_agents
    uninstall_managed "$DEV_FEEDBACK_SOURCE" "$DEV_FEEDBACK_TARGET" "dev-harness-feedback"
    uninstall_managed "$PEER_ADVISOR_SOURCE" "$PEER_ADVISOR_TARGET" "peer-advisor"
    uninstall_managed "$OPENCODE_LAUNCHER_SOURCE" "$OPENCODE_LAUNCHER_TARGET" "opencode-launcher"
    for name in "${SKILL_NAMES[@]}"; do
        uninstall_managed "${ADAPTER_ROOT}/skills/${name}" "${GLOBAL_SKILLS_DIR}/${name}" "skill-${name}"
    done
    for name in "${PRIVATE_SKILL_NAMES[@]}"; do
        uninstall_managed "${ADAPTER_ROOT}/skills/${name}" "${PRIVATE_SKILLS_DIR}/${name}" "private-skill-${name}"
    done
    process_stale_managed_states uninstall
    uninstall_index
    uninstall_rules
    for name in "${TEMPLATED_AGENT_NAMES[@]}"; do uninstall_templated_agent "$name"; done
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
