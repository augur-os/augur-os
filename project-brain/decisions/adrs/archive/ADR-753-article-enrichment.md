---
status: Implemented
date: 2026-05-16
deciders:
  - gsannikov
related:
  - ADR-738
  - ADR-740
  - ADR-743
  - ADR-748
  - ADR-750
  - ADR-751
hub: brain
tags:
  - ingest
  - enrichment
  - wiki
  - compiled-truth
  - llm-assisted-mcp
  - vendor-neutral
  - daemon-job
superseded_by: null
spec_file: 2026-05-15-gbrain-ingest-port-design.md
plan_file: 2026-05-16-adr-753-article-enrichment.md
depends_on:
  - ADR-751
---

# ADR-753: Article enrichment for URL and file notes

## Status

Implemented.

## Context

After ADR-751 a captured URL produces a note with a title, the cleaned body, and tags — but no synthesis. The user re-reads the article to remember what mattered. This breaks the "30-second-comprehensible card" goal called out in the spec. Captured files (PDFs, docs) have the same problem at greater length.

The linked spec settled the enrichment shape during brainstorming:

- Enriched output is **inside** the note, not in a sibling file. The note's markdown body grows five named top-level sections at the top (Executive summary, Key insights, Why it matters, Verbatim quotes, Cross-references) and the original extracted content remains preserved at the bottom under `## Original content`. One file = one card, consistent with Rule 32.
- Enrichment runs **automatically** in the background on every newly-captured `type: url` and `type: file` note. The capture is fast; the enrichment is best-effort and never blocks the user.
- Users can also **manually trigger** enrichment from the BrowseDetailPanel ("Enrich…" button) — useful for re-enriching after entities are added or for backfilling old un-enriched notes.
- Enrichment is **dispatched through the LLM-Assisted MCP Pattern** (`docs/references/llm-assisted-mcp-pattern.md`). The active AI client (or a spawned CLI session in Mode 2 for daemon-triggered enrichment) owns the summarization step. No hardcoded vendor.
- **Cross-references** are resolved against the ADR-738 typed graph: the dispatch payload includes a list of existing wiki entity slugs as candidates; the AI client may add new ones.
- **Idempotency** is via frontmatter version field (`x-augur-enrichment-version`). Re-running enrichment at the same version is a no-op; bumping the version triggers a re-enrichment.
- **Auto-trigger mechanism** is a JSONL pending-enrichment queue (under runtime state). Source-card writers append to it on every new url/file note. A daemon job drains the queue on its cadence.

The compiled-truth section-replacement helpers from ADR-740 (`shared-vault/skills/ingest/scripts/wiki_timeline.py`) are the model for how named sections are extracted and replaced inside a markdown body. The wiki implementation lives inside the `ingest` skill (alongside the other `wiki_*.py` files), so enrichment lives there too.

## Decision

Implement article enrichment as a pure-logic module in `shared-vault/skills/ingest/scripts/article_enrichment.py` plus two MCP atomic ops:

1. `enrich-article(note_path)` — reads the note, verifies it is type url or type file and not already enriched at the current version, returns the LLM-Assisted MCP Pattern payload `{needs_llm: true, raw_content_preview, existing_entities, instructions, expected_result_schema, note_path}`. The active AI client (or a spawned CLI session) produces the five fields per the schema.
2. `submit-enrich-article-result(note_path, executive_summary, key_insights, why_it_matters, verbatim_quotes, cross_references_json)` — merges the fields into the note body as named sections (preserving the raw content at the bottom), stamps `x-augur-enrichment-status: enriched` and `x-augur-enrichment-version: 1` into frontmatter, writes back.

The pure-logic module owns the section template, body split/merge, idempotency check, and dispatch payload builder. The MCP layer composes these with I/O. The daemon job at `shared-vault/skills/ingest/augur/scripts/run_pending_enrichment.py` drains a JSONL queue at `<runtime>/pending_enrichment.jsonl` (resolved by a new `get_pending_enrichment_queue_path()` helper) and dispatches enrichment per pending note via the LLM-Assisted MCP Pattern's Mode-2 CLI session helper.

