---
status: Implemented
date: 2026-04-29
deciders:
  - gsannikov
related:
  - docs/superpowers/specs/2026-04-28-cross-client-bundle-architecture-design.md
  - docs/superpowers/specs/2026-04-28-cross-client-bundle-migration-design.md
  - docs/superpowers/specs/2026-04-29-track4-visibility-filter-removal-design.md
  - docs/superpowers/plans/2026-04-29-track4-visibility-filter-removal.md
  - ADR-567-bundle-architecture-phase0-cleanup.md
  - ADR-568-track3b-dashboard-hub-routing.md
  - ADR-569-track3a-framework-server-split.md
hub: null
tags:
  - architecture
  - bundle-migration
  - track-4
  - mcp
  - cleanup
superseded_by: null
---

# ADR-570: Track 4 — Visibility Filter Removal

## Status

Implemented. Final track of the cross-client bundle architecture
migration.

## Context

The `filter_tools_for_client` mechanism in
`src/mcp/augur_shared/client_surface.py` (formerly in `augur_mcp/`)
existed because the legacy `augur` monolith registered ~200 tools and
exposing all of them to every client overwhelmed AI tool selectors —
the filter restricted each client to roughly 9% of the surface via
the `CURATED_VISIBLE_TOOLS` and `COWORK_VISIBLE_TOOLS` frozensets,
driven by an `x-augur-visibility` SKILL.md frontmatter field. After
Tracks 1, 2, and 3a, no MCP server registers more than ~205 tools
per-server (augur-framework). Surface size is now naturally bounded
by per-bundle topology, the filter is dead code, and Layer 1 of the
migration target architecture explicitly rejects hidden-by-default
tools and proprietary SKILL.md fields.

## Decision

Track 4 ships a single PR (`3d6bf0ddd`) that deletes the visibility
filter end-to-end:

- **Deleted** `CURATED_VISIBLE_TOOLS` and `COWORK_VISIBLE_TOOLS`
  frozensets from `src/mcp/augur_shared/client_surface.py`.
- **Deleted** `filter_tools_for_client` (purely visibility, no
  non-visibility branches survived).
- **Deleted** `x-augur-visibility` field reads in `src/`:
  `src/plugins/skill_discovery.py` no longer reads the frontmatter
  field (`SkillRecord.visibility` retained as `""` for backward
  compat); `src/plugins/command_discovery.py` removes the `is None`
  gate; `src/mcp/augur_mcp/infrastructure/browse/index.py` drops the
  enrichment branch; `scripts/classify_skills.py` and
  `scripts/generate-skill-release-matrix.py` drop their reads.
- **Removed** the filter call site in
  `src/mcp/augur_mcp/server.py` `_patched_list_tools` and the
  startup curated-tool-missing warning loop.
- **Test cleanup** — deleted
  `src/mcp/augur_mcp/tests/test_client_surface.py` (purely
  visibility-filter assertions); removed the visibility-filter test
  from `tests/mcp/test_client_surface.py`; removed
  `test_get_features_not_exposed_in_curated_client_surface` from
  `tests/test_mcp_stale_cleanup.py`; widened
  `test_augur_framework_server.py` tool-count bound from 30-150 to
  100-300 to reflect the full unfiltered surface.
- **Kept** `PLUGIN_TOOL_SOURCES` (tool → owner mapping) — it is
  consumed by architecture allowlist tests and
  `test_client_surface_skill_owners.py` and is not visibility data.
- **Kept** resource and template filters — they are not
  tool-visibility logic.

The migration-spec verification gate ("verify across 3 clients:
fresh sessions show full per-server tool surfaces; the 91%-hidden
problem cannot recur because the mechanism is gone") is met.

## Consequences

- The cross-client bundle architecture migration is architecturally
  complete. Final state: standard MCP + standard SKILL.md, no
  proprietary `x-augur-visibility` field, per-bundle server
  topology, no monolith, no hidden-by-default tools.
- `tools/list` on a fresh session now returns the full per-server
  surface for every client (Claude Code, Codex, Gemini): full
  `apple-*` from `augur-apple`, full `ingest-*` from `augur-ingest`,
  full `augur-core` and `augur-framework` tool sets, etc.
- `SkillRecord.visibility` remains as a backward-compat empty
  string. Removing the field outright is not blocking and can land
  with an unrelated record-cleanup pass.
- Post-merge user steps: pull Augur, reload AI client sessions,
  verify `tools/list` shows full per-server surfaces.

## Verification

- `tests/cli/test_augur_framework_server.py` — passes with
  tool-count bound widened to 100-300 (full unfiltered surface).
- `tests/cli/test_augur_core_server.py` — passes with comment
  clarifying that the bound reflects an unfiltered surface.
- `tests/mcp/test_client_surface.py` — passes after
  visibility-filter test removal; resource/template,
  dynamic-markdown, and discovery-client coverage retained.
- `tests/test_mcp_stale_cleanup.py` — passes after removing the
  curated-surface stale-cleanup test.
- Dashboard build clean (Track 4 deletes dead code; no UI files
  modified beyond tool-name string-list cleanup).

## Commits

One PR landed on branch `track4-visibility-filter-removal`, merged
via `0f16a2652`:

1. **PR 1** — `3d6bf0ddd` `refactor(track4): delete visibility filter — migration complete`
