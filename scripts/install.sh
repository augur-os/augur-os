#!/bin/bash
#
# Augur One-Line Installer
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/augur-os/augur-os/main/scripts/install.sh | bash
#   ./scripts/install.sh --from vault
#
# Or download and run:
#   chmod +x scripts/install.sh && ./scripts/install.sh
#
# Options:
#   --from <source>            Record install source and auto-configure MCP for that platform
#                              (e.g., vault, claude-code, codex, cursor)
#   --configure <list>         Configure MCP for additional clients (comma-separated)
#                              (e.g., --configure "cursor,codex" or --configure=windsurf)
#   --install-cli-shortcuts    Append ca/xa/ga/gca shell functions that delegate to
#                              Augur's main/worktree launchers. Opt-in.
#                              Equivalent: AUGUR_INSTALL_CLI_ALIASES=1
#

set -e

# Ensure localhost bypasses proxies
export NO_PROXY="localhost,127.0.0.1,::1"

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

REPO_URL="https://github.com/augur-os/augur-os.git"
# Default install directory - can be overridden with AUGUR_DIR env var
INSTALL_DIR="${AUGUR_DIR:-$HOME/Projects/augur}"
BRANCH="${AUGUR_BRANCH:-main}"
RUN_TESTS="${RUN_TESTS:-1}"  # Set RUN_TESTS=0 to skip pytest during install
PY_VERSION_MIN="3.11"
PY_VERSION_MAX_EXCLUSIVE="3.14"  # Avoid 3.14+ due to wheel gaps (onnxruntime/ocrmypdf)

# ═══════════════════════════════════════════════════════════════════════════════
# COLORS
# ═══════════════════════════════════════════════════════════════════════════════

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m' # No Color

# Disable colors if not terminal
if [ ! -t 1 ]; then
    RED='' GREEN='' YELLOW='' BLUE='' CYAN='' BOLD='' DIM='' NC=''
fi

# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

print_header() {
    echo ""
    echo -e "${BOLD}${CYAN}═══════════════════════════════════════════════════════${NC}"
    echo -e "${BOLD}${CYAN}  $1${NC}"
    echo -e "${BOLD}${CYAN}═══════════════════════════════════════════════════════${NC}"
    echo ""
}

print_step() {
    echo -e "${BOLD}${BLUE}▶ $1${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${CYAN}ℹ $1${NC}"
}

check_command() {
    if command -v "$1" &> /dev/null; then
        return 0
    else
        return 1
    fi
}

version_ge() {
    # Compare two dotted versions, returns 0 if $1 >= $2
    [ "$(printf '%s\n' "$2" "$1" | sort -V | head -n1)" = "$2" ]
}

ensure_python() {
    print_step "Checking Python version (${PY_VERSION_MIN}+ < ${PY_VERSION_MAX_EXCLUSIVE})..."

    PYTHON_CMD=""
    if check_command python3.11; then
        PYTHON_CMD="python3.11"
    elif check_command python3; then
        PYTHON_CMD="python3"
    elif check_command python; then
        PYTHON_CMD="python"
    fi

    if [ -z "$PYTHON_CMD" ]; then
        print_error "Python 3 is not installed. Please install Python ${PY_VERSION_MIN} (recommended)."
        exit 1
    fi

    PY_VERSION="$($PYTHON_CMD -c 'import sys; print(".".join(map(str, sys.version_info[:3])))')"
    PY_MAJOR="$($PYTHON_CMD -c 'import sys; print(sys.version_info.major)')"
    PY_MINOR="$($PYTHON_CMD -c 'import sys; print(sys.version_info.minor)')"

    if [ "$PY_MAJOR" -ne 3 ]; then
        print_error "Python 3 is required (found $PY_VERSION)."
        exit 1
    fi
    if ! version_ge "$PY_VERSION" "$PY_VERSION_MIN"; then
        print_error "Python >= ${PY_VERSION_MIN} is required (found $PY_VERSION)."
        exit 1
    fi
    if version_ge "$PY_VERSION" "$PY_VERSION_MAX_EXCLUSIVE"; then
        print_error "Python >= ${PY_VERSION_MAX_EXCLUSIVE} is not supported yet (found $PY_VERSION). Please install Python ${PY_VERSION_MIN}."
        exit 1
    fi

    print_success "Using $PYTHON_CMD ($PY_VERSION)"
}

