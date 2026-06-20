---
description: Detect direct filesystem access in API routes that bypass MCP-first policy.
visibility: auto
---

# auto-fs-bypass

Scan API routes for direct filesystem operations that should be routed through MCP tools.

## Scan

Finds direct `fs` imports and file operations in API routes, while honoring `@fs-exempt`
markers for acknowledged exceptions.

## Fix

Report only. Route migrations require deliberate MCP-tool rewiring rather than blind edits.
