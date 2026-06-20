---
status: Implemented
date: 2026-03-18
deciders:
  - Gur Sannikov
related:
  - ADR-437
  - ADR-436
  - ADR-270
hub: system
tags:
  - onboarding
  - install
  - multi-platform
  - obsidian
  - vscode
superseded_by: null
---

# ADR-438: Multi-Entry Onboarding [RECONSTRUCTED]

## Context

Augur's onboarding assumed a single entry point: Claude Code via `git clone`. With ADR-437 introducing distribution plugins for Obsidian and VS Code, users can now arrive from multiple platforms. Each platform needs different post-install configuration (vault scaffold for Obsidian, MCP wiring for VS Code/Cursor), and the onboard skill had no concept of connecting additional platforms to an existing installation. There was no state tracking for onboarding completion.

## Decision

Make Augur installable from any platform entry point (Claude Code, Obsidian, VS Code, Cursor) via a single `install.sh` with platform-aware flags, converging on identical installed state with per-platform post-install configuration.

### Install Script Enhancement

`install.sh` gains a `--configure <client-list>` flag (in addition to ADR-437's `--from <platform>`) for per-platform post-install hooks:

- **obsidian**: Scaffolds `.obsidian/` in the vault, marks vault as scaffolded in state
- **vscode**: Configures MCP for VS Code via `configure_mcp.py`
- **cursor**: Configures MCP for Cursor via `configure_mcp.py`
- **claude-code**: Configures MCP for Claude Code (usually auto-configured)

When `--configure` is passed, the setup wizard and OAuth wizard are skipped (non-interactive mode).

### Onboard State Tracking

A new `src/scripts/onboard_state.py` module manages `~/Library/Application Support/Augur/state/onboard-complete.json` with:

- `installed_at` -- ISO timestamp
- `install_source` -- platform that triggered install
- `configured_clients` -- list of configured platforms
- `vault_scaffolded` -- whether Obsidian vault was set up
- `dashboard_started` -- whether dashboard has been started

The module is both importable for Python tools and callable as a CLI for `install.sh` integration: `write`, `read`, `add-client`, `mark-vault-scaffolded`.

### Onboard Skill Modes

The `/onboard` skill gains new modes:

| Mode | Flag | Behavior |
|------|------|----------|
| default | *(none)* | Check if installed; if not, run full install; if yes, show status + offer `--connect` |
| connect | `--connect <platform>` | Add a platform to existing install |
| status | `--status` | Read and display `onboard-complete.json` |
| migrate | `--migrate` | Legacy data migration |
| full | `--full` | Fresh install + migration + verification |

### Platform-Specific Getting-Started Messages

After install, users see messages tailored to their entry platform (vault path for Obsidian, "restart IDE" for VS Code/Cursor, `/commands` for Claude Code).

## Consequences

### Positive

- Users arriving from any platform get a consistent, complete installation
- Connecting additional platforms to an existing install is a single command (`/onboard --connect obsidian`)
- Onboard state tracking enables status checks and prevents duplicate installations
- Non-interactive mode allows automated installation from platform plugins

### Negative

- `install.sh` complexity increases with per-platform hooks
- State file at `~/Library/Application Support/Augur/state/` is macOS-specific (XDG fallback exists for Linux)
- Platform-specific messages must be kept in sync between `install.sh` and SKILL.md

### Neutral

- The `/onboard` default mode remains backward-compatible (interactive setup for Claude Code)
- State file schema is simple JSON, readable by any tool

## Alternatives Considered

### Alternative 1: Separate Install Scripts Per Platform

Create `install-obsidian.sh`, `install-vscode.sh`, etc.

**Rejected because**: Duplicates 90% of the install logic. Platform-specific configuration is a small layer on top of the universal install, best handled by flags.

### Alternative 2: Platform Detection Without State Tracking

Auto-detect installed platforms without persisting state.

**Rejected because**: Auto-detection is fragile (different IDE config paths across OS versions) and provides no history. Explicit state tracking is more reliable and enables the `--status` mode.

## References

- Implementation plan: `docs/superpowers/plans/2026-03-18-multi-entry-onboarding.md`
- Onboard skill: `.claude/skills/onboard/SKILL.md`
- State module: `src/scripts/onboard_state.py`
- ADR-437: Distribution Plugin Architecture (`--from` flag)
- ADR-436: Obsidian Vault Integration (vault scaffold)

## Impact Manifest

```yaml
impact:
  paths_renamed: []
  apis_changed:
    - "scripts/install.sh gains --configure <client-list> flag"
    - "/onboard gains --connect, --status modes"
  patterns_deprecated: []
  files_affected:
    - "scripts/install.sh"
    - "src/scripts/onboard_state.py"
    - ".claude/skills/onboard/SKILL.md"
```
