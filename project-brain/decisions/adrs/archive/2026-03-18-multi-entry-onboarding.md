# Multi-Entry Onboarding (ADR-438) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Augur installable from any platform entry point (Claude Code, Obsidian, VS Code, Cursor) via a single `install.sh` with platform-aware flags, converging on identical installed state with per-platform post-install configuration.

**Architecture:** `install.sh` is the universal entry point. ADR-437 adds `--from <platform>`. This ADR adds `--configure <client-list>` for post-install hooks (vault scaffold, MCP config). The onboard skill (`/onboard`) becomes a wrapper: fresh install if needed, otherwise post-install configuration via `--connect` and `--status` modes. State tracked in `onboard-complete.json`.

**Tech Stack:** Bash (install.sh), Python 3.11+ (state tracking helpers), SKILL.md (agent instructions)

**Spec:** get_vault_dir()/dev/adrs/ADR-438-multi-entry-onboarding.md

---

## File Structure

### New files

| File | Responsibility |
|---|---|
| `src/scripts/onboard_state.py` | Read/write `onboard-complete.json` — CLI for install.sh to call, importable for Python tools |
| `tests/test_onboard_state.py` | Unit tests for onboard state tracking |
| `tests/test_install_configure.py` | Integration tests for `install.sh --configure` flag |

### Modified files

| File | Change |
|---|---|
| `scripts/install.sh` | Add `--configure` flag, post-install hooks, state tracking, getting-started messages |
| `.claude/skills/onboard/SKILL.md` | Add `--connect` and `--status` modes, rewrite to use install.sh internally |

---

## Task 1: Onboard State Tracking Module

**Files:**
- Create: `src/scripts/onboard_state.py`
- Test: `tests/test_onboard_state.py`
- Reference: `src/config/paths.py` (`get_state_dir()`)

- [ ] **Step 1: Write failing tests for onboard state**

```python
# tests/test_onboard_state.py
import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

# Dynamic import
_scripts_dir = Path(__file__).resolve().parent.parent / "src" / "scripts"
_spec = importlib.util.spec_from_file_location(
    "onboard_state", _scripts_dir / "onboard_state.py"
)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["onboard_state"] = _mod
_spec.loader.exec_module(_mod)

read_state = _mod.read_state
write_state = _mod.write_state
add_configured_client = _mod.add_configured_client
mark_vault_scaffolded = _mod.mark_vault_scaffolded
STATE_FILENAME = _mod.STATE_FILENAME


def test_state_filename():
    """State file is named correctly."""
    assert STATE_FILENAME == "onboard-complete.json"


def test_read_state_returns_none_when_missing(tmp_path):
    """Returns None when state file does not exist."""
    with patch.object(_mod, "_state_path", return_value=tmp_path / STATE_FILENAME):
        result = read_state()
        assert result is None


def test_write_state_creates_file(tmp_path):
    """write_state creates the JSON file with correct structure."""
    state_file = tmp_path / STATE_FILENAME
    with patch.object(_mod, "_state_path", return_value=state_file):
        write_state(install_source="obsidian", configured_clients=["obsidian"])
        assert state_file.exists()
        data = json.loads(state_file.read_text())
        assert data["install_source"] == "obsidian"
        assert data["configured_clients"] == ["obsidian"]
        assert "installed_at" in data
        assert data["vault_scaffolded"] is False
        assert data["dashboard_started"] is False


def test_add_configured_client_appends(tmp_path):
    """add_configured_client adds to existing list without duplicates."""
    state_file = tmp_path / STATE_FILENAME
    state_file.write_text(json.dumps({
        "installed_at": "2026-03-18T15:30:00Z",
        "install_source": "claude-code",
        "configured_clients": ["claude-code"],
        "vault_scaffolded": False,
        "dashboard_started": False,
    }))
    with patch.object(_mod, "_state_path", return_value=state_file):
        add_configured_client("obsidian")
        data = json.loads(state_file.read_text())
        assert "obsidian" in data["configured_clients"]
        assert "claude-code" in data["configured_clients"]
        assert len(data["configured_clients"]) == 2


def test_add_configured_client_no_duplicate(tmp_path):
    """add_configured_client does not duplicate existing client."""
    state_file = tmp_path / STATE_FILENAME
    state_file.write_text(json.dumps({
        "installed_at": "2026-03-18T15:30:00Z",
        "install_source": "claude-code",
        "configured_clients": ["claude-code"],
        "vault_scaffolded": False,
        "dashboard_started": False,
    }))
    with patch.object(_mod, "_state_path", return_value=state_file):
        add_configured_client("claude-code")
        data = json.loads(state_file.read_text())
        assert data["configured_clients"] == ["claude-code"]


def test_mark_vault_scaffolded(tmp_path):
    """mark_vault_scaffolded sets flag to true."""
    state_file = tmp_path / STATE_FILENAME
    state_file.write_text(json.dumps({
        "installed_at": "2026-03-18T15:30:00Z",
        "install_source": "obsidian",
        "configured_clients": ["obsidian"],
        "vault_scaffolded": False,
        "dashboard_started": False,
    }))
    with patch.object(_mod, "_state_path", return_value=state_file):
        mark_vault_scaffolded()
        data = json.loads(state_file.read_text())
        assert data["vault_scaffolded"] is True


def test_read_state_returns_data(tmp_path):
    """read_state returns parsed dict when file exists."""
    state_file = tmp_path / STATE_FILENAME
    expected = {
        "installed_at": "2026-03-18T15:30:00Z",
        "install_source": "vscode",
        "configured_clients": ["vscode", "claude-code"],
        "vault_scaffolded": True,
        "dashboard_started": False,
    }
    state_file.write_text(json.dumps(expected))
    with patch.object(_mod, "_state_path", return_value=state_file):
        result = read_state()
        assert result == expected


def test_write_state_creates_parent_dirs(tmp_path):
    """write_state creates parent directories if missing."""
    state_file = tmp_path / "nested" / "dir" / STATE_FILENAME
    with patch.object(_mod, "_state_path", return_value=state_file):
        write_state(install_source="claude-code", configured_clients=["claude-code"])
        assert state_file.exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Projects/Augur && uv run python -m pytest tests/test_onboard_state.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement onboard_state.py**

```python
# src/scripts/onboard_state.py
"""
Onboard state tracking for multi-entry onboarding (ADR-438).

Manages ~/Library/Application Support/Augur/state/onboard-complete.json.
CLI interface for install.sh, importable for Python tools.

Usage from bash:
    python src/scripts/onboard_state.py write --source obsidian --clients obsidian
    python src/scripts/onboard_state.py read
    python src/scripts/onboard_state.py add-client vscode
    python src/scripts/onboard_state.py mark-vault-scaffolded
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

STATE_FILENAME = "onboard-complete.json"


def _state_path() -> Path:
    """Resolve state file path via src.config.paths. Never hardcoded."""
    from src.config.paths import get_state_dir
    return get_state_dir() / STATE_FILENAME


def read_state() -> dict | None:
    """Read onboard state. Returns None if file doesn't exist."""
    path = _state_path()
    if not path.exists():
        return None
    return json.loads(path.read_text())


