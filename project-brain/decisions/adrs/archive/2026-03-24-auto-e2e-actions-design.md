# auto-e2e-actions Design Spec

## Goal

Validate the POST/write direction of the dashboard pipeline: every action button calls an MCP tool, the tool writes to vault, and the written data appears back in the GET path. Complements `auto-e2e-pipeline` (GET direction).

## Architecture

Autoloop skill following the OpsCommand protocol (`scan()` + `fix()`). Discovers all dashboard actions from SKILL.md frontmatter, classifies them by dispatch type, and progressively validates wiring → schema → execution → round-trip at increasing difficulty levels.

## Difficulty Levels

| Level | Check | Side Effects |
|-------|-------|-------------|
| **d0** | **Wiring audit** — discover all `fire`/`modal`/`ide` actions via SKILL.md frontmatter, verify each action's `mcp_tool` is registered in the MCP server | None (static) |
| **d1** | **Schema validation** — for each action with modal fields, verify the MCP tool accepts the declared field names as parameters (Pydantic model introspection) | None |
| **d2** | **Execution test** — call each mutation tool with minimal `_e2e_test_*` args, verify `{success: true}`. Clean up immediately. | Writes + deletes test items |
| **d3** | **Round-trip test** — write item via mutation, call corresponding GET tool, verify item appears, then delete. Full write→read→delete cycle. | Same + read verification |

## Scope

### Testable dispatch types
- `fire` — direct MCP tool call
- `modal` — form fields → MCP tool via `submitTool: mcp://augur/{tool}`
- `ide` — initial tool call is identical to `fire` (IDE only matters for multi-step follow-up)

### Skipped dispatch types
- `chat` — requires interactive agent session
- `oneshot` — requires CLI agent execution
- `auto` — delegates to IDE/chat, not directly testable

## Action Discovery

Actions are discovered from three sources in SKILL.md frontmatter:

1. **Page actions**: `x-augur-config.contributions.actions[]` — buttons on hub pages
2. **Modal definitions**: `x-augur-config.modals.{id}` — form definitions with `submitTool`
3. **Row actions**: `x-augur-config.contributions.blocks[].row_actions[]` — per-row table actions

For each action, extract the MCP tool name:
- `fire`/`ide` actions: `mcp_tool` field or `mcp_tools[0]`
- `modal` actions: parse `submitTool: mcp://augur/{tool-name}` from modal definition
- Row actions: `mcp_tool` field in row_actions array

## Tool Registration Verification (d0)

Cross-reference discovered tool names against actual MCP tool registrations:
- Scan `skills/*/scripts/mcp/__init__.py` for `@mcp.tool(name=...)` patterns
- Also check `src/mcp/augur_mcp/` for core tool registrations
- Flag actions whose `mcp_tool` doesn't match any registered tool

## Schema Validation (d1)

For actions with modal `fields` declarations:
- Extract field names from modal definition (e.g., `name`, `severity`, `notes`)
- Call the MCP tool with empty args to trigger Pydantic validation
- Parse the validation error to extract required parameter names
- Compare modal fields against tool parameters — flag mismatches

## Execution Test (d2)

For each mutation tool, construct minimal test args:

### Test item convention
- All IDs prefixed with `_e2e_test_` (e.g., `_e2e_test_symptom_001`)
- Include `source: "e2e-test"` field where supported
- Title/name fields use `_e2e_test_` prefix for identification

### Minimal arg construction
- Required string fields: `"_e2e_test_{field_name}"`
- Required number fields: `1`
- Required URL fields: `"https://example.com/_e2e_test"`
- Optional fields: omitted

### Execution flow
1. Cleanup: delete any stale `_e2e_test_*` items from previous runs
2. Call mutation tool with test args
3. Verify response contains `success: true` (or no `error` field)
4. Immediately call corresponding delete tool to clean up
5. If cleanup fails, flag as `action_cleanup_failed` but don't block

## Round-Trip Test (d3)

Full write→read→delete cycle:

