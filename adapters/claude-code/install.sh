#!/usr/bin/env bash
#
# MAINFRAME Claude Code adapter installer.
# Safe by default: backs up mutable settings before merging and existing
# immutable targets before linking.
#
# Delivered:
#   - plugin:       plugin/  →  ~/.claude/skills/mainframe/
#                   Claude Code auto-loads it as the 'mainframe' plugin via
#                   the skills-dir mechanism. Skills, commands, and hooks
#                   inside get the `mainframe:` namespace prefix.
#   - agents:       agents/  →  ~/.claude/agents/mainframe/
#                   User-level agents retain agent-scoped hooks and MCP
#                   servers, which Claude Code ignores for plugin agents.
#   - umbrella:     export/CLAUDE.md  →  ~/.claude/CLAUDE.md
#                   export/settings.json is safely merged into the mutable
#                   ~/.claude/settings.json with local ownership state.
#   - credentials:  shared/credentials/credentials-index.md
#                   → ~/.claude/credentials-index.md
#                   Stable adapter-facing link; the repository file remains
#                   the only editable catalog.
#   - rules:        export/rules/* item-by-item  →  ~/.claude/rules/
#                   (Plugin format does not support path-scoped rules with
#                   `paths:` frontmatter; per-item keeps the layer composable.)
#
# Migration cleanup removes stale per-item symlinks left by older layouts.
#
# Usage:
#   ./install.sh              # install (with safe merge and backups)
#   ./install.sh --dry-run    # show what would happen, no changes
#   ./install.sh --yes        # approve a required Claude Code update
#   ./install.sh --uninstall  # remove owned settings and symlinks
#   ./install.sh --help
#
# Idempotent: re-running with the same state does nothing.

set -euo pipefail

# ---- Colors and logging ----

if [[ -t 1 ]]; then
    RED=$'\033[0;31m'
    GREEN=$'\033[0;32m'
    YELLOW=$'\033[1;33m'
    BLUE=$'\033[0;34m'
    BOLD=$'\033[1m'
    NC=$'\033[0m'
else
    RED='' GREEN='' YELLOW='' BLUE='' BOLD='' NC=''
fi

log_info()    { echo "${BLUE}[i]${NC} $1"; }
log_ok()      { echo "${GREEN}[ok]${NC} $1"; }
log_warn()    { echo "${YELLOW}[!]${NC} $1"; }
log_error()   { echo "${RED}[x]${NC} $1" >&2; }
log_action()  { echo "${BOLD}→${NC} $1"; }

# ---- Parameters ----

DRY_RUN=0
UNINSTALL=0
DEV=0
ASSUME_YES=0
PREFLIGHT_ONLY=0

usage() {
    cat <<EOF
MAINFRAME Claude Code adapter installer

Installs the shared hub runtime as a Claude Code plugin: a single symlink in
~/.claude/skills/ points to this adapter's plugin/ directory, which Claude
Code auto-loads as the 'mainframe' plugin. Skills, commands, and hooks inside
the plugin become available with the 'mainframe:' namespace prefix.

Specialist profiles are installed separately at ~/.claude/agents/mainframe/ as
user-level agents named mainframe-*. This preserves agent-scoped hooks and MCP
servers, which Claude Code intentionally ignores on plugin-shipped agents.

The umbrella CLAUDE.md stays a direct symlink because Claude Code does not edit
it. User settings are different: Claude Code writes /model, /effort, and
/config choices to ~/.claude/settings.json, so MAINFRAME merges its policy and
initial defaults into a regular local file instead of linking repository source.
Path-scoped rules in export/rules/ install per-item.

The first install after upgrading from the pre-plugin layout also cleans up
stale per-item symlinks in ~/.claude/{skills,agents,hooks}/ left over from
the old layout, and removes the empty directories if any.

Usage:
  $0                  Install (links immutable artifacts, safely merges user
                      settings, and backs up changed existing files).
  $0 --dev            Install PLUS the hub-development instrumentation:
                      the 'harness-feedback' skill and the hub data
                      namespace ~/.claude/mainframe -> workspace/runtime/
                      in this repo (gitignored), holding friction reports
                      (feedback/) and Claude-specific local usage telemetry
                      (claude-code/telemetry/ — a local SQLite DB; nothing
                      leaves the machine).
                      Ordinary users do not need this.
  $0 --dry-run        Show what would happen, no changes.
  $0 --yes            Approve a required Claude Code update without prompting.
  $0 --uninstall      Remove MAINFRAME-owned settings and symlinks (incl.
                      --dev ones; telemetry/feedback data is left in place).
  $0 --help           Show this message.

Idempotent: re-running is safe — correct links and merged settings stay intact.

Backups (if any) live at:
  ~/.claude/<file>.backup-YYYYMMDD-HHMMSS-PID

EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)   DRY_RUN=1 ;;
        --dev)       DEV=1 ;;
        --yes)       ASSUME_YES=1 ;;
        --preflight) PREFLIGHT_ONLY=1 ;;
        --uninstall) UNINSTALL=1 ;;
        -h|--help)   usage; exit 0 ;;
        *) log_error "Unknown argument: $1"; usage; exit 2 ;;
    esac
    shift
