---
status: Superseded
date: '2025-01-15'
deciders:
- Core team
related: []
hub: null
tags:
- plugin
- system
- ide
- agents
superseded_by: null
---

# ADR-008: Plugin System for IDE Agents

## Context

Augur had 39 skills spread across `plugins/{factory,vertical,services}/` directories, each with SKILL.md files and associated modules. This structure served well but presented challenges:

- **No bundling**: Related skills (e.g., developer, architect, validator) exist as separate units
- **No event-driven automation**: No way to automatically run quality gates on file changes
- **Not distributable**: Can't easily share skill bundles with team or community
- **Always-on**: Skills can't be enabled/disabled as groups
- **Divergent from ecosystem**: Claude Code introduced a plugin model that's becoming standard

Claude Code plugins offer a packaging format with:
- Bundled skills, commands, hooks, and agents
- Event-driven hooks (PreToolUse, PostToolUse, SessionStart, Stop)
- Marketplace distribution model
- Enable/disable per plugin

## Decision

Adopt a **plugin-based architecture** for organizing and distributing IDE agent capabilities:

### Plugin Directory Structure
```
plugin-name/
├── .augur-plugin/
│   └── plugin.json         # Metadata, dependencies
├── skills/                  # Auto-registered skills
│   └── skill-name/
│       └── SKILL.md
├── commands/                # Slash commands
├── hooks/                   # Hook configurations
├── agents/                  # Subagent definitions
└── README.md
```

### plugin.json Schema
```json
{
  "name": "dev",
  "version": "1.0.0",
  "description": "Core development skills",
  "author": "augur",
  "skills": ["developer", "advisor", "validator", "devops", "frontend"],
  "commands": [],
  "hooks": {
    "PreToolUse": ["security-scanner"]
  },
  "dependencies": {}
}
```

### Hook System
```yaml
# augur-config/hooks.yaml
hooks:
  PreToolUse:
    - name: secrets-guard
      matcher: "Write|Edit"
      handler: |
        if echo "$HOOK_FILE_PATH" | grep -qE '\.(env|pem|key)$'; then
          exit 1  # Block
        fi
      mode: command  # sync, can block

  PostToolUse:
    - name: auto-lint
      matcher: "Write|Edit"
      handler: "structure-enforcer:lint_file"
      mode: prompt  # async, advisory
```

### Execution Modes
- **command**: Synchronous, blocking. Non-zero exit blocks the action.
- **prompt**: Asynchronous, fire-and-forget. Advisory notifications only.

### Plugin Groupings (Migration)

> **Note**: The original 9-bundle plan below was superseded by the current hub-based layout.
> Current bundles: `admin`, `ai`, `career`, `consulting`, `dev`, `enterprise`, `finance`,
> `health`, `home`, `lifestyle`, `observability`, `orchestration`, `productivity`,
> `professional`, `services`. See `ls plugins/` for the authoritative list.

Original plan (historical):
- `factory-core`: developer, architect, validator, devops, librarian
- `factory-quality`: security, data-scientist, data-engineer, webapp-testing, user-advocate
- `factory-management`: executor, oss-manager, business-expert, structure-enforcer
- `factory-product`: frontend, vision-keeper, experiment-tracker, contract-reviewer
- `vertical-life`: recipes, virtual-doctor, finance-tracker, reading
- `vertical-work`: careers, interview, marketing, content, community-manager, investor-relations
- `vertical-ideas`: ideas, metrics-dashboard
- `services-core`: voice, inbox, vector-rag, calendar, notifications
- `services-data`: list-manager, file-organizer, knowledge-manager, ocr

### MCP Tools
- `list-plugins` - List all plugins with status
- `toggle-plugin` - Enable/disable plugins
- `install-plugin` - Install from git URL or local path
- `uninstall-plugin` - Remove user-installed plugins
- `plugin-health` - Health check for all plugins
- `reload-plugin` - Reload to pick up changes

## Consequences

### Positive

- **Logical organization**: Related skills bundled together
- **Event-driven quality gates**: Hooks block sensitive file writes, auto-lint on changes
- **Distributable**: Can share plugin bundles via git repos
- **Toggle-able**: Enable/disable entire plugin bundles
- **Ecosystem alignment**: Compatible with Claude Code plugin conventions
- **Extensible**: Easy to add community plugins

