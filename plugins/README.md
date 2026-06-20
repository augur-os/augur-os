# Augur Plugins

Platform integrations and cross-client agent definitions.

- `agents/` — Subagent definitions synced to all IDE clients (Claude, Gemini, Codex, Cursor, etc.)
- `obsidian/` — Obsidian community plugin for discovering/installing Augur
- `vscode/` — VS Code extension for discovering/installing Augur
- `lib/` — Shared health check protocol

## Architecture (ADR-437)

Each plugin implements exactly 5 capabilities:

| # | Capability | Description |
|---|-----------|-------------|
| 1 | Detect    | Check if Augur is installed |
| 2 | Install   | Call install.sh --from <platform> |
| 3 | Configure | Run configure_mcp.py --client <platform> |
| 4 | Status    | Show connection health |
| 5 | Link      | Open the Augur dashboard |

## Plugins

| Platform | Directory | Format |
|----------|-----------|--------|
| Obsidian | obsidian/ | Community plugin |
| VS Code  | vscode/   | VS Code extension |

Claude Code's plugin is at `dist/plugins/augur/` (already exists).

## Health Check Protocol

All plugins use the shared protocol:

1. Check install dir exists (`~/Projects/Augur` or `$AUGUR_DIR`)
2. Check MCP server reachable (`localhost:3001/health`)
3. Check dashboard reachable (`localhost:3000`)
4. Read last sync from `~/Library/Application Support/Augur/state/`

## Development

```bash
# Obsidian plugin
cd obsidian && npm install && npm run build

# VS Code extension
cd vscode && npm install && npm run build
```