done

# ---- Configuration ----

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ADAPTER_ROOT="${PROJECT_ROOT}/adapters/claude-code"
CLAUDE_DIR="$HOME/.claude"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)-$$"
MIN_CLAUDE_VERSION="2.1.226"

# Single-file (and single-dir) artifacts. Format: "<source-relative-to-project>:<target-absolute>"
# Layout:
#   - plugin/ is symlinked as a single directory under ~/.claude/skills/mainframe/.
#     Claude Code auto-loads it as the 'mainframe' plugin via the skills-dir mechanism,
#     and skills/commands/hooks inside get the `mainframe:` namespace prefix.
#   - agents/ is symlinked under ~/.claude/agents/mainframe/ so Claude Code loads
#     the profiles at user scope and honors agent-scoped fields unavailable to
#     plugin agents.
#   - CLAUDE.md stays a direct symlink. settings.json is handled separately by
#     settings-manager.py because Claude Code mutates user preferences in place.
#   - the repository-owned, gitignored credentials index is exposed through a
#     stable Claude-facing path so moving the checkout does not break skills or
#     permissions. The index itself remains in shared/credentials/.
ARTIFACTS=(
    "adapters/claude-code/export/CLAUDE.md:${CLAUDE_DIR}/CLAUDE.md"
    "shared/credentials/credentials-index.md:${CLAUDE_DIR}/credentials-index.md"
    "adapters/claude-code/plugin:${CLAUDE_DIR}/skills/mainframe"
    "adapters/claude-code/agents:${CLAUDE_DIR}/agents/mainframe"
)

SETTINGS_SOURCE="${ADAPTER_ROOT}/export/settings.json"
SETTINGS_TARGET="${CLAUDE_DIR}/settings.json"
SETTINGS_STATE="${CLAUDE_DIR}/.mainframe-settings-state.json"
SETTINGS_MANAGER="${ADAPTER_ROOT}/settings-manager.py"

# Hub-development instrumentation, installed ONLY with --dev (see usage).
# ~/.claude/mainframe is the hub-OWNED data namespace. The telemetry hook's
# early shell gate opens only while claude-code/telemetry exists. The adapter
# segment prevents a future Codex dev install from enabling Claude telemetry.
DEV_ARTIFACTS=(
    "dev/skills/harness-feedback:${CLAUDE_DIR}/skills/harness-feedback"
    "workspace/runtime:${CLAUDE_DIR}/mainframe"
)
TELEMETRY_DIR="${PROJECT_ROOT}/workspace/runtime/claude-code/telemetry"
TELEMETRY_DB="${TELEMETRY_DIR}/telemetry.db"

# Directories whose CONTENTS are linked item-by-item into ~/.claude/<dir>/.
# These layers have no plugin-format equivalent, so they stay outside the plugin and
# install per-item so the hub composes with anything the user already has there:
#   - `rules/` — path-scoped rules with `paths:` frontmatter (no plugin support).
#   - `output-styles/` — user-selectable styles activated via `/config`; per-item so
#     the hub's styles sit alongside the user's own.
# Format: "<source-dir-relative>:<target-dir-absolute>"
MANAGED_DIRS=(
    "adapters/claude-code/export/rules:${CLAUDE_DIR}/rules"
    "adapters/claude-code/export/output-styles:${CLAUDE_DIR}/output-styles"
)

# Safe backup dir for items inside managed dirs (skills/, hooks/, rules/, etc.).
# Claude Code scans those dirs wholesale, so a sibling .backup-* file there could
# trip discovery. Top-level files (CLAUDE.md, settings.json) keep the sibling-file
# backup style because discovery keys on exact filenames at that level.
SAFE_BACKUP_DIR=""

