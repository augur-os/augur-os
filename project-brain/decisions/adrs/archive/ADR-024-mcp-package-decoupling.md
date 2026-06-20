---
status: Superseded
date: ''
deciders: []
related: []
hub: null
tags:
- mcp
- package
- decoupling
- pypi
- distribution
superseded_by: null
---

# ADR-024: MCP Package Decoupling for PyPI Distribution

## Context
Augur will be open-sourced for multiple users. Each user shares the same minimal plugins/ai/skills/ai_bridge but has their own plugins and data. The `augur-mcp` package needs to be independently installable via PyPI.

Current state: `plugins/augur-mcp/` has 12 files with direct `src.*` imports, making it impossible to `pip install` standalone.

## Decision

Decouple `augur-mcp` from plugins/ai/skills/ai_bridge dependencies using a **layered approach**:

### Layer 1: Core MCP (Zero plugins/ai/skills/ai_bridge deps)
- Server startup, tool registration, MCP protocol
- Config via environment variables
- Works with `pip install augur-mcp` alone

### Layer 2: Extended Features (Optional plugins/ai/skills/ai_bridge integration)
- IDE tools, skill generation, advanced context
- Gracefully disabled when plugins/ai/skills/ai_bridge not present
- Enabled automatically when running within full Augur

## Kernel Dependencies Analysis

| Category | Imports | Strategy |
|----------|---------|----------|
| **Logging** | `src.augur_logging` | Already has fallback ✅ |
| **Paths/Config** | `src.config.paths`, `src.config.path_config` | Env vars + defaults |
| **MCP Tools Config** | `src.config.mcp_tools` | Local config file |
| **Context** | `src.context_injector` | Optional, disable tools if missing |
| **IDE Tools** | `src.llm.ide_*` | Optional, disable if missing |
| **Plugin System** | `src.plugins.*`, `src.skills.*` | Interface + optional impl |
| **Scripts** | `src.scripts.*` | Optional, disable tools if missing |

## Implementation Plan

### Phase 1: Create Compatibility Layer
Create `augur_mcp/compat.py` that:
- Attempts plugins/ai/skills/ai_bridge imports with try/except
- Provides fallback implementations or None
- Exposes `KERNEL_AVAILABLE` flag

### Phase 2: Config Independence
- Use env vars: `AUGUR_DATA_DIR`, `AUGUR_PLUGINS_DIR`, `AUGUR_CONFIG_DIR`
- Create `augur_mcp/standalone_config.py` for non-kernel mode
- Load tool configs from `~/.augur/config/` when standalone

### Phase 3: Optional Tool Registration
- Tools that require kernel → only register if `KERNEL_AVAILABLE`
- Core tools (list-skills, get-context) → work in both modes
- IDE tools (check-ide, ide-backlog) → kernel-only

### Phase 4: Package Structure
```
plugins/
├── augur-mcp/           # Core MCP server (PyPI: augur-mcp)
│   ├── src/augur_mcp/
│   │   ├── core/        # Zero deps - protocol, server
│   │   ├── tools/       # Tool implementations
│   │   ├── compat.py    # Kernel compatibility layer
│   │   └── config.py    # Standalone config support
│   └── pyproject.toml
└── augur-src/        # Future: plugins/ai/skills/ai_bridge as separate package
```

### Phase 5: User Experience

**Standalone install:**
```bash
pip install augur-mcp
export AUGUR_PLUGINS_DIR=~/my-plugins
export AUGUR_DATA_DIR=~/my-data
augur-mcp serve
```

**Full install (with plugins/ai/skills/ai_bridge):**
```bash
git clone augur
cd augur && pip install -e .
# Automatically detects plugins/ai/skills/ai_bridge, enables all features
```

## Files to Modify

| File | Changes |
|------|---------|
| `augur_mcp/compat.py` | New - plugins/ai/skills/ai_bridge compatibility layer |
| `augur_mcp/config.py` | Add standalone config resolution |
| `augur_mcp/tools/internal/*.py` | Wrap plugins/ai/skills/ai_bridge imports in try/except |
| `augur_mcp/server.py` | Conditional tool registration |
| `augur_mcp/context_manager.py` | Optional plugins/ai/skills/ai_bridge context |
| `pyproject.toml` | Add `[full]` extra for plugins/ai/skills/ai_bridge deps |

## Consequences

### Positive
- Users can `pip install augur-mcp` without cloning monorepo
- Clear upgrade path via PyPI versions
- Plugin developers don't need full plugins/ai/skills/ai_bridge
- Smaller install size for basic usage

### Negative
- Some features disabled in standalone mode
- Need to maintain compatibility layer
- Two config resolution paths

### Neutral
- Monorepo users see no change (plugins/ai/skills/ai_bridge auto-detected)
