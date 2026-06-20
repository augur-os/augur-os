---
status: Implemented
date: 2026-05-11
deciders:
  - gsannikov
related:
  - ADR-722
  - ADR-723
hub: command
tags:
  - daemon
  - dashboard
  - browse
  - discoverability
  - background-routines
  - mcp
superseded_by: null
spec_file: 2026-05-11-background-routines-unified-design.md
plan_file: 2026-05-11-background-routines-unified.md
---

# ADR-727: Background Routines — Unified Discovery and Browse Category

> **ADR-727 is an index file.** The substantive design and implementation steps live in the linked spec. The implementation plan is pending (`/superpowers:writing-plans` to be run next). This file carries pointers, status, and a one-line decision summary.

## Decision summary

Replace the misleadingly-named `scheduled-executions` Browse category with a unified `background-routines` category that discovers all six kinds of autonomous triggers on the machine (`per-skill-schedule`, `daemon-service`, `daemon-script`, `launchd-agent`, `github-action`, `mcp-background`), exposes a unified `Routine` schema with **cadence + last-run as first-class UI surfaces** in card / table / detail panel / description line, and surfaces estimated token cost per AI-CLI-spawning routine so users can see what's burning their Claude budget at a glance.

## Spec (canonical)

- [`docs/superpowers/specs/2026-05-11-background-routines-unified-design.md`](../superpowers/specs/2026-05-11-background-routines-unified-design.md)

## Plan (canonical, drives `/adr implement`)

- [`docs/superpowers/plans/2026-05-11-background-routines-unified.md`](../superpowers/plans/2026-05-11-background-routines-unified.md) — 19 tasks across 4 spec checkpoints. TDD discipline: each task is one focused commit.

## Status notes

**Discovered 2026-05-11 morning.** User woke up to find 30%+ of their Claude 5h budget consumed overnight with no visible activity in Claude Code session history. Investigation traced the consumption to `insight_scanner` — a daemon adaptive-loop service from `config/system/adaptive_loops.yaml` that runs every 12h and spawns ~39 Claude Code background sessions (one per dashboard page) asking for improvement suggestions. The bug: the Browse "Scheduled Executions" page only shows `per-skill-schedule` entries; daemon-service / daemon-script / launchd / GitHub-Actions / MCP-background routines are invisible. The user can't disable what they can't see.

**Tactical defense already in place** (commit `41c7a2509`): `insight_scanner.interval_hours` set to `876000` in `adaptive_loops.yaml`, deferring its next fire ~100 years. This is the immediate gate; this ADR is the structural fix.

Spec written 2026-05-11 in same session via `/superpowers:brainstorming`. Broad scope chosen (all six source kinds, not just the two existing systems). View-only controls for v1 (pause/run-now/edit deferred to follow-on ADRs). Token-cost surfacing on by default — the killer feature that turns the dashboard into the canonical "what's burning my Claude budget" view.

Ready to implement once the plan is produced.

## Related

- ADR-722 — Setup Completeness Widget (parallel pattern: dashboard surfaces something the user couldn't otherwise see)
- ADR-723 — Augur Pages HTML Artifacts (parallel pattern: another Browse-category-driven discoverability fix; `kind` chip pattern echoed here as `source_kind` chips)
- ADR-216 — Hot-reload interval each cycle from service config (archived; the mechanism that lets `interval_hours: 876000` take effect within the next daemon cycle)
- ADR-176 — Adaptive Loop Engine (archived; introduced the daemon services this ADR newly surfaces)
- `docs/references/ai-client-execution-model.md` — "Trigger → AI Client Session → Agent orchestrates → MCP tools execute" (the execution model that made daemon-spawned Claude sessions invisible to UI)

## Impact manifest

```yaml
paths_renamed:
  - "Browse category id: scheduled-executions → background-routines"
  - "RAG index category: scheduled-executions → background-routines"
  - "Detail panel component: ScheduledExecutionDetailPanel.tsx → BackgroundRoutineDetailPanel.tsx"
apis_changed:
  - "New MCP tool: list-routines (returns unified Routine[] across all 6 source kinds, with filters: source_kind, spawn_kind, status)"
  - "Type alias for one release: ScheduledExecutionDetail → Routine"
patterns_deprecated:
  - "Browse category id scheduled-executions — one-release alias period (URL redirect + type alias), then removed per CLAUDE.md rule 14"
files_affected:
  - "shared-vault/skills/daemon/scripts/routine_discovery.py (NEW)"
  - "shared-vault/skills/daemon/scripts/schedule_executor.py (per-skill-schedule discoverer reuses discover_schedules)"
  - "shared-vault/skills/daemon/scripts/mcp/routine_tools.py (NEW — list-routines MCP tool)"
  - "apps/dashboard/lib/browse/types.ts (BROWSE_CATEGORIES + ViewMode union)"
  - "apps/dashboard/lib/browse/transforms.ts (case rename + new description line format)"
  - "apps/dashboard/lib/browse/routine-format.ts (NEW — formatCadence, formatRelativeTime, humanizeTokens helpers)"
  - "apps/dashboard/components/shared/ScheduledExecutionDetailPanel.tsx → BackgroundRoutineDetailPanel.tsx (rename + 2-column cadence/last-run layout)"
  - "apps/dashboard/components/shared/ScheduledExecutionTableView.tsx (column updates + first-class cadence/next-run/last-run that survive responsive collapse)"
  - "apps/dashboard/app/(views)/browse/useBrowseState.ts (?category=scheduled-executions → background-routines redirect)"
  - "shared-vault/skills/ingest/scripts/wiki_source_inventory.py (category id rename)"
  - "tests/unit/test_routine_discovery.py (NEW — per-discoverer + aggregation tests)"
  - "tests/unit/test_list_routines_mcp.py (NEW — MCP tool tests)"
  - "config/system/capability_exposure.yaml (list-routines entry)"
```
