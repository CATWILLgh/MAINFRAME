#!/usr/bin/env bash
#
# MAINFRAME hub installer.
# Safe by default: backs up any existing target before linking.
#
# Linked:
#   - plugin:       dist/claude-code/plugin/  →  ~/.claude/skills/mainframe/
#                   Claude Code auto-loads it as the 'mainframe' plugin via
#                   the skills-dir mechanism. Skills, agents, commands, and
#                   hooks inside get the `mainframe:` namespace prefix.
#   - umbrella:     dist/claude-code/CLAUDE.md  →  ~/.claude/CLAUDE.md
#                   dist/claude-code/settings.json  →  ~/.claude/settings.json
#                   (Plugin format does not provide an equivalent for these.)
#   - rules:        dist/claude-code/rules/* item-by-item  →  ~/.claude/rules/
#                   (Plugin format does not support path-scoped rules with
#                   `paths:` frontmatter; per-item keeps the layer composable.)
#
# Migration cleanup: removes any stale per-item symlinks in
# ~/.claude/{skills,agents,hooks}/ left over from the pre-plugin layout. If
# the per-layer directories end up empty, they are removed (the plugin owns
# those artifacts now).
#
# Usage:
#   ./install.sh              # install (with backup of existing files)
#   ./install.sh --dry-run    # show what would happen, no changes
#   ./install.sh --uninstall  # remove symlinks managed by this hub
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
OPENCODE=0

usage() {
    cat <<EOF
MAINFRAME hub installer

Installs the hub as a Claude Code plugin: a single symlink in
~/.claude/skills/ points to this repo's dist/claude-code/plugin/ directory, which Claude
Code auto-loads as the 'mainframe' plugin. Skills, agents, commands, and hooks
inside the plugin become available with the 'mainframe:' namespace prefix.

Single-file artifacts that the plugin format does not support stay as direct
symlinks: CLAUDE.md (umbrella instructions) and settings.json (permissions
and user-level config). Path-scoped rules in dist/claude-code/rules/ install per-item.

The first install after upgrading from the pre-plugin layout also cleans up
stale per-item symlinks in ~/.claude/{skills,agents,hooks}/ left over from
the old layout, and removes the empty directories if any.

Usage:
  $0                  Install (creates symlinks; backs up existing files).
  $0 --dev            Install PLUS the hub-development instrumentation:
                      the 'harness-feedback' skill and the hub data
                      namespace ~/.claude/mainframe -> workspace/runtime/
                      in this repo (gitignored), holding friction reports
                      (feedback/) and local usage telemetry (telemetry/ —
                      a local SQLite DB; nothing leaves the machine).
                      Ordinary users do not need this.
  $0 --opencode       Install PLUS the OpenCode projection: generates
                      OpenCode-format agents from core/agents/ (via
                      adapters/opencode/build_opencode.py, needs the repo
                      .venv), links
                      them into ~/.config/opencode/agents/, and merges the
                      hub-managed 'permission' + secret-free 'mcp' keys into
                      ~/.config/opencode/opencode.json (one rolling backup
                      at opencode.json.backup). CLAUDE.md and skills need no
                      projection — OpenCode picks them up from ~/.claude
                      natively. NOTE: hub hooks do not transfer; OpenCode
                      runs have thinner guardrails than Claude Code.
  $0 --dry-run        Show what would happen, no changes.
  $0 --uninstall      Remove symlinks created by this script (incl. --dev
                      and --opencode ones; telemetry/feedback data and
                      opencode.json edits are left in place).
  $0 --help           Show this message.

Idempotent: re-running is safe — already-correct symlinks are left alone.

Backups (if any) live at:
  ~/.claude/<file>.backup-YYYYMMDD-HHMMSS

EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)   DRY_RUN=1 ;;
        --dev)       DEV=1 ;;
        --opencode)  OPENCODE=1 ;;
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

# Single-file (and single-dir) artifacts. Format: "<source-relative-to-project>:<target-absolute>"
# Layout:
#   - dist/claude-code/plugin/ is symlinked as a single directory under ~/.claude/skills/mainframe/.
#     Claude Code auto-loads it as the 'mainframe' plugin via the skills-dir mechanism,
#     and skills/agents/commands/hooks inside get the `mainframe:` namespace prefix.
#   - CLAUDE.md and settings.json stay as direct symlinks because the plugin format
#     does not provide an equivalent for the umbrella instructions or user-level
#     permission rules.
ARTIFACTS=(
    "dist/claude-code/CLAUDE.md:${CLAUDE_DIR}/CLAUDE.md"
    "dist/claude-code/settings.json:${CLAUDE_DIR}/settings.json"
    "dist/claude-code/plugin:${CLAUDE_DIR}/skills/mainframe"
)