install_system_deps() {
    print_step "Installing system dependencies for OCR (tesseract, qpdf, ghostscript, poppler, antiword)..."
    local system="$1"
    if [ "$system" = "darwin" ]; then
        if check_command brew; then
            if ! brew install tesseract qpdf ghostscript poppler antiword; then
                print_warning "Homebrew install failed. Install manually: brew install tesseract qpdf ghostscript poppler antiword"
            fi
        else
            print_warning "Homebrew not found. Install it from https://brew.sh, then run: brew install tesseract qpdf ghostscript poppler antiword"
        fi
    elif [ "$system" = "linux" ]; then
        if check_command apt-get; then
            if ! sudo apt-get update; then
                print_warning "apt-get update failed. Install system deps manually."
            else
                if ! sudo apt-get install -y tesseract-ocr tesseract-ocr-heb qpdf ghostscript poppler-utils antiword; then
                    print_warning "apt-get install failed. Ensure you have sudo access and try manually."
                fi
            fi
        else
            print_warning "Unsupported package manager. Install manually: tesseract-ocr qpdf ghostscript poppler-utils antiword"
        fi
    else
        print_warning "Unknown platform. Please install system plugins manually: tesseract, qpdf, ghostscript, poppler-utils, antiword"
    fi

    # Verify critical binaries
    for cmd in tesseract qpdf gs pdfinfo; do
        if ! check_command "$cmd"; then
            print_warning "$cmd not found after installation. Some OCR features may fail until installed."
        fi
    done
}

create_virtualenv() {
    print_step "Setting up Python environment with uv..."
    cd "$INSTALL_DIR"
    uv sync
    print_success "Python environment created with uv."
}

verify_document_understanding() {
    print_step "Verifying document-understanding capability..."
    cd "$INSTALL_DIR"
    if ! uv run python - <<'PY'
import importlib.util
from pathlib import Path

tool_path = Path("project-brain/capabilities/skills/document-extractor/scripts/mcp/tools_extract.py").resolve()
spec = importlib.util.spec_from_file_location("document_extractor_status", tool_path)
module = importlib.util.module_from_spec(spec)
assert spec is not None and spec.loader is not None
spec.loader.exec_module(module)
status = module.get_extraction_status_impl()
caps = status.get("capabilities", {})
print(f"  document parsing: {'OK' if caps.get('document_parsing_ready') else 'MISSING'}")
print(f"  text PDF extraction: {'OK' if caps.get('text_pdf_extraction_ready') else 'MISSING'}")
print(f"  OCR enhancement: {'OK' if caps.get('ocr_enhancement_ready') else 'Unavailable'}")
print(f"  advanced vision OCR: {'Optional' if caps.get('advanced_vision_ready') else 'Not installed'}")
PY
    then
        print_warning "Document capability check could not complete. You can rerun it later from the document-extractor status tool."
    fi
}

run_tests() {
    if [ "$RUN_TESTS" = "0" ]; then
        print_info "Skipping tests (RUN_TESTS=0)."
        return
    fi
    print_step "Running Local RAG test suite..."
    LOCAL_RAG_REAL_OCR_DEPS=1 uv run pytest project-brain/capabilities/skills/knowledge/augur/tests -q
    print_success "Tests passed."
}

# ═══════════════════════════════════════════════════════════════════════════════
# SEED-TO-VAULT MIGRATION (for skills-pack upgrades)
# ═══════════════════════════════════════════════════════════════════════════════