### Negative

- **Migration effort**: Reorganized 39 skills into new structure (completed)
- **Learning curve**: Team must understand plugin vs skill distinction
- **Hook complexity**: Debugging hook interactions may be challenging

### Neutral

- Plugins registered with central `exo` MCP server (not per-plugin servers)
- Hook configurations stored in data repo (augur-config/hooks.yaml)
- Skills within plugins retain their original SKILL.md format
- **Single system**: `plugins/` is the only skill location (no `plugins/` directory)

## Alternatives Considered

### Alternative 1: Per-Plugin MCP Servers

Each plugin spawns its own MCP server (like Claude Code). Rejected because:
- Adds complexity to manage multiple servers
- Single MCP server is simpler to debug
- Central server already handles 100+ tools effectively
- Can revisit if scalability becomes an issue

### Alternative 2: Keep Flat Structure

Continue with individual skills in `plugins/`. Rejected because:
- No bundling for distribution
- No event-driven hooks
- Growing skill count (39+) becoming unwieldy
- Missing ecosystem alignment opportunity

### Alternative 3: Claude Code Plugin Format Exactly

Adopt Claude Code's exact `.claude-plugin/` structure. Rejected because:
- `.augur-plugin/` namespace avoids confusion
- Can still parse Claude Code plugins if needed
- Allows Augur-specific extensions

### Alternative 4: Async-Only Hooks

Only support fire-and-forget hooks. Rejected because:
- Can't block dangerous actions (e.g., .env writes)
- Security gates require synchronous blocking
- Both modes needed for different use cases

## Implementation

### Files Created
- `src/llm/hooks/` - Hook registry and executor
- `src/plugins/` - Plugin registry, loader, schema
- `src/skills/registry.py` - Updated to load from plugins/
- `src/mcp/augur_mcp/domain/plugins.py` - Plugin MCP tools
- `augur-config/hooks.yaml` - Hook configurations
- `plugins/` - All skills organized in 9 plugin bundles

### Key Design Decisions
1. **Both hook modes**: `command` (sync/blocking) + `prompt` (async/advisory)
2. **Central MCP server**: All plugin tools register with existing `exo` server
3. **Full migration**: All 39 skills migrated to 9 plugin bundles
4. **Handler detection**: Shell scripts vs skill handlers distinguished by regex pattern
5. **Single system**: `plugins/` is the sole skill location (removed `plugins/`)
6. **Data repo mirroring**: Data repo restructured to mirror plugin bundles (see below)

### Data Repository Structure

The data repository (`augur-data/`) was restructured to mirror the plugin bundle organization:

**Before (flat by category)**:
```
augur-data/
├── factory/developer/
├── orchestrator/executor/
├── vertical/careers/
└── services/calendar/
```

**After (by plugin bundle)** *(Note: bundle names below are from the original plan; current bundles use hub-based names like `dev/`, `ai/`, `career/`, etc.)*:
```
augur-data/
├── dev/                    # developer, advisor, validator, devops, frontend
├── ai/                     # ai_bridge, knowledge, mcp-app-factory, install, scraper
├── career/                 # career, content, growth, linkedin-writer
├── finance/                # finance, wealth
├── health/                 # health, wearables
├── lifestyle/              # lifestyle (recipes, reading, etc.)
├── orchestration/          # executor, router, swarm
├── observability/          # daemon, metrics, observe
├── admin/                  # channels, settings, updater
├── config/                 # Global configuration
└── runtime/                # Logs, cache, temp
```

**Path Resolution**: `src/config/paths.py` contains `SKILL_TO_DATA_BUNDLE` mapping to resolve skill names to their bundle directories via `get_skill_data_dir(skill_name)`.

**Rationale for mirroring**:
- Consistent mental model: code and data use same organizational structure
- Easier navigation: knowing where a skill's code lives tells you where its data lives
- Future-proofing: plugin-level data isolation supports potential distribution model

## References

- [Claude Code Plugins Documentation](https://code.claude.com/docs/en/plugins)
- [Claude Code Plugin Blog](https://claude.com/blog/claude-code-plugins)
- `src/llm/hooks/` - Hook implementation
- `src/plugins/` - Plugin implementation
- `augur-config/hooks.yaml` - Hook configurations
- `plugins/` - Migrated plugin bundles
