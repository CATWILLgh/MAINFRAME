#!/usr/bin/env bash
#
# MAINFRAME hub installer.
# Symlinks artifacts from this repo's export/ into ~/.claude/.
# Safe by default: backs up any existing target before linking.
#
# Linked:
#   - single files:         export/CLAUDE.md, export/settings.json
#   - directory contents:   export/{skills,hooks,rules,agents,commands,output-styles}/*
#     Per-item (not whole-dir symlinks) so the hub composes with any user-created
#     skills/hooks/rules/etc. instead of replacing the entire directory.
#
# Usage:
#   ./install.sh              # install (with backup of existing files)
#   ./install.sh --dry-run    # show what would happen, no changes
#   ./install.sh --uninstall  # remove symlinks managed by this hub
#   ./install.sh --help
#
# Idempotent: re-running with the same state does nothing.
# Drift cleanup: install also removes hub-symlinks in ~/.claude/<layer>/ whose
# export/ targets have been removed since the last run.

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

usage() {
    cat <<EOF
MAINFRAME hub installer

Symlinks artifacts from this repo's export/ into ~/.claude/, so the hub's
global Claude Code customizations take effect across every project.

Linked: export/CLAUDE.md, export/settings.json, and the contents of
export/{skills,hooks,rules,agents,commands,output-styles}/ (item-by-item).

Usage:
  $0                  Install (creates symlinks; backs up existing files).
  $0 --dry-run        Show what would happen, no changes.
  $0 --uninstall      Remove symlinks created by this script.
  $0 --help           Show this message.

Idempotent: re-running is safe — already-correct symlinks are left alone.

Backups (if any) live at:
  ~/.claude/<file>.backup-YYYYMMDD-HHMMSS

EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)   DRY_RUN=1 ;;
        --uninstall) UNINSTALL=1 ;;
        -h|--help)   usage; exit 0 ;;
        *) log_error "Unknown argument: $1"; usage; exit 2 ;;
    esac
    shift
done

# ---- Configuration ----

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="$HOME/.claude"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"

# Single-file artifacts. Format: "<source-relative-to-project>:<target-absolute>"
ARTIFACTS=(
    "export/CLAUDE.md:${CLAUDE_DIR}/CLAUDE.md"
    "export/settings.json:${CLAUDE_DIR}/settings.json"
)

# Directories whose CONTENTS are linked item-by-item into ~/.claude/<dir>/.
# Per-item (not a whole-dir symlink) so the hub composes with any skills/hooks
# the user already has, instead of replacing the directory.
# Format: "<source-dir-relative>:<target-dir-absolute>"
MANAGED_DIRS=(
    "export/skills:${CLAUDE_DIR}/skills"
    "export/hooks:${CLAUDE_DIR}/hooks"
    "export/rules:${CLAUDE_DIR}/rules"
    "export/agents:${CLAUDE_DIR}/agents"
    "export/commands:${CLAUDE_DIR}/commands"
    "export/output-styles:${CLAUDE_DIR}/output-styles"
)

# Safe backup dir for items inside managed dirs (skills/, hooks/, rules/, etc.).
# Claude Code scans those dirs wholesale, so a sibling .backup-* file there could
# trip discovery. Top-level files (CLAUDE.md, settings.json) keep the sibling-file
# backup style because discovery keys on exact filenames at that level.
SAFE_BACKUP_DIR=""

# ---- Helpers ----

# Verify the script is run from the right repo (export/ must exist).
check_prerequisites() {
    if [[ ! -d "${PROJECT_ROOT}/export" ]]; then
        log_error "export/ directory not found at ${PROJECT_ROOT}"
        log_error "Run this script from the MAINFRAME repo root."
        exit 1
    fi
    if [[ ! -d "${CLAUDE_DIR}" ]]; then
        log_info "${CLAUDE_DIR} does not exist; creating."
        if [[ $DRY_RUN -eq 0 ]]; then
            mkdir -p "${CLAUDE_DIR}"
        fi
    fi
}

# Warn (do NOT fail) if python3 is missing. The hub's hooks (CLAUDE.md/skill
# validators and the suppression-marker scan) are written in Python and will
# silently no-op without python3. We surface this so the user decides what to do.
check_python() {
    if command -v python3 >/dev/null 2>&1; then
        log_info "python3 found: $(command -v python3)"
    else
        log_warn "python3 not found on PATH."
        log_warn "The hub's Python hooks (validators + suppression-marker scan) will"
        log_warn "silently no-op without python3. Install python3 to enable them, or"
        log_warn "proceed and run without those hooks. Continuing — informational only."
    fi
}