# ---- Helpers ----

claude_version() {
    local output
    output="$(claude --version 2>/dev/null || true)"
    if [[ "$output" =~ ([0-9]+)\.([0-9]+)\.([0-9]+) ]]; then
        printf '%s.%s.%s\n' "${BASH_REMATCH[1]}" "${BASH_REMATCH[2]}" "${BASH_REMATCH[3]}"
        return 0
    fi
    return 1
}

version_at_least() {
    local current="$1" required="$2"
    local current_major current_minor current_patch
    local required_major required_minor required_patch
    IFS=. read -r current_major current_minor current_patch <<<"$current"
    IFS=. read -r required_major required_minor required_patch <<<"$required"
    [[ "$current_major$current_minor$current_patch$required_major$required_minor$required_patch" =~ ^[0-9]+$ ]] || return 1

    if (( current_major != required_major )); then
        (( current_major > required_major ))
    elif (( current_minor != required_minor )); then
        (( current_minor > required_minor ))
    else
        (( current_patch >= required_patch ))
    fi
}

check_claude_version() {
    if ! command -v claude >/dev/null 2>&1; then
        log_error "Claude Code ${MIN_CLAUDE_VERSION}+ is required but 'claude' is not on PATH."
        log_error "Install it from https://code.claude.com/docs/en/installation and retry."
        return 1
    fi

    local current
    if ! current="$(claude_version)"; then
        log_error "Could not parse the installed Claude Code version from 'claude --version'."
        return 1
    fi
    if version_at_least "$current" "$MIN_CLAUDE_VERSION"; then
        log_ok "Claude Code ${current} satisfies the required ${MIN_CLAUDE_VERSION}+."
        return 0
    fi

    log_warn "MAINFRAME requires Claude Code ${MIN_CLAUDE_VERSION}+; found ${current}."
    if [[ $DRY_RUN -eq 1 ]]; then
        log_action "would ask to run 'claude update' before installation"
        return 0
    fi

    local approve=0 reply=""
    if [[ $ASSUME_YES -eq 1 ]]; then
        approve=1
    elif [[ -t 0 && -t 1 ]]; then
        printf 'Update Claude Code now with `claude update`? [y/N] ' > /dev/tty
        IFS= read -r reply < /dev/tty || true
        case "$reply" in
            y|Y|yes|YES|Yes) approve=1 ;;
        esac
    fi

    if [[ $approve -ne 1 ]]; then
        log_error "Installation stopped before making changes."
        log_error "Run 'claude update', or rerun this installer with '--yes'."
        return 1
    fi

    log_info "Updating Claude Code with the official updater..."
    if ! claude update; then
        log_error "'claude update' failed; installation stopped."
        return 1
    fi
    if ! current="$(claude_version)" || ! version_at_least "$current" "$MIN_CLAUDE_VERSION"; then
        log_error "Claude Code is still below ${MIN_CLAUDE_VERSION} after the update; installation stopped."
        return 1
    fi
    log_ok "Claude Code updated to ${current}."
}

# Verify the adapter sources are present.
check_prerequisites() {
    if [[ ! -d "${ADAPTER_ROOT}/export" || ! -d "${ADAPTER_ROOT}/plugin" || ! -d "${ADAPTER_ROOT}/agents" ]]; then
        log_error "Claude Code adapter sources are incomplete at ${ADAPTER_ROOT}"
        exit 1
    fi
    if [[ ! -d "${CLAUDE_DIR}" ]]; then
        log_info "${CLAUDE_DIR} does not exist; creating."
        if [[ $DRY_RUN -eq 0 ]]; then
            mkdir -p "${CLAUDE_DIR}"
        fi
    fi
}

# Fail before delivery if Python is unavailable. Every shipped runtime hook uses
# Python; installing without it would replace normal checks with repeated shell
# fallback reports that cannot use the Python deduplication layer.
check_python() {
    if command -v python3 >/dev/null 2>&1 && python3 -c 'import sys' >/dev/null 2>&1; then
        log_info "python3 found: $(command -v python3)"
        return 0
    fi
    log_error "A working python3 is required by MAINFRAME hooks but was not found on PATH."
    log_error "Install Python 3 and retry; no Claude adapter files were changed."
    return 1
}

check_settings_inputs() {
    python3 "$SETTINGS_MANAGER" check \
        --source "$SETTINGS_SOURCE" \
        --target "$SETTINGS_TARGET" \
        --state "$SETTINGS_STATE"
}

