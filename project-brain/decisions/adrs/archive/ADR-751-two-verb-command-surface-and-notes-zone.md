---
status: Implemented
date: 2026-05-15
deciders:
  - gsannikov
related:
  - ADR-595
  - ADR-738
  - ADR-740
  - ADR-742
  - ADR-743
  - ADR-748
  - ADR-750
hub: brain
tags:
  - command-surface
  - ingest
  - browse
  - vault-layout
  - daily-ergonomics
  - deprecation
superseded_by: null
spec_file: 2026-05-15-gbrain-ingest-port-design.md
plan_file: 2026-05-15-adr-751-note-command-surface.md
---

# ADR-751: Two-verb daily command surface and unified notes zone

## Status

Implemented.

## Context

Today the input surface for the brain is split across three commands — `/ingest` (URL/file/folder/email-drop), `/save` (in-session artifact export), and the existing `save-prompt` and `save-url-source` atomic ops — none of which is a natural daily verb. "Ingest" is technical jargon. The capture-thought case (gbrain's `signal-detector`) has no Augur-side path at all today. A user with a thought, a URL, an audio file, or a folder all takes different paths to land content in the brain, and the on-disk layout splits captures across `<vault>/inbox/`, `<vault>/sources/`, and `<vault>/prompts/` — each surfaced as a separate Browse tab.

The brainstorming in the linked spec settled this with the user: the daily input surface collapses to a single verb, `/note`, with `/ask` as the daily output verb. `/save` retains its current narrow role for in-session artifact export (weekly, not daily). `/ingest` retires with a one-version grace-period alias. The vault collapses to a single `<vault>/notes/` zone with frontmatter (`x-augur-note-type`) discriminating url / file / thought / voice-memo / meeting / image / prompt. The Browse page collapses three tabs (`inbox`, `sources`, `prompts`) into one canonical `notes` tab with preset filter URLs (`/browse?view=notes&type=prompt` becomes the prompt-library URL).

Audio modality (voice-memo + meeting) and post-ingest article enrichment are deliberately scoped to separate follow-on ADRs (ADR-752 and ADR-753) so that this ADR remains a single, atomically-mergeable change: surface + storage + Browse fold.

## Decision

Adopt `/note` as the single daily input verb. It dispatches on argument shape (URL → URL ingest path, audio file → audio path, folder → inbox-scan, free text → thought, etc.) and on explicit override flags (`--as prompt`, `--memo`, `--meeting`, `--thought`, `--from email`, `--trigger <slug>`). `/ingest` becomes a thin deprecation alias that prints a one-time-per-session notice and delegates to `/note` with identical arguments. Hard removal of `/ingest` in the next minor-version cycle after this ADR ships.

Atomic ops (`save-url-source`, `save-prompt`, `inbox-consume-folder`, and the related writers) rewire their target path to `<vault>/notes/` and write an `x-augur-note-type` discriminator into frontmatter. Existing helper `get_vault_notes_dir()` in `src/config/paths.py:489` already resolves the canonical path. An idempotent one-shot migration script moves existing cards from `<vault>/inbox/`, `<vault>/sources/`, and `<vault>/prompts/` into `<vault>/notes/`, classifying each by its current frontmatter shape; the empty source directories remain on disk for one grace-period cycle.

The dashboard's Browse page retires three `ViewMode` entries (`inbox`, `sources`, `prompts`) in favour of a single canonical `notes` ViewMode with filter-chip UI. Retired URLs redirect (`/browse?view=inbox` → `/browse?view=notes`; `/browse?view=sources` → `/browse?view=notes&type=url,file`; `/browse?view=prompts` → `/browse?view=notes&type=prompt`). `BrowseCard` and `BrowseDetailPanel` gain type-conditional rendering keyed off `x-augur-note-type` (badge + metadata strip on the card; per-type sections on the detail panel). Capture-entry components rename in lockstep: `IngestFAB`/`IngestModal`/`IngestDropZone`/`IngestQueueItem` → `NoteFAB`/`NoteModal`/`NoteDropZone`/`NoteQueueItem`.

`config/system/capability_exposure.yaml` gets a new `command:note:` entry exposed to every supported AI client; `command:ingest:` keeps an entry but is marked `classification_status: deprecated`.

## Non-Goals

- Audio modality (voice-memo + meeting). Owned by ADR-752 and its plan.
- Article enrichment for url/file notes. Owned by ADR-753 and its plan.
- Ambient signal-detector / per-message conversation capture. Explicit `/note <thought>` is the only thought-capture path in this slate; ambient client-hook capture is deferred.
- Bulk archive crawl from external folders (gbrain `archive-crawler`). Deferred indefinitely.
- External webhook intake (gbrain `webhook-transforms`). Deferred indefinitely.
- Configurable entity-type templates (gbrain person/company wiki pages). Deferred; ADR-738 typed graph captures entity relationships at the graph layer for now.
- `/prompt` alias. Pure two-verb discipline — `/note --as prompt` is the explicit override.
- Renaming the `ingest` skill itself. The skill name stays `ingest` internally; only the user-facing command renames.

## Consequences

- One-shot vault migration runs against the real user vault (the plan includes both a dry-run and an apply step). Old folders remain empty placeholders for one minor-version cycle.
- Six atomic-op files in `shared-vault/skills/ingest/scripts/` are rewired; their existing tests adapt to assert the new path + frontmatter shape.
- Three retired `ViewMode` entries trigger redirects; bookmarks pointing at the old views land on the canonical filtered URLs.
- Four dashboard components rename, with all their importers updating in lockstep. TypeScript build will fail until every importer is touched, which serves as a built-in checklist.
- `BrowseItem` interface is unchanged. The existing `typeBadge` string field and `metadata` record absorb every new field.
- `/ingest` continues to work, prints a deprecation notice, and dispatches to `/note`. After this ADR's grace period, removing `/ingest` becomes a one-line edit (delete the alias).
- New slash command `/note` requires `command:note:` in `config/system/capability_exposure.yaml` and a `sync commands all` to project to every client surface.
- The notes zone becomes the single source of truth for "what the brain has captured." Searches, browse, retrieval, and enrichment (ADR-753) all operate on this one directory.

## Critical context for fresh-session execution

The plan assumes the following Augur conventions, which are mandatory and not optional. A fresh-session agent must respect them:

1. **Test convention.** Skill tests live under `shared-vault/skills/<skill>/augur/tests/` and load modules via `importlib.util.spec_from_file_location(...)`, not via dotted module path. This is enforced by Augur's import-bootstrap. Tests that use dotted imports will silently load the wrong module or fail to find one entirely.

2. **Command capability registration.** Every new slash command requires an entry in `config/system/capability_exposure.yaml` under the `command:<name>:` key. Without this entry, the command does not project to any client surface (`/note` will not appear in `.claude/commands/`, `.codex/commands/`, etc.). The plan covers this; verify the entry exists after the relevant task.

3. **Vendor-neutrality.** No file in this slate calls a specific LLM vendor's API directly. All LLM-class work routes through the active AI client's session (the agent reasoning, not a hidden provider call). This ADR's scope has no LLM work; the constraint applies cumulatively across the slate.

4. **`sync_agents` artifact scope.** After editing command source files in `shared-vault/skills/<skill>/commands/*.md`, regenerate client surfaces with `augur sync commands all` — **not** `augur sync agents all`. The latter is a different artifact class and does not regenerate command projection.

5. **Dashboard ops.** Do not manually kill the dev server, `rm -rf apps/dashboard/.next`, or run `pnpm dev` directly. Use `/dev-build` for builds and `/dev-debug` for diagnosis. The slash commands carry safety guarantees (port detection, codex thread state, post-build verification) that direct invocations skip.

6. **Verification standard.** A passing test suite, a green build, or an HTTP 200 from `curl` are **not** value validation. Per CLAUDE.md Rule 34, this ADR's plan ends with a real-data verification task that captures notes via `/note` against the real vault and inspects the resulting files. Do not skip this step or weaken it to a tmp-path fixture run.

7. **Browser verification.** Dashboard-touching changes require client-side load verification per CLAUDE.md Rule 28 — HTTP 200 + SSR markup does not prove a page works in Next.js because dev-server build manifests routinely drift from on-disk chunks. The plan's verification task includes a real-browser load step.

## Execution Kickoff

This ADR is self-contained for fresh-session execution. To implement on any machine:

```
# 1. Clone Augur and bootstrap once on the new machine.
corepack enable && pnpm install && uv sync

# 2. Verify prerequisites (none for this ADR — it is the load-bearing one).
#    ADR-752 and ADR-753 require ADR-751 implemented and merged first.

# 3. Trigger the plan with the writing-plans → executing-plans skill chain.
#    In a Claude Code / Codex / Gemini session, invoke either:
#      a) superpowers:subagent-driven-development on docs/superpowers/plans/2026-05-15-adr-751-note-command-surface.md
#      b) superpowers:executing-plans on the same plan file
#    Both modes are documented in the plan's "Execution handoff" section.

# 4. The plan owns the rest: 16 tasks, each with TDD-shaped steps, exact file paths, exact commands, exact commit messages.

# 5. After Task 15 (browser verification) and Task 16 (Rule 34 real-data verification), this ADR can be marked Implemented via /adr.
```

**Prerequisites:** none. This ADR is load-bearing and must merge before ADR-752 or ADR-753 can execute.

**Plan file:** `docs/superpowers/plans/2026-05-15-adr-751-note-command-surface.md`.

**Spec file:** `docs/superpowers/specs/2026-05-15-gbrain-ingest-port-design.md`.

**Status transition on completion:** flip frontmatter `status: Proposed` → `status: Implemented` via `/adr`, regenerate the ADR index (`python scripts/regenerate_adr_index.py` or the equivalent), and ensure `docs/generated/adr-index.md` lists this ADR as Implemented.

## Related

- ADR-595 — mail drop intake (the `--from email` flag in `/note` continues the existing email-drop path)
- ADR-738 — typed knowledge graph (note frontmatter feeds entity extraction; this ADR does not change graph contracts)
- ADR-740 — compiled-truth + timeline pattern (wiki pages remain at `<vault>/wiki/`, unchanged)
- ADR-742 — retrieval eval harness (notes-zone unification simplifies the eval corpus path)
- ADR-743 — file-based job ledger (migration script logs its run via the ledger)
- ADR-748 — triggerable prompt cards (prompts now live in `<vault>/notes/` with `x-augur-note-type: prompt`; trigger semantics unchanged)
- ADR-750 — content-aware ingest and browser-first fetch (URL ingest path inside `/note` is unchanged from `/ingest` — same fetch, same prompt-detection, same atomic op contract; only the destination path changes)
- ADR-752 — audio-ingest skill (depends on ADR-751)
- ADR-753 — article enrichment (depends on ADR-751)