# Resolve the absolute path that a symlink points to, or empty string if not a symlink.
readlink_safe() {
    local path="$1"
    if [[ -L "$path" ]]; then
        if command -v greadlink >/dev/null 2>&1; then
            greadlink -f "$path"
        else
            # Fallback for macOS bash without coreutils
            python3 -c "import os, sys; print(os.path.realpath(sys.argv[1]))" "$path"
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

bootstrap_secrets() {
    local bin_dir="$HOME/.local/bin"
    local secret_src="${PROJECT_ROOT}/export/scripts/secret"
    local secret_link="${bin_dir}/secret"
    local store_dir="${XDG_CONFIG_HOME:-$HOME/.config}/credentials"
    local index_src="${PROJECT_ROOT}/export/templates/credentials-index.md"
    local index_dst="${CLAUDE_DIR}/credentials-index.md"
    local zshenv="$HOME/.zshenv"
    local source_line='[ -f ~/.config/credentials/secrets.env ] && set -a && . ~/.config/credentials/secrets.env && set +a'

    if [[ ! -f "$secret_src" ]]; then
        log_warn "skipping secret helper: source ${secret_src} missing"
    else
        if [[ ! -d "$bin_dir" ]]; then
            if [[ $DRY_RUN -eq 1 ]]; then
                log_action "would create ${bin_dir}"
            else
                mkdir -p "$bin_dir"
                log_ok "created ${bin_dir}"
            fi
        fi
        if [[ -L "$secret_link" ]]; then
            local current
            current="$(readlink_safe "$secret_link")"
            if [[ "$current" == "$secret_src" ]]; then
                log_ok "secret helper already linked: ${secret_link}"
            else
                log_warn "${secret_link} points to ${current}; replacing"
                if [[ $DRY_RUN -eq 0 ]]; then
                    rm "$secret_link"
                    ln -s "$secret_src" "$secret_link"
                    log_ok "relinked ${secret_link} → ${secret_src}"
                fi
            fi
        elif [[ -e "$secret_link" ]]; then
            log_warn "${secret_link} exists and is not a symlink; not overwriting"
        else
            if [[ $DRY_RUN -eq 1 ]]; then
                log_action "would link ${secret_link} → export/scripts/secret"
            else
                ln -s "$secret_src" "$secret_link"
                log_ok "linked ${secret_link} → export/scripts/secret"
            fi
        fi
    fi

    if [[ ! -d "$store_dir" ]]; then
        if [[ $DRY_RUN -eq 1 ]]; then
            log_action "would create ${store_dir} (0700)"
        else
            mkdir -p "$store_dir"
            chmod 700 "$store_dir"
            log_ok "created ${store_dir} (0700)"
        fi
    else
        log_ok "credentials store dir already exists: ${store_dir}"
    fi

    # Copy (not symlink): the index is user-editable and grows over time.
    if [[ -e "$index_dst" ]]; then
        log_ok "credentials index already present: ${index_dst}"
    elif [[ ! -f "$index_src" ]]; then
        log_warn "skipping index template: source ${index_src} missing"
    else
        if [[ $DRY_RUN -eq 1 ]]; then
            log_action "would copy ${index_src} → ${index_dst}"
        else
            cp "$index_src" "$index_dst"
            log_ok "seeded ${index_dst} from template"
        fi
    fi

    if [[ -f "$zshenv" ]] && grep -Fq "$source_line" "$zshenv" 2>/dev/null; then
        log_ok ".zshenv already sources ${store_dir}/secrets.env"
    else
        if [[ $DRY_RUN -eq 1 ]]; then
            log_action "would append source-line to ${zshenv}"
        else
            {
                echo ""
                echo "# MAINFRAME hub: auto-source personal secrets store."
                echo "$source_line"
            } >> "$zshenv"
            log_ok "appended source-line to ${zshenv}"
        fi
    fi

    if [[ $DRY_RUN -eq 0 ]]; then
        log_warn "Recommendation: exclude ${store_dir} from cloud backups (Time Machine, iCloud, Backblaze)."
    fi
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
    log_warn "Related hook(s) will be SILENT until installed manually."
    log_warn "To enable: 'uv tool install $install_arg' OR 'pipx install $tool'."
    return 1
}

bootstrap_python_security_tools() {
    _install_tool ruff ruff@latest
    _install_tool pip-audit pip-audit
}

_install_osv_scanner() {
    if command -v osv-scanner >/dev/null 2>&1; then
        log_ok "osv-scanner already installed ($(osv-scanner --version 2>&1 | head -1)) — nodejs-deps-audit hook active."
        return 0
    fi
    if [[ $DRY_RUN -eq 1 ]]; then
        log_info "[dry-run] would download osv-scanner binary from GitHub releases to ~/.local/bin/."
        return 0
    fi
    local os="$(uname -s | tr '[:upper:]' '[:lower:]')"
    local arch="$(uname -m)"
    case "$arch" in
        x86_64|amd64) arch=amd64 ;;
        arm64|aarch64) arch=arm64 ;;
        *) log_warn "Unsupported arch ($arch) for osv-scanner binary download."; return 1 ;;
    esac
    local asset="osv-scanner_${os}_${arch}"
    local target="${HOME}/.local/bin/osv-scanner"
    mkdir -p "${HOME}/.local/bin"
    local latest_tag
    latest_tag="$(curl -fsSL https://api.github.com/repos/google/osv-scanner/releases/latest 2>/dev/null \
                    | grep '"tag_name"' | sed -E 's/.*"v?([^"]+)".*/\1/')"
    if [[ -z "$latest_tag" ]]; then
        log_warn "Could not query GitHub for osv-scanner latest release; skipping."
        return 1
    fi
    local url="https://github.com/google/osv-scanner/releases/download/v${latest_tag}/${asset}"
    log_info "Downloading osv-scanner v${latest_tag} from $url..."
    if curl -fsSL "$url" -o "$target" && chmod +x "$target"; then
        log_ok "osv-scanner installed at $target — nodejs-deps-audit hook active."
        return 0
    fi
    rm -f "$target"
    log_warn "Could not download osv-scanner binary; nodejs-deps-audit hook will be SILENT."
    log_warn "Install manually from https://github.com/google/osv-scanner/releases or 'go install github.com/google/osv-scanner/v2/cmd/osv-scanner@latest'."
    return 1
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
    log_warn "$pkg-related hook will be SILENT until installed manually."
    return 1
}

bootstrap_nodejs_security_tools() {
    _install_tool semgrep semgrep
    _install_osv_scanner
    _install_npm_global oxlint
}

bootstrap_frontend_quality_tools() {
    _install_npm_global dependency-cruiser depcruise
    _install_npm_global knip
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

# ---- Main ----

main() {
    if [[ $DRY_RUN -eq 1 ]]; then
        log_info "${BOLD}DRY RUN${NC} — nothing will be changed."
    fi

    check_prerequisites
    check_python

    if [[ $UNINSTALL -eq 1 ]]; then
        log_info "Uninstalling MAINFRAME hub symlinks from ${CLAUDE_DIR}..."
        for entry in "${ARTIFACTS[@]}"; do
            local src="${entry%%:*}"
            local tgt="${entry##*:}"
            uninstall_one "$src" "$tgt"
        done
        for entry in "${MANAGED_DIRS[@]}"; do
            uninstall_dir_contents "${entry%%:*}" "${entry##*:}"
        done
        uninstall_one "export/scripts/secret" "$HOME/.local/bin/secret"
        log_warn "User data left in place: ~/.config/credentials/, ~/.claude/credentials-index.md, ~/.zshenv source-line."
        log_warn "Remove them manually if you want a full reset."
        log_ok "Uninstall complete."
        list_backups
        return 0
    fi

    log_info "Installing MAINFRAME hub symlinks into ${CLAUDE_DIR}..."
    log_info "Source: ${PROJECT_ROOT}/export"
    log_info "Timestamp tag for any backups: ${TIMESTAMP}"
    echo

    for entry in "${ARTIFACTS[@]}"; do
        local src="${entry%%:*}"
        local tgt="${entry##*:}"
        install_one "$src" "$tgt"
    done
    for entry in "${MANAGED_DIRS[@]}"; do
        install_dir_contents "${entry%%:*}" "${entry##*:}"
    done

    # Drift cleanup pass — after install so stale items get reported alongside.
    for entry in "${MANAGED_DIRS[@]}"; do
        cleanup_stale_in_dir "${entry%%:*}" "${entry##*:}"
    done

    echo
    bootstrap_secrets

    echo
    bootstrap_python_security_tools

    echo
    bootstrap_nodejs_security_tools

    echo
    bootstrap_frontend_quality_tools

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
