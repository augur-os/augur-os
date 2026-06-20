---
title: Bidirectional Routine Drift Detection and Resolution
date: 2026-05-17
status: draft
related:
  - src/lib/runtime/codex_automations.py
  - src/mcp/augur_framework/tools/infrastructure/browse/scheduled_sources/
  - src/mcp/augur_framework/tools/infrastructure/browse/scheduled_executions.py
  - src/mcp/augur_framework/tools/infrastructure/browse/index.py
  - apps/dashboard/lib/browse/cardModel.ts
  - apps/dashboard/components/shared/BrowseCategoryActions.tsx
  - shared-vault/skills/daemon/scripts/mcp/__init__.py
  - shared-vault/skills/ai/scripts/sync_agents/adapters/codex.py
---

# Bidirectional Routine Drift Detection and Resolution

## Goal

Augur declares background routines in repo-tracked seed files and projects them into two runtime surfaces: Codex automations on the local filesystem and Claude remote routines in the Anthropic cloud. Today the projection is one-way and destructive — any edit a user makes directly in Codex or Claude is silently overwritten on the next sync. The user must be able to (a) see drift surfaced honestly per routine, (b) refresh the Browse view from cloud truth on demand, and (c) resolve each drift explicitly by either pulling the surface state into the seed or pushing the seed back over the surface.

This is a user-visible correctness fix. A schedule that the user tunes in Codex and then watches Augur silently overwrite is worse than no Augur layer at all.

## Scope

In scope:

- Identity markers and drift detection across Codex automations, Claude remote routines, and Augur-internal schedules.
- Non-destructive sync that preserves user edits unless explicitly forced.
- A read-through cache file for Claude remote routines, refreshable on demand from any single machine without cross-machine coordination.
- Two explicit per-routine conflict-resolution actions: `Adopt cloud version` and `Push my version`.
- A drift CLI (`aug routine drift`) and matching MCP tools for the dashboard.
- Browse-card visibility of `managed_by` and `drift_status` with a cache-age freshness indicator on Claude-remote cards.

Out of scope:

- Forking a drifted routine into a permanent second seed entry (`Keep both`). If the user wants two divergent routines, they add a new seed entry manually.
- Cross-machine cache sharing. Each laptop's cache is independent; refresh re-reads cloud truth per machine. Multi-machine consistency is deferred to a follow-up ADR.
- A daemon-driven background refresh schedule. Refresh stays user-triggered; Browse cards show last-fetched timestamp so the user knows the freshness.
- File locking for concurrent edit races. Last writer wins; next refresh reflects actual disk state.
- A push-back path for Claude remote that bypasses the `claude --print` subprocess (i.e. direct API auth from server-side Python). The subprocess pattern is the v1 strategy; addendum-ADR if it proves unreliable.

## Architecture

### The three-surface model

Each routine has up to three representations:

- **Seed** (declarative source): `assets/seeds/routine-schedule.yaml` under the owning skill. Lives in git, single source of intent for Augur-owned routines.
- **Installed surface state**: `~/.codex/automations/<id>/automation.toml` for Codex; cloud routine record (Anthropic `RemoteTrigger`) for Claude. The runtime that actually fires schedules.
- **Local cache** (Claude only, per-machine): `<cache_dir>/claude-remote-routines.json`. A snapshot of the cloud, refreshed on demand. Reflects what this machine last saw of cloud truth; the cache file IS the per-machine ownership registry for Claude remote routines.

A routine may exist in any subset of these. Augur classifies each routine by ownership and drift status on every read.

### Identity markers

- **Codex**: every TOML Augur writes embeds `managed_by = "augur"` and `augur_seed_hash = "<sha>"`. The hash is computed at write time over the canonical schedule fields (id, prompt, rrule, model, reasoning_effort, workspace).
- **Claude remote**: the Anthropic API exposes no metadata field, so the cache file IS the registry. Any routine id present in the cache is Augur-owned. Any cloud routine id not in the cache is `external`.
- **Augur-internal**: every entry is Augur-owned by construction.

