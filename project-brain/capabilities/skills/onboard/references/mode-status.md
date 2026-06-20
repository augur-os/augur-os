# Mode: --status

Display the current Augur installation state. Read-only, modifies nothing.

## Steps

1. **Read state file** — Load `~/Library/Application Support/Augur/state/onboard-complete.json`.
2. **Display status table**:

| Field | Source |
|-------|--------|
| Installed | Check if install dir exists |
| Install source | `install_source` from state file |
| Connected platforms | `configured_clients` from state file |
| Vault scaffolded | `vault_scaffolded` from state file |
| Dashboard status | Ping `localhost:3000` |
| MCP status | Ping `localhost:3001/health` |
| Codex MCP | Check `~/.codex/config.toml` for `[mcp_servers.augur-core]` and `[mcp_servers.augur-framework]` |
| Codex prompts | Check `~/.codex/prompts/` contains Augur prompt files |
| Codex plugin | Check `~/.codex/plugins/cache/augur-local/augur/` exists |
| Codex marketplace (global) | Check `~/.agents/plugins/marketplace.json` for augur entry |
| Codex marketplace (repo) | Check `.agents/plugins/marketplace.json` for augur entry |
| AI cloud clients | Run `python project-brain/capabilities/skills/onboard/scripts/cloud_status.py --repo-root "$(pwd)"` |
| Cloud review mode | Ready when profile, workflow/app, and required credentials are present |
| Cloud write mode | Use `--mode write` for read-only write/fix/PR prerequisite display; disabled unless the displayed client is explicitly opted in |

If no state file exists, show "Augur has not been fully onboarded. Run `/onboard` first."
