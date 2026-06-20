# MCP Health Audit Overview

`auto-mcp-health-audit` is the adaptive skill that checks whether dashboard MCP wiring still matches the tools actually registered in Python.

## Why It Exists

- Dashboard regressions often show up as empty pages, silent fallbacks, or stale tool names after refactors.
- This skill audits both the static wiring and selected runtime behavior so the adaptive engine can fix safe issues automatically and escalate the rest.

## Primary Surfaces

- Slash command: `/auto-mcp-health-audit`
- Dashboard page: `/adaptive/auto-mcp-health-audit`
- Aggregated API route: `/api/auto-mcp-health-audit`

## Runtime Signal Sources

- Route tool references extracted from dashboard route definitions
- `@mcp.tool(name=...)` registrations found in Python MCP modules
- Runtime probe responses used to classify healthy, masked, and broken routes
