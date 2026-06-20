---
title: project-browse-devonly-view-hydration-race
name: project-browse-devonly-view-hydration-race
description: Hard-navigating to a Browse devOnly view (e.g. ?view=agent-profiles)
  can race the dashboard-mode rehydration and fall back to Skills; switch via in-app
  tab click or preset localStorage
brain_scope: project
type: project
status: active
source_client: claude-code
source_file: project_browse_devonly_view_hydration_race.md
source_hash: 81cc9ba3fc356147
---


Browse devOnly categories (agent-profiles, mcp-tools, etc.) only render when dashboard mode is `development`. `isDev = (useModeStore.mode === "development")`, and the mode store (`apps/dashboard/lib/stores/modeStore.ts`) starts at the SSR-safe default `operation`, then rehydrates from `localStorage["augur:dashboard-mode"]` in a `queueMicrotask` AFTER mount.

So a hard browser navigation to `http://localhost:3000/browse?view=agent-profiles` frequently lands on the **Skills** view with "More 6": at the moment `readUrlViewMode` runs, `isDev` is still false (pre-microtask), so the devOnly view resolves to `skills`. The nav can even show the dev tab as "selected" while the content pane still shows Skills (stale-render mismatch).

**How to reach a devOnly Browse view reliably when verifying in-browser:**
- Preferred: do an in-app tab click (click the "Agent Profiles" tab / "More 17" dropdown) — no reload, no race, once `isDev` is already true.
- Or set `localStorage["augur:dashboard-mode"]="development"` (and optionally `localStorage["augur:browse:view"]="agent-profiles"`), then reload and wait for hydration before asserting.

This is NOT a degraded dev server — the page loads and APIs return 200s; it's purely the mode-hydration timing. Don't reach for `/dev-build` over it. Related: [[project-worktree-dashboard-port-verification]], [[feedback-client-side-verification]].
