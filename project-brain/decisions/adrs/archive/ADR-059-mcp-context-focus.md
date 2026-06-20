---
status: Superseded
date: '2026-02-09'
deciders:
- Gur Sannikov
related: []
hub: null
tags:
- mcp
- context
- focus
- skill
- aware
superseded_by: null
---

# ADR-059: MCP Context Focus & Skill-Aware Tool Scoping

**Superseded by**: [ADR-254](ADR-254-agent-discovery-protocol.md)

## Context

The MCP context switching system (ADR-030) dynamically loads/unloads tools based on the current dashboard page. However, tool groups are coarse-grained. Every app page (`/career`, `/health`, `/finance`, `/lifestyle`, etc.) maps to the same `BRAIN_DATA` tool group. When a user is on `/career`, the AI gets the same generic tools as `/lifestyle` — no skill-specific data paths, actions, chains, or commands.

**Two disconnected systems:**
- `ContextInjector` (context enrichment) knows about skills and pages via `registry.yaml`
- `ContextManager` (tool loading) knows about pages and tool groups via `mcp_tool_groups.yaml`
- Neither connects pages to skill-specific tool sets

**CLI gap:** CLI users have no way to focus their session on a specific skill's context. The browser has page-based switching, but CLI agents get no equivalent.

## Decision

Introduce a unified **focus mechanism** — a single `focus-context` MCP tool callable from both the browser (on page navigation) and CLI (`/focus` command). It narrows the active tool set to skill-specific tools and returns a `FocusPayload` with the skill's data paths, actions, chains, and orientation prompt.

### Architecture

```
Dashboard (TS)              CLI Agent               MCP Tool
useMCPContext.ts            /focus career            focus-context
        |                        |                        |
        | POST /api/mcp/         | calls MCP tool         |
        | context/focus          | focus-context           |
        v                        v                        v
+---------------------------------------------------------------+
|                   focus-context MCP Tool                       |
|  (augur_mcp/tools/internal/context.py)                        |
+---------------------------------------------------------------+
        |
        | 1. Resolve skill (name or page -> skill via registry.yaml)
        | 2. Load SKILL.md, dashboard.yaml, data paths
        | 3. Build FocusPayload
        | 4. Call ContextManager.focus_on_skill() to narrow tools
        v
+---------------------------------------------------------------+
|              ContextManager.focus_on_skill()                   |
|  (augur_mcp/context_manager.py)                               |
|                                                                |
|  - Reads skill_tool_groups from mcp_tool_groups.yaml          |
|  - Narrows active tools: core + skill-specific only           |
|  - Stores focused_skill in state                              |
|  - Returns tool diff (added/removed)                          |
+---------------------------------------------------------------+
```

### Data Flow: Browser

1. User navigates to `/career`
2. `useMCPContext.ts` detects skill page (not a system page)
3. Calls `POST /api/mcp/context/focus` with `{ current_page: "/career" }`
4. API route calls `focus-context` MCP tool
5. `focus-context` resolves `/career` → `career` skill via `registry.yaml` `page_contexts`
6. Calls `ContextManager.focus_on_skill("career")` → narrows active tools
7. Returns `FocusPayload` to browser

### Data Flow: CLI

1. User types `/focus career` (or `/focus` to infer from session)
2. Agent calls `focus-context` MCP tool with `skill_name="career"`
3. Same steps 5-7 as browser path
4. Agent receives FocusPayload with paths, actions, chains, orientation prompt

### Page-to-Skill Mapping

Reuses existing `registry.yaml` `page_contexts` section — no duplication.

| Page | Skill | Bundle |
|------|-------|--------|
| `/career` | career | apps |
| `/health` | health | apps |
| `/finance` | finance | apps |
| `/lifestyle` | lifestyle | apps |
| `/content` | content | apps |
| `/eisenhower` | eisenhower | apps |
| `/home` | home-automation | apps |
| `/venture` | venture-augur | apps |
| `/knowledge` | knowledge | services |
| `/apple` | apple | services |
| `/google-workspace` | google-workspace | services |
| `/organizer` | organizer | services |
| `/factory` | mcp-app-factory | crew |

System pages (`/`, `/settings`, `/brain`, `/workforce`, `/inbox`, `/projects`) continue using `switch-mcp-context`.

### FocusPayload Schema

