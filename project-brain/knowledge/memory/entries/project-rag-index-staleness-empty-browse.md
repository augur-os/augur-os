---
title: project-rag-index-staleness-empty-browse
name: project-rag-index-staleness-empty-browse
description: Filesystem-backed Browse categories (commands/actions/scripts/pages/mcp-tools/skills/workflows)
  go silently empty/decimated when the machine-local RAG index has stale source_paths;
  reindex with unified_indexer.py
brain_scope: project
type: project
status: active
source_client: claude-code
source_file: project_rag_index_staleness_empty_browse.md
source_hash: 8d3cbf0254e0267f
---


`browse-index` serves each category from a **machine-local** RAG index at
`~/Library/Application Support/Augur/rag/<category>/*.md` (NOT in the repo;
resolved via `get_rag_category_dir`). For the `_FILESYSTEM_BACKED_CATEGORIES`
(actions, commands, mcp-tools, pages, scripts, skills, workflows),
`_filter_missing_source_path_entries` (in `src/mcp/.../browse/index.py`) **drops
every entry whose `source_path` no longer exists on disk** — silently, with no
status or signal. So when skill files move (e.g. the ADR-601/770
`shared-vault/skills` → `project-brain/capabilities/skills` migration) and the
index isn't rebuilt, those tabs read empty or decimated even though the index
files still exist. Symptom seen 2026-05-22: commands 0 (122 on disk, all stale
`shared-vault/` paths), scripts 64/675, actions 4/63, pages 3/11; mcp-tools was
also under-indexed 30→217.

**Diagnose:** compare disk vs browse count, then check an index entry's
`source_path` exists:
`ls "$(rg ... )"`. `count:0` with no `status` = stale-filtered (dir exists);
`status:"not_indexed"` = no dir.

**Fix (live):** `python3 src/lib/index/unified_indexer.py --category <cat>`
(or no `--category` for a full rebuild). The scanner is correct; the index was
just stale. The index is machine-local — the **other mirrored machine needs its
own reindex**.

**Why it went stale / durable fix:** there is no daemon reindex, and
`scripts/hooks/post-commit-index` was **orphaned** (the active
`core.hooksPath=.githooks` post-commit/post-merge only ran git-lfs) AND omitted
commands/actions/mcp-tools. Now wired: `.githooks/post-commit` and
`.githooks/post-merge` (pull/sync vector, via `AUGUR_REINDEX_BASE=ORIG_HEAD`)
both invoke `post-commit-index`, which now also triggers on
`/commands/*.md`, `/actions/*.md`, `/scripts/mcp/`, and `SKILL.md` changes.

**Not bugs:** `workflows` is genuinely empty (0 `references/workflow*.md` files
anywhere); `system-metadata` is an unimplemented placeholder category (no
scanner — its action text literally asks which scanner should own it);
`extensions-bundles` is fed by `list-skills` (97), NOT browse-index — probing
browse-index for it is misleading. Related: [[project-test-suite-topology]].
