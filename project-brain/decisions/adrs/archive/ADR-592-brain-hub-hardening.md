---
status: Implemented
date: 2026-04-22
deciders:
  - Gur Sannikov
related: []
hub: brain
tags: []
superseded_by: null
---

# ADR-592: Brain Hub Hardening

## Context

The Brain hub had buttons that did not always produce visible outcomes, displayed values without source or freshness context, and a backlog of staged surfaces (Agent Control Center, Brain Harness, RAG pages, schedule, OCR/import) that were close to ready but not held to a real survival gate. Some pages used silent fallback data when MCP calls failed, which made broken state look healthy.

Brain should be trustworthy as a user-facing control surface: every visible button performs a useful action or explains why it is unavailable, every displayed value comes from current real data with clear stale/empty/error states, and the flat IA (`/brain/memory`, `/brain/search`, `/brain/daily-logs`, `/brain/profile`, `/brain/workspace`) is preserved.

Staged Brain code should not become live just because it exists. Surfaces with overlapping ownership (RAG vs Search/Workspace, schedule vs central scheduler, OCR with non-MCP endpoints) should remain staged until they have a distinct Brain job and pass the gate.

## Decision

Use a contract-driven survival audit with two tracks:

1. Harden the five live Brain pages against shared **action** and **data** contracts:
   - Backend MCP tools (`tools_memory_dashboard.py`, `tools_memory_profile.py`) expose explicit source/freshness fields and structured profile writes through `write_frontmatter()`.
   - Dashboard adds shared `contracts.ts` (`assertMcpSuccess`, `formatFreshness`, `formatOperationError`, `getPrimarySourceLabel`) and harden hooks to remove fallback data and surface success/error notices.
   - Live pages and components (`MemorySearchWidget`, `DailyLogsCalendar`, `HumanApiProfile`, `MemoryWorkspacePanel`, `WikiMaintenancePanel`) display source labels, freshness, and visible action outcomes.

2. Run each staged Brain surface through a survival gate (distinct Brain value, exact MCP wiring, real data, visible outcomes, ownership, tests, browser verification). Promote only those that pass:
   - Promote Agent Control Center to `/brain/agents` and Brain Harness to `/brain/harness`.
   - Defer RAG/schedule pages for rework; do not promote OCR/import (relies on beta/mock text and non-MCP endpoint).
   - Record the audit in `docs/references/brain-hub-staged-surface-audit.md`.

Verification requires browser-load on the worktree-owned dashboard port for every live and promoted route.

## Consequences

### Positive
- Brain pages display current data with explicit source, freshness, and operation outcome.
- Staged code is judged by user value, not by existence.
- Promoted pages (`/brain/agents`, `/brain/harness`) extend Brain with non-overlapping value.
- Failed MCP calls surface in the UI instead of being hidden by fallback data.

### Negative
- Some staged pages remain unshipped until rework lands.
- Provider configuration stays in Settings; users looking for it under Brain need a one-hop redirect.

### Neutral
- Brain IA stays flat; no nested `/brain/knowledge/memory` style routes are reintroduced.

## Alternatives Considered

### Alternative 1: Revive the whole Brain cockpit
Promote Agent Control Center, Harness, RAG pages, schedules, and OCR at once. Rejected: too broad, risks duplicate ownership, stale wiring, and nested navigation.

### Alternative 2: Live pages first, staged backlog second
Safest for current five pages but leaves the staged-surface scope unresolved.

## References
- Plan: docs/superpowers/plans/2026-04-22-brain-hub-hardening.md
- Spec: docs/superpowers/specs/2026-04-22-brain-hub-hardening-design.md
