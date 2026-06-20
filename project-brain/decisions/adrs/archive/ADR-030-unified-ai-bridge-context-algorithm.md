---
status: Implemented
date: '2026-01-31'
deciders:
- Augur Core Team
related: []
hub: null
tags:
- unified
- bridge
- context
- switch
- algorithm
superseded_by: null
---

# ADR-030: Unified AI Bridge with Context Switch Algorithm

## Context

The AI Bridge skill needs to support multiple AI coding clients (Claude Code, Cursor, Windsurf, GitHub Copilot, Gemini CLI, OpenCode, Antigravity, VSCode, Codex) with a unified source of truth for rules, skills, and MCP configurations.

Key challenges:
1. Each client has different paths and formats for skills/commands
2. MCP tools and Skills can overlap, causing context bloat
3. No clear merge priority between user settings, mode, skills, and MCP

## Decision

### 1. Unified Skills-First Architecture

**Source of Truth:** `data/ai-bridge/`
```
data/ai-bridge/
├── skills/                     # All skills/commands
│   └── {name}/SKILL.md
├── agent-rules.md              # Global rules
├── mcp-server-entry.json       # MCP config template
└── client-feature-matrix-*.md  # Investigation docs
```

**Per-Client Adapters:** Transform skills to client-specific formats during sync.

### 2. Context Switch Algorithm

**Merge Priority (Highest → Lowest):**
1. **User Settings** - Always override
2. **Dev/Operation Mode** - Different tool sets
3. **Open Web Page Context** - Browser integration
4. **Core Skills** - MCP basic tools (no plugins required)
5. **Linked Skills** - Project-specific, may overlap with MCP
6. **MCP Commands** - Auto-disabled if covered by higher-priority skill

### 3. Client-Aware MCP Management

- **Full Skills clients** (Claude, Cursor, Windsurf, Copilot): Auto-disable MCP when Skills cover functionality
- **Limited Skills clients** (Gemini): Keep all MCP enabled (fallback)
- User settings ALWAYS override

### 4. Mode Detection

- Web dashboard toggle → **persists to config** until changed
- MCP command: `augur-config --mode dev`
- Modes: `dev` (development tools) | `ops` (operations tools)

### 5. Page Context Refresh

- Poll every 3-5 seconds while dashboard is open
- No polling when closed

## Consequences

**Positive:**
- Single source of truth for all AI clients
- Reduced context overhead via smart MCP/Skills merge
- User preferences respected across all clients
- Clean adapter pattern for client-specific formats

**Negative:**
- Migration effort from `agent-workflows/` to `skills/`
- Complexity in context manager logic
- Requires testing across all 9 clients

## Testing & Verification

### Unit Tests

| Test Case | Expected Result |
|-----------|----------------|
| `test_skills_sync_claude` | Skills copied to `.claude/skills/` with headers |
| `test_skills_sync_windsurf` | YAML frontmatter stripped, output to `.windsurf/workflows/` |
| `test_skills_sync_copilot` | Skills copied to `.github/skills/` |
| `test_mcp_config_generation` | MCP config generated for each client path |
| `test_claude_desktop_merge` | Existing MCP servers preserved, Augur entry merged |
| `test_mode_persistence` | Mode saved to config, survives restart |
| `test_context_merge_priority` | User settings override all other sources |

### Integration Tests

| Scenario | Steps | Verification |
|----------|-------|-------------|
| Skills overlap with MCP | 1. Link `rag-search` skill<br>2. Build context | MCP `query_rag` disabled, skill enabled |
| Limited client fallback | 1. Set client=gemini<br>2. Build context | All MCP tools enabled (no auto-disable) |
| User override | 1. Disable skill in settings<br>2. Enable MCP tool | Both changes respected in context |
| Mode switch | 1. Set mode=dev via MCP<br>2. Check persisted config | Config shows `mode: dev` |

### Use Cases

#### UC-1: Developer starts session in Claude Code
```
1. User opens project in Claude Code 2.1.3+
2. sync_agents.py runs (manual or hook)
3. Skills from data/ai-bridge/skills/ → .claude/skills/
4. User invokes /code-review
5. Claude loads skill, executes workflow
```
**Verify**: Skill appears in `/` menu, executes correctly.

#### UC-2: Developer switches to Windsurf
```
1. User opens same project in Windsurf
2. sync_agents.py has already generated .windsurf/workflows/
3. User invokes /code-review
4. Windsurf loads workflow (plain MD, no frontmatter)
```
**Verify**: Workflow appears without YAML syntax errors.

#### UC-3: MCP tool disabled by skill
```
1. Skill `rag-search` is linked
2. MCP tool `query_rag` covers same functionality
3. Context manager builds tool list
4. query_rag auto-disabled
```
**Verify**: `query_rag` not in enabled tools list.

#### UC-4: User overrides MCP disable
```
1. Skill disables MCP `query_rag`
2. User sets: mcp_overrides.query_rag = enabled
3. Context manager builds tool list
```
**Verify**: `query_rag` IS in enabled tools list (user override wins).

#### UC-5: Mode toggle via dashboard
```
1. User clicks "Dev Mode" in web dashboard
2. Mode persisted to augur config
3. User closes dashboard
4. Next context load reads mode from config
```
**Verify**: Mode persists across sessions.

#### UC-6: Mode toggle via MCP command
```
1. User runs: augur-config --mode ops
2. Config updated
3. Context manager loads ops tools
```
**Verify**: Dev tools not loaded, ops tools loaded.

## Related ADRs

- ADR-017: Unified Context Management
- ADR-020: Local Agent Orchestration
- ADR-024: MCP Package Decoupling
