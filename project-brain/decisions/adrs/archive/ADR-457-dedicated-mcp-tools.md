---
id: ADR-457
title: Dedicated MCP Tools — Replace Generic file-* Tool Abuse
status: Deprecated
date: 2026-03-19
deprecated: '2026-05-05'
tags: [mcp, api, dashboard, architecture]
---

# ADR-457: Dedicated MCP Tools — Replace Generic file-* Tool Abuse

## Deprecation (2026-05-05)

**Dropped.** The underlying problem — generic `file-list`/`file-write`/`file-read` abuse with `gracefulFallback` masking failures — was resolved through route removal and replacement, not through building all 21 dedicated tools.

Verified state at deprecation:
- Zero `TODO_CLEANUP(adr-266)` markers remain in `apps/dashboard/`
- Zero routes use `toolName: 'file-list'`, `'file-write'`, or `'file-read'`
- 7 of the 21 proposed tools shipped (`set-config`, `hub-notes`, `prompt-feedback`, `agent-rules-sync`, `self-heal-event`, `adaptive-growth`, `llm-config`)
- The remaining 14 tools were never needed because the routes that would have called them were removed, replaced by domain-specific tools added under other ADRs, or absorbed into `set-config` scopes

The success criteria of this ADR are met. The exhaustive 21-tool list is no longer the contract; future MCP tools are added per-feature as needed.

## Context

38 dashboard API routes call generic `file-list`, `file-write`, and `file-read` MCP tools with domain-specific parameters that don't match the tool schemas. All have `TODO_CLEANUP(adr-266)` markers and `gracefulFallback: { enabled: true }` masking the failures.

**Impact**: ~3,100 validation errors in logs (1,650 file-list, 1,200 file-write, 264 file-read). The dashboard "works" via fallbacks, but returns static/empty data instead of real data.

## Decision

Create 21 dedicated MCP tools organized by domain, replacing generic file operations. Routes update their `toolName` to the new tool and remove `gracefulFallback`.

## Implementation Plan

### Priority 1 — Highest Error Count (covers ~70% of errors)

| Tool | Routes | Replaces | Domain |
|------|--------|----------|--------|
| `set-config` | 18 | file-write | Settings, preferences, layout, nav state |
| `skill-data-list` | ~15 | file-list | Skill/plugin data browsing |
| `skill-data-read` | ~10 | file-read | Skill/plugin data reading |
| `skill-data-write` | ~10 | file-write | Skill/plugin data writing |

### Priority 2 — Medium Impact

| Tool | Routes | Domain |
|------|--------|--------|
| `hub-notes` | 1 | Hub-scoped notes CRUD |
| `usage-track` | 1 | Page view/action tracking |
| `schedules-crud` | 5 | Schedule CRUD + history |
| `chat-history` | 3 | JSONL session storage |
| `bridge-config` | 4 | Bridge connection CRUD |

### Priority 3 — Low Volume

| Tool | Routes | Domain |
|------|--------|--------|
| `workflows-list` | 1 | Workflow catalog |
| `help-request` | 2 | Support ticketing |
| `prompt-read` | 1 | Prompt YAML loading |
| `prompt-feedback` | 2 | Prompt feedback recording |
| `agent-rules-sync` | 1 | Agent config sync |
| `self-heal-event` | 1 | Event logging |
| `adaptive-growth` | 4 | Task/backlog management |
| `productization-plan` | 3 | Plan CRUD |
| `file-upload` | 1 | Binary upload |
| `llm-config` | 3 | LLM configuration |
| `skills-manager` | 2 | Skill enable/disable |
| `nav-layout-state` | 8 | Nav/layout/dashboard toggles |

### Implementation Pattern

**Python side** (`src/mcp/augur_mcp/`):
```python
@mcp.tool(name="set-config")
async def set_config(scope: str, key: str | None = None, value: Any = None, **kwargs) -> dict:
    """Write configuration by scope (preferences, layout, nav-order, etc.)"""
    path = resolve_config_path(scope, key)
    # domain-specific write logic
    return {"success": True}
```

**Dashboard side** (route update):
```typescript
// Before:
toolName: "file-write",
extractParams: async (req) => ({ scope: "preferences", key, value }),
gracefulFallback: { enabled: true, data: { success: false } },

// After:
toolName: "set-config",
extractParams: async (req) => ({ scope: "preferences", key, value }),
// No gracefulFallback — tool handles domain logic correctly
```

### Migration Steps Per Tool

1. Create Python tool in appropriate module
2. Register in MCP server
3. Update route `toolName` + remove `gracefulFallback`
4. Remove `TODO_CLEANUP(adr-266)` comment
5. Verify with `auto-test-api` scan

### Routes to Keep As-Is

`/api/files/*` routes — these are intentionally generic file operations (passthrough).

## Success Criteria

- Zero `file-list`/`file-write`/`file-read` validation errors in dashboard logs
- All 38 routes use dedicated tools
- All `TODO_CLEANUP(adr-266)` markers removed
- No `gracefulFallback` masking real failures

## References

- ADR-266: MCP-first API routes
- ADR-287: MCP-First Dashboard
- ADR-453: Dashboard vault decoupling
- CLAUDE.md rules #5 (no workarounds), #11 (MCP-first API), #17 (wiring audit)