```python
@dataclass
class FocusPayload:
    skill_name: str           # "career"
    skill_path: str           # "plugins/career/skills/career"
    bundle: str               # "apps"
    data_dir: str             # "plugins/career/"
    skill_md_summary: str     # First ~50 lines of SKILL.md
    actions: list[dict]       # [{id, label, description, flow}, ...]
    chains: list[str]         # ["interview_prep"]
    active_tools: list[str]   # Tools now active after focus
    removed_tools: list[str]  # Tools removed during focus
    added_tools: list[str]    # Tools added during focus
    focus_prompt: str         # Markdown summary for agent injection
```

### Skill Tool Groups

New section in `mcp_tool_groups.yaml`:

```yaml
skill_tool_groups:
  career:
    include_groups: [BRAIN_DATA]
    tools: []
  venture-augur:
    include_groups: [BRAIN_DATA, WORKFORCE_CHAINS]
    tools: []
  _default:
    include_groups: [BRAIN_DATA]
    tools: []
```

### Relationship to Existing Tools

| Tool | After ADR-059 |
|------|--------------|
| `switch-mcp-context` | Preserved for system pages. Not deprecated. |
| `focus-context` | New. Used for skill pages. Superset of switch. |
| `get-context` | Preserved. Read-only enrichment. |
| `preload-mcp-context` | Preserved. |

## Consequences

### Positive

- Skill-specific tool scoping reduces noise and context window pressure
- Unified mechanism — browser and CLI use identical Python code
- Incremental adoption — `_default` fallback means no config needed for most skills
- Agent orientation — FocusPayload provides instant understanding of the skill

### Negative

- Two context-switch paths (skill pages vs system pages) adds branching in `useMCPContext.ts`
- New `skill_tool_groups` config section to maintain (mitigated by `_default` fallback)

### Neutral

- `get-context` with `skill_hint` remains unchanged
- `page_contexts` in `registry.yaml` requires no changes

## Alternatives Considered

### Alternative 1: Extend switch-mcp-context

Add skill resolution to the existing tool. Rejected: would overcomplicate the simple page-to-group mapper used by system pages.

### Alternative 2: Per-skill MCP servers

Each skill runs its own MCP server. Rejected: 30+ servers, violates monorepo architecture, conflicts with ADR-030 centralized design.

## References

- ADR-030: Context Merge Algorithm
- ADR-053: Slash Command Restructure
- `src/mcp/augur_mcp/context_manager.py`
- `src/mcp/augur_mcp/tools/internal/context.py`
- `config/dashboard/mcp_tool_groups.yaml`
- `data/core/ide-integration/registry.yaml` (`page_contexts` section)

## Implementation Prompt

> Paste this into Claude Code to execute this ADR.

**Team name**: `adr-059-context-focus`

### Phase 1: Config & Data Model
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | medium | Add `FocusPayload` dataclass and `focus_on_skill()`, `get_skill_tools()`, `clear_focus()` methods to `ContextManager` | `src/mcp/augur_mcp/context_manager.py` |
| 1.2 | developer | low | Add `skill_tool_groups` section and `focus-context` to `core_tools` | `config/dashboard/mcp_tool_groups.yaml` |

### Phase 2: MCP Tool & Slash Command
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | medium | Add `focus-context` tool to `register_context_tools()` | `src/mcp/augur_mcp/tools/internal/context.py` |
| 2.2 | developer | low | Create `/focus` slash command workflow | `data/ai-bridge/agent-workflows/focus.md` |

### Phase 3: Dashboard Integration
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | frontend | medium | Add `focusContext()` method and `FocusPayload` interface to `MCPContextClient.ts` | `src/dashboard/lib/mcp/MCPContextClient.ts` |
| 3.2 | frontend | low | Create API route for focus | `src/dashboard/app/api/mcp/context/focus/route.ts` |
| 3.3 | frontend | medium | Update `useMCPContext.ts` to call `focusContext()` for skill pages | `src/dashboard/hooks/useMCPContext.ts` |

### Final Phase: Verification
| Step | Agent | Tier | Task |
|------|-------|------|------|
| V.1 | validator | low | Run all tests, `npm run build`, verify no regressions |

### Completion Criteria
- [ ] `focus-context` MCP tool registered and responding
- [ ] `/focus` slash command created
- [ ] `skill_tool_groups` config in place
- [ ] Browser skill pages call `focus-context`, system pages call `switch-mcp-context`
- [ ] CLI `/focus career` and browser `/career` produce equivalent FocusPayload
- [ ] All tests pass, build succeeds
