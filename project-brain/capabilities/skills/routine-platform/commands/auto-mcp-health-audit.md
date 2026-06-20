---
description: Audit MCP route wiring, runtime health, and safe auto-fixes
visibility: auto
---

# auto-mcp-health-audit

Run the MCP health audit across client-config integrity, route wiring, runtime
probes, and safe fixes.

## Scan

- **Phase 0 — client config integrity.** First reconciles canonical roots: it
  snapshots the configured roots (documents, vault, …) and auto-records any that
  moved into `config/system/path_migrations.yaml`, so a root move needs no manual
  map entry (also runnable on demand via `aug config reconcile-paths`). Then it
  reads each AI client's MCP config (Claude Desktop config + DXT extension
  settings, project `.mcp.json`, Codex, Gemini) and flags any server `cwd` or
  directory-typed extension setting that no longer exists on disk — the class of
  failure where an Augur root moves and a client's MCP server silently
  crash-loops.
- **Phase 1+ — wiring & runtime.** Cross-references dashboard proxy routes with
  MCP tool registrations and probes runtime health.

## Fix

- Auto-repairs a dangling client path by rewriting it to its unambiguous
  successor from `config/system/path_migrations.yaml` (only when the rewritten
  path exists on disk). User-owned configs only; the generated `.mcp.json` is
  flagged to run `aug config sync` instead of being hand-edited.
- Applies safe fixes for obvious wiring defects and writes a structured audit
  report.