Source-card writers (`source_cards.py` and `inbox_tools.py`) get a single post-write line each: enqueue the new note path with `reason: "new"`. Wrapped in try/except so a queue write failure never blocks the note capture (Rule 1: user-visible correctness first).

`apps/dashboard/components/shared/BrowseCard.tsx` renders an `enrichment_status` badge on url and file cards (`raw` / `enriching…` / `enriched`). `BrowseDetailPanel.tsx` gains an "Enrich…" action button on url/file detail panels that calls `enrich-article` against the current note path.

`config/system/capability_exposure.yaml` gets `mcp-tool:enrich-article` and `mcp-tool:submit-enrich-article-result` entries.

`shared-vault/skills/ingest/SKILL.md` declares the new daemon job `run-pending-enrichment` with a 5-minute cadence (the daemon-job registration key is whatever the daemon skill currently recognizes; the plan inspects the daemon skill and uses the canonical key).

## Non-Goals

- Re-summarizing on every entity-graph update. Initial enrichment per note version is the spec; a future ADR can layer "stale enrichment detection" if the graph changes substantially.
- Enrichment of voice-memo / meeting / thought / image / prompt notes. Those types have their own structure from ADR-748 and ADR-752 and direct user input; they do not need an AI summary.
- Per-section regeneration ("regenerate only the key insights"). The current op is whole-note enrichment; partial regen is a follow-up.
- Compiled-truth/timeline merge (ADR-740). Enrichment writes named sections, but those sections are not compiled-truth sections. ADR-740's pattern continues to govern wiki pages, not notes.
- Vendor-specific enrichment quality tuning. The dispatch payload is provider-neutral; the active AI client decides quality.
- Inline editing of enriched sections from the dashboard. The user edits the note file directly to revise.
- Automatic deletion of low-quality enrichment. If the AI client produces a weak summary, the user re-triggers enrichment or edits manually. No silent overwriting of human-edited sections (the writer always overwrites the five named sections — users who hand-edit those sections will lose their edits on re-enrichment; this is documented in the section comments).

## Consequences

- Source-card writers gain one line each post-write — minor edit, fully covered by existing test files.
- New runtime state file `<runtime>/pending_enrichment.jsonl`. Append-only; the daemon job rewrites it on drain.
- New daemon job at 5-minute cadence. On a fresh machine without a running daemon, the user can run the script manually: `uv run python shared-vault/skills/ingest/augur/scripts/run_pending_enrichment.py`. The plan's verification step exercises this.
- Browse UI gets a small `enrichment_status` badge and an "Enrich…" button — both additive, no layout changes.
- Enrichment is **best-effort.** Queue failures, CLI dispatch failures, or AI client unavailable all leave the note un-enriched with `enrichment_status: pending` (or absent) and the note still captures correctly. Re-running the daemon job retries automatically.
- A user offline / with no AI client configured / on a fresh machine without `dispatch_agent_session` available will see notes captured but not auto-enriched. Manual "Enrich…" still works when an AI client is the caller.
- Idempotency: re-running enrichment at version 1 is a no-op. Future ADRs can bump the version (e.g. when adding a new section) and the next pass re-enriches automatically.
- The plan's verification task captures three real URLs (long-form essay, technical tutorial, news/opinion) and inspects each enriched file end-to-end. This is the Rule 34 anchor.

## Critical context for fresh-session execution

The same conventions named in ADR-751 and ADR-752 apply — repeated here for standalone-session execution:

1. **Test convention:** skill tests under `shared-vault/skills/<skill>/augur/tests/` load modules via `importlib.util.spec_from_file_location(...)`, never dotted imports.
2. **Capability exposure:** every new MCP tool requires an entry in `config/system/capability_exposure.yaml` under `mcp-tool:<name>:`.
3. **Vendor neutrality:** no direct LLM-vendor API calls. Enrichment dispatches via the LLM-Assisted MCP Pattern at `docs/references/llm-assisted-mcp-pattern.md`.
4. **`sync_agents` artifact scope:** after editing MCP tool files, regenerate client surfaces with `augur sync mcp all`. After editing skill SKILL.md frontmatter that affects commands or daemon jobs, the relevant `sync` flavor is the right one — read the file you changed; if it's a `commands/*.md`, use `sync commands`. `sync agents all` is a different artifact class and does NOT regenerate command/MCP/daemon-job surfaces.
5. **Dashboard ops:** use `/dev-build` and `/dev-debug`. Do not `pnpm dev` directly.
6. **Verification standard:** Rule 34 requires real captured URLs (the plan's verification task names three URLs from your real reading list). The user-facing output to inspect is the markdown file body — open it, read the executive summary, confirm it summarizes; read the verbatim quotes, confirm they are actually from the source.
7. **Browser verification (Rule 28):** dashboard changes require real-browser load. The plan's verification opens BrowseDetailPanel on a url note and clicks "Enrich…", watching the status badge cycle.
8. **Rule 1 (user-visible correctness first):** enrichment is best-effort, and a queue/CLI failure must never break the note capture itself. The plan wraps enqueue calls in try/except to enforce this.
9. **Daemon may not be running on a fresh machine.** The plan includes a manual-run verification step so enrichment is exercised even without the daemon service active.

## Execution Kickoff

This ADR is self-contained for fresh-session execution. To implement on any machine:

```
# 1. Prerequisites: ADR-751 must be Implemented.
grep "^status:" docs/adrs/ADR-751-two-verb-command-surface-and-notes-zone.md
# Must show: status: Implemented
# ADR-752 is NOT a prerequisite for ADR-753 (audio and enrichment are independent).

# 2. Bootstrap dependencies on the new machine.
corepack enable && pnpm install && uv sync

# 3. Trigger the plan via the writing-plans → executing-plans skill chain.
#    In a Claude Code / Codex / Gemini session, invoke either:
#      a) superpowers:subagent-driven-development on docs/superpowers/plans/2026-05-16-adr-753-article-enrichment.md
#      b) superpowers:executing-plans on the same plan file

# 4. The plan owns the rest: 9 tasks, TDD-shaped, exact file paths, exact commands.

# 5. Task 9 (real-data verification per Rule 34) captures three real URLs:
#    - a long-form essay
#    - a technical tutorial
#    - a news/opinion piece
#    Runs /note against each, waits up to the daemon's cadence (or manually drains the queue), then inspects each enriched note file.

# 6. After Task 9 succeeds, flip frontmatter status to Implemented via /adr.
```

**Prerequisites:** ADR-751 Implemented. ADR-752 is **not** a prerequisite — this ADR is independent.

**Plan file:** `docs/superpowers/plans/2026-05-16-adr-753-article-enrichment.md` (9 tasks).

**Spec file:** `docs/superpowers/specs/2026-05-15-gbrain-ingest-port-design.md`.

**External dependencies:** none beyond what ADR-751 already establishes. Whisper.cpp is not needed for enrichment (that is ADR-752's concern).

**Daemon setup note:** the plan declares a new daemon job. On a fresh machine where the daemon is not running, the verification step shows how to run the job manually. Starting the daemon for ongoing auto-enrichment is a separate user concern documented in `docs/agent-topics/WORKFLOWS.md`.

**Status transition on completion:** flip frontmatter `status: Proposed` → `status: Implemented` via `/adr`, regenerate `docs/generated/adr-index.md`.

## Related

- ADR-738 — typed knowledge graph (cross-reference candidates come from this graph)
- ADR-740 — compiled-truth + timeline pattern (model for named-section splitter/merger; enrichment uses the same section-aware pattern but writes to notes, not wiki pages)
- ADR-743 — file-based job ledger (the daemon job records phase events here; the pending queue is JSONL alongside)
- ADR-748 — triggerable prompt cards (enrichment skips prompt notes — they are user-authored, not source-captured)
- ADR-750 — content-aware ingest and browser-first fetch (enrichment runs on the raw content captured by this path)
- ADR-751 — two-verb daily command surface and unified notes zone (load-bearing prereq)
- ADR-752 — audio-ingest skill (sibling in the same slate; independent of this ADR — can ship in either order after ADR-751)
- LLM-Assisted MCP Pattern reference: `docs/references/llm-assisted-mcp-pattern.md`