def write_state(
    *,
    install_source: str,
    configured_clients: list[str],
    vault_scaffolded: bool = False,
    dashboard_started: bool = False,
) -> dict:
    """Create or overwrite onboard state file.

    Args:
        install_source: Platform that triggered install (obsidian, vscode, claude-code, etc.)
        configured_clients: List of clients configured during install.
        vault_scaffolded: Whether Obsidian vault scaffold was run.
        dashboard_started: Whether dashboard has been started.

    Returns:
        The state dict that was written.
    """
    state = {
        "installed_at": datetime.now(timezone.utc).isoformat(),
        "install_source": install_source,
        "configured_clients": configured_clients,
        "vault_scaffolded": vault_scaffolded,
        "dashboard_started": dashboard_started,
    }
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2) + "\n")
    return state


def add_configured_client(client: str) -> dict:
    """Add a client to the configured_clients list. No-op if already present.

    Creates state file if it doesn't exist (uses 'unknown' as install_source).

    Returns:
        The updated state dict.
    """
    state = read_state()
    if state is None:
        return write_state(install_source="unknown", configured_clients=[client])
    clients = state.get("configured_clients", [])
    if client not in clients:
        clients.append(client)
        state["configured_clients"] = clients
        path = _state_path()
        path.write_text(json.dumps(state, indent=2) + "\n")
    return state


def mark_vault_scaffolded() -> dict:
    """Set vault_scaffolded to True in state file.

    Creates state file if it doesn't exist.

    Returns:
        The updated state dict.
    """
    state = read_state()
    if state is None:
        return write_state(
            install_source="unknown",
            configured_clients=[],
            vault_scaffolded=True,
        )
    state["vault_scaffolded"] = True
    path = _state_path()
    path.write_text(json.dumps(state, indent=2) + "\n")
    return state


def main():
    """CLI entry point for install.sh integration."""
    parser = argparse.ArgumentParser(description="Augur onboard state management")
    sub = parser.add_subparsers(dest="command", required=True)

    # write
    write_cmd = sub.add_parser("write", help="Create onboard state")
    write_cmd.add_argument("--source", required=True, help="Install source platform")
    write_cmd.add_argument(
        "--clients", required=True, help="Comma-separated configured clients"
    )

    # read
    sub.add_parser("read", help="Read onboard state (JSON to stdout)")

    # add-client
    add_cmd = sub.add_parser("add-client", help="Add a configured client")
    add_cmd.add_argument("client", help="Client name to add")

    # mark-vault-scaffolded
    sub.add_parser("mark-vault-scaffolded", help="Set vault_scaffolded=true")

    args = parser.parse_args()

    if args.command == "write":
        clients = [c.strip() for c in args.clients.split(",") if c.strip()]
        state = write_state(install_source=args.source, configured_clients=clients)
        print(json.dumps(state, indent=2))
    elif args.command == "read":
        state = read_state()
        if state is None:
            print("{}")
            sys.exit(1)
        print(json.dumps(state, indent=2))
    elif args.command == "add-client":
        state = add_configured_client(args.client)
        print(json.dumps(state, indent=2))
    elif args.command == "mark-vault-scaffolded":
        state = mark_vault_scaffolded()
        print(json.dumps(state, indent=2))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Projects/Augur && uv run python -m pytest tests/test_onboard_state.py -v`
Expected: All 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/scripts/onboard_state.py tests/test_onboard_state.py
git commit -m "feat: add onboard state tracking module (ADR-438)"
```

---

## Task 2: Add --configure Flag to install.sh

> **Prerequisite:** ADR-437 must be implemented first (adds `--from` flag and `parse_flags()` to install.sh). Verify: `grep -q 'FROM_PLATFORM' scripts/install.sh` must succeed.

> **IMPORTANT:** Before adding `--configure`, also add a `BASH_SOURCE` guard to `install.sh` so that `source install.sh` in tests doesn't trigger `main()`:
> ```bash
> if [[ "${BASH_SOURCE[0]}" == "${0}" && -z "${AUGUR_SOURCED:-}" ]]; then
>     main "$@"
> fi
> ```

**Files:**
- Modify: `scripts/install.sh`
- Test: `tests/test_install_configure.py`

- [ ] **Step 1: Write failing integration tests for --configure flag**