### Drift detection

Drift detection runs in-process on every Browse read; it is cheap (file parse + hash compare).

For Codex: parse the installed TOML, project its current fields back into a schedule-shaped dict, recompute the hash, compare to the embedded `augur_seed_hash`. Mismatch means the user has edited the TOML since Augur wrote it (`codex-edited`). Separately, compare the embedded hash against the hash of the current desired seed; mismatch there means Augur's intent has moved on but the TOML still reflects its last write (`seed-evolved`).

For Claude remote: the cache file carries one `drift_status` field per cached routine. The freshness signal lives in the cache's top-level `fetched_at` timestamp. Drift is reclassified during refresh, which fetches cloud truth and compares to the cached snapshot before overwriting it.

For Augur-internal: always `in-sync` (single owner, no concurrent writers).

### Non-destructive sync

`sync_codex_automations` checks each existing TOML before overwrite:

- Untagged (no `managed_by = "augur"`) → skip (manual user creation, never touch).
- Tagged but file-hash mismatch (user edited) → skip with a warning unless `force=True`.
- Tagged and file-hash matches → safe to overwrite from current seed.

Prune deletes only tagged entries no longer present in the desired-seed set; untagged entries survive prune.

### Conflict resolution

Two explicit user-triggered actions per drifted routine:

- **Adopt cloud version**: pull the surface state into the seed file. For Codex: read the live TOML fields, locate the seed entry that owns that id (by scanning skill roots), rewrite the entry in YAML, then re-sync to re-embed a fresh `augur_seed_hash`. For Claude remote: a no-op for v1 (claude routines have no seed file today; adopting just acknowledges the cache as desired — future ADR may give claude routines real seeds).
- **Push my version**: force-sync seed over surface for one routine. For Codex: `sync_codex_automations` scoped to that routine_id with `force=True`. For Claude remote: spawn `claude --print` to call `RemoteTrigger action=update` with the cached fields (same subprocess pattern as refresh, same OAuth boundary).

No third action. If the user wants two divergent routines, they add a second seed entry by hand — explicit beats implicit.

### Refresh model

Cloud refresh is manual and user-triggered. Two MCP tools back the dashboard buttons:

- `routine-refresh-codex`: pure server-side rescan of `~/.codex/automations/`. Fast, no external calls.
- `routine-refresh-cloud`: spawns `claude --print "<refresh prompt>"`. The subprocess inherits the user's OAuth via the Claude CLI, calls `RemoteTrigger action=list`, and rewrites the cache file in Augur's normalized schema. The Anthropic OAuth token is never read or stored by server-side Python.

Browse cards on the `claude-remote` source display a freshness label derived from the cache's `fetched_at` timestamp (e.g. "cache: 14m ago"). This is the user's signal that what they see may or may not be current.

## Components

### Server (Python)

- `src/lib/runtime/codex_automations.py` — `compute_seed_hash`, `_toml_fields_to_schedule_shape`, `read_automation_drift_status`, non-destructive `sync_codex_automations`.
- `src/mcp/augur_framework/tools/infrastructure/browse/scheduled_sources/codex.py` — reads installed Codex TOMLs, emits `managed_by`/`drift_status`. Loads desired seeds via `_load_desired_seeds`.
- `src/mcp/augur_framework/tools/infrastructure/browse/scheduled_sources/claude_remote.py` — reads cache file, emits one row per cached routine. Owner always `augur`.
- `src/mcp/augur_framework/tools/infrastructure/browse/scheduled_sources/claude.py` — local-agent-mode tasks; schema bug fixed (`scheduledTasks` ∨ `tasks`).
- `src/mcp/augur_framework/tools/infrastructure/browse/scheduled_sources/augur_internal.py` — daemon-owned loops, always in-sync.
- `src/mcp/augur_framework/tools/infrastructure/browse/scheduled_executions.py` — aggregator; merges sources and exposes refresh + conflict impls.
- `src/mcp/augur_framework/tools/infrastructure/browse/index.py` — merges aggregator output into the `background-routines` Browse category.