# Hub-development instrumentation, installed ONLY with --dev (see usage).
# ~/.claude/mainframe is the hub-OWNED data namespace: the hooks log telemetry
# only while it exists. ~/.claude/telemetry cannot serve as the opt-in marker —
# Claude Code itself creates and uses that directory on every machine.
DEV_ARTIFACTS=(
    "dev/skills/harness-feedback:${CLAUDE_DIR}/skills/harness-feedback"
    "workspace/runtime:${CLAUDE_DIR}/mainframe"
)

# Directories whose CONTENTS are linked item-by-item into ~/.claude/<dir>/.
# These layers have no plugin-format equivalent, so they stay outside the plugin and
# install per-item so the hub composes with anything the user already has there:
#   - `rules/` — path-scoped rules with `paths:` frontmatter (no plugin support).
#   - `output-styles/` — user-selectable styles activated via `/config`; per-item so
#     the hub's styles sit alongside the user's own.
# Format: "<source-dir-relative>:<target-dir-absolute>"
MANAGED_DIRS=(
    "dist/claude-code/rules:${CLAUDE_DIR}/rules"
    "dist/claude-code/output-styles:${CLAUDE_DIR}/output-styles"
)

# Safe backup dir for items inside managed dirs (skills/, hooks/, rules/, etc.).
# Claude Code scans those dirs wholesale, so a sibling .backup-* file there could
# trip discovery. Top-level files (CLAUDE.md, settings.json) keep the sibling-file
# backup style because discovery keys on exact filenames at that level.
SAFE_BACKUP_DIR=""

# ---- Helpers ----

# Verify the script is run from the right repo (dist/ must exist).
check_prerequisites() {
    if [[ ! -d "${PROJECT_ROOT}/dist" ]]; then
        log_error "dist/ directory not found at ${PROJECT_ROOT}"
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

# Append the secrets-source line to a shell rc file, idempotently. The `secret`
# env-vars must reach each shell the user actually opens: zsh reads ~/.zshenv on
# every invocation; bash/sh read ~/.bashrc (interactive) and ~/.profile (login).
# Non-interactive shells read no rc file and are out of scope.
_append_secret_source_line() {
    local rcfile="$1" source_line="$2"
    if grep -Fqs "$source_line" "$rcfile" 2>/dev/null; then
        log_ok "$(basename "$rcfile") already sources the secrets store"
        return 0
    fi
    if [[ $DRY_RUN -eq 1 ]]; then
        log_action "would append source-line to ${rcfile}"
        return 0
    fi
    {
        echo ""
        echo "# MAINFRAME hub: auto-source personal secrets store."
        echo "$source_line"
    } >> "$rcfile"
    log_ok "appended source-line to ${rcfile}"
}

bootstrap_secrets() {
    local bin_dir="$HOME/.local/bin"
    local secret_src="${PROJECT_ROOT}/dist/claude-code/scripts/secret"
    local secret_link="${bin_dir}/secret"
    local store_dir="${XDG_CONFIG_HOME:-$HOME/.config}/credentials"
    local index_src="${PROJECT_ROOT}/dist/claude-code/templates/credentials-index.md"
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
                log_action "would link ${secret_link} → dist/claude-code/scripts/secret"
            else
                ln -s "$secret_src" "$secret_link"
                log_ok "linked ${secret_link} → dist/claude-code/scripts/secret"
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

    # zsh: always (it reads ~/.zshenv on every invocation; create if absent).
    # bash/sh: only rc files that already exist — don't create init files for a
    # shell the user may not use.
    _append_secret_source_line "$zshenv" "$source_line"
    if [[ -f "$HOME/.bashrc" ]]; then _append_secret_source_line "$HOME/.bashrc" "$source_line"; fi
    if [[ -f "$HOME/.profile" ]]; then _append_secret_source_line "$HOME/.profile" "$source_line"; fi

    if [[ $DRY_RUN -eq 0 ]]; then
        log_warn "Recommendation: exclude ${store_dir} from cloud backups (Time Machine, iCloud, Backblaze)."
    fi
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
    log_warn "Some tooling prerequisites are missing — related hooks stay SILENT until installed:"
    if [[ $need_py -eq 1 ]]; then
        log_warn "  - uv OR pipx (for ruff / pip-audit / semgrep):"
        case "$mgr" in
            apt)  log_warn "      sudo apt install -y pipx && pipx ensurepath" ;;
            brew) log_warn "      brew install uv   (or: brew install pipx)" ;;
            dnf)  log_warn "      sudo dnf install -y pipx && pipx ensurepath" ;;
            *)    log_warn "      install uv (https://docs.astral.sh/uv/) or pipx" ;;
        esac
    fi
    if [[ $need_npm -eq 1 ]]; then
        log_warn "  - npm / Node.js (for oxlint / dependency-cruiser / knip / fallow):"
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
    log_warn "Related hook(s) will be SILENT until installed manually."
    log_warn "To enable: 'uv tool install $install_arg' OR 'pipx install $tool'."
    return 1
}