install_settings() {
    local args=(
        install
        --source "$SETTINGS_SOURCE"
        --target "$SETTINGS_TARGET"
        --state "$SETTINGS_STATE"
        --backup "${SETTINGS_TARGET}.backup-${TIMESTAMP}"
    )
    if [[ $DRY_RUN -eq 1 ]]; then
        args+=(--dry-run)
    fi
    python3 "$SETTINGS_MANAGER" "${args[@]}"
}

uninstall_settings() {
    local args=(
        uninstall
        --source "$SETTINGS_SOURCE"
        --target "$SETTINGS_TARGET"
        --state "$SETTINGS_STATE"
        --backup "${SETTINGS_TARGET}.backup-${TIMESTAMP}"
    )
    if [[ $DRY_RUN -eq 1 ]]; then
        args+=(--dry-run)
    fi
    python3 "$SETTINGS_MANAGER" "${args[@]}"
}

# Resolve the absolute path that a symlink points to, or empty string if not a symlink.
readlink_safe() {
    local path="$1"
    if [[ -L "$path" ]]; then
        if command -v greadlink >/dev/null 2>&1; then
            greadlink -f "$path"
        elif command -v python3 >/dev/null 2>&1 \
                && python3 -c 'import sys' >/dev/null 2>&1; then
            # Fallback for macOS bash without coreutils
            python3 -c "import os, sys; print(os.path.realpath(sys.argv[1]))" "$path"
        else
            # MAINFRAME creates absolute links. Without Python, a relative or
            # otherwise different link remains unmatched and is preserved.
            readlink "$path"
        fi
    else
        echo ""
    fi
}

# Lazily create a safe backup dir for items inside managed dirs.
ensure_safe_backup_dir() {
    if [[ -z "$SAFE_BACKUP_DIR" ]]; then
        SAFE_BACKUP_DIR="${CLAUDE_DIR}/.backup-${TIMESTAMP}"
        if [[ $DRY_RUN -eq 0 ]]; then
            mkdir -p "$SAFE_BACKUP_DIR"
        fi
    fi
}

# Backup an existing target. Two strategies depending on location:
#  - Top-level files (~/.claude/<name>): sibling .backup-* file. Discovery there
#    keys on exact filenames so the backup is invisible.
#  - Items inside a managed dir (~/.claude/<layer>/<name>): move into a hidden
#    per-run backup dir to avoid polluting layer discovery.
backup_target() {
    local target="$1"
    local parent
    parent="$(dirname "$target")"

    if [[ "$parent" == "$CLAUDE_DIR" ]]; then
        local backup="${target}.backup-${TIMESTAMP}"
        if [[ $DRY_RUN -eq 1 ]]; then
            log_action "would back up ${target} → ${backup}"
        else
            mv "$target" "$backup"
            log_ok "backed up ${target} → ${backup}"
        fi
    else
        ensure_safe_backup_dir
        local rel="${target#${CLAUDE_DIR}/}"
        local dest="${SAFE_BACKUP_DIR}/${rel}"
        if [[ $DRY_RUN -eq 1 ]]; then
            log_action "would move ${target} → ${SAFE_BACKUP_DIR}/${rel}"
        else
            mkdir -p "$(dirname "$dest")"
            mv "$target" "$dest"
            log_ok "moved ${target} → ${SAFE_BACKUP_DIR}/${rel}"
        fi
    fi
}

# Install one artifact: source → target.
install_one() {
    local src_rel="$1"
    local target="$2"
    local src_abs="${PROJECT_ROOT}/${src_rel}"

    if [[ ! -e "$src_abs" ]]; then
        log_warn "skipping: source ${src_rel} does not exist in repo"
        return 0
    fi

    # Already a symlink pointing to the correct source?
    if [[ -L "$target" ]]; then
        local current
        current="$(readlink_safe "$target")"
        if [[ "$current" == "$src_abs" ]]; then
            log_ok "already linked: ${target} → ${src_rel}"
            return 0
        else
            log_warn "${target} is a symlink to a different path: ${current}"
            backup_target "$target"
        fi
    elif [[ -e "$target" ]]; then
        # Regular file or directory present — back it up before linking.
        backup_target "$target"
    fi

    if [[ $DRY_RUN -eq 1 ]]; then
        log_action "would link ${target} → ${src_rel}"
    else
        ln -s "$src_abs" "$target"
        log_ok "linked ${target} → ${src_rel}"
    fi
}

