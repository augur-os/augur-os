---
title: Track 4 — Visibility Filter Removal (Design)
date: 2026-04-29
status: proposed
scope: design
related:
  - 2026-04-28-cross-client-bundle-architecture-design.md
  - 2026-04-28-cross-client-bundle-migration-design.md
  - 2026-04-29-track3a-framework-split-design.md
---

# Track 4 — Visibility Filter Removal (Design)

## Purpose

The original `CURATED_VISIBLE_TOOLS` and `COWORK_VISIBLE_TOOLS` filters in `client_surface.py` exist because the `augur` monolith registered ~200 tools and exposing all of them to every client (Claude Code, Codex, Gemini) overwhelmed the AI's tool selector — the filter restricted the surface to ~9% of tools per client.

After Tracks 1, 2, 3a, the architecture eliminates the root cause:
- Track 1 extracted 5 framework libraries to `src/lib/` — tools backed by these libraries became operational/framework concerns
- Track 2 split 5 vault bundles into per-bundle MCP servers (each with 7-42 tools max)
- Track 3a split the project monolith into `augur-core` (29 tools) + `augur-framework` (~114 tools), retired 23 dormant tools, and dismantled the `augur_mcp/` namespace

After Track 3a ships, no server registers more than ~114 tools. The visibility filter is no longer the bandage hiding the 200-tool problem — it's just dead code adding indirection.

Track 4 deletes the filter and the `x-augur-visibility` field references that the filter consumed.

## Decisions