bootstrap_python_security_tools() {
    # Tooling installs are best-effort: `|| true` keeps one failure from aborting
    # the phase under `set -e` (each helper warns internally on failure).
    _install_tool ruff ruff@latest || true
    _install_tool pip-audit pip-audit || true
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
                    | grep -oE '"tag_name"[[:space:]]*:[[:space:]]*"v?[^"]+"' \
                    | sed -E 's/.*"v?([^"]+)"$/\1/')"
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
    log_warn "If this is a permissions error, set a user-writable global prefix and retry:"
    log_warn "  npm config set prefix ~/.local   (ensure ~/.local/bin is on PATH)"
    log_warn "$pkg-related hook will be SILENT until installed manually."
    return 1
}

bootstrap_nodejs_security_tools() {
    _install_tool semgrep semgrep || true
    _install_osv_scanner || true
    _install_npm_global oxlint || true
}

bootstrap_frontend_quality_tools() {
    _install_npm_global dependency-cruiser depcruise || true
    _install_npm_global knip || true
    _install_npm_global fallow || true
}

# OpenCode dual-target layer (--opencode). The generator owns all format
# translation; this function only runs it and links its output. Generated
# agents live in dist/opencode/agents/ (gitignored, derived)
# so ~/.config/opencode/agents/ gets the same item-by-item symlink treatment
# as the other managed dirs.
OPENCODE_AGENTS_SRC="dist/opencode/agents"
# Hand-written OpenCode-native artifacts (not generated) live in the
# adapters/opencode/ dialect dir and symlink out directly, like dist/claude-code/rules.
OPENCODE_PLUGINS_SRC="adapters/opencode/plugins"
# Skills also reach OpenCode via its ~/.claude compat scan; the native links
# are insurance against that scan changing — duplicate names dedupe to a
# single listing (verified empirically), so double discovery is harmless.
OPENCODE_SKILLS_SRC="dist/claude-code/plugin/skills"
opencode_config_dir() { echo "${XDG_CONFIG_HOME:-$HOME/.config}/opencode"; }

install_opencode() {
    local py="${PROJECT_ROOT}/.venv/bin/python3"
    local cfg_dir
    cfg_dir="$(opencode_config_dir)"

    if ! command -v opencode >/dev/null 2>&1; then
        log_warn "opencode not found on PATH — skipping the OpenCode layer."
        return 0
    fi
    if [[ ! -x "$py" ]]; then
        log_warn "Skipped OpenCode projection — .venv missing"
        log_warn "(bootstrap: python3 -m venv .venv && .venv/bin/pip install tiktoken pyyaml)."
        return 0
    fi

    local gen_args=(--root "${PROJECT_ROOT}")
    [[ $DRY_RUN -eq 1 ]] && gen_args+=(--dry-run)
    if ! "$py" "${PROJECT_ROOT}/adapters/opencode/build_opencode.py" "${gen_args[@]}"; then
        log_error "build_opencode.py failed; OpenCode layer not installed."
        return 1
    fi

    if [[ $DRY_RUN -eq 1 ]]; then
        log_action "would link generated agents into $(opencode_config_dir)/agents/"
        log_action "would link security-gate plugin into $(opencode_config_dir)/plugins/"
        log_action "would link hub skills into $(opencode_config_dir)/skills/"
        log_action "would link dist/opencode/AGENTS.md to $(opencode_config_dir)/AGENTS.md"
        return 0
    fi
    install_dir_contents "$OPENCODE_AGENTS_SRC" "${cfg_dir}/agents"
    cleanup_stale_in_dir "$OPENCODE_AGENTS_SRC" "${cfg_dir}/agents"
    install_dir_contents "$OPENCODE_PLUGINS_SRC" "${cfg_dir}/plugins"
    cleanup_stale_in_dir "$OPENCODE_PLUGINS_SRC" "${cfg_dir}/plugins"
    install_dir_contents "$OPENCODE_SKILLS_SRC" "${cfg_dir}/skills"
    cleanup_stale_in_dir "$OPENCODE_SKILLS_SRC" "${cfg_dir}/skills"
    # Global instructions: beats OpenCode's ~/.claude/CLAUDE.md fallback in its
    # resolution order, replacing CC-flavored text with the composed render.
    ln -sfn "${PROJECT_ROOT}/dist/opencode/AGENTS.md" "${cfg_dir}/AGENTS.md"
    log_ok "OpenCode layer installed. Restart OpenCode sessions to pick it up."
}