# Uninstall one artifact: remove symlink if it points to our source.
# Does NOT auto-restore backups — user decides if they want to.
uninstall_one() {
    local src_rel="$1"
    local target="$2"
    local src_abs="${PROJECT_ROOT}/${src_rel}"

    if [[ ! -L "$target" ]]; then
        log_info "skipping: ${target} is not a symlink"
        return 0
    fi

    local current
    current="$(readlink_safe "$target")"
    if [[ "$current" != "$src_abs" ]]; then
        log_warn "skipping: ${target} symlink points elsewhere (${current})"
        return 0
    fi

    if [[ $DRY_RUN -eq 1 ]]; then
        log_action "would remove symlink ${target}"
    else
        rm "$target"
        log_ok "removed symlink ${target}"
    fi
}

# Symlink each child of a hub source dir into the target dir, item-by-item.
install_dir_contents() {
    local src_dir_rel="$1"
    local target_dir="$2"
    local src_dir_abs="${PROJECT_ROOT}/${src_dir_rel}"

    if [[ ! -d "$src_dir_abs" ]]; then
        return 0  # nothing to link from this dir yet
    fi

    if [[ ! -d "$target_dir" ]]; then
        if [[ $DRY_RUN -eq 1 ]]; then
            log_action "would create ${target_dir}"
        else
            mkdir -p "$target_dir"
            log_ok "created ${target_dir}"
        fi
    fi

    local child base
    for child in "$src_dir_abs"/*; do
        [[ -e "$child" ]] || continue  # guard against empty-glob literal
        base="$(basename "$child")"
        install_one "${src_dir_rel}/${base}" "${target_dir}/${base}"
    done
}

# Non-fatal preflight: the tooling phase is best-effort, so surface missing
# prerequisites up front with OS-appropriate install hints, instead of letting
# the user discover them as a string of per-tool failures.
check_tooling_prerequisites() {
    local need_py=0 need_npm=0
    if ! command -v uv >/dev/null 2>&1 && ! command -v pipx >/dev/null 2>&1; then need_py=1; fi
    if ! command -v npm >/dev/null 2>&1; then need_npm=1; fi
    if [[ $need_py -eq 0 && $need_npm -eq 0 ]]; then
        return 0
    fi
    local mgr=""
    if command -v apt-get >/dev/null 2>&1; then mgr=apt
    elif command -v brew >/dev/null 2>&1; then mgr=brew
    elif command -v dnf >/dev/null 2>&1; then mgr=dnf
    fi
    log_warn "Some optional analyzers are missing — their checks will report unavailable when applicable:"
    if [[ $need_py -eq 1 ]]; then
        log_warn "  - uv OR pipx (for ruff):"
        case "$mgr" in
            apt)  log_warn "      sudo apt install -y pipx && pipx ensurepath" ;;
            brew) log_warn "      brew install uv   (or: brew install pipx)" ;;
            dnf)  log_warn "      sudo dnf install -y pipx && pipx ensurepath" ;;
            *)    log_warn "      install uv (https://docs.astral.sh/uv/) or pipx" ;;
        esac
    fi
    if [[ $need_npm -eq 1 ]]; then
        log_warn "  - npm / Node.js (for oxlint):"
        case "$mgr" in
            apt)  log_warn "      sudo apt install -y nodejs npm" ;;
            brew) log_warn "      brew install node" ;;
            dnf)  log_warn "      sudo dnf install -y nodejs npm" ;;
            *)    log_warn "      install Node.js (https://nodejs.org)" ;;
        esac
    fi
    log_warn "This installer is idempotent — re-run it after installing them."
}

_install_tool() {
    local tool="$1" install_arg="$2"
    if command -v "$tool" >/dev/null 2>&1; then
        log_ok "$tool already installed ($($tool --version 2>/dev/null | head -1)) — related hooks active."
        return 0
    fi
    if [[ $DRY_RUN -eq 1 ]]; then
        log_info "[dry-run] would install $tool via 'uv tool install $install_arg' (fallback: 'pipx install $tool')."
        return 0
    fi
    if command -v uv >/dev/null 2>&1; then
        log_info "Installing $tool via 'uv tool install $install_arg'..."
        if uv tool install "$install_arg" >/dev/null 2>&1; then
            log_ok "$tool installed via uv."
            return 0
        fi
        log_warn "'uv tool install $install_arg' failed; trying pipx fallback."
    fi
    if command -v pipx >/dev/null 2>&1; then
        log_info "Installing $tool via 'pipx install $tool'..."
        if pipx install "$tool" >/dev/null 2>&1; then
            log_ok "$tool installed via pipx."
            return 0
        fi
        log_warn "'pipx install $tool' failed."
    fi
    log_warn "Could not install $tool (no working uv/pipx found)."
    log_warn "Related hook(s) will report the unavailable analyzer when applicable."
    log_warn "To enable: 'uv tool install $install_arg' OR 'pipx install $tool'."
    return 1
}

bootstrap_python_security_tools() {
    # Tooling installs are best-effort: `|| true` keeps one failure from aborting
    # the phase under `set -e` (each helper warns internally on failure).
    _install_tool ruff ruff@latest || true
}

_install_npm_global() {
    local pkg="$1"
    local binary="${2:-$pkg}"
    if command -v "$binary" >/dev/null 2>&1; then
        log_ok "$binary already installed ($($binary --version 2>&1 | head -1)) — related hooks active."
        return 0
    fi
    if [[ $DRY_RUN -eq 1 ]]; then
        log_info "[dry-run] would install $pkg via 'npm install -g $pkg'."
        return 0
    fi
    if ! command -v npm >/dev/null 2>&1; then
        log_warn "npm not found on PATH; cannot install $pkg."
        log_warn "Install Node.js (which provides npm) or skip the related hook."
        return 1
    fi
    log_info "Installing $pkg via 'npm install -g $pkg'..."
    if npm install -g "$pkg" >/dev/null 2>&1; then
        log_ok "$pkg installed via npm — related hooks active."
        return 0
    fi
    log_warn "'npm install -g $pkg' failed."
    log_warn "If this is a permissions error, set a user-writable global prefix and retry:"
    log_warn "  npm config set prefix ~/.local   (ensure ~/.local/bin is on PATH)"
    log_warn "$pkg-related hook will report the unavailable analyzer when applicable."
    return 1
}

bootstrap_nodejs_security_tools() {
    _install_npm_global oxlint || true
}

# Drift cleanup: remove hub-symlinks in ~/.claude/<layer>/ whose targets in
# export/ no longer exist. Leaves user-created real files/folders untouched.
# Backups go to the safe per-run dir, NOT in-place.
cleanup_stale_in_dir() {
    local src_dir_rel="$1"
    local target_dir="$2"
    local src_dir_abs="${PROJECT_ROOT}/${src_dir_rel}"

    if [[ ! -d "$target_dir" ]]; then
        return 0
    fi

    local entry resolved
    for entry in "$target_dir"/*; do
        [[ -e "$entry" || -L "$entry" ]] || continue
        [[ -L "$entry" ]] || continue                      # only manage symlinks
        resolved="$(readlink_safe "$entry")"
        [[ "$resolved" == "${src_dir_abs}/"* ]] || continue # only our hub
        [[ -e "$resolved" ]] && continue                    # target still present
        if [[ $DRY_RUN -eq 1 ]]; then
            log_action "would remove stale symlink ${entry} (target ${resolved} gone)"
        else
            backup_target "$entry"
            log_ok "removed stale symlink ${entry}"
        fi
    done
}

# Remove the symlinks previously created for each child of a hub source dir.
uninstall_dir_contents() {
    local src_dir_rel="$1"
    local target_dir="$2"
    local src_dir_abs="${PROJECT_ROOT}/${src_dir_rel}"

    if [[ ! -d "$src_dir_abs" ]]; then
        return 0
    fi

    local child base
    for child in "$src_dir_abs"/*; do
        [[ -e "$child" ]] || continue
        base="$(basename "$child")"
        uninstall_one "${src_dir_rel}/${base}" "${target_dir}/${base}"
    done
}

# List any existing backups so user knows what's restorable.
list_backups() {
    local backups
    # Avoid relying on a glob expanding when nothing matches.
    backups=$(find "${CLAUDE_DIR}" -maxdepth 1 -name '*.backup-*' 2>/dev/null | sort || true)
    if [[ -n "${backups:-}" ]]; then
        log_info "Existing backups in ${CLAUDE_DIR}:"
        echo "${backups}" | sed 's/^/    /'
        log_info "Restore manually with: mv <backup> <original-name>"
    fi
}

# Old per-item symlinks under ~/.claude/{skills,agents,hooks}/ from previous
# layouts can shadow the current plugin skills or user-level agents.
cleanup_stale_post_migration() {
    local stale_skills=(
        code-audit curl-requests git-conventional-commits-ru nestjs-backend-patterns
        nextjs-backend-patterns
        no-suppression-markers ops-app-server-safety python-backend-patterns
        frontend-design react-frontend-patterns secrets-handling severity-calibration shadcn
        surface-ticket ticket task-workflow testing-strategy
    )
    local stale_agents=(
        decision-reviewer.md devops-engineer.md mainframe-devops-engineer.md nestjs-backend-engineer.md
        nextjs-backend-engineer.md python-backend-engineer.md
        react-frontend-engineer.md researcher.md web-search.md
    )
    local stale_hooks=(
        bash-pattern-reminder.py comment-discipline-reminder.py frontend-dead-code.py
        frontend-fsd-gate.py nodejs-deps-audit.py nodejs-security-scan.py
        nodejs-security-stop-gate.py path-validation.py python-deps-audit.py
        python-security-scan.py python-security-stop-gate.py scan-suppression-markers.py
        stop-gate-suppression-markers.py rules
    )

    local removed=0
    local name target

    for name in "${stale_skills[@]}"; do
        target="${CLAUDE_DIR}/skills/${name}"
        if [[ -L "$target" ]]; then
            if [[ $DRY_RUN -eq 1 ]]; then
                log_action "would remove stale: ${target}"
            else
                rm "$target"
                log_ok "removed stale symlink: ${target}"
            fi
            ((removed++))
        fi
    done
    for name in "${stale_agents[@]}"; do
        target="${CLAUDE_DIR}/agents/${name}"
        if [[ -L "$target" ]]; then
            if [[ $DRY_RUN -eq 1 ]]; then
                log_action "would remove stale: ${target}"
            else
                rm "$target"
                log_ok "removed stale symlink: ${target}"
            fi
            ((removed++))
        fi
    done
    for name in "${stale_hooks[@]}"; do
        target="${CLAUDE_DIR}/hooks/${name}"
        if [[ -L "$target" ]]; then
            if [[ $DRY_RUN -eq 1 ]]; then
                log_action "would remove stale: ${target}"
            else
                rm "$target"
                log_ok "removed stale symlink: ${target}"
            fi
            ((removed++))
        fi
    done

    if [[ $removed -gt 0 ]]; then
        log_info "removed ${removed} stale per-item symlinks from the pre-migration layout"
    fi

    # Remove empty legacy layer directories. Required parents are recreated
    # immediately before installing the current artifacts.
    local dir
    for dir in "${CLAUDE_DIR}/agents" "${CLAUDE_DIR}/hooks"; do
        if [[ -d "$dir" && -z "$(ls -A "$dir" 2>/dev/null)" ]]; then
            if [[ $DRY_RUN -eq 1 ]]; then
                log_action "would rmdir empty ${dir}"
            else
                rmdir "$dir"
                log_ok "removed empty ${dir}"
            fi
        fi
    done
}

# ---- Main ----

main() {
    if [[ $DRY_RUN -eq 1 ]]; then
        log_info "${BOLD}DRY RUN${NC} — nothing will be changed."
    fi

    if [[ $UNINSTALL -eq 0 ]]; then
        check_claude_version
        check_python
        check_settings_inputs
    fi
    if [[ $PREFLIGHT_ONLY -eq 1 ]]; then
        return 0
    fi

    if [[ $UNINSTALL -eq 1 ]]; then
        if [[ ! -d "${CLAUDE_DIR}" ]]; then
            log_ok "Nothing to uninstall: ${CLAUDE_DIR} does not exist."
            return 0
        fi
        if [[ -e "$SETTINGS_STATE" || -L "$SETTINGS_TARGET" ]]; then
            check_python
            check_settings_inputs
            uninstall_settings
        fi
        log_info "Uninstalling MAINFRAME hub symlinks from ${CLAUDE_DIR}..."
        for entry in "${ARTIFACTS[@]}"; do
            local src="${entry%%:*}"
            local tgt="${entry##*:}"
            uninstall_one "$src" "$tgt"
        done
        for entry in "${DEV_ARTIFACTS[@]}"; do
            uninstall_one "${entry%%:*}" "${entry##*:}"
        done
        for entry in "${MANAGED_DIRS[@]}"; do
            uninstall_dir_contents "${entry%%:*}" "${entry##*:}"
        done
        log_warn "Shared secrets and workspace/runtime/ data were left in place."
        log_warn "Remove them manually if you want a full reset."
        log_ok "Uninstall complete."
        list_backups
        return 0
    fi

    check_prerequisites

    log_info "Installing the MAINFRAME Claude Code adapter into ${CLAUDE_DIR}..."
    log_info "Source: ${ADAPTER_ROOT}/{agents,export,plugin}"
    log_info "Timestamp tag for any backups: ${TIMESTAMP}"
    echo

    cleanup_stale_post_migration

    local layer_dir
    for layer_dir in "${CLAUDE_DIR}/skills" "${CLAUDE_DIR}/agents"; do
        if [[ ! -d "$layer_dir" ]]; then
            if [[ $DRY_RUN -eq 1 ]]; then
                log_action "would create ${layer_dir}"
            else
                mkdir -p "$layer_dir"
                log_ok "created ${layer_dir}"
            fi
        fi
    done

    for entry in "${ARTIFACTS[@]}"; do
        local src="${entry%%:*}"
        local tgt="${entry##*:}"
        install_one "$src" "$tgt"
    done

    install_settings
    if [[ $DEV -eq 1 ]]; then
        if [[ $DRY_RUN -eq 1 ]]; then
            log_action "would create workspace/runtime/claude-code/{telemetry,feedback,model-lab} (hub data, gitignored)"
        else
            mkdir -p "${TELEMETRY_DIR}" \
                     "${PROJECT_ROOT}/workspace/runtime/claude-code/feedback" \
                     "${PROJECT_ROOT}/workspace/runtime/claude-code/model-lab/spark/hook-regression-candidates"
            if python3 "${ADAPTER_ROOT}/plugin/hooks/scripts/telemetry.py" \
                    --initialize "${TELEMETRY_DB}"; then
                log_ok "Initialized Claude telemetry database in WAL mode."
            else
                log_warn "Could not initialize Claude telemetry; dev telemetry will report the failure when invoked."
            fi
        fi
        for entry in "${DEV_ARTIFACTS[@]}"; do
            install_one "${entry%%:*}" "${entry##*:}"
        done
        # Local hub reference page (dev-only, gitignored output). Best-effort:
        # a missing .venv warns rather than failing the install.
        if [[ $DRY_RUN -eq 1 ]]; then
            log_action "would generate workspace/runtime/hub.html (local hub map)"
        elif [[ -x "${PROJECT_ROOT}/.venv/bin/python3" ]]; then
            if "${PROJECT_ROOT}/.venv/bin/python3" \
                    "${PROJECT_ROOT}/tools/build_hub_page.py" \
                    --root "${PROJECT_ROOT}" >/dev/null 2>&1; then
                log_ok "Generated workspace/runtime/hub.html — open it in a browser for the hub map."
            else
                log_warn "Could not generate hub.html (build_hub_page.py failed); skipping."
            fi
        else
            log_warn "Skipped hub.html — .venv missing (python3 -m venv .venv && .venv/bin/pip install pyyaml tiktoken)."
        fi
    else
        # A plain reinstall explicitly turns adapter development mode off.
        # Remove only symlinks owned by this repository; runtime data remains.
        for entry in "${DEV_ARTIFACTS[@]}"; do
            local dev_target="${entry##*:}"
            if [[ -L "$dev_target" ]]; then
                uninstall_one "${entry%%:*}" "$dev_target"
            fi
        done
    fi
    for entry in "${MANAGED_DIRS[@]}"; do
        install_dir_contents "${entry%%:*}" "${entry##*:}"
    done

    # Drift cleanup pass — after install so stale items get reported alongside.
    for entry in "${MANAGED_DIRS[@]}"; do
        cleanup_stale_in_dir "${entry%%:*}" "${entry##*:}"
    done

    echo
    check_tooling_prerequisites

    echo
    bootstrap_python_security_tools

    echo
    bootstrap_nodejs_security_tools

    echo
    log_ok "Install complete."
    if [[ $DRY_RUN -eq 0 ]]; then
        list_backups
        if [[ -n "$SAFE_BACKUP_DIR" ]]; then
            log_info "Managed-dir backups for this run: ${SAFE_BACKUP_DIR}"
        fi
        echo
        log_info "Next: start a new Claude Code session and verify the hub takes effect."
        log_info "Rollback at any time: $0 --uninstall"
    fi
}

main "$@"