install_cli_aliases() {
    print_step "Installing CLI shortcuts (ca/xa/ga/gca) into shell rc..."

    local rc_file=""
    case "$(basename "${SHELL:-}")" in
        zsh)  rc_file="$HOME/.zshrc" ;;
        bash)
            if [ "$(uname -s)" = "Darwin" ] && [ -f "$HOME/.bash_profile" ]; then
                rc_file="$HOME/.bash_profile"
            else
                rc_file="$HOME/.bashrc"
            fi
            ;;
        *)
            if [ "$(uname -s)" = "Darwin" ]; then
                rc_file="$HOME/.zshrc"
            else
                rc_file="$HOME/.bashrc"
            fi
            ;;
    esac

    local marker="# === augur CLI shortcuts (ca/xa/ga) ==="
    local end_marker="# === end augur CLI shortcuts ==="
    if [ -f "$rc_file" ]; then
        local tmp
        tmp=$(mktemp)
        awk -v start="$marker" -v end="$end_marker" '
            $0 == start { skip=1; next }
            skip && $0 == end { skip=0; next }
            $0 ~ /^alias[[:space:]]+(ca|xa|ga|gca)=/ && $0 ~ /scripts\/ai-launch\.sh[[:space:]]--/ { next }
            !skip { print }
        ' "$rc_file" > "$tmp" && mv "$tmp" "$rc_file"
        print_info "Refreshed CLI shortcut block in $rc_file"
    fi

    cat >> "$rc_file" <<EOF

$marker
# Augur CLI shortcuts (ca/xa/ga/gca) - prompt main vs worktree, then launch.
# Use "xa --desktop" to open this repo in Codex Desktop for browser-capable sessions.
# Delegating to scripts/{xa,ca,ga,gca}-launch.sh keeps all logic version-controlled.
unalias ca xa ga gca 2>/dev/null || true
xa() { "$INSTALL_DIR/scripts/xa-launch.sh" "\$@"; }
ca() { "$INSTALL_DIR/scripts/ca-launch.sh" "\$@"; }
ga() { "$INSTALL_DIR/scripts/ga-launch.sh" "\$@"; }
gca() { "$INSTALL_DIR/scripts/gca-launch.sh" "\$@"; }
$end_marker
EOF
    print_success "Added ca/xa/ga/gca aliases to $rc_file"
    print_info "Open a new shell or run 'source $rc_file' to load them now"
}

