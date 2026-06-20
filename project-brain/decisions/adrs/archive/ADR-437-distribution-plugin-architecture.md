---
status: Implemented
date: 2026-03-18
deciders:
  - Gur Sannikov
related:
  - ADR-436
  - ADR-438
hub: system
tags:
  - distribution
  - plugins
  - obsidian
  - vscode
  - onboarding
superseded_by: null
---

# ADR-437: Distribution Plugin Architecture [RECONSTRUCTED]

## Context

Augur was only installable via `git clone` and manual configuration. Users discovering Augur through Obsidian or VS Code had no way to install or connect from within their tool. There was no standardized contract for platform-native plugins, and no mechanism to track which platform triggered an installation.

## Decision

Create thin distribution plugins for Obsidian and VS Code that detect, install, configure, and monitor Augur from within each platform. Every plugin implements exactly five capabilities:

| # | Capability | Description |
|---|-----------|-------------|
| 1 | **Detect** | Check if Augur is installed (`~/Projects/Augur` or `$AUGUR_DIR`) |
| 2 | **Install** | Run `scripts/install.sh --from <platform>` if not installed |
| 3 | **Configure** | Run `scripts/configure_mcp.py --client <platform>` to wire MCP |
| 4 | **Status** | Show connection health (MCP server, dashboard, last sync) |
| 5 | **Link** | Open dashboard at `localhost:3000` |

### Shared Health Check Protocol

All plugins use the same health check sequence:
1. Check install dir exists (`~/Projects/Augur` or `$AUGUR_DIR`)
2. Ping MCP server at `localhost:3001/health`
3. Ping dashboard at `localhost:3000`
4. Read last sync timestamp from `~/Library/Application Support/Augur/state/`

This is implemented as a shared TypeScript library at `dist/platform-plugins/lib/health.ts`.

### Install Source Tracking

The `install.sh` script accepts a `--from <platform>` flag and writes install source metadata to `~/Library/Application Support/Augur/state/install-source.json`, recording the originating platform, timestamp, install directory, and installer version.

### Plugin Implementations

- **Obsidian**: Community plugin at `dist/platform-plugins/obsidian/` with a status panel view, ribbon icon, and commands for install/status/dashboard
- **VS Code**: Extension at `dist/platform-plugins/vscode/` with a sidebar webview provider, status bar item, and commands for install/status/dashboard

Plugins are intentionally thin distribution wrappers -- they do NOT execute skills, run AI, or duplicate Augur functionality.

## Consequences

### Positive

- Augur is discoverable and installable from Obsidian and VS Code marketplaces
- Single health check protocol ensures consistent status reporting across all platforms
- Install source tracking enables platform-specific post-install configuration
- Five-capability contract makes adding new platform plugins straightforward

### Negative

- Obsidian and VS Code plugins must be maintained alongside Augur core
- Health check library is currently inlined in each plugin (no shared module import in Obsidian plugin API)
- macOS-specific install flow (Terminal.app via AppleScript in Obsidian)

### Neutral

- Claude Code's plugin already exists at `dist/plugins/augur/` and is unaffected
- Health check uses localhost HTTP pings, which work regardless of platform

## Alternatives Considered

### Alternative 1: Single Install Script Without Platform Plugins

Keep `git clone` as the only install path, with platform-specific post-install scripts.

**Rejected because**: Users in Obsidian/VS Code would never discover Augur. The plugins serve as distribution and discovery mechanisms, not just installers.

### Alternative 2: Full-Feature Platform Plugins

Build rich plugins with AI execution, skill browsing, and knowledge access.

**Rejected because**: Duplicating Augur functionality in each platform is unsustainable. The thin-plugin + fat-MCP architecture keeps plugins simple and pushes all logic to the MCP server.

## References

- Implementation plan: `docs/superpowers/plans/2026-03-18-distribution-plugins.md`
- Platform plugins: `dist/platform-plugins/README.md`
- Shared health lib: `dist/platform-plugins/lib/health.ts`
- ADR-436: Obsidian Vault Integration
- ADR-438: Multi-Entry Onboarding

## Impact Manifest

```yaml
impact:
  paths_renamed: []
  apis_changed:
    - "scripts/install.sh gains --from <platform> flag"
  patterns_deprecated: []
  files_affected:
    - "scripts/install.sh"
    - "dist/platform-plugins/lib/health.ts"
    - "dist/platform-plugins/obsidian/manifest.json"
    - "dist/platform-plugins/obsidian/src/main.ts"
    - "dist/platform-plugins/vscode/package.json"
    - "dist/platform-plugins/vscode/src/extension.ts"
    - "dist/platform-plugins/README.md"
```