- **Single PR, single small commit.** No coordination across repos, no manifest changes, no client-config updates. Just delete dead code.
- **Delete `CURATED_VISIBLE_TOOLS` and `COWORK_VISIBLE_TOOLS` frozensets** in `src/mcp/augur_shared/client_surface.py` (after Track 3a's move) or `src/mcp/augur_mcp/client_surface.py` (if running before Track 3a).
- **Simplify or delete `filter_tools_for_client`.** If the filter logic is purely visibility-based, delete entirely. If there are residual non-visibility branches (e.g., per-client metadata), simplify to those paths only.
- **Remove `x-augur-visibility` field references** from any code that still reads it. The field was already irrelevant by Layer 1; this PR removes the dead reads.
- **Ships after Track 3a** because the filter lives in `client_surface.py` which Track 3a moves and reorganizes. Running Track 4 before Track 3a creates merge conflicts.
- **Tracks 1, 2, 3a are independent prerequisites for the GOAL** (no server is overwhelmed) but the FILE that gets deleted lives wherever Track 3a put it. Track 4 must run AFTER 3a.

## Architecture

### What gets deleted

After Track 3a's PR 7 (`src/mcp/augur_mcp/` dismantled), the visibility infrastructure lives in `src/mcp/augur_shared/client_surface.py`. Track 4 deletes:

- The `CURATED_VISIBLE_TOOLS` frozenset literal
- The `COWORK_VISIBLE_TOOLS` frozenset literal
- The `filter_tools_for_client(client_id, tools)` function (if its only logic is visibility filtering)
- Any imports of these symbols across `src/`, `apps/`, `tests/`
- `x-augur-visibility` field reads in any module (Augur-side and dashboard-side)

If `filter_tools_for_client` has non-visibility branches (e.g., per-client tool name customization), simplify it to only those branches; the visibility filter conditional is removed.

### What stays

- The 7 servers (augur-core, augur-framework, 5 vault) keep their per-server `tools/list` registration as-is — no tool count changes.
- The `aug config sync` CLI is unaffected.
- Per-client capability advertisement (e.g., `apps/dashboard/app/api/mcp/capabilities/route.ts`) still operates if it has logic beyond the now-deleted filter.

### Test cleanup

Tests that asserted the filter's behavior are deleted or updated:
- Any test in `tests/` that checks `CURATED_VISIBLE_TOOLS` membership gets deleted (no longer meaningful).
- Any test that exercises `filter_tools_for_client` either gets deleted (filter is gone) or simplifies if the function survives in reduced form.

### Verification

Per the migration spec's Track 4 verification:
- A fresh Claude Code session lists previously-hidden tools (e.g., `apple-list-emails` from `augur-apple`, `obsidian-read` from `augur-obsidian`, `extract-document` from `augur-framework`).
- A fresh Codex session does the same.
- A fresh Gemini session does the same.
- `tools/list` against `augur-core` and `augur-framework` returns the same tools regardless of which client connects (no per-client filtering).
- The 91%-hidden problem cannot recur because the mechanism that caused it no longer exists.

## Migration shape (1 PR)

### PR 1 — Delete visibility filter

Steps:

1. Read `src/mcp/augur_shared/client_surface.py` to see current shape post-Track-3a.
2. Delete `CURATED_VISIBLE_TOOLS` and `COWORK_VISIBLE_TOOLS` frozenset literals.
3. Inspect `filter_tools_for_client` — if its only logic is visibility filtering, delete the function. If it has other logic, simplify to remove the visibility branch only.
4. Audit grep for symbol references:
   ```bash
   grep -rn "CURATED_VISIBLE_TOOLS\|COWORK_VISIBLE_TOOLS\|filter_tools_for_client" --include="*.py" --include="*.ts" --include="*.tsx" .
   ```
5. Update or delete each reference based on what filter_tools_for_client looks like post-simplification.
6. Audit grep for `x-augur-visibility`:
   ```bash
   grep -rn "x-augur-visibility\|x_augur_visibility" --include="*.py" --include="*.ts" --include="*.tsx" --include="*.md" --include="*.yaml" .
   ```
7. Remove field reads from code (.py, .ts). Leave .md and .yaml documentation references that describe the legacy behavior — those are historical, not current code paths.
8. Update test files: delete tests that asserted filter behavior; update tests that referenced the function but exercised other logic.
9. Run full test cascade.
10. Build dashboard.
11. Verification: spawn fresh sessions in each of the 3 AI clients and confirm tools/list returns expected counts (post-Track-3a baselines).

### Verification gate

- All Augur tests pass (no allowlist regression)
- Dashboard builds clean
- Manual: fresh Claude Code session shows tools that were previously hidden (e.g., from `augur-apple` per-bundle server)
- `tools/list` against `augur-core` and `augur-framework` returns identical tool sets regardless of which client connects

### ADR

After PR 1 ships, write `track4-visibility-filter-removal.md`:
- Status: Implemented
- Context: 1-paragraph linking to Layer 1 + Layer 4 specs
- Decision: deleted filter + the architectural conditions (Tracks 1-3a) that made it dead code
- Consequences: filter cannot recur; per-client tool surfaces are now naturally bounded by per-server registration

## Risk register

| Risk | Likelihood | Mitigation |
|---|---|---|
| `filter_tools_for_client` has non-visibility callers | Low | Audit grep before deletion; simplify rather than delete if other logic exists |
| Some test relies on the filter being active to scope what `tools/list` returns | Medium | Audit tests in PR 1 step 8; delete or update; run full cascade |
| Dashboard expects a tool to be "hidden" and breaks when it's exposed | Low | Tool surface is now per-server; dashboard wasn't previously filtering by `x-augur-visibility` directly (the filter was server-side) |
| `x-augur-visibility` field is read by something not caught in the audit grep | Low | The field has been irrelevant since Layer 1; any remaining reads were dead at that point |

## Done criteria

1. ✅ `CURATED_VISIBLE_TOOLS` and `COWORK_VISIBLE_TOOLS` are deleted from `client_surface.py`
2. ✅ `filter_tools_for_client` is either deleted or simplified to non-visibility logic
3. ✅ `x-augur-visibility` field is no longer read anywhere in `.py` / `.ts` / `.tsx` code
4. ✅ All tests pass; dashboard builds clean
5. ✅ Fresh sessions in Claude Code / Codex / Gemini show full per-server tool surfaces (verified manually)
6. ✅ ADR `track4-visibility-filter-removal.md` written

## Migration complete

After Track 4 ships, the cross-client bundle architecture migration is complete:

- ✅ Phase 0: layering cleanup (committed via Phase 0 PR)
- ✅ Track 1: 5 framework libraries extracted to `src/lib/`
- ✅ Track 2: 5 vault bundles split into per-bundle MCP servers
- ✅ Track 3a: project monolith split into `augur-core` + `augur-framework`; src/ hardcodes retired; allowlist empty
- ✅ Track 3b: dashboard hub-routing redesigned around `config/system/hubs.yaml`
- ✅ Track 4: visibility filter deleted

The architecture matches Layer 1's target state: standard MCP + standard SKILL.md, no proprietary fields, per-bundle server topology, no monolith, no hidden-by-default tools.