```python
# tests/test_install_configure.py
"""Integration tests for install.sh --configure flag.

These tests invoke install.sh functions in isolation via bash subprocess.
They do NOT run the full installer (no git clone, no deps install).
"""

import json
import subprocess
import os
from pathlib import Path
from unittest.mock import patch

INSTALL_SH = Path(__file__).resolve().parent.parent / "scripts" / "install.sh"
STATE_SCRIPT = Path(__file__).resolve().parent.parent / "src" / "scripts" / "onboard_state.py"


def test_install_sh_accepts_configure_flag():
    """install.sh --help mentions --configure."""
    result = subprocess.run(
        ["bash", "-c", f"AUGUR_SOURCED=1 source {INSTALL_SH} 2>/dev/null; parse_flags --configure obsidian; echo $CONFIGURE_CLIENTS"],
        capture_output=True, text=True, timeout=10,
    )
    assert "obsidian" in result.stdout


def test_install_sh_accepts_multiple_configure_clients():
    """--configure accepts comma-separated list."""
    result = subprocess.run(
        ["bash", "-c", f"AUGUR_SOURCED=1 source {INSTALL_SH} 2>/dev/null; parse_flags --configure obsidian,vscode; echo $CONFIGURE_CLIENTS"],
        capture_output=True, text=True, timeout=10,
    )
    assert "obsidian,vscode" in result.stdout


def test_configure_obsidian_calls_scaffold(tmp_path):
    """--configure obsidian triggers vault scaffold."""
    # Verify the configure_client function exists in install.sh
    result = subprocess.run(
        ["bash", "-c", f"grep -c 'configure_client()' {INSTALL_SH}"],
        capture_output=True, text=True, timeout=10,
    )
    assert int(result.stdout.strip()) >= 1


def test_state_written_after_configure(tmp_path):
    """Onboard state is written after --configure completes."""
    state_file = tmp_path / "onboard-complete.json"
    env = os.environ.copy()
    env["AUGUR_STATE"] = str(tmp_path)
    env["PYTHONPATH"] = str(INSTALL_SH.parent.parent)
    result = subprocess.run(
        [
            "python3", str(STATE_SCRIPT),
            "write", "--source", "obsidian", "--clients", "obsidian",
        ],
        capture_output=True, text=True, timeout=10,
        env=env,
    )
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["install_source"] == "obsidian"
    assert "obsidian" in data["configured_clients"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Projects/Augur && uv run python -m pytest tests/test_install_configure.py -v`
Expected: FAIL — `parse_flags` function not found in install.sh

- [ ] **Step 3: Add --configure flag and post-install hooks to install.sh**

Add the following sections to `scripts/install.sh`. The changes are:

1. Add `parse_flags()` function after the HELPERS section
2. Add `configure_client()` function for per-platform post-install
3. Add `write_onboard_state()` function to call `onboard_state.py`
4. Add `print_getting_started()` function for per-platform messages
5. Wire them into `main()`

**After the `check_command()` function (line ~85), add:**

```bash
# ═══════════════════════════════════════════════════════════════════════════════
# FLAG PARSING
# ═══════════════════════════════════════════════════════════════════════════════

FROM_PLATFORM=""
CONFIGURE_CLIENTS=""

parse_flags() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --from)
                FROM_PLATFORM="$2"
                shift 2
                ;;
            --configure)
                CONFIGURE_CLIENTS="$2"
                shift 2
                ;;
            *)
                shift
                ;;
        esac
    done
}
```

**After `create_virtualenv()` (line ~169), add:**