### MCP tools

| Tool | Purpose | Status |
|---|---|---|
| `routine-refresh-codex` | Rescan installed Codex automations. | shipped |
| `routine-refresh-cloud` | Spawn `claude --print` to refresh cache. | shipped |
| `routine-adopt-cloud` | Pull surface state into seed. | Phase D |
| `routine-push-local` | Force-sync seed over surface. | Phase D |

### CLI verbs

| Verb | Status |
|---|---|
| `aug routine drift [--source]` | shipped |
| `aug routine adopt <id>` | Phase D |
| `aug routine push <id> [--force]` | Phase D |

### Dashboard

- `apps/dashboard/lib/browse/cardModel.ts:routineSlots` — owner and drift badges per card. Shipped.
- `apps/dashboard/components/shared/BrowseCategoryActions.tsx` — Refresh Codex / Refresh cloud menu items. Shipped.
- Per-card secondary actions for `Adopt cloud` / `Push my version` on drifted entries. Phase D.
- Freshness label on `claude-remote` cards derived from cache `fetched_at`. Phase D.

### Cache file schema

```json
{
  "fetched_at": "<iso8601 UTC>",
  "routines": [
    {
      "id": "<trigger id>",
      "name": "<display name>",
      "cron_expression": "<cron>",
      "enabled": true,
      "prompt_summary": "<one-line prompt>",
      "model": "<session model>",
      "repo": "<git url>",
      "last_run_at": null,
      "next_run_at": "<iso8601 or null>",
      "drift_status": "in-sync | cloud-edited | cloud-deleted"
    }
  ]
}
```

## Data flow

### Write path (seed → surface)

```
routine-schedule.yaml (seed)
    │ load_codex_schedule_seed
    ▼
schedules: list[dict]
    │ sync_codex_automations(apply=True, prune=True, force=False)
    ▼
for each schedule:
  ├── read installed TOML
  ├── read_automation_drift_status → (managed_by, drift_status)
  ├── managed_by == "manual"        → SKIP (untagged; user owns)
  ├── drift_status == "codex-edited" → SKIP (user edited)
  └── else                           → WRITE TOML (embed augur_seed_hash)
prune: delete only tagged entries no longer in desired set
```

### Read path (Browse renders)

```
GET /browse?view=background-routines
    │ /api/mcp/tool → browse-index(category="background-routines")
    ▼
browse_index_impl
    ├── background_routines.list_background_routine_items (daemon, launchd, GH actions)
    └── scheduled_executions.list_scheduled_execution_items
          ├── load_augur_internal_schedules
          ├── load_codex_schedules         (TOML + drift detection)
          ├── load_claude_schedules        (local agent mode, legacy)
          └── load_claude_remote_schedules (cache file)
    │
    ▼ cardModel.routineSlots
       ├── badges: cadence, status, owner, drift
       └── metadata rows: managed_by, drift_status, freshness
    │
    ▼ BrowseDisplayRenderer → cards on screen
```

### Refresh path (cloud)

```
user clicks "Refresh cloud routines"
    │ mcpCall("routine-refresh-cloud")
    ▼
refresh_cloud_routines_impl
    ├── spawn `claude --print "<refresh prompt>"`
    │     └── Claude session uses RemoteTrigger action=list
    │           └── Write tool → cache file with fetched_at + routines
    ├── re-read cache → list_scheduled_execution_items
    └── return updated cloud entries + fetched_at
```

### Adopt path

```
user clicks "Adopt cloud version" on drifted card
    │ mcpCall("routine-adopt-cloud", {routine_id})
    ▼
routine_adopt_cloud_impl
    ├── source==codex: read installed TOML; locate seed file owning this id;
    │                  rewrite YAML entry to match TOML fields; re-sync
    │                  (force=False, will now match)
    ├── source==claude-remote: v1 no-op (no seed file exists for claude
    │                          routines today)
    └── return refreshed Browse rows
```

