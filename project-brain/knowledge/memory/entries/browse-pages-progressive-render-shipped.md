---
title: browse-pages-progressive-render-shipped
name: browse-pages-progressive-render-shipped
description: Browse pages tab progressive render + artifacts-in-index shipped (2026-06-11);
  diagnosis lessons (occlusion throttling, MCP per-call overhead) and the recorded
  out-of-scope follow-ups
brain_scope: project
type: project
status: active
source_client: claude-code
source_file: browse-pages-progressive-render-shipped.md
source_hash: c9d947f6a3dd9456
---


Browse pages load-speed work shipped to main 2026-06-11 (spec `docs/superpowers/specs/2026-06-10-browse-pages-load-speed-design.md`, 12 commits ending `1949cfb5a` + merge `6120dad6f`). Pages tab: first card ~420ms, full 44-card set ~920ms on :3000 (was 3.5s–minutes).

**What shipped:** (a) `index_pages` Pass 3 ingests sidecar-backed HTML artifacts into the pages browse index (`artifact--{slug}.md`; sidecar I/O now in `src/lib/artifacts_sidecar.py`, MCP-import-free for the indexer); (b) `save-artifact`/`artifacts-reindex` refresh the pages category via `asyncio.to_thread`; (c) dashboard pages tab dropped its `artifacts-list` query (`extractIndexedArtifacts` reads them from browse-index items); (d) Browse `loading` gate is dataLoading only — folder-context/pins no longer block; skeletons/error-state only when the grid is empty; error banner rides partial content; loading pill covers `loading || reindexing`.

**Diagnosis lessons:**
- An occluded Chrome window (`document.visibilityState === "hidden"` — common when driving the browser remotely or when it's behind the terminal) throttles timers and can stretch dashboard loading states from seconds to minutes. ALWAYS check `visibilityState` before trusting browser timing measurements.
- React Query v5: a manual `refetch()` on an existing key keeps `status: "success"` — `loading` (status==="pending") never fires for same-key refetches; pending-forever is the signature of a disabled query. Fiber-walking `memoizedProps.client.getQueryCache()` from the page is an effective way to dump live query states.

**MCP per-call overhead FIXED (2026-06-11, commits `aa45055e5`+`16e9c8a0a`-era on main):** root cause was NOT transport — the GIL serialized concurrent tool calls because `insights-pending` re-parsed a 1.3MB/2,377-insight `insights.yaml` with pure-Python `yaml.safe_load` (~640ms CPU) on every dashboard page load (and returned a 1.16MB response the badge never read). Fix: mtime-keyed parse cache + CSafeLoader in `daemon/scripts/insights_pending_impl.py` + `count_only` arg from FloatingChat. Burst of 12 concurrent tools: wall 1.69s→0.64s, worst call 1.66s→0.60s. Diagnosis keys: burst wall ≈ sum of solo times = GIL/CPU serialization, not queueing; `mcp_invocations.jsonl` `duration_ms` includes pool/GIL wait, so compare solo-vs-burst durations. Gotcha: skill MCP modules must load sibling impls via `spec_from_file_location` (namespaced), never bare `import` — the plugin loader doesn't put the skill's scripts dir on sys.path (broke registration silently: "Failed to load MCP tools ... No module named").

**Remaining follow-ups:** ~2,074 PENDING daemon insights accumulated (badge shows 2074; needs pruning/resolution policy — data hygiene, user decision); app shell fires ~11 non-browse MCP calls per load plus `get_local_backend_status` polling every 5–15s (ollama subprocess probes each time); `/api/health` returns 500 on :3000; residual burst CPU ~0.4s spread across diagnostics/plugin-events/setup tools.

Related: [[sdlc-autonomy-aug-dev-build]], [[project-worktree-dashboard-port-verification]]