```bash
# ═══════════════════════════════════════════════════════════════════════════════
# POST-INSTALL HOOKS
# ═══════════════════════════════════════════════════════════════════════════════

configure_client() {
    local client="$1"
    print_step "Configuring for ${client}..."

    case "$client" in
        obsidian)
            # Scaffold Obsidian vault: create .obsidian/ in vault dir
            print_step "Scaffolding Obsidian vault..."
            local vault_dir
            vault_dir=$(cd "$AUGUR_DIR" && PYTHONPATH=. uv run python -c "from src.config.paths import get_vault_dir; print(get_vault_dir())" 2>/dev/null || echo "${HOME}/Projects/Au-vault")
            mkdir -p "${vault_dir}"

            # Call obsidian-scaffold via Python if MCP tools are available,
            # otherwise do minimal scaffold directly
            if [ -f "${INSTALL_DIR}/src/scripts/onboard_state.py" ]; then
                cd "$INSTALL_DIR"
                uv run python -c "
from pathlib import Path
import json

from src.config.paths import get_vault_dir; vault = get_vault_dir()
obs_dir = vault / '.obsidian'
obs_dir.mkdir(parents=True, exist_ok=True)

# app.json
app_json = obs_dir / 'app.json'
if not app_json.exists():
    app_json.write_text(json.dumps({
        'alwaysUpdateLinks': True,
        'newFileLocation': 'current',
        'attachmentFolderPath': '.attachments',
    }, indent=2) + '\n')

# appearance.json
appearance_json = obs_dir / 'appearance.json'
if not appearance_json.exists():
    appearance_json.write_text(json.dumps({
        'accentColor': '',
        'theme': 'obsidian',
    }, indent=2) + '\n')

print(f'Obsidian vault scaffolded at {obs_dir}')
" || print_warning "Obsidian scaffold failed — run '/onboard --connect obsidian' later"
                # Mark vault as scaffolded in state
                PYTHONPATH="$INSTALL_DIR" uv run python "$INSTALL_DIR/src/scripts/onboard_state.py" mark-vault-scaffolded 2>/dev/null || true
            fi
            print_success "Obsidian vault configured"
            ;;

        vscode)
            # Configure MCP for VS Code
            print_step "Configuring MCP for VS Code..."
            local vscode_dir="${HOME}/.vscode"
            mkdir -p "${vscode_dir}"
            if [ -f "${INSTALL_DIR}/src/scripts/configure_mcp.py" ]; then
                cd "$INSTALL_DIR"
                uv run python src/scripts/configure_mcp.py --apply 2>/dev/null || \
                    print_warning "VS Code MCP config failed — run 'python src/scripts/configure_mcp.py --apply' manually"
            fi
            print_success "VS Code MCP configured"
            ;;

        cursor)
            # Configure MCP for Cursor
            print_step "Configuring MCP for Cursor..."
            if [ -f "${INSTALL_DIR}/src/scripts/configure_mcp.py" ]; then
                cd "$INSTALL_DIR"
                uv run python src/scripts/configure_mcp.py --apply 2>/dev/null || \
                    print_warning "Cursor MCP config failed — run 'python src/scripts/configure_mcp.py --apply' manually"
            fi
            print_success "Cursor MCP configured"
            ;;

        claude-code)
            # Configure MCP for Claude Code (default, usually auto-configured)
            print_step "Configuring MCP for Claude Code..."
            if [ -f "${INSTALL_DIR}/src/scripts/configure_mcp.py" ]; then
                cd "$INSTALL_DIR"
                uv run python src/scripts/configure_mcp.py --apply 2>/dev/null || \
                    print_warning "Claude Code MCP config failed — run 'python src/scripts/configure_mcp.py --apply' manually"
            fi
            print_success "Claude Code MCP configured"
            ;;

        *)
            print_warning "Unknown client: ${client}. Skipping configuration."
            ;;
    esac
}

write_onboard_state() {
    local source="$1"
    local clients="$2"

    if [ -z "$source" ]; then
        source="claude-code"
    fi
    if [ -z "$clients" ]; then
        clients="$source"
    fi

    print_step "Writing onboard state..."
    if [ -f "${INSTALL_DIR}/src/scripts/onboard_state.py" ]; then
        cd "$INSTALL_DIR"
        PYTHONPATH="$INSTALL_DIR" uv run python "$INSTALL_DIR/src/scripts/onboard_state.py" \
            write --source "$source" --clients "$clients" 2>/dev/null || \
            print_warning "Failed to write onboard state"
    fi
}

print_getting_started() {
    local source="$1"
    echo ""
    print_header "Getting Started"

    case "$source" in
        obsidian)
            echo -e "Augur is installed and your vault is configured."
            echo -e "Open Obsidian and add ${CYAN}get_vault_dir()${NC} as a vault."
            echo -e "The dashboard is at ${CYAN}http://localhost:3000${NC}."
            echo ""
            echo -e "Next steps:"
            echo -e "  1. Open Obsidian → Open folder as vault → get_vault_dir()"
            echo -e "  2. Start the dashboard: ${CYAN}cd $INSTALL_DIR && pnpm --filter dashboard dev${NC}"
            echo -e "  3. Connect more platforms: ${CYAN}/onboard --connect <platform>${NC}"
            ;;

        vscode)
            echo -e "Augur is installed and MCP is configured for VS Code."
            echo -e "Open the Augur sidebar in VS Code to check status."
            echo -e "The dashboard is at ${CYAN}http://localhost:3000${NC}."
            echo ""
            echo -e "Next steps:"
            echo -e "  1. Restart VS Code to load MCP configuration"
            echo -e "  2. Start the dashboard: ${CYAN}cd $INSTALL_DIR && pnpm --filter dashboard dev${NC}"
            echo -e "  3. Connect more platforms: ${CYAN}/onboard --connect <platform>${NC}"
            ;;

        cursor)
            echo -e "Augur is installed and MCP is configured for Cursor."
            echo -e "Open the Augur sidebar in Cursor to check status."
            echo -e "The dashboard is at ${CYAN}http://localhost:3000${NC}."
            echo ""
            echo -e "Next steps:"
            echo -e "  1. Restart Cursor to load MCP configuration"
            echo -e "  2. Start the dashboard: ${CYAN}cd $INSTALL_DIR && pnpm --filter dashboard dev${NC}"
            echo -e "  3. Connect more platforms: ${CYAN}/onboard --connect <platform>${NC}"
            ;;

        claude-code|*)
            echo -e "Augur is installed."
            echo -e "Run ${CYAN}/commands${NC} to see available commands."
            echo -e "The dashboard is at ${CYAN}http://localhost:3000${NC}."
            echo ""
            echo -e "Next steps:"
            echo -e "  1. Run ${CYAN}/commands${NC} to explore available skills"
            echo -e "  2. Start the dashboard: ${CYAN}cd $INSTALL_DIR && pnpm --filter dashboard dev${NC}"
            echo -e "  3. Connect more platforms: ${CYAN}/onboard --connect <platform>${NC}"
            ;;
    esac
    echo ""
}
```

**Modify the `main()` function.** At the very start of `main()`, add flag parsing:

```bash
main() {
    # Parse flags first (--from, --configure)
    parse_flags "$@"

    print_header "Augur Installer"
    # ... existing code unchanged through run_tests ...
```

**Replace the end of `main()`** (everything after `run_tests` through the closing `}`). Replace the existing setup wizard / OAuth / "Next steps" block:

```bash
    # ─────────────────────────────────────────────────────────────────────────
    # Run setup wizard (skip if --configure was passed — non-interactive mode)
    # ─────────────────────────────────────────────────────────────────────────

    if [ -z "$CONFIGURE_CLIENTS" ]; then
        print_step "Running setup wizard..."
        echo ""
        SETUP_SCRIPT="${INSTALL_DIR}/plugins/dev/skills/devops/scripts/setup_wizard.py"

        if [ -f "$SETUP_SCRIPT" ]; then
            uv run python "$SETUP_SCRIPT"
        else
            print_warning "Setup wizard script not found: $SETUP_SCRIPT"
            print_step "Skipping setup wizard — you can run it manually later"
        fi

        # Configure LLM providers
        OAUTH_SCRIPT="${INSTALL_DIR}/plugins/dev/skills/devops/scripts/oauth_wizard.py"
        if [ -f "$OAUTH_SCRIPT" ]; then
            print_step "Configuring LLM providers..."
            uv run python "$OAUTH_SCRIPT" || print_warning "Provider setup skipped or failed — you can run it later"
        fi
    fi

    # ─────────────────────────────────────────────────────────────────────────
    # Post-install: configure clients (--configure flag)
    # ─────────────────────────────────────────────────────────────────────────

    if [ -n "$CONFIGURE_CLIENTS" ]; then
        IFS=',' read -ra CLIENTS <<< "$CONFIGURE_CLIENTS"
        for client in "${CLIENTS[@]}"; do
            configure_client "$(echo "$client" | xargs)"  # trim whitespace
        done
    fi

    # ─────────────────────────────────────────────────────────────────────────
    # Write onboard state
    # ─────────────────────────────────────────────────────────────────────────

    write_onboard_state "$FROM_PLATFORM" "$CONFIGURE_CLIENTS"

    # ─────────────────────────────────────────────────────────────────────────
    # Getting-started message (per platform)
    # ─────────────────────────────────────────────────────────────────────────

    print_success "Environment ready."
    print_getting_started "${FROM_PLATFORM:-claude-code}"
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Projects/Augur && uv run python -m pytest tests/test_install_configure.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Manual smoke test**

Test the flag parsing works in isolation (does NOT run the full installer):

```bash
cd ~/Projects/Augur && bash -c 'source scripts/install.sh 2>/dev/null; parse_flags --from obsidian --configure obsidian; echo "FROM=$FROM_PLATFORM CONFIGURE=$CONFIGURE_CLIENTS"'
```

Expected output: `FROM=obsidian CONFIGURE=obsidian`

- [ ] **Step 6: Commit**

```bash
git add scripts/install.sh tests/test_install_configure.py
git commit -m "feat: add --configure flag and post-install hooks to install.sh (ADR-438)"
```

---

## Task 3: Platform-Specific Post-Install Hooks

**Files:**
- Modify: `scripts/install.sh` (the `configure_client()` function added in Task 2)
- Test: `tests/test_install_configure.py` (add hook-specific tests)

This task validates that each platform hook does what it claims. The `configure_client()` function was added in Task 2 — this task adds targeted tests.

- [ ] **Step 1: Add tests for obsidian vault scaffold hook**

Append to `tests/test_install_configure.py`:

```python
def test_obsidian_scaffold_creates_dot_obsidian(tmp_path):
    """Obsidian scaffold creates .obsidian/ with app.json and appearance.json."""
    vault_dir = tmp_path / "Vault" / "Augur"
    vault_dir.mkdir(parents=True)

    result = subprocess.run(
        [
            "python3", "-c", f"""
import json
from pathlib import Path

vault = Path("{vault_dir}")
obs_dir = vault / '.obsidian'
obs_dir.mkdir(parents=True, exist_ok=True)

app_json = obs_dir / 'app.json'
app_json.write_text(json.dumps({{
    'alwaysUpdateLinks': True,
    'newFileLocation': 'current',
    'attachmentFolderPath': '.attachments',
}}, indent=2) + '\\n')

appearance_json = obs_dir / 'appearance.json'
appearance_json.write_text(json.dumps({{
    'accentColor': '',
    'theme': 'obsidian',
}}, indent=2) + '\\n')

print('OK')
""",
        ],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0
    assert (vault_dir / ".obsidian" / "app.json").exists()
    assert (vault_dir / ".obsidian" / "appearance.json").exists()

    app_data = json.loads((vault_dir / ".obsidian" / "app.json").read_text())
    assert app_data["alwaysUpdateLinks"] is True
    assert app_data["attachmentFolderPath"] == ".attachments"


def test_obsidian_scaffold_idempotent(tmp_path):
    """Running scaffold twice does not overwrite existing config."""
    vault_dir = tmp_path / "Vault" / "Augur"
    obs_dir = vault_dir / ".obsidian"
    obs_dir.mkdir(parents=True)

    # Write custom config first
    custom = {"customSetting": True}
    (obs_dir / "app.json").write_text(json.dumps(custom))

    # Run scaffold — should NOT overwrite
    subprocess.run(
        [
            "python3", "-c", f"""
import json
from pathlib import Path

vault = Path("{vault_dir}")
obs_dir = vault / '.obsidian'
obs_dir.mkdir(parents=True, exist_ok=True)

app_json = obs_dir / 'app.json'
if not app_json.exists():
    app_json.write_text(json.dumps({{
        'alwaysUpdateLinks': True,
    }}, indent=2) + '\\n')
""",
        ],
        capture_output=True, text=True, timeout=10,
    )

    # Custom config preserved
    data = json.loads((obs_dir / "app.json").read_text())
    assert data == custom
```

- [ ] **Step 2: Run tests**

Run: `cd ~/Projects/Augur && uv run python -m pytest tests/test_install_configure.py -v`
Expected: All tests PASS (scaffold creates files, idempotent behavior verified)

- [ ] **Step 3: Commit**

```bash
git add tests/test_install_configure.py
git commit -m "test: add post-install hook tests for obsidian scaffold (ADR-438)"
```

---

## Task 4: Redesign Onboard SKILL.md with --connect and --status Modes

**Files:**
- Modify: `.claude/skills/onboard/SKILL.md`

The onboard skill is agent instructions (not code). This task rewrites the SKILL.md to:
1. Add `--connect <platform>` and `--status` modes
2. Wire the default mode to call `install.sh` internally
3. Add per-platform getting-started instructions

- [ ] **Step 1: Rewrite SKILL.md**

Replace the entire contents of `.claude/skills/onboard/SKILL.md` with:

```markdown
---
name: onboard
description: Setup wizard for fresh installs, platform connections, and install status. Use --connect
  to add platforms, --status to check state, --migrate for upgrades.
x-augur-visibility: core
x-augur-hub: command
x-augur-tab: system
x-augur-master: claude-code
x-augur-plugin: augur
---

# /onboard

## Augur Onboarding — Multi-Entry Setup

## Usage

- `/onboard` — Interactive step-by-step setup (default, fresh install via Claude Code)
- `/onboard --connect <platform>` — Add a platform to existing install (obsidian, vscode, cursor)
- `/onboard --status` — Show install state and connected platforms
- `/onboard --migrate` — Migration-focused onboarding for existing installations
- `/onboard --full` — Complete onboarding: fresh install + migration + verification

## Options

| Flag | Description |
|------|-------------|
| `--help` | Show usage and stop |
| `--evolve` | Trigger skill self-improvement |
| `--connect <platform>` | Connect a new platform to existing install |
| `--status` | Show onboard state: install source, configured clients, vault status |
| `--migrate` | Run migration-focused onboarding (legacy paths, vault migration, plugin verification) |
| `--full` | Run complete onboarding (fresh install + migration + verification) |

## Mode Selection

Parse arguments to determine mode:

| Argument | Mode | What runs |
|----------|------|-----------|
| *(none)* | default | Check if installed. If not: run full install. If yes: show status + offer --connect |
| `--connect <platform>` | connect | Add platform to existing install via `configure_client()` hooks |
| `--status` | status | Read `onboard-complete.json`, display state |
| `--migrate` | migrate | Legacy data migration (unchanged from previous behavior) |
| `--full` | full | Fresh install + migration + verification |

---

### Mode: default (`/onboard`)

1. **Check if Augur is already installed** — Read `onboard-complete.json` via:
   ```bash
   cd "$(git rev-parse --show-toplevel)" && PYTHONPATH=. uv run python src/scripts/onboard_state.py read
   ```
   If the command exits 0 and returns valid JSON, Augur is installed.

2. **If NOT installed** — Run the full interactive setup:

   #### Step 1: Clone Repository
   ```bash
   mkdir -p ~/Projects && cd ~/Projects
   git clone https://github.com/gsannikov/augur.git Augur
   cd Augur
   ```

   #### Step 2: Configure Git Hooks
   ```bash
   git config core.hooksPath .githooks
   ```

   #### Step 3: Install Dependencies
   ```bash
   corepack enable
   pnpm install
   uv sync
   ```

   #### Step 4: Configure IDE (Automatic)
   MCP is auto-configured when you start the dashboard. Manual:
   ```bash
   python3 src/scripts/configure_mcp.py --apply
   ```

   #### Step 5: Start Dashboard
   ```bash
   pnpm --filter dashboard dev
   ```

   #### Step 6: Write Onboard State
   ```bash
   PYTHONPATH=. uv run python src/scripts/onboard_state.py write --source claude-code --clients claude-code
   ```

   #### Step 7: Verify Setup
   Run the Post-Onboarding Checklist (below).

3. **If already installed** — Show status and offer options:
   ```
   Augur is already installed (source: <install_source>).
   Connected platforms: <configured_clients>
   Vault scaffolded: <yes/no>

   Options:
   - /onboard --connect obsidian  — add Obsidian vault integration
   - /onboard --connect vscode    — configure MCP for VS Code
   - /onboard --connect cursor    — configure MCP for Cursor
   - /onboard --status            — show full install state
   - /onboard --migrate           — run migration checks
   ```

---

### Mode: `--connect <platform>`

Connect a new platform to an existing Augur installation. Supported platforms: `obsidian`, `vscode`, `cursor`, `claude-code`.

1. **Verify Augur is installed** — Read state. If not installed, tell user to run `/onboard` first.

2. **Run platform-specific configuration:**

   **obsidian:**
   - Scaffold Obsidian vault (create `.obsidian/` in `get_vault_dir()/`):
     ```bash
     cd ~/Projects/Augur && uv run python -c "
     from pathlib import Path
     import json
     from src.config.paths import get_vault_dir; vault = get_vault_dir()
     obs_dir = vault / '.obsidian'
     obs_dir.mkdir(parents=True, exist_ok=True)
     app_json = obs_dir / 'app.json'
     if not app_json.exists():
         app_json.write_text(json.dumps({
             'alwaysUpdateLinks': True,
             'newFileLocation': 'current',
             'attachmentFolderPath': '.attachments',
         }, indent=2) + '\n')
     appearance_json = obs_dir / 'appearance.json'
     if not appearance_json.exists():
         appearance_json.write_text(json.dumps({
             'accentColor': '',
             'theme': 'obsidian',
         }, indent=2) + '\n')
     print(f'Obsidian vault scaffolded at {obs_dir}')
     "
     ```
   - Mark vault scaffolded:
     ```bash
     PYTHONPATH=. uv run python src/scripts/onboard_state.py mark-vault-scaffolded
     ```
   - Tell user: "Open Obsidian -> Open folder as vault -> get_vault_dir()"

   **vscode:**
   - Configure MCP for VS Code:
     ```bash
     python3 src/scripts/configure_mcp.py --apply
     ```
   - Tell user: "Restart VS Code to load MCP configuration."

   **cursor:**
   - Configure MCP for Cursor:
     ```bash
     python3 src/scripts/configure_mcp.py --apply
     ```
   - Tell user: "Restart Cursor to load MCP configuration."

   **claude-code:**
   - Configure MCP for Claude Code:
     ```bash
     python3 src/scripts/configure_mcp.py --apply
     ```
   - Tell user: "MCP configured. Run `/commands` to explore."

3. **Update state** — Add the platform to configured_clients:
   ```bash
   PYTHONPATH=. uv run python src/scripts/onboard_state.py add-client <platform>
   ```

4. **Show getting-started message** for the connected platform.

---

### Mode: `--status`

Read and display the onboard state.

1. **Read state:**
   ```bash
   cd "$(git rev-parse --show-toplevel)" && PYTHONPATH=. uv run python src/scripts/onboard_state.py read
   ```

2. **Display formatted output:**

   ```
   Augur Install Status
   ────────────────────
   Installed:          <installed_at>
   Install source:     <install_source>
   Connected clients:  <configured_clients, comma-separated>
   Vault scaffolded:   <yes/no>
   Dashboard started:  <yes/no>
   ```

3. **If state file doesn't exist** (exit code 1):
   ```
   Augur is not installed. Run /onboard to set up.
   ```

---

### Mode: `--migrate`

Run when upgrading an existing Augur installation to the current structure. Skip clone/install steps.

1. **Detect legacy data** — Scan for data in deprecated paths:
   - `plugins/` (pre-ADR-426 skill locations)
   - `.agent/workflows/` (pre-skill workflow files)
   - `config/dashboard/*.yaml` (centralized config, should be decentralized per ADR-163)
   - Old vault paths that don't match `get_vault_dir()/` layout

2. **Migrate to vault** — Move user-editable data (memory, actions, skill data) to `get_vault_dir()/` following ADR-270 external directory layout. Use `src.config.paths` for path resolution, never hardcode.

3. **Verify plugin structure** — Confirm skills are in `.claude/skills/{skill}/` per ADR-426/ADR-430. Flag any skills still in legacy `plugins/` directories.

4. **Verify MCP wiring** — Run `python3 src/scripts/configure_mcp.py --apply` to ensure IDE integration is current.

5. **Run Post-Onboarding Checklist** (below).

### Mode: `--full`

Run for a complete setup that also handles migration. Executes all default steps (1-7) followed by all `--migrate` steps, then the Post-Onboarding Checklist.

---

## Getting-Started Messages

After completing any mode, show the appropriate platform message:

| Platform | Message |
|----------|---------|
| claude-code | "Augur is installed. Run `/commands` to see available commands, or open `localhost:3000` for the dashboard." |
| obsidian | "Augur is installed and your vault is configured. Open Obsidian and add get_vault_dir() as a vault. The dashboard is at localhost:3000." |
| vscode | "Augur is installed and MCP is configured. Restart VS Code to load configuration. The dashboard is at localhost:3000." |
| cursor | "Augur is installed and MCP is configured. Restart Cursor to load configuration. The dashboard is at localhost:3000." |

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `python` not found | Use `python3` on macOS/Linux |
| Claude Desktop doesn't show MCP | Restart Claude Desktop after running configure_mcp.py |
| Dashboard build fails | Run `pnpm install` again, check Node version (20+) |
| Permission denied (Python) | Run `uv sync` instead of pip |
| `onboard-complete.json` not found | Run `/onboard` to create initial state |
| `--connect` fails for obsidian | Ensure `get_vault_dir()/` exists and is writable |

## Post-Onboarding Checklist

- [ ] Repository cloned
- [ ] Git hooks configured (`git config core.hooksPath .githooks`)
- [ ] Dependencies installed (pnpm + uv)
- [ ] IDE integration configured (Claude Desktop/Claude Code CLI/Cursor)
- [ ] Dashboard running at localhost:3000
- [ ] MCP tools visible in IDE (`claude mcp list` for Claude Code CLI)
- [ ] Onboard state written (`onboard-complete.json` exists)
```

- [ ] **Step 2: Verify SKILL.md frontmatter is valid YAML**

```bash
cd ~/Projects/Augur && python3 -c "
import yaml
from pathlib import Path
content = Path('.claude/skills/onboard/SKILL.md').read_text()
_, fm, _ = content.split('---', 2)
data = yaml.safe_load(fm)
assert data['name'] == 'onboard'
assert 'connect' in data['description'] or 'connections' in data['description']
print('SKILL.md frontmatter valid')
"
```

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/onboard/SKILL.md
git commit -m "feat: redesign onboard SKILL.md with --connect and --status modes (ADR-438)"
```

---

## Task 5: Getting-Started Messages per Platform

**Files:**
- Already implemented in `scripts/install.sh` (Task 2, `print_getting_started()`)
- Already implemented in `.claude/skills/onboard/SKILL.md` (Task 4, Getting-Started Messages table)

This task validates that the messages are correct and consistent between install.sh and the onboard skill.

- [ ] **Step 1: Verify install.sh messages match SKILL.md messages**

```bash
cd ~/Projects/Augur && bash -c '
# Extract getting-started cases from install.sh
grep -A3 "obsidian)" scripts/install.sh | head -5
grep -A3 "vscode)" scripts/install.sh | head -5
grep -A3 "cursor)" scripts/install.sh | head -5
grep -A3 "claude-code)" scripts/install.sh | head -5
'
```

Verify each platform mentions:
- obsidian: vault path, "Open Obsidian", dashboard URL
- vscode: "MCP is configured", "Restart VS Code", dashboard URL
- cursor: "MCP is configured", "Restart Cursor", dashboard URL
- claude-code: `/commands`, dashboard URL

- [ ] **Step 2: No separate commit needed** — messages are part of Tasks 2 and 4.

---

## Task 6: Integration Tests

**Files:**
- Modify: `tests/test_install_configure.py` (add end-to-end scenario tests)
- Modify: `tests/test_onboard_state.py` (add CLI integration tests)

- [ ] **Step 1: Add end-to-end scenario tests**

Append to `tests/test_install_configure.py`:

```python
def test_end_to_end_obsidian_flow(tmp_path):
    """Simulate: install.sh --from obsidian --configure obsidian.

    Verifies state file is created with correct source and client.
    """
    env = os.environ.copy()
    env["AUGUR_STATE"] = str(tmp_path)
    env["PYTHONPATH"] = str(INSTALL_SH.parent.parent)

    # Step 1: Write state (simulates what install.sh does after install)
    result = subprocess.run(
        [
            "python3", str(STATE_SCRIPT),
            "write", "--source", "obsidian", "--clients", "obsidian",
        ],
        capture_output=True, text=True, timeout=10,
        env=env,
    )
    assert result.returncode == 0

    # Step 2: Mark vault scaffolded (simulates configure_client obsidian)
    result = subprocess.run(
        [
            "python3", str(STATE_SCRIPT),
            "mark-vault-scaffolded",
        ],
        capture_output=True, text=True, timeout=10,
        env=env,
    )
    assert result.returncode == 0

    # Step 3: Read back and verify
    result = subprocess.run(
        [
            "python3", str(STATE_SCRIPT),
            "read",
        ],
        capture_output=True, text=True, timeout=10,
        env=env,
    )
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["install_source"] == "obsidian"
    assert "obsidian" in data["configured_clients"]
    assert data["vault_scaffolded"] is True


def test_end_to_end_vscode_flow(tmp_path):
    """Simulate: install.sh --from vscode --configure vscode.

    Verifies state file is created with correct source and client.
    """
    env = os.environ.copy()
    env["AUGUR_STATE"] = str(tmp_path)
    env["PYTHONPATH"] = str(INSTALL_SH.parent.parent)

    # Write state
    result = subprocess.run(
        [
            "python3", str(STATE_SCRIPT),
            "write", "--source", "vscode", "--clients", "vscode",
        ],
        capture_output=True, text=True, timeout=10,
        env=env,
    )
    assert result.returncode == 0

    # Read back
    result = subprocess.run(
        ["python3", str(STATE_SCRIPT), "read"],
        capture_output=True, text=True, timeout=10,
        env=env,
    )
    data = json.loads(result.stdout)
    assert data["install_source"] == "vscode"
    assert data["configured_clients"] == ["vscode"]
    assert data["vault_scaffolded"] is False


def test_connect_adds_client_to_existing(tmp_path):
    """Simulate: /onboard --connect obsidian on existing claude-code install."""
    env = os.environ.copy()
    env["AUGUR_STATE"] = str(tmp_path)
    env["PYTHONPATH"] = str(INSTALL_SH.parent.parent)

    # Initial install from claude-code
    subprocess.run(
        [
            "python3", str(STATE_SCRIPT),
            "write", "--source", "claude-code", "--clients", "claude-code",
        ],
        capture_output=True, text=True, timeout=10,
        env=env,
    )

    # Connect obsidian
    subprocess.run(
        [
            "python3", str(STATE_SCRIPT),
            "add-client", "obsidian",
        ],
        capture_output=True, text=True, timeout=10,
        env=env,
    )

    # Mark vault scaffolded
    subprocess.run(
        [
            "python3", str(STATE_SCRIPT),
            "mark-vault-scaffolded",
        ],
        capture_output=True, text=True, timeout=10,
        env=env,
    )

    # Verify final state
    result = subprocess.run(
        ["python3", str(STATE_SCRIPT), "read"],
        capture_output=True, text=True, timeout=10,
        env=env,
    )
    data = json.loads(result.stdout)
    assert data["install_source"] == "claude-code"
    assert set(data["configured_clients"]) == {"claude-code", "obsidian"}
    assert data["vault_scaffolded"] is True


def test_status_on_fresh_machine(tmp_path):
    """Simulate: /onboard --status on machine with no install."""
    env = os.environ.copy()
    env["AUGUR_STATE"] = str(tmp_path)
    env["PYTHONPATH"] = str(INSTALL_SH.parent.parent)

    result = subprocess.run(
        ["python3", str(STATE_SCRIPT), "read"],
        capture_output=True, text=True, timeout=10,
        env=env,
    )
    # Exit code 1 when no state file
    assert result.returncode == 1
    assert result.stdout.strip() == "{}"
```

- [ ] **Step 2: Add CLI integration tests for onboard_state.py**

Append to `tests/test_onboard_state.py`:

```python
def test_cli_write_and_read(tmp_path):
    """CLI write then read round-trips correctly."""
    import subprocess, os
    env = os.environ.copy()
    env["AUGUR_STATE"] = str(tmp_path)
    env["PYTHONPATH"] = str(Path(__file__).resolve().parent.parent)
    script = str(Path(__file__).resolve().parent.parent / "src" / "scripts" / "onboard_state.py")

    # Write
    result = subprocess.run(
        ["python3", script, "write", "--source", "cursor", "--clients", "cursor"],
        capture_output=True, text=True, timeout=10, env=env,
    )
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["install_source"] == "cursor"

    # Read
    result = subprocess.run(
        ["python3", script, "read"],
        capture_output=True, text=True, timeout=10, env=env,
    )
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["install_source"] == "cursor"
    assert data["configured_clients"] == ["cursor"]


def test_cli_add_client(tmp_path):
    """CLI add-client appends to existing state."""
    import subprocess, os
    env = os.environ.copy()
    env["AUGUR_STATE"] = str(tmp_path)
    env["PYTHONPATH"] = str(Path(__file__).resolve().parent.parent)
    script = str(Path(__file__).resolve().parent.parent / "src" / "scripts" / "onboard_state.py")

    # Write initial
    subprocess.run(
        ["python3", script, "write", "--source", "claude-code", "--clients", "claude-code"],
        capture_output=True, text=True, timeout=10, env=env,
    )

    # Add client
    result = subprocess.run(
        ["python3", script, "add-client", "vscode"],
        capture_output=True, text=True, timeout=10, env=env,
    )
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert set(data["configured_clients"]) == {"claude-code", "vscode"}
```

- [ ] **Step 3: Run all tests**

Run: `cd ~/Projects/Augur && uv run python -m pytest tests/test_onboard_state.py tests/test_install_configure.py -v`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_onboard_state.py tests/test_install_configure.py
git commit -m "test: add integration tests for multi-entry onboarding (ADR-438)"
```

---

## Completion Criteria

- [ ] `scripts/install.sh` accepts `--configure <client-list>` flag
- [ ] `scripts/install.sh --from obsidian --configure obsidian` scaffolds vault and writes state
- [ ] `scripts/install.sh --from vscode --configure vscode` configures MCP and writes state
- [ ] `onboard-complete.json` created at `~/Library/Application Support/Augur/state/` with correct schema
- [ ] `src/scripts/onboard_state.py` CLI works: `write`, `read`, `add-client`, `mark-vault-scaffolded`
- [ ] `/onboard --status` instructions in SKILL.md show install state from `onboard-complete.json`
- [ ] `/onboard --connect obsidian` instructions in SKILL.md add Obsidian to existing install
- [ ] Getting-started message varies by platform (obsidian/vscode/cursor/claude-code)
- [ ] All tests pass: `uv run python -m pytest tests/test_onboard_state.py tests/test_install_configure.py -v`
- [ ] Setup wizard and OAuth wizard are skipped when `--configure` is passed (non-interactive mode)