### Push path

```
user clicks "Push my version" on drifted card
    │ mcpCall("routine-push-local", {routine_id})
    ▼
routine_push_local_impl
    ├── source==codex: sync_codex_automations(seeds, force=True) scoped to this id
    ├── source==claude-remote: spawn `claude --print` to call RemoteTrigger
    │                          action=update with cached fields
    └── return refreshed Browse rows
```

## Error handling

| Failure | Behavior |
|---|---|
| TOML parse error during sync | Treat as `unknown` ownership → skip; log to stderr. Sync continues. |
| Cache file missing or corrupt | `load_claude_remote_schedules` returns `[]`. Browse shows 0 claude-remote cards. Refresh re-creates cache. |
| `claude` CLI not on PATH | Refresh tool returns `{success: false, error: "..."}`. Dashboard shows error toast with copy-paste fallback command. |
| `claude --print` timeout (120s) | Same as above. Cache untouched. |
| Adopt finds no matching seed file | Return error: "No Augur seed owns this id; entry may be external." UI disables Adopt upfront for external entries. |
| RemoteTrigger update fails on push | Return subprocess error; cache untouched; user retries. |
| Two processes edit same TOML concurrently | Last writer wins; next refresh reflects actual disk state. No locking in v1. |
| User deletes routine on claude.ai between refreshes | Next refresh marks cache entry `cloud-deleted`; Adopt removes it from cache; next sync prune respects the deletion. |

## Testing strategy

### Unit tests

| What | How |
|---|---|
| `compute_seed_hash` determinism | Same input → same hash; field-order independent. |
| `read_automation_drift_status` per case | Fixtures: untagged TOML, matching hash, mismatched hash, missing-from-seed. Assert returned tuple. |
| `_toml_fields_to_schedule_shape` projection | Round-trip: render TOML → re-parse → re-hash → equals embedded hash. |
| `sync_codex_automations` non-destructive | Setup: tagged TOML with manual edit. Run sync without force. Assert file unchanged + skip warning. |
| `sync_codex_automations` force=True | Same setup. Run with force. Assert file overwritten. |
| `sync_codex_automations` prune skips untagged | Setup: untagged TOML + tagged TOML neither in desired set. Run prune. Assert only tagged deleted. |
| `load_claude_remote_schedules` schema | Empty cache returns `[]`; one routine returns one normalized row. |
| `routine_adopt_cloud_impl` | Set up drifted TOML; call adopt; assert seed YAML matches surface; subsequent drift check returns `in-sync`. |

### Integration tests

| What | How |
|---|---|
| End-to-end sync skip on drift | Real fixture path; write tagged TOML; mutate cron; run sync; assert skip + file preserved. |
| `aug routine drift` JSON shape | Run CLI; parse stdout; assert keys present and counts add up. |
| `routine-refresh-codex` MCP tool round-trip | Spawn augur-core MCP server; invoke tool; assert response shape. |

### Dashboard end-to-end

Per CLAUDE.md rule 28, every dashboard change must be verified in a real browser, not via curl or accessibility-tree alone.

| What | How |
|---|---|
| Drift badge renders correctly | Setup: tagged TOML with mutated cron. Open `/browse?view=background-routines`. Screenshot. Assert orange `codex-edited` badge visible on the card with the mutated cron displayed. |
| Refresh-codex button calls tool | Click "Refresh Codex routines" in Manage menu. Assert toast appears, card list re-fetches. |
| Refresh-cloud button shows fallback when CLI missing | Mock PATH to remove `claude`. Click "Refresh cloud routines". Assert error toast with copy-button. |
| Adopt action clears drift | Click kebab → "Adopt cloud version" on drifted card. Assert seed file updated, badge changes to `in sync`. |

## Status

Phases A–C are shipped and verified end-to-end (Section 5 manual smoke test confirmed during the session that authored this spec). Phase D — the two conflict-resolution MCP tools, matching CLI verbs, per-card kebab actions, and freshness label — remains for implementation.
