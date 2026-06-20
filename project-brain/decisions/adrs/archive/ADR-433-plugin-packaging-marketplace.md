---
status: Implemented
date: 2026-03-17
deciders:
  - Gur Sannikov
related:
  - ADR-430
  - ADR-431
  - ADR-432
hub: dev
tags:
  - plugins
  - packaging
  - marketplace
  - distribution
superseded_by: null
---

# ADR-433: Plugin Distribution — Packaging & Marketplace

> Sub-ADR of ADR-430. Phase 3. Embarrassingly parallel — 9 independent packaging tasks.

## Context

ADR-431 cleaned up skill directories. ADR-432 migrated metadata and updated framework integration. This sub-ADR packages the cleaned, standardized skills into 8 Claude Code plugins and creates the marketplace manifest.

## Decision

Execute Phase 3 (plugin packaging, 9 steps) from ADR-430. All steps are fully parallel.

**Prerequisite**: ADR-432 must be Implemented (framework reads from plugin cache dirs).

## Implementation Prompt

**Team name**: `adr-433-packaging`

### Gate 0: Pre-flight
Verify ADR-432 is Implemented. All SKILL.md have `x-augur-plugin`. Framework scans plugin cache.

### Full Parallel: Package all plugins simultaneously
**Strategy**: PARALLEL via team agents (all 9 independent)

Each agent creates a complete plugin directory with `.claude-plugin/plugin.json`, copies full skill directories, and validates with `claude plugin validate`.

| Agent | Plugin | Skills | Source |
|-------|--------|--------|--------|
| `pkg-bootstrap` | `augur` | 1: onboard | Create check-platform hook, hooks.json with SessionStart matcher |
| `pkg-system` | `augur-system` | 15: channels, import, remote-access, save, system-cleanup, updater, workflows, discovery, file-manager, daemon, dev-loops, kill-augur, metrics, observe, ops-daemon | Merge admin + core + observability hubs |
| `pkg-knowledge` | `augur-knowledge` | 12: ai_bridge, ask, commands, dev-learn, dev-sync, knowledge, nightly, rag, reindex-project, scraper, search, sync-agents | ai hub (minus onboard) |
| `pkg-dashboard` | `augur-dashboard` | ~16: renderer, page-builder, dev-build, frontend, test-ui, dashboard-setup (new), + 10 dashboard-focused auto-* skills | Create dashboard-setup skill with npm install + mount-plugins |
| `pkg-adaptive` | `augur-adaptive` | ~44: all code-focused auto-* skills | Per classification from ADR-432 |
| `pkg-dev` | `augur-dev` | ~11: advisor, dev-adr, dev-debug, dev-merge, dev-rollback, dev-test, developer, devops, mcp-app-factory, test-client, validator | dev hub |
| `pkg-life` | `augur-life` | 12: apple, eisenhower, google-workspace, organizer, reading-list, finance, wealth, health, wearables, books, lifestyle, home-automation | Merge productivity + finance + health + lifestyle + home |
| `pkg-career` | `augur-career` | 10: career, coach, content, danit, growth, interview-coach, linkedin-writer, post, project-dev, venture-augur | Merge career + professional |
| `pkg-marketplace` | `augur-marketplace` | N/A | Create marketplace.json listing all 8 plugins. Wait for all other agents to provide version info. |

**Each agent follows this template**:

```bash
# 1. Create plugin structure
mkdir -p {plugin}/.claude-plugin
mkdir -p {plugin}/skills

# 2. Write plugin.json
cat > {plugin}/.claude-plugin/plugin.json << 'EOF'
{
  "name": "{plugin-name}",
  "description": "{description}",
  "version": "1.0.0",
  "author": { "name": "Gur Sannikov" }
}
EOF

# 3. Copy full skill directories (EVERYTHING — scripts, assets, augur/, references/)
for skill in {skill-list}; do
  cp -r .claude/skills/$skill {plugin}/skills/$skill
done

# 4. Add README.md and LICENSE

# 5. Validate
claude plugin validate {plugin}/
```

**Special cases**:
- `pkg-bootstrap`: Creates the `onboard` skill + `hooks/hooks.json` + `hooks/check-platform` script
- `pkg-dashboard`: Creates new `dashboard-setup` skill (npm install + build + mount-plugins)
- `pkg-marketplace`: Runs LAST (needs all plugin versions). Creates marketplace.json with all 8 entries.

### Gate 1: Plugin validation
Each agent runs `claude plugin validate` and reports result. All 8 must pass.

### Gate 2: Installation test
```bash
# Test marketplace
claude plugin marketplace add ./augur-marketplace
claude plugin install augur
claude plugin install augur-system
claude plugin install augur-knowledge

# Verify skills appear
claude --print "list all available slash commands" | grep -c "/"
# Should find system + knowledge skills

# Clean up test
claude plugin uninstall augur-knowledge
claude plugin uninstall augur-system
claude plugin uninstall augur
claude plugin marketplace remove augur-marketplace
```

### Completion Criteria
- [ ] All 8 plugins pass `claude plugin validate`
- [ ] Each plugin's skills appear in `/commands` when installed
- [ ] Marketplace manifest lists all 8 plugins with correct sources
- [ ] `claude plugin install augur-system` installs cleanly
- [ ] `claude plugin install augur-knowledge` installs cleanly
- [ ] MCP tools from installed plugins discovered by `augur mcp serve`
- [ ] Dashboard pages from installed plugins found by `mount-plugins`
- [ ] Personal/client skills in `.claude/skills/` not affected by plugin install
- [ ] ADR-433 status → Implemented
