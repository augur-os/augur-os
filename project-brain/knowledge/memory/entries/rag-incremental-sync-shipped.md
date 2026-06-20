---
title: rag-incremental-sync-shipped
name: rag-incremental-sync-shipped
description: RAG watcher-driven freshness shipped 2026-06-10 — architecture, ops levers,
  and the dashboard-MCP exposure gate that bit during closeout
brain_scope: project
type: project
status: active
source_client: claude-code
source_file: rag-incremental-sync-shipped.md
source_hash: 1cfb875a87f1006c
---


RAG incremental sync (spec/plan docs/superpowers/{specs,plans}/2026-06-10-rag-incremental-sync*) shipped to main 2026-06-10 (merge a2fd181f8 + closeout fix 0841f1c37).

**Architecture:** `rag_watcher` daemon child service (watchdog/FSEvents, supervised by unified_daemon) watches brain-registry roots + document sources → 3s debounce per category → `src/lib/index/incremental.sync_categories()` (scoped `reindex_category` + manifest patch under a PID-stamped lock at runtime/`rag_sync.lock`). Only `documents` triggers chunk/BM25 work. Surfaces: `aug rag sync|status`, `rag-sync`/`rag-status` MCP tools, dashboard RAG card "Sync now". Measured: note→indexed in ~5s; delete propagation ~4s.

**Root cause of the old staleness:** nightly adaptive loops require a Codex client schedule manifest — the daemon's `--loop` executor only runs `continuous` triggers, so `knowledge-enrichment` never fired. The daily reconcile now lives inside rag_watcher (03:00, full `reindex_all`).

**Known behaviors / ops levers:**
- Reconcile date IS persisted across restarts (fixed e777a23dc, same day): WatcherCore seeds from `rag_watcher_state.json`'s `last_reconcile_date`, so daemon restarts after 03:00 no longer pay a redundant full reindex; stale categories still recover via the startup catch-up diff. (Note: the running watcher uses old code until the next daemon restart.)
- `aug dev build` did NOT recycle the dashboard bridge's MCP children in this session (`mcp_recycled: false`); recycling them manually (`kill <dashboard-Augur-* pids>`) is safe — the bridge respawns on next request.
- The dashboard `/api/mcp/tool` "Unknown tool" gate is `src/lib/capabilities/export_filter.allowed_mcp_runtime_tool_names`: dashboard targets only register tools whose `capability_exposure.yaml` entry has `primary_surface: mcp|mcp via dashboard` — tools with NO entry pass by default. That's why rag-sync (no entry) worked while rag-status (`primary_surface: cli`) was invisible for months and the RAG card showed "No stat data available" since inception.
- Running Augur CLI/ops from a git worktree can rewrite client MCP configs (claude_desktop_config.json) to the worktree path → "System Move Detected" overlay on the dashboard; the overlay's Heal button repairs toward the :3000 server's own root and is the sanctioned fix.

**Honest residuals:** 5 pre-existing main test failures (tests/dashboard/python/test_mcp.py::test_audit_plugin_all + 4 in tests/packages/augur-mcp/infrastructure/test_browse_helpers.py) — deliberately NOT fixed by this session because a parallel session's ADR-771 personal-vault-layout refactor had test_browse_helpers.py + src/config/paths.py dirty in the main checkout (fixing in parallel would collide); re-check after their merge. evals replay WARN attributed to 17-day index/manifest drift (1aed3493→f6aba02c), not code — judgments need recapture. Old `x-augur-config.loop` (knowledge-enrichment) block still in rag SKILL.md frontmatter — now redundant with the watcher reconcile, removal is a separate decision.

Related: [[sdlc-autonomy-aug-dev-build]], [[project-worktree-dashboard-port-verification]]
