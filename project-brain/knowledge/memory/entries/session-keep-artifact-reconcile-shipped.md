---
title: session-keep-artifact-reconcile-shipped
name: session-keep-artifact-reconcile-shipped
description: Session-aware no-arg /keep shipped (2026-06-11) — artifact-locate/keep/cleanup
  MCP tools on augur-framework; how the lanes work and what still needs user verification
brain_scope: project
type: project
status: active
source_client: claude-code
source_file: session-keep-artifact-reconcile-shipped.md
source_hash: 890b0e17d173724c
---


Session-aware `/keep` artifact reconcile shipped to main 2026-06-11 (commits `dd77ae29c..2b5add902`). Solves: slides/docs authored in Claude Desktop drift out of sync (Downloads exports never filed; Drive integration leaves version litter outside synced folders).

- Bare `/keep` in any client session = Session Reconcile flow (policy in `project-brain/capabilities/skills/augur-core/commands/keep.md`); `/keep <args>` unchanged.
- Three MCP tools in `src/mcp/augur_framework/tools/infrastructure/artifact_reconcile.py` (framework server = the only client-reachable home; ingest bundle is dashboard-only): `artifact-locate` (Downloads + Drive mirror sweep → version families, counter regex is `\(\d{1,3}\)$` so years like "(2024)" stay distinct), `artifact-keep` (files via ingest packet lifecycle stage→route→consume, lane 2 base64 needs `validate=True`-clean input, 25MB guard), `artifact-cleanup` (all-or-nothing validation, send2trash only, refuses non-existing dest folders, `allowed_roots` not exposed via MCP).
- Drive ops are filesystem ops on the mirror `~/Library/CloudStorage/GoogleDrive-<email>/My Drive` (full My Drive mounted); the connected Drive MCP has no move/trash tools.
- No `aug config sync` needed at ship time — topology unchanged; clients see the tools after session/server reload.
- Real-data verification found live version litter in Drive: `resume_gur_sannikov_gilat` (4 versions), `augur-deck-preseed-final (1).pdf` (2) — good first targets for the user's Claude Desktop checkpoint, which was still PENDING at ship time.
- Pre-existing debt found (NOT from this work, both fail at base `29e701c3a`): `tests/dashboard/python/test_mcp.py::test_audit_plugin_all` (plugin audit total==0 in fresh worktrees — environment-dependent), and 2 ingest `test_adr_index_adapter` failures.

Related: [[sdlc-autonomy-aug-dev-build]], [[adr771-knowledge-layout-complete]]
