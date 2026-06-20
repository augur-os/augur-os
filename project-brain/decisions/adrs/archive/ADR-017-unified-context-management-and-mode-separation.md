---
status: Implemented
date: '2026-01-22'
deciders: []
related: []
hub: null
tags:
- unified
- context
- management
- mode
- separation
superseded_by: null
---

# ADR-017: Unified Context Management & Mode Separation

**Decision Makers**: Augur Team

## Context

The Augur project has grown to include multiple IDEs (Claude Code, Cursor, Antigravity, Windsurf), various skills across bundles, and a dashboard with many pages. Current issues:

1. **Scattered sources of truth**: IDE definitions in `.agent/`, `.claude/`, root files
2. **No mode separation**: Users see dev tools (code review, CI) when doing life tasks (interview prep)
3. **Cognitive overload**: All action buttons, chains, and commands visible regardless of context
4. **Unclear skill categorization**: Some "core" skills are actually operation skills (inbox, calendar)

## Decision

### 1. Single Source of Truth for IDE Integration

All IDE definitions move to `data/core/ide-integration/`:

```
data/core/ide-integration/
├── index.yaml          # IDE capability mapping
├── registry.yaml       # Auto-generated unified registry
├── workflows/          # Moved from .agent/workflows/
├── chains/             # Moved from .agent/chains/
└── agents/             # User-defined agents
```

Root `/.` folders become symlinks or auto-generated files.

### 2. Dev Mode vs Operation Mode

| Mode | Purpose | Primary Use |
|------|---------|-------------|
| **Dev Mode** | Build/enhance the second brain | Write code, create skills, modify chains |
| **Operation Mode** | Use the second brain for life | Health queries, interview prep, email triage |

### 3. Bundle = Mode Rule

| Bundle | Mode | Purpose |
|--------|------|---------|
| `plugins/orchestration/` | Dev | Skills that BUILD the brain |
| `plugins/ai/` | Operation | Horizontal capabilities (inbox, calendar) |
| `plugins/consulting/` | Operation | Vertical domains (career, health) |

### 4. Dev as a Toggleable Plugin

Dev is NOT core infrastructure. It's a plugin that can be:
- Enabled/disabled like services/apps
- Replaced with custom versions (e.g., "Dev tuned for Company X")

**Two-level gating for dev pages**:
1. Dev plugin must be enabled
2. Dev mode toggle must be ON

### 5. Mode-Aware Filtering

All components filter by mode:
- **Navigation**: Dev pages hidden in operation mode
- **Action buttons**: `mode: dev|operation|both` field
- **Slash commands**: Context-aware based on page + mode
- **Chains**: Dev chains hidden in operation mode
- **MCP tools**: `get-context` returns mode-filtered results

## Consequences

### Positive

1. **Reduced cognitive load**: Users only see relevant options
2. **Clear mental model**: "Building" vs "Using" the brain
3. **Single source of truth**: All IDE definitions in one place
4. **Cross-IDE consistency**: Same MCP tools work everywhere
5. **Customizable**: Can replace dev bundle for specific needs
6. **Future-proof**: New IDEs just need instructions template

### Negative

1. **Migration effort**: Moving files, updating paths
2. **Backward compatibility**: Must maintain symlinks temporarily
3. **Two-level gating complexity**: Plugin + toggle for dev

### Risks

1. **Broken references**: Hardcoded paths may break during migration
2. **Test coverage gaps**: May miss some path updates
3. **User confusion**: Need clear communication about mode toggle

## Implementation

### Phase Summary (8 Phases)

| Phase | Name | Key Actions |
|-------|------|-------------|
| 1 | Restructure Data Repo | Move workflows/chains to data repo, create symlinks |
| 2 | Update generate_instructions.py | Read from data repo, generate all IDE files |
| 3 | Create Registry Generator | Auto-generate unified registry.yaml |
| 4 | Enhance Context Injector | Mode-aware MCP tool responses |
| 5 | Clean Up Stale Files | Delete AGENTS.md, update .gitignore |
| 6 | Migrate Skills | Move 10 skills to services/apps bundles |
| 7 | Update Dashboard | Two-level dev gating, nav filtering |
| 8 | Update Documentation | Terminology in agent-rules.md |

### Skills to Migrate

**Core → Services (8)**:
- inbox, calendar, knowledge-manager, data-scientist
- notifications, metrics, file-organizer, vector-rag

**Core → Apps (2)**:
- business-expert, contract-reviewer

### Validation

- 40 qualifying questions across phases
- 44+ validation checks
- 32 end-to-end integration tests
- 10 user journeys (4 dev, 6 operation)

## Alternatives Considered

### 1. Per-Skill Mode Tagging

**Rejected**: Too complex. Bundle = Mode is simpler and sufficient.

### 2. Auto-Detect Mode from IDE

**Rejected**: Unreliable. Simple toggle is clearer.

### 3. Dev as Core (Not Plugin)

**Rejected**: Violates "all skills are plugins" principle, prevents customization.

### 4. Separate Dashboards for Dev/Operation

**Rejected**: Overkill. Mode toggle within single dashboard is sufficient.

## References

- Full plan: `~/.claude/plans/tender-snuggling-iverson.md`
- Vision doc: `docs/SECOND_BRAIN_AS_SOFTWARE.md`
- Agent rules: `docs/agent-rules.md`
