---
status: Implemented
date: 2026-06-01
deciders:
  - gsannikov
related:
  - ADR-601
  - ADR-783
hub: dev
tags:
  - mcp
  - skills
  - vault
  - separation
  - capability-exposure
superseded_by: null
spec_file: null
plan_file: null
---

# ADR-795: Private vault skills are process-separated from the project-tier MCP server

## Decision summary

The project-tier `augur-framework` MCP monolith registers **project-brain
skills only**. Private/user vault skills (under the configured vault's
`capabilities/skills/`) are never loaded by the monolith — for any consumer
(AI clients, the dashboard MCP bridge, or the in-process `aug` CLI runtime).
Private vault skills are reachable only on demand through dedicated vault-tier
`bundle_server` instances. The boundary is enforced structurally by skill
**source root**, not by a per-bundle blocklist.

## Context

The `augur-framework` monolith scanned every managed skill root —
`project-brain/capabilities/skills/` **and** the private vault
`capabilities/skills/` — and registered all non-excluded bundles. Only the
`vault` and `ingest` bundles were split out via `monolith_exclusions`.

Two problems surfaced:

1. **No real separation.** Private vault skills (e.g. `books-augur`,
   `file-manager-augur`) were imported and registered into the project-tier
   server even though the capability-exposure policy filtered their tools to
   zero on strict AI-client targets. The project server was loading private
   code it would never expose.

2. **Startup cost.** Loading those bundles ran their `register_tools()` and
   decorated every tool through the capability-policy filter. Combined with an
   unrelated uncached-YAML defect (fixed separately), this inflated server
   startup and contributed to the MCP client's 30s startup timeout.

The capability-exposure policy already separated private skills at the
**exposure** layer for AI clients, but not at the **loading/process** layer.
The owner requires full separation: private skills must not co-mingle with
project skills in the project-tier server at all.

## Decision

- Add `project_tier_skill_source_dirs()` (`src/config/paths.py`): managed skill
  roots minus the configured-vault and legacy-vault roots.
- Add a `scope` argument to `_collect_skill_dirs()`
  (`src/mcp/augur_shared/plugin_tools.py`). Default `"all"` preserves existing
  behavior; `"project"` restricts to project-tier roots.
- The monolith registrar `register_plugin_tools()` passes `scope="project"`
  for every target (AI client, dashboard, CLI).
- `bundle_server`, skill-registry discovery, hub capability discovery, and
  Browse-dev keep `scope="all"` so vault bundles remain resolvable by name and
  vault content stays discoverable/searchable.

Filtering by source root (not bundle name) keeps the boundary future-proof:
any new private skill dropped into the vault is excluded automatically.

## Consequences

- **AI clients (Claude Code / Codex / Gemini):** no change to the visible tool
  list (vault tools were already policy-filtered to zero) — but the server no
  longer loads private skill code, and starts faster.
- **Dashboard MCP bridge:** no longer surfaces vault-skill tools
  (`list-books`, `list-book-notes`, `manage-books`, `get-file-manager-status`).
- **`aug` CLI in-process runtime:** no longer reaches vault-skill tools through
  the monolith.
- **Vault skills are not orphaned:** they remain resolvable on demand via
  `python -m augur_shared.bundle_server <bundle-name>`, and remain visible to
  discovery/registry/Browse/search (`scope="all"`).

### Explicitly rejected: auto-wiring per-bundle vault-tier servers

Adding `vault_tier` entries for `books-augur` / `file-manager-augur` was
considered and rejected. `vault_tier` servers are auto-registered into AI
clients (the Augur Claude Code plugin's `.mcp.json` registers them), so doing
so would re-introduce `books` into Claude Code as its own top-level server —
re-co-mingling private and project surfaces. Wiring a dedicated personal MCP
server for vault skills, if ever desired, is an explicit opt-in and out of
scope here.

## Verification

- `augur-framework` boot logs show no "Registering books/file-manager" lines;
  `_collect_skill_dirs(scope="project")` returns 0 vault skills (24 total) vs
  `scope="all"` 8 vault skills (32 total).
- `client-mcp` exposed tool count unchanged (32).
- `bundle_server` still resolves `books-augur`, `file-manager-augur`, `vault`,
  `ingest`.
- Capability-policy and plugin-tool test suites pass.
