---
title: adr811-brain-redesign-shipped
name: adr811-brain-redesign-shipped
description: ADR-811 project-brain redesign shipped (2026-06-11) — ADRs live in project-brain/decisions/adrs
  as plain markdown (582 total, 554 archived extracted from zips), client-memory sweep
  mirrors client memories into brains daily, venture content moved to vault, scaffold
  pruned to 4 fed folders
brain_scope: project
type: project
status: active
source_client: claude-code
source_file: adr811-brain-redesign-shipped.md
source_hash: a85e9278188958c9
---


ADR-811 (supersedes ADR-608 location clause + ADR-642 zip model) shipped 2026-06-11, fixing the four "brain is empty" root causes:

1. **Decisions**: canonical ADR home is `project-brain/decisions/adrs/` — `get_adr_dir()` points there; live + archived ADRs are plain markdown (`archive/` holds ~554 extracted bodies; archive zips deleted; `adrs-index.json` uses `archive_member`, legacy `zip_member` read as fallback). Browse ADR view + extract route work client-side (fixed: runtime `adr-extracts/` added to open/reveal allowlist in `browse/_helpers.py`, commit e496c5970). After ADR/brain file moves, **Browse indexes go stale until reindexed** — run `reindex-browse-category` for affected categories or wait for nightly.
2. **Memory**: system-of-record + dumb sweep (no engine). `src/lib/client_memory_sweep.py` + wrapper `project-brain/capabilities/skills/knowledge/scripts/memory_client_sweep.py`, scheduled daily 05:15 as `memory-client-sweep` in daemon tasks.yaml. Routes `metadata.type: project` → project-brain `knowledge/memory/entries/`, other tiers → Au-vault `memory/entries/` (note: personal brain memory dir per `memory_dir_for_brain` is `Au-vault/memory`, NOT `knowledge/memory` which is the knowledge-skill RAG store — dual-store, both legitimate). Brain `MEMORY.md` files are generated indexes — never hand-edit. Sweep is idempotent (source_hash dedupe), never modifies client stores.
3. **Visibility**: project-brain = public-when-released; placement test "would you publish this on the docs site?". Venture/pitch content (5 venture notes + 6 concepts + 3 queries) moved to Au-vault `knowledge/notes/venture/` + `knowledge/wiki/{concepts,queries}/`.
4. **Fed-folder rule**: brain folders exist only with a named writer. Pruned to {capabilities, config, decisions, knowledge}. `_SKELETON_DIRS` in `src/lib/brain_manifest.py` is the scaffold template — it was updated too; if a folder must return, add it there AND name the writer in ADR-811.

**Closeout debts all fixed same day** (commits 57c131100, 75dea91a2, 7c8dc43ac, 1fc1f04dd): cron-nightly now calls `sync_agents sync all`; memory entries ride vault Browse cards with a `memory` tag (indexed at `state/rag/vault/shared/memory/entries/`); the legacy superpowers zip extracted to plain md (archive now 958 files, zero zips); the venture-layout memory entry rerouted to personal tier (edit `metadata.type` in the ~/.claude source file and re-sweep to reroute an entry). Remaining by design: memory entries in project-brain contain machine paths — fine while release excludes project-brain/**, needs a prune rule if the brain ever ships.

See [[category-action-refactor-spec]] for the parallel browse-category work that landed mid-migration (ADR-812/813 by the other session).