### Round-trip pair discovery
Actions and blocks in the same SKILL.md are paired:
- Block's `data_source.mcp_tool` = GET tool
- Action's `mcp_tool` = POST tool
- Same `page` field = they belong together

Example pairs:
| Mutation (POST) | GET (read-back) | Skill |
|-----------------|-----------------|-------|
| `add-career-job` | `get-career-jobs` | career |
| `add-symptom` | `get-virtual-doctor-symptoms` | health |
| `manage-reading-list-articles` (action=add) | `list-reading-list-articles` | reading-list |
| `manage-movies` (action=add) | `list-movies` | lifestyle |

### Round-trip flow
1. Call GET tool, note current item count
2. Call POST tool with `_e2e_test_*` args
3. Call GET tool again
4. Verify count increased by 1, or `_e2e_test_*` item appears in response
5. Call DELETE tool (if available) to clean up
6. Verify count returns to original

## Issue Classification

| Broken Stage | Kind | Fixability | Description |
|-------------|------|------------|-------------|
| `action_unwired` | actionable | manual | Action has no `mcp_tool` field |
| `action_tool_missing` | actionable | manual | `mcp_tool` not registered in MCP server |
| `action_schema_mismatch` | actionable | manual | Modal fields don't match tool parameters |
| `action_exec_failed` | broken | manual | Tool called with valid args, returned error |
| `action_roundtrip_broken` | broken | manual | Write succeeded but read-back doesn't show item |
| `action_cleanup_failed` | maintenance | manual | Test item couldn't be deleted |

## Fix Strategy

- d0 issues: report-only (wiring fixes need manual work)
- d1 issues: report with field diff (modal fields vs tool params)
- d2 issues: report tool error message, suggest fix
- d3 issues: `action_roundtrip_broken` is the critical signal — pipeline between write and read is broken. Report both tool responses for debugging.

At d2+, auto-fix for `action_tool_missing`: fuzzy-match the action's `mcp_tool` against registered tools, suggest the closest match.

## SKILL.md Frontmatter

```yaml
name: auto-e2e-actions
x-augur-type: autoloop
x-augur-tags: [e2e, actions, mutations, validation, pipeline]
description: >
  Validate the POST/write direction: dashboard actions → MCP tools → vault writes → data appears in GET.
  Covers: auto-e2e-actions, scan, action wiring, round-trip, mutation validation

x-augur-visibility: auto

x-augur-loop:
  name: testing
  tier: 2
  trigger: nightly

x-augur-hub: adaptive
x-augur-tab: infrastructure
```

## File Structure

```
skills/auto-e2e-actions/
├── SKILL.md
├── scripts/
│   ├── __init__.py
│   └── e2e_actions.py          # OpsCommand: scan() + fix()
├── augur/
│   └── tests/
│       ├── __init__.py
│       └── test_e2e_actions.py
├── assets/seeds/.gitkeep
├── references/.gitkeep
└── evals/.gitkeep
```

## Dependencies

| File | Usage |
|------|-------|
| `src/lib/ops_protocol.py` | OpsContext, ScanResult, FixResult, make_issue, evolution_gap |
| `src/lib/frontmatter_utils.py` | parse_frontmatter (read SKILL.md) |
| `src/config/paths.py` | get_all_client_skill_dirs, get_project_root |
| `src/mcp/augur_mcp/infrastructure/browse/index.py` | browse_index_impl (for MCP tool list) |
| `auto-e2e-pipeline` | Shares pattern: _call_api_tool, _check_dashboard_health |

## Relationship to auto-e2e-pipeline

| Aspect | auto-e2e-pipeline | auto-e2e-actions |
|--------|-------------------|------------------|
| Direction | GET (read) | POST (write) |
| What it tests | Data flows from vault to dashboard | Actions flow from dashboard to vault |
| Discovery | Browse categories + page tool refs | SKILL.md actions + modals + row_actions |
| Side effects | None (read-only) | d2+ writes/deletes test items |
| Complement | Verifies data is visible | Verifies data can be created/modified |
