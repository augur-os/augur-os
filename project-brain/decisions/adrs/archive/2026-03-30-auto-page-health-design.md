# Auto Page Health Autoloop

**Date:** 2026-03-30
**Status:** Approved

## Problem

Dashboard pages reference MCP tools by name in YAML configs and TSX code. Tools get renamed, removed, or broken — pages silently show "No data" or 500 errors with no automated detection.

## Decision

New autoloop `auto-page-health` that scans all dashboard pages, verifies every MCP tool reference, and auto-fixes broken tool names in YAML configs.

### Difficulty Levels

| Level | Behavior |
|---|---|
| d0 | Scan only — report broken tools and pages |
| d1 | Auto-fix YAML: fuzzy-match broken tool names against MCP registry, update YAML, verify, commit |
| d2 | Also flag TSX pages with broken tools as migration candidates |

### Scan Phase

1. Walk `skills/*/augur/pages/*.yaml` — extract `mcp_tool` values from blocks and sources
2. Walk `skills/dashboard/pages/**/page.tsx` — extract tool names from `useMcpQuery`, `useMcpMutation`, `useMcpPoll` calls
3. Connect to MCP server, get list of all registered tools
4. For each referenced tool: check if registered, call it, verify it returns data

**Issue format:**
```python
{
    "action": "broken-tool",
    "file": "skills/health/augur/pages/overview.yaml",
    "tool": "health-summary",
    "page": "life/health",
    "error": "tool not registered",
    "suggestion": "get-health-summary",
}
```

### Fix Phase (d1+)

For each broken tool in a YAML config:
1. Compute edit distance between broken name and all registered tools
2. If closest match has distance <= 3 or shares a common prefix/suffix, propose it
3. Update the YAML file with the corrected tool name
4. Re-verify: call the corrected tool via MCP
5. If verification passes, commit the fix
6. If verification fails, revert the change and report as unresolved

TSX pages with broken tools are reported but not auto-fixed (d2 reports them as migration candidates).

### Files

- `skills/auto-page-health/SKILL.md` — skill metadata with `x-augur-loop` config
- `skills/auto-page-health/scripts/page_health.py` — `scan()` + `fix()` entry points

### SKILL.md Config

```yaml
name: auto-page-health
x-augur-type: autoloop
x-augur-hub: adaptive
x-augur-tab: testing
x-augur-loop:
  name: page-health
  tier: 1
  trigger: nightly
```

### Integration

- Uses `src.lib.ops_protocol.OpsContext`, `ScanResult`, `FixResult`
- Reuses tool extraction logic from `scripts/verify-page-tools.py`
- Connects to MCP server via `mcp.client.stdio.stdio_client` (same as auto-test-mcp)
- Output: structured JSON report + console summary
- Nightly run via the adaptive daemon
