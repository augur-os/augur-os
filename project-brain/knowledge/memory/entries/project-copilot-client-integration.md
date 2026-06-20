---
title: project-copilot-client-integration
name: project-copilot-client-integration
description: Copilot CLI is Augur's 4th client (gca shortcut); how its MCP wiring
  actually works — checkout-local .mcp.json injection, NOT home config — and the two
  latent bugs that hid this
brain_scope: project
type: project
status: active
source_client: claude-code
source_file: project-copilot-client-integration.md
source_hash: 1b88a8bdb74f401a
---


GitHub Copilot CLI is a first-class Augur client since 2026-06-10 (merged to main, `f5cccc6cd`): `gca` shortcut (parity with ca/xa/ga, launches `copilot --allow-all`), sync adapters (`copilot` rules + `copilot_plugin` bundle → `.github/skills|agents|prompts`), cli_config `CopilotAdapter`, installer alias block.

**Why:** The spec assumed augur MCP servers would sync into `~/.copilot/mcp-config.json` — real-data verification disproved it: `augur-core`/`augur-framework` are `scope: project` and are NEVER exported to ANY client's home config (gemini/codex home configs have no augur entries either; codex/gemini get MCP via plugin bundles). Copilot has no plugin MCP mechanism, so `agent_launch` injects `--additional-mcp-config @.mcp.json` at exec time (`with_copilot_project_mcp`), resolving the checkout-local project config — worktree-correct by construction.

**How to apply:**
- Copilot CLI does NOT expand `${VAR}` in MCP configs and hard-fails on a missing `--additional-mcp-config` file — any config handed to it must be fully resolved (absolute paths) and existence-guarded.
- The repo-root `.mcp.json` has two writers: `aug config sync` (full, main checkouts; `generate_project_mcp_json`) and `generate-worktree-mcp.py --all` (fresh worktrees, `--client-id worktree`). Both emit resolved entries.
- Two latent bugs were exposed by rule-34 real-data verification (both fixed): `generate_project_mcp_json` was called without its required `dest` arg (crashed every full `aug config sync`; a mocked test hid it) and emitted `${AUGUR_ROOT}` templates no client reliably expands.
- `sync all copilot` expands to BOTH adapters via `_SYNC_CLIENT_EXPANSIONS` (codex precedent); the plugin-pack copilot installer prunes stale marker-bearing `.github` files (marker-checked, three roots only).
- `aug config sync` drift-removes legacy `augur-core` from `~/.claude/settings.json` (home configs carry no project-scoped servers; Claude uses `.mcp.json` + plugins). Backup: `~/.claude/settings.json.bak.20260610T093643Z`.
- Installer rc block: `unalias ca xa ga gca` precedes the function definitions — without it, oh-my-zsh git aliases (`ga`, `gca`) abort zsh rc parsing (exit 126). Markers must never change (orphans existing user blocks).

Related: [[sdlc-autonomy-aug-dev-build]], [[augur-cross-client-never-claude-only]]