migrate_seeds_to_vault() {
    local vault_dir
    vault_dir=$(python3 -c "from src.config.paths import get_vault_dir; print(get_vault_dir())" 2>/dev/null)

    if [ -z "$vault_dir" ]; then
        print_warning "Could not resolve vault directory — skipping seed migration"
        return
    fi

    local migrated=0
    for skill_dir in "$INSTALL_DIR"/project-brain/capabilities/skills/*/; do
        local skill_name
        skill_name=$(basename "$skill_dir")
        local seeds_dir="$skill_dir/assets/seeds"
        local vault_skill_dir="$vault_dir/$skill_name"

        # Skip if no seeds dir
        [ -d "$seeds_dir" ] || continue

        # Skip if seeds only contains the original _seed.yaml and template dirs
        # (no user-created files to migrate)
        local file_count
        file_count=$(find "$seeds_dir" -type f ! -name '_seed.yaml' | wc -l)
        [ "$file_count" -gt 0 ] || continue

        # Copy seeds to vault (don't overwrite existing vault data)
        mkdir -p "$vault_skill_dir"
        cp -rn "$seeds_dir"/* "$vault_skill_dir"/ 2>/dev/null
        migrated=$((migrated + 1))
    done

    if [ "$migrated" -gt 0 ]; then
        print_success "Migrated data from $migrated skill(s) to vault"
    fi
}

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN INSTALLATION
# ═══════════════════════════════════════════════════════════════════════════════

main() {
    # Parse arguments (ADR-437, ADR-438)
    INSTALL_FROM=""
    CONFIGURE_CLIENTS=""
    INSTALL_CLI_SHORTCUTS=0
    if [ "$AUGUR_INSTALL_CLI_ALIASES" = "1" ] || [ "$AUGUR_INSTALL_CLI_ALIASES" = "true" ]; then
        INSTALL_CLI_SHORTCUTS=1
    fi
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --from)
                INSTALL_FROM="$2"
                shift 2
                ;;
            --from=*)
                INSTALL_FROM="${1#*=}"
                shift
                ;;
            --configure)
                CONFIGURE_CLIENTS="$2"
                shift 2
                ;;
            --configure=*)
                CONFIGURE_CLIENTS="${1#*=}"
                shift
                ;;
            --install-cli-shortcuts)
                INSTALL_CLI_SHORTCUTS=1
                shift
                ;;
            *)
                shift
                ;;
        esac
    done

    print_header "Augur Installer"

    echo -e "This script will:"
    echo -e "  1. Check prerequisites (git, uv, corepack/pnpm, Python ${PY_VERSION_MIN}+ < ${PY_VERSION_MAX_EXCLUSIVE})"
    echo -e "  2. Clone or update the Augur repository"
    echo -e "  3. Install system OCR dependencies (tesseract/qpdf/ghostscript/poppler/antiword)"
    echo -e "  4. Install Node.js dependencies with pnpm and Python deps with uv"
    echo -e "  5. Run Local RAG tests (set RUN_TESTS=0 to skip)"
    echo -e "  6. Run the setup wizard"
    echo ""
    echo -e "${BOLD}Skills included (9):${NC}"
    echo -e "  💼 Job Analyzer      - Job scoring & tracking"
    echo -e "  🎯 Interview Prep    - STAR stories & negotiation"
    echo -e "  📚 Reading List      - Article capture & summarization"
    echo -e "  💡 Ideas Capture     - Idea expansion & scoring"
    echo -e "  🎙️ Voice Memos       - Transcription & analysis"
    echo -e "  🔍 Local RAG         - Semantic document search"
    echo -e "  📱 Social Media      - Platform-optimized posts"
    echo -e "  🍳 Recipe Manager    - Recipe extraction & tracking"
    echo -e "  🔧 Setup Manager     - Environment management"
    echo ""

    # ─────────────────────────────────────────────────────────────────────────
    # Check prerequisites
    # ─────────────────────────────────────────────────────────────────────────

    print_step "Checking prerequisites..."

    # Check git
    if check_command git; then
        print_success "git is installed"
    else
        print_error "git is not installed"
        echo ""
        echo "Please install git first:"
        case "$(uname -s)" in
            Darwin)
                echo "  brew install git"
                echo "  or: xcode-select --install"
                ;;
            Linux)
                echo "  sudo apt install git"
                echo "  or: sudo yum install git"
                ;;
            *)
                echo "  Please install git for your platform"
                ;;
        esac
        exit 1
    fi

    # Check uv
    if check_command uv; then
        print_success "uv is installed ($(uv --version))"
    else
        print_warning "uv is not installed. Installing..."
        curl -LsSf https://astral.sh/uv/install.sh | sh
        export PATH="$HOME/.local/bin:$PATH"
        if check_command uv; then
            print_success "uv installed successfully"
        else
            print_error "Failed to install uv"
            exit 1
        fi
    fi

    ensure_python

    # Enable corepack for pnpm
    if ! check_command corepack; then
        print_step "Installing corepack..."
        npm install -g corepack
    fi
    corepack enable
    print_success "corepack enabled (pnpm available)"

    # ─────────────────────────────────────────────────────────────────────────
    # Confirm installation directory
    # ─────────────────────────────────────────────────────────────────────────

    print_step "Installation directory"

    echo -e "Skills will be installed to: ${CYAN}${INSTALL_DIR}${NC}"
    echo ""

    # Check if directory exists
    if [ -d "$INSTALL_DIR" ]; then
        if [ -d "$INSTALL_DIR/.git" ]; then
            print_warning "Directory exists and is a git repository"
            echo ""
            read -p "Update existing installation? [Y/n] " -n 1 -r
            echo ""
            if [[ $REPLY =~ ^[Nn]$ ]]; then
                print_info "Installation cancelled"
                exit 0
            fi

            # Pull latest changes
            print_step "Updating existing installation..."
            cd "$INSTALL_DIR"
            git fetch origin "$BRANCH"
            git checkout "$BRANCH"
            git pull origin "$BRANCH"
            print_success "Updated to latest version"
        else
            print_error "Directory exists but is not an Augur repository"
            echo "Please remove it or set AUGUR_DIR to a different location:"
            echo "  AUGUR_DIR=~/other/path ./scripts/install.sh"
            exit 1
        fi
    else
        # Clone repository
        print_step "Cloning repository..."

        # Create parent directory if needed
        mkdir -p "$(dirname "$INSTALL_DIR")"

        git clone --depth 1 --branch "$BRANCH" "$REPO_URL" "$INSTALL_DIR"
        print_success "Repository cloned"

        cd "$INSTALL_DIR"
    fi

    # Configure shared git hooks (binary/large-file/path guards)
    print_step "Configuring git hooks..."
    cd "$INSTALL_DIR"
    git config core.hooksPath .githooks
    print_success "Git hooks configured (.githooks/pre-commit)"

    # Install Node.js dependencies
    print_step "Installing Node.js dependencies with pnpm..."
    pnpm install
    print_success "Node.js dependencies installed."

    SYSTEM="$(uname -s | tr '[:upper:]' '[:lower:]')"
    install_system_deps "$SYSTEM"
    create_virtualenv
    verify_document_understanding
    run_tests

    # Migrate any standalone skill data to vault
    migrate_seeds_to_vault

    # ─────────────────────────────────────────────────────────────────────────
    # Run setup script
    # ─────────────────────────────────────────────────────────────────────────

    print_step "Running setup wizard..."
    echo ""
    SETUP_SCRIPT="${INSTALL_DIR}/project-brain/capabilities/skills/platform-admin/scripts/setup_wizard.py"

    if [ -f "$SETUP_SCRIPT" ]; then
        uv run python "$SETUP_SCRIPT"
    else
        print_warning "Setup wizard script not found: $SETUP_SCRIPT"
        print_step "Skipping setup wizard - you can run it manually later"
    fi

    # ─────────────────────────────────────────────────────────────────────────
    # Configure LLM providers (OAuth / API key / Ollama)
    # ─────────────────────────────────────────────────────────────────────────

    OAUTH_SCRIPT="${INSTALL_DIR}/project-brain/capabilities/skills/platform-admin/scripts/oauth_wizard.py"
    if [ -f "$OAUTH_SCRIPT" ]; then
        print_step "Configuring LLM providers..."
        uv run python "$OAUTH_SCRIPT" || print_warning "Provider setup skipped or failed - you can run it later"
    fi

    # Record install source (ADR-437)
    if [ -n "$INSTALL_FROM" ]; then
        STATE_DIR="$HOME/Library/Application Support/Augur/state"
        mkdir -p "$STATE_DIR"
        cat > "$STATE_DIR/install-source.json" << SRCEOF
{
  "source": "$INSTALL_FROM",
  "installed_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "install_dir": "$INSTALL_DIR"
}
SRCEOF
        print_success "Install source recorded: $INSTALL_FROM"
    fi

    # Auto-configure MCP for originating platform (ADR-437)
    if [ -n "$INSTALL_FROM" ]; then
        # Map platform aliases for MCP configuration
        MCP_CLIENT="$INSTALL_FROM"
        if [ "$INSTALL_FROM" = "cowork" ]; then
            MCP_CLIENT="claude_desktop"
        fi
        CONFIGURE_SCRIPT="${INSTALL_DIR}/scripts/configure_mcp.py"
        if [ -f "$CONFIGURE_SCRIPT" ]; then
            print_step "Auto-configuring MCP for $INSTALL_FROM..."
            uv run python "$CONFIGURE_SCRIPT" --client "$MCP_CLIENT" || print_warning "MCP auto-config skipped"
        fi
    fi

    # Configure additional MCP clients (ADR-438)
    if [ -n "$CONFIGURE_CLIENTS" ]; then
        CONFIGURE_SCRIPT="${INSTALL_DIR}/scripts/configure_mcp.py"
        if [ -f "$CONFIGURE_SCRIPT" ]; then
            IFS=',' read -ra CLIENTS <<< "$CONFIGURE_CLIENTS"
            for client in "${CLIENTS[@]}"; do
                client=$(echo "$client" | xargs)  # trim whitespace
                print_step "Configuring MCP for $client..."
                uv run python "$CONFIGURE_SCRIPT" --client "$client" || print_warning "MCP config for $client skipped"
            done
        fi
    fi

    # Keep Codex workspace-local by default, but if Codex is the active target
    # or a Codex plugin cache already exists, refresh both the prompt sync and
    # the installed Codex plugin cache so the Codex app does not keep serving
    # stale skill snapshots after local skill migrations.
    CODEX_CACHE_DIR="$HOME/.codex/plugins/cache/augur-local/augur"
    if [[ "$INSTALL_FROM" == "codex" ]] || [[ "$CONFIGURE_CLIENTS" == *"codex"* ]] || [[ -d "$CODEX_CACHE_DIR" ]]; then
        SYNC_AGENTS="${INSTALL_DIR}/project-brain/capabilities/skills/ai/scripts/sync_agents"
        if [ -d "$SYNC_AGENTS" ]; then
            print_step "Syncing Codex skills..."
            PYTHONPATH="${INSTALL_DIR}/project-brain/capabilities:${INSTALL_DIR}:${INSTALL_DIR}/src/mcp:${SYNC_AGENTS}" \
                uv run python -m skills.ai.scripts.sync_agents sync all || print_warning "Codex skill sync skipped"
        fi

        ASSEMBLER="${INSTALL_DIR}/project-brain/capabilities/skills/plugin-pack/scripts/plugin_assembler.py"
        if [ -f "$ASSEMBLER" ]; then
            print_step "Refreshing Codex plugin cache..."
            PYTHONPATH="${INSTALL_DIR}/project-brain/capabilities:${INSTALL_DIR}:${INSTALL_DIR}/src/mcp:${INSTALL_DIR}/project-brain/capabilities/skills/plugin-pack/scripts" \
                uv run python "$ASSEMBLER" --target codex --install || print_warning "Codex plugin cache refresh skipped"
        fi
    fi

    # Install Cowork plugin if cowork was configured (ADR-503)
    if [[ "$INSTALL_FROM" == "cowork" ]] || [[ "$CONFIGURE_CLIENTS" == *"cowork"* ]]; then
        ASSEMBLER="${INSTALL_DIR}/project-brain/capabilities/skills/plugin-pack/scripts/plugin_assembler.py"
        if [ -f "$ASSEMBLER" ]; then
            print_step "Assembling Cowork plugin..."
            PYTHONPATH="${INSTALL_DIR}/project-brain/capabilities:${INSTALL_DIR}:${INSTALL_DIR}/src/mcp:${INSTALL_DIR}/project-brain/capabilities/skills/plugin-pack/scripts" \
                uv run python "$ASSEMBLER" --target cowork --install || print_warning "Cowork plugin assembly skipped"
        fi
    fi

    # Auto-scaffold Obsidian-flavored config if installed with --from vault (ADR-436/437, ADR-605)
    if [ "$INSTALL_FROM" = "vault" ]; then
        print_step "Scaffolding vault (Obsidian-flavored config)..."
        VAULT_ADAPTER="${INSTALL_DIR}/project-brain/capabilities/skills/ai/scripts/sync_agents/vault_adapters/obsidian.py"
        if [ -f "$VAULT_ADAPTER" ]; then
            uv run python -c "
import sys; sys.path.insert(0, '${INSTALL_DIR}/project-brain/capabilities'); sys.path.insert(1, '${INSTALL_DIR}')
from dotenv import load_dotenv; load_dotenv()
sys.path.insert(0, '${INSTALL_DIR}/project-brain/capabilities/skills/ai/scripts/sync_agents')
from vault_adapters.obsidian import ObsidianVaultAdapter
result = ObsidianVaultAdapter().scaffold()
print(f'Vault scaffold: {result[\"status\"]}')
" || print_warning "Vault scaffold skipped"
        fi
    fi

    # Write onboard-complete.json (ADR-438)
    STATE_DIR="$HOME/Library/Application Support/Augur/state"
    mkdir -p "$STATE_DIR"

    # Build configured_clients list
    CONFIGURED_LIST="[]"
    if [ -n "$INSTALL_FROM" ] || [ -n "$CONFIGURE_CLIENTS" ]; then
        # Combine --from platform with --configure list
        ALL_CLIENTS=""
        if [ -n "$INSTALL_FROM" ]; then
            ALL_CLIENTS="\"$INSTALL_FROM\""
        fi
        if [ -n "$CONFIGURE_CLIENTS" ]; then
            IFS=',' read -ra EXTRA <<< "$CONFIGURE_CLIENTS"
            for c in "${EXTRA[@]}"; do
                c=$(echo "$c" | xargs)
                if [ -n "$ALL_CLIENTS" ]; then
                    ALL_CLIENTS="$ALL_CLIENTS, \"$c\""
                else
                    ALL_CLIENTS="\"$c\""
                fi
            done
        fi
        CONFIGURED_LIST="[$ALL_CLIENTS]"
    fi

    # Check vault scaffold status
    VAULT_SCAFFOLDED="false"
    if [ -d "$HOME/Vault/Augur/.obsidian" ]; then
        VAULT_SCAFFOLDED="true"
    fi

    cat > "$STATE_DIR/onboard-complete.json" << ONBEOF
{
  "installed_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "install_source": "${INSTALL_FROM:-claude-code}",
  "configured_clients": $CONFIGURED_LIST,
  "vault_scaffolded": $VAULT_SCAFFOLDED,
  "dashboard_started": false
}
ONBEOF
    print_success "Onboarding state recorded"

    if [ "$INSTALL_CLI_SHORTCUTS" = "1" ]; then
        install_cli_aliases
    fi

    print_success "Environment ready."
    echo ""
    echo "Get to know your AI setup, build your local second brain, and talk with your projects."
    echo ""
    echo "Fast launch next step: choose a folder and run:"
    echo "  Which folder should I initialize?"
    echo "  cd \"${INSTALL_DIR}\" && uv run aug init --project <folder>"
    echo "This creates or attaches project-brain/ and writes the read-only AI artifact inventory."
    echo "Browse: http://localhost:3000/browse"
    echo "Next action: Ask Augur about this project."
    echo ""
    if [ "$INSTALL_FROM" = "cowork" ]; then
        echo "Next steps:"
        echo "  1) Restart Claude Desktop"
        echo "  2) Augur tools and skills will appear automatically"
        echo "  3) Ask Augur about this project"
    else
        echo "Next steps:"
        echo "  1) Run Python commands with: uv run <command>"
        echo "  2) (Optional) Re-run tests anytime: LOCAL_RAG_REAL_OCR_DEPS=1 uv run pytest project-brain/capabilities/skills/knowledge/augur/tests -q"
        echo "  3) Start augmenting your mind with Augur!"
        echo ""
        if [ "$INSTALL_CLI_SHORTCUTS" = "1" ]; then
            echo "CLI shortcuts installed in your shell rc:"
            echo "  ca   -> Augur Claude launcher (main/worktree prompt)"
            echo "  xa   -> Augur Codex launcher (main/worktree prompt)"
            echo "  xa --desktop -> open Augur in Codex Desktop for browser-capable sessions"
            echo "  ga   -> Augur Gemini launcher (main/worktree prompt)"
            echo "  gca  -> Augur GitHub Copilot CLI launcher (main/worktree prompt)"
            echo ""
        else
            echo "Optional: install ca/xa/ga/gca shortcuts through Augur's main/worktree launchers"
            echo "  xa also supports --desktop after shortcuts are installed"
            echo "  by re-running with --install-cli-shortcuts"
            echo ""
        fi
        echo "Shared/team skills live in: ${INSTALL_DIR}/project-brain/capabilities/skills/"
        echo "User data lives in: ~/Vault/Augur/"
    fi
}

# ═══════════════════════════════════════════════════════════════════════════════
# Error handling
# ═══════════════════════════════════════════════════════════════════════════════

trap 'print_error "Installation failed!"; exit 1' ERR

# ═══════════════════════════════════════════════════════════════════════════════
# Run
# ═══════════════════════════════════════════════════════════════════════════════

main "$@"