uninstall_opencode() {
    uninstall_dir_contents "$OPENCODE_AGENTS_SRC" "$(opencode_config_dir)/agents"
    uninstall_dir_contents "$OPENCODE_PLUGINS_SRC" "$(opencode_config_dir)/plugins"
    uninstall_dir_contents "$OPENCODE_SKILLS_SRC" "$(opencode_config_dir)/skills"
    local agents_md="$(opencode_config_dir)/AGENTS.md"
    if [[ -L "$agents_md" && "$(readlink "$agents_md")" == "${PROJECT_ROOT}/dist/opencode/AGENTS.md" ]]; then
        rm "$agents_md"
        log_ok "Removed AGENTS.md symlink."
    fi
    log_warn "opencode.json is left as-is (hub-managed 'permission'/'mcp' keys"
    log_warn "included); previous version, if any, is at opencode.json.backup."
}

# Drift cleanup: remove hub-symlinks in ~/.claude/<layer>/ whose targets in
# dist/ no longer exist. Leaves user-created real files/folders untouched.
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

# Old per-item symlinks under ~/.claude/{skills,agents,hooks}/ from the
# pre-plugin install layout dangle after the move; left in place they
# would shadow the new plugin's namespaced artifacts.
cleanup_stale_post_migration() {
    local stale_skills=(
        code-audit curl-requests git-conventional-commits-ru nestjs-backend-patterns
        no-suppression-markers ops-app-server-safety python-backend-patterns
        react-frontend-patterns secrets-handling severity-calibration shadcn
        surface-ticket task-workflow testing-strategy
    )
    local stale_agents=(
        nestjs-backend-engineer.md python-backend-engineer.md
        react-frontend-engineer.md web-search.md
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

    # If agents/ and hooks/ are now empty (all entries were stale and removed),
    # remove the directories themselves — the plugin owns them now.
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

    check_prerequisites
    check_python

    if [[ $UNINSTALL -eq 1 ]]; then
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
        uninstall_opencode
        uninstall_one "dist/claude-code/scripts/secret" "$HOME/.local/bin/secret"
        log_warn "User data left in place: ~/.config/credentials/, ~/.claude/credentials-index.md, ~/.zshenv source-line, workspace/runtime/ (telemetry + feedback)."
        log_warn "Remove them manually if you want a full reset."
        log_ok "Uninstall complete."
        list_backups
        return 0
    fi

    log_info "Installing MAINFRAME hub symlinks into ${CLAUDE_DIR}..."
    log_info "Source: ${PROJECT_ROOT}/dist"
    log_info "Timestamp tag for any backups: ${TIMESTAMP}"
    echo

    cleanup_stale_post_migration

    if [[ ! -d "${CLAUDE_DIR}/skills" ]]; then
        if [[ $DRY_RUN -eq 1 ]]; then
            log_action "would create ${CLAUDE_DIR}/skills"
        else
            mkdir -p "${CLAUDE_DIR}/skills"
            log_ok "created ${CLAUDE_DIR}/skills"
        fi
    fi

    for entry in "${ARTIFACTS[@]}"; do
        local src="${entry%%:*}"
        local tgt="${entry##*:}"
        install_one "$src" "$tgt"
    done
    if [[ $DEV -eq 1 ]]; then
        if [[ $DRY_RUN -eq 1 ]]; then
            log_action "would create workspace/runtime/{telemetry,feedback} (hub data, gitignored)"
        else
            mkdir -p "${PROJECT_ROOT}/workspace/runtime/telemetry" \
                     "${PROJECT_ROOT}/workspace/runtime/feedback"
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
    fi
    for entry in "${MANAGED_DIRS[@]}"; do
        install_dir_contents "${entry%%:*}" "${entry##*:}"
    done

    # Drift cleanup pass — after install so stale items get reported alongside.
    for entry in "${MANAGED_DIRS[@]}"; do
        cleanup_stale_in_dir "${entry%%:*}" "${entry##*:}"
    done

    if [[ $OPENCODE -eq 1 ]]; then
        echo
        # Guarded call: under `set -e` a bare failing call here would abort
        # the remaining install phases (secrets, tooling) silently.
        if ! install_opencode; then
            log_warn "OpenCode layer failed; continuing with the rest of the install."
        fi
    fi

    echo
    bootstrap_secrets

    echo
    check_tooling_prerequisites

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
