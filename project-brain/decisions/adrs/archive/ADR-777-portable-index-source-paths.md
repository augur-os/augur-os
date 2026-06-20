---
status: Implemented
date: 2026-05-23
deciders:
  - gsannikov
related: [ADR-270, ADR-737, ADR-759, ADR-776]
hub: null
tags: [browse, dashboard, rag, worktree, index, paths, cross-platform]
superseded_by: null
spec_file: null
plan_file: null
---

# ADR-777: Portable (project-relative) index source paths + cross-platform file actions

## Decision summary

The RAG/browse index `source_path` for **in-repo** artifacts is stored
**project-root-relative and POSIX-normalized**, and resolved to an absolute path
against the **active** project root at read time. The index is machine-shared
across checkouts/worktrees (ADR-270 places it under `~/Library/...`, outside any
checkout; ADR-759 shares it deliberately), so an entry must resolve correctly
from whichever checkout reads it. File-action MCP helpers (`reveal-in-finder`,
`open-file`) also gain a Windows branch so the buttons work on macOS, Windows,
and Linux.

## Context

A worktree dashboard (`localhost:3003`, repo `…/augur-wt-20260523-010252`)
showed broken Browse file actions and "No content available" for project-brain /
wiki items. Root cause: the **shared** RAG index — last written by the **main**
checkout — stored absolute `source_path` values like
`/Users/…/Projects/Augur/project-brain/knowledge/wiki/README.md`. The worktree's
MCP only permits paths under its own roots (`[get_project_root(), vault,
documents, logs]`), so `file-info`/`file-read`/`reveal-in-finder` all rejected
the foreign main-checkout path — even though an identical file exists at the
worktree path. On the main dashboard (`:3000`) the same path was allowed, so the
bug was invisible there.

The skills scanner already did the right thing (`source_path_for(skill_md, root)`
→ relative POSIX); wiki, vault (shared scope), prompts (IDE branch), and
mcp-server manifests did not — they baked in `str(absolute_path)`.

Separately, `reveal-in-finder`/`open-file` only branched on macOS (`open`) vs
"else" (`xdg-open`), so on Windows they fell through to `xdg-open` (which does
not exist there) and failed regardless of path.

## Decision

1. **Writers store portable paths.** In-repo scanners write
   `source_path_for(file, project_root)` (relative POSIX when under the root,
   absolute POSIX otherwise). Applied to wiki, vault (shared), prompts (IDE),
   and mcp-server manifests. External paths (private vault, logs, documents)
   remain absolute — they are already checkout-agnostic on a given machine.
2. **Read-time resolution for all categories.** `_source_path_for_output`
   resolves a project-relative `source_path` to an absolute path under the active
   `get_project_root()` for every filesystem-backed category (previously only
   `pages`). This single chokepoint — where an index entry becomes the
   dashboard's path/action target — repairs Open File, Reveal, Copy Path,
   content read, and brain-id resolution at once, symmetrically on every
   checkout. Absolute/external paths and non-file values (route hrefs, URLs)
   pass through unchanged.
3. **Cross-platform file actions.** `reveal-in-finder` uses `explorer /select,`
   on Windows (with `check=False`, since Explorer exits non-zero on success) and
   `open -R` on macOS; `open-file` uses `os.startfile` on Windows and `open` on
   macOS; Linux keeps `xdg-open`.
4. **Honest failures.** When a file action is genuinely blocked, the dashboard
   surfaces the real reason (the MCP `{status:"error", message}` envelope)
   instead of a misleading "File not found" toast / "No content available."

## Consequences

- The shared index is checkout-agnostic: one relative entry resolves to the
  worktree path on `:3003` and the main path on `:3000`. A one-time reindex
  migrates existing absolute entries; because resolution is symmetric, the same
  reindex fixes both dashboards.
- POSIX-normalized relative paths are portable across the user's macOS and
  Windows machines (each rebuilds its own machine-local index), avoiding
  separator-locked entries (CLAUDE.md rule 30).
- New convention for future scanners: in-repo `source_path` must go through
  `source_path_for`, never `str(absolute_path)`.
- `os.startfile` is Windows-only; it is called only inside the Windows branch and
  carries a `# type: ignore[attr-defined]`.

## Implementation

- `src/lib/index/_scanners_knowledge.py` — `index_wiki` gains `root`; wiki + prompts(IDE) use `source_path_for`.
- `src/lib/index/_scanners_structural.py` — `index_vault` gains `root`; vault(shared) + mcp-server manifests use `source_path_for`.
- `src/lib/index/unified_indexer.py` — `reindex_category` threads `root` into `index_wiki`/`index_vault`.
- `src/mcp/augur_framework/tools/infrastructure/browse/index.py` — `_source_path_for_output` resolves all categories.
- `src/mcp/augur_framework/tools/infrastructure/browse/file_actions.py` — Windows branch for reveal/open.
- `apps/dashboard/lib/browse/executeAction.ts`, `apps/dashboard/components/shared/BrowseDetailPanel.tsx` — honest error surfacing.
- `tests/test_worktree_index_path_isolation.py` — relative/external writers, read-time resolution, traversal rejection, Windows/macOS action branches.

## Verification

- Reindexed wiki/vault/prompts/mcp-servers; on-disk entry became `source_path: project-brain/knowledge/wiki/README.md`.
- `file-info`/`file-read`/`reveal-in-finder` succeed on the relative path via the `:3003` MCP (resolve to the worktree); `:3000` resolves the same entry to the main checkout (no regression).
- Browser (`:3003`): "Project Brain Wiki" card now renders content and Reveal in Finder succeeds with no error toast / console error.
- `tests/test_worktree_index_path_isolation.py` (9) green; existing indexer (79) and browse/file-action (66) suites green.
