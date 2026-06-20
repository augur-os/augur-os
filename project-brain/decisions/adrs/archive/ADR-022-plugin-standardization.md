---
status: Implemented
date: '2026-01-27'
deciders:
- Augur Team
related: []
hub: null
tags:
- plugin
- standardization
- compliance
- audit
superseded_by: null
---

# ADR-022: Plugin Standardization and Compliance Audit

## Context

After Phase 0 restructuring (ADR-014 flattened structure, ADR-016 monorepo migration), the plugin ecosystem has 20 standalone plugins with inconsistent structures. Some plugins have:
- Missing required files (MCP tools, API endpoints, tests)
- Inconsistent data directory paths
- Direct print() statements instead of centralized logging
- No backlog tracking for bugs/features/improvements
- Missing dependency declarations

This inconsistency makes it difficult to:
- Onboard new developers
- Maintain quality standards
- Understand plugin capabilities
- Track plugin health

## Decision

### 1. Plugin Template Specification

All plugins MUST comply with `docs/templates/plugin-spec.yaml` which defines:

**Required Files (24):**
```
plugins/{bundle}/skills/{skill}/
├── dashboard.yaml          # Hub configuration
├── SKILL.md                # Skill documentation
├── README.md               # Developer docs
├── version.yaml            # Version tracking
├── requirements.txt        # Python deps
├── package.json            # Node deps
├── schemas/*.schema.yaml   # Data schemas
├── dashboard/
│   ├── page.tsx
│   ├── layout.tsx
│   ├── loading.tsx
│   └── tabs/OverviewTab.tsx
├── api/
│   ├── health/route.ts
│   └── {resource}/route.ts
├── mcp/
│   ├── __init__.py
│   └── tools.py
├── scripts/*.py
├── chains/*.yaml
├── backlog/
│   ├── BACKLOG.md
│   ├── bugs/
│   ├── features/
│   └── improvements/
└── tests/
    ├── test_mcp.py
    ├── test_api.py
    └── *.test.tsx
```

**Required dashboard.yaml Fields:**
- `hub.id`, `hub.title`, `hub.subtitle`, `hub.icon`, `hub.category`
- `data_dir` (flat: `{plugin-name}/`)
- `mode` (all | dev | operation)
- `dependencies.plugins`, `dependencies.mcp_servers`
- `actions`, `chains`, `schemas`
- `tabs` with `devOnly`/`operationOnly` flags

### 2. Data Directory Rules

**Pattern**: `data/{plugin-name}/` (flat, no nesting)

```
data/
├── daemon/         # daemon skill runtime data
├── career/         # NOT plugins/careers/
├── venture/        # NOT plugins/consulting-expert/
├── crew/           # Exception: crew skill data
├── config-data/    # Shared sensitive config
└── runtime/        # Shared runtime (logs, cache)
```

**Forbidden:**
- `plugins/`, `data/services/`, `data/core/`
- Nested bundle paths

### 3. Logging Requirements

**Required Pattern:**
```python
from src/lib.augur_logging import get_entity_logger
logger = get_entity_logger("{plugin-name}")
```

**Forbidden:**
- `print()` in library code (allowed in CLI scripts)
- `import logging` directly
- `logging.basicConfig()`

**Audit Command:** `python3 .github/scripts/audit_logging.py`

### 4. Plugin Audit Priority

| Priority | Plugins | Rationale |
|----------|---------|-----------|
| **P0** | platform, daemon, knowledge, venture, icloud | Core infrastructure & high business value |
| **P1** | scraper, organizer, career, capture, health | System utilities & high usage |
| **P2** | wearables, enterprise, finance, lifestyle, ideas, content, eisenhower, home, client-terminal-automation, client-smb-design | Lower priority personal/business tools |

**Audit Order (P0 first):**

| # | Plugin | Category | Description |
|---|--------|----------|-------------|
| 1 | platform | system | Core infrastructure, agents, tools |
| 2 | daemon | system | Background services, logging, metrics |
| 3 | knowledge | system | RAG, search, OCR |
| 4 | venture | business | Business/venture management |
| 5 | icloud | system | Apple iCloud integration |
| 6 | scraper | system | Web data extraction |
| 7 | organizer | system | File/system organization |
| 8 | career | business | Job search, interview prep |
| 9 | capture | productivity | Voice memos, vision capture |
| 10 | health | personal | Health tracking, medical records |
| 11 | wearables | productivity | Watch, location tracking |
| 12 | enterprise | business | Organization management |
| 13 | finance | personal | Personal finance tracking |
| 14 | lifestyle | personal | Reading, recipes, places |
| 15 | ideas | personal | Ideas, personal projects |
| 16 | content | personal | Content creation studio |
| 17 | eisenhower | productivity | Task prioritization matrix |
| 18 | home | personal | Smart home automation |
| 19 | client-terminal-automation | productivity | Terminal automation |
| 20 | client-smb-design | business | SMB client portal |

### 5. Plugin Categories

| Category | Description | Examples |
|----------|-------------|----------|
| `system` | Core infrastructure | platform, daemon, organizer, scraper, knowledge, icloud |
| `productivity` | Getting things done | capture, wearables, eisenhower, client-terminal-automation |
| `personal` | Life management | health, lifestyle, finance, content, ideas, home |
| `business` | Professional | career, venture, enterprise, client-smb-design |

## Consequences

### Positive

- Consistent plugin structure across all 20 plugins
- Clear onboarding path for new developers
- Centralized logging with correlation ID support
- Backlog tracking per plugin for bugs/features
- Automated compliance auditing
- Clear dependency declarations

### Negative

- Significant upfront work to bring all plugins to compliance
- More files to maintain per plugin
- Stricter requirements may slow initial development

### Neutral

- Templates provided in `plugins/ai/skills/mcp-app-factory/templates/`
- Plugin specification in `plugins/ai/skills/mcp-app-factory/plugin-spec.yaml`
- Plugin Factory skill provides wizard UI, audit dashboard, and MCP tools
- Audit script validates compliance
- Priority-based rollout (P0 → P1 → P2)

## Implementation Plan

1. **Phase 1**: Audit and fix P0 plugins (platform, daemon, knowledge, venture, icloud)
2. **Phase 2**: Audit and fix P1 plugins (scraper, organizer, career, capture, health)
3. **Phase 3**: Audit and fix P2 plugins (remaining 10)
4. **Phase 4**: Add compliance check to CI pipeline

## References

- `plugins/ai/skills/mcp-app-factory/plugin-spec.yaml` - Plugin specification
- `plugins/ai/skills/mcp-app-factory/templates/` - File templates
- `plugins/ai/skills/mcp-app-factory/scripts/scaffold.py` - Plugin scaffolding
- `plugins/ai/skills/mcp-app-factory/scripts/audit.py` - Plugin compliance audit
- `.github/scripts/audit_logging.py` - Logging audit script
- ADR-014: Three-tier plugin architecture
- ADR-016: Monorepo migration
- ADR-018: Plugin dependency management
