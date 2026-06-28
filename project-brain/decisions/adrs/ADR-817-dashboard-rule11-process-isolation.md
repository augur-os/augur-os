---
status: Implemented
date: 2026-06-25
deciders:
  - Gur
related:
  - ADR-642
  - ADR-810
hub: null
tags:
  - dashboard
  - mcp
  - rule-11
  - process-isolation
  - architecture
superseded_by: null
spec_file: 2026-06-25-dashboard-rule11-process-isolation-design.md
plan_file: 2026-06-25-dashboard-rule11-process-isolation.md
---

# ADR-817: Dashboard rule-11 process isolation (Phase 2)

> **ADR-817 is an index file.** The substantive design lives in the linked spec. This file carries pointers, status, and a one-line decision summary.

## Decision summary

The dashboard server must not own process-spawning that an MCP tool can provide: migrate capabilities introspection, file/dir/editor opening, and chat-session writes to existing MCP tools; delete the now-dead generic command + Python/CLI runners; and formally mark the inherently-process surfaces (interactive PTY terminal, native-terminal launcher, ADR-642 extraction, upload staging) as permanent `@spawn-exempt`/`@fs-exempt` exemptions.

## Context

Phase 1 (`2026-06-25-dashboard-dev-oom-fix`, merged `ed9db106`) fixed the acute symptom — a `next-server` heap that OOM-rebooted a 16 GB machine — via a RAM-aware heap clamp and a bounded exec output buffer. Phase 2 is the architectural cause: the dashboard hosting `spawn`/`exec`/direct-`fs` at all, against rule 11. Scope is **pragmatic** (user-confirmed 2026-06-25): migrate what existing MCP tools already cover, formally exempt the rest. The interactive PTY terminal is a **permanent sanctioned exemption** (a live terminal cannot be a request/response MCP tool).

## Spec (canonical)

- [`docs/superpowers/specs/2026-06-25-dashboard-rule11-process-isolation-design.md`](../../../docs/superpowers/specs/2026-06-25-dashboard-rule11-process-isolation-design.md)

## Plan (canonical, drives `/adr implement`)

- [`docs/superpowers/plans/2026-06-25-dashboard-rule11-process-isolation.md`](../../../docs/superpowers/plans/2026-06-25-dashboard-rule11-process-isolation.md)

## Status notes

**Implemented** (2026-06-25). Migrated: capabilities route → `list-skills` MCP (no per-request Python spawn); file/dir/settings open → `system-open` MCP. Deleted dead `cliRunner.ts`/`pythonRunner.ts`. Verified on `:3001`: capabilities API returns 26 real skills via MCP, Browse·Skills renders 89 skill cards, no console/chunk errors.

A closeout audit found spawns beyond the original inventory and classified ALL of them honestly: interactive PTY (SessionManager, cli/actions, cli/exec) + native-terminal launcher + preferred-editor/file-picker → permanent `@spawn-exempt`; MCP-transport launch (connection/preflight) → `@spawn-exempt` (cannot route through MCP); `llm-retry.ts` → `@spawn-exempt` referencing its governing **ADR-106**; `cli-config` session write + config reads → `@fs-exempt`. Two follow-ups remain (NOT regressions): `plugin-discovery/paths.ts` spawns Python for path resolution (`TODO_CLEANUP` → migratable to `get-path-config` MCP), and `list-skills` returns empty `triggers` (minor fidelity vs the old CLI; descriptions/titles intact). The spec's open question (chains/buttons) was moot — the route made only one CLI call (`list -j`).

## Related

- ADR-642 — sanctioned `@spawn-exempt` precedent (ADR archive extraction).
- ADR-810 — agent-callable dev surface / SDLC autonomy.

## Impact Manifest

```yaml
impact:
  paths_renamed: []
  apis_changed:
    - "GET /api/mcp/capabilities: internal data source moves from CLI spawn to POST /api/mcp/tool (response shape unchanged)"
  patterns_deprecated:
    - "dashboard server-side spawn/exec for data introspection (replaced by MCP tool calls)"
  files_affected:
    - apps/dashboard/app/api/mcp/capabilities/route.ts
    - apps/dashboard/lib/server/cliRunner.ts
    - apps/dashboard/lib/server/pythonRunner.ts
    - apps/dashboard/lib/server/spawn.ts
    - apps/dashboard/app/actions.ts
    - apps/dashboard/app/api/cli/cli-config.ts
    - apps/dashboard/lib/server/nativeTerminal.ts
```
