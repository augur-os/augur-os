---
title: gbrain ingest port — daily two-verb command surface, audio modality, article enrichment
date: 2026-05-15
status: Draft
authors: [gsannikov]
related_adrs: [ADR-738, ADR-740, ADR-742, ADR-743, ADR-748, ADR-750]
adr_slate: [ADR-751, ADR-752, ADR-753]
supersedes_memory: project-gbrain-borrow-slate (extends; does not retire)
---

# gbrain ingest port — design spec

## Summary

Port the ingest-adjacent capabilities from gbrain (github.com/garrytan/gbrain) that Augur is genuinely missing, while rebuilding the daily user-facing command surface around two verbs: `/note` for anything entering the brain and `/ask` for anything coming out. The slate adds one new modality (audio — voice memos and meetings) and one enrichment layer (article enrichment for captured URLs and files). The current `/ingest` command is retired and aliased to `/note` for a grace period. The vault collapses `brain/inbox/` into a unified `brain/notes/` zone typed by frontmatter; the Browse page collapses three content tabs (`inbox`, `sources`, `prompts`) into a single canonical `notes` tab with preset filter URLs.

## Goals

1. **Daily ergonomics first.** The captured-thought, captured-URL, captured-file, captured-audio flows all share one verb and one mental model. The user types `/note` many times per day and does not have to remember which sub-command to use.
2. **Fill the genuine modality gap.** Voice memos and meeting recordings have no path into Augur today. Both need transcription + classification + entity-aware enrichment.
3. **Make captured cards substantially richer.** Article enrichment turns a raw URL grab into a structured summary + verbatim quotes + key insights + why-it-matters block, so cards are 30-second-comprehensible.
4. **Stay vendor-neutral and local-first.** No transcription provider or AI vendor is hardcoded; the substrate is pluggable via SKILL.md frontmatter, with a local default (whisper.cpp) that needs zero cloud calls.
5. **Stay file-first.** Every output of every new capability is a markdown file with frontmatter that a user can `cat`, `grep`, or open in any editor. No databases. No opaque artifact stores.

## Non-goals

- Porting the gbrain `signal-detector` ambient-conversation hook. Explicit `/note <thought>` covers the explicit-thought case; ambient client-hook capture is deferred until there is a concrete demand.
- Bulk archive crawl (gbrain `archive-crawler`). Deferred — the `inbox-scan-folder` surface covers active inboxes; bulk archive backfill is a separate slate when needed.
- External webhook intake (gbrain `webhook-transforms`). Deferred — push-style intake is a separate concern with its own security model and tunneling requirements; revisit when there is concrete integration pull.
- Porting gbrain's `book-mirror` skill. Adjacent to Augur's existing `books` capability; not in this slate.
- Porting gbrain's `brain-pdf` skill. It is an export pipeline, not ingest; out of scope.
- Porting gbrain's `media-ingest` skill. Substantially overlapped by Augur's `document-extractor` after audio support lands.
- Building configurable entity templates (person/company/etc. wiki pages). Out of scope for this slate; revisit when there is concrete user pull. ADR-738 typed graph already captures entity relationships; explicit wiki pages per entity type can be added later without re-architecture.
- Per-AI-client behavioral differences. The active AI client owns synthesis dispatch per Rule 19; this spec is vendor-neutral.

## Locked decisions

The following were settled during brainstorming and are inputs to the design, not open questions:

1. **Two-verb command surface.** `/note` for input, `/ask` for output. `/save` retained for in-session artifact export (rare, weekly). `/ingest` retired with grace-period alias.
2. **Pure two-verb minimalism.** No `/prompt` alias; prompts are captured via `/note --as prompt` or content-aware autodetect.
3. **Hybrid skill topology.** One new skill (`audio-ingest`); extensions to existing skills (`ingest`, `wiki`, `document-extractor`); no per-gbrain-skill 1:1 mirroring.
4. **Unified `brain/notes/` vault zone.** Frontmatter `x-augur-note-type` distinguishes url / file / thought / voice-memo / meeting / image / prompt.
5. **Single canonical Browse tab.** `inbox`, `sources`, `prompts` ViewModes retire; `notes` becomes the canonical content tab with filter-chip URLs replacing them.
6. **Transcription substrate.** Local whisper.cpp default; pluggable provider declared in `audio-ingest/SKILL.md` frontmatter. Lives inside `document-extractor` as a new extraction op (audio is just another binary modality).
7. **Audio classification.** Agent reads transcript and classifies voice-memo vs meeting (heuristics: speaker count, first-person voice, duration band, sentence shape). Manual override via `--memo` / `--meeting` flags.
8. **Signal-detector deferred.** Explicit `/note <thought>` only. No ambient client-hook capture in this slate.

## Command surface

### Daily verbs

```
/note <anything>     Single input verb. Router dispatches by argument shape.
/ask  <question>     Single query verb. --remember retains answer.
```

#### `/note` dispatch table

| Argument shape | Detection | Pipeline | Resulting note type |
|----------------|-----------|----------|--------------------|
| `https://...` | URL regex | url-extract → save-url-source | `url` |
| `*.pdf`, `*.docx`, `*.md`, `*.html`, `*.txt` | file path + ext | document-extractor → note write | `file` |
| `*.m4a`, `*.mp3`, `*.wav`, `*.mp4`, `*.mov` (audio track only) | file path + ext | document-extractor (transcribe) → audio-ingest classify → note write | `voice-memo` or `meeting` |
| `*.png`, `*.jpg`, `*.heic`, `*.webp` | file path + ext | document-extractor (OCR + caption) → note write | `image` |
| existing directory path | inode is dir | inbox-scan-folder (existing) | per-file notes |
| free text (no path, no URL) | fallback | save-prompt or thought-write based on content-aware sniff | `thought` or `prompt` |
| (empty) | no arg | open interactive Note picker UI (drop / paste / type) | depends |

#### `/note` flags (override autodetect)

- `--thought` — force type `thought`
- `--as prompt` — force type `prompt` (skip content-aware sniff)
- `--memo` — force audio type `voice-memo`
- `--meeting` — force audio type `meeting`
- `--folder` — treat path as a folder even if it could be a file
- `--url` — treat text as URL even without scheme
- `--from <email>` — non-interactive intake from a configured source (currently only `email` via ADR-595 mail drop; `archive` and `webhook` deferred)
- `--trigger <prompt-slug>` — run a saved prompt with current context

### Retired

- `/ingest` — alias to `/note` for one minor-version cycle, prints deprecation notice on use. Hard removal in the version after.

### Unchanged

- `/save <artifact>` — in-session artifact export. Workflow tool, not daily.
- `/ask <question>` — query brain. Unchanged surface and flags including `--remember`.

## Vault layout

The dashboard URL `/brain/notes` corresponds to the vault folder `<vault>/notes/` (no literal `brain/` prefix at the folder level — `brain` is the hub name in the sidebar). `get_vault_notes_dir()` in `src/config/paths.py` already resolves this path. The migration below references absolute vault sub-paths.

### Before

```
<vault>/
  inbox/         # source cards from URLs, email-drop, folder ingests
  sources/       # URL source cards (sub-tree: sources/urls/)
  prompts/       # prompt cards (triggerable; ADR-748)
  notes/         # already exists, empty for most users
  wiki/          # compiled-truth pages (ADR-740)
  insights/      # brain-insights synthesis
```

### After

```
<vault>/
  notes/         # ALL /note outputs; frontmatter x-augur-note-type discriminates
    2026-05-15-url-hbr-leverage.md            (type: url)
    2026-05-15-thought-rrf-as-trust.md        (type: thought)
    2026-05-15-voice-monday-recap.m4a.md      (type: voice-memo)
    2026-05-15-meeting-team-sync.mp4.md       (type: meeting)
    2026-05-15-prompt-pr-review.md            (type: prompt, triggerable: true)
    2026-05-15-file-q2-financials.pdf.md      (type: file)
    2026-05-15-image-whiteboard-arch.png.md   (type: image)
  wiki/          # unchanged
  insights/      # unchanged
  inbox/         # retired after migration; empty
  sources/       # retired after migration; empty
  prompts/       # retired after migration; empty
```

The migration absorbs `inbox/`, `sources/`, and `prompts/` into `notes/` with `x-augur-note-type` frontmatter. The empty retired directories remain on disk for one minor-version cycle (so external tooling that grep'd them does not break overnight); the version after this ADR removes the directory helpers entirely.

### Migration

One-shot Python script under `shared-vault/skills/ingest/augur/scripts/migrate_inbox_to_notes.py`:

1. Walk `brain/inbox/*.md`.
2. Read existing frontmatter. Classify by existing markers (`source: url` → `type: url`, `prompt_triggerable: *` → `type: prompt`, otherwise → `type: file`).
3. Write `x-augur-note-type` into frontmatter.
4. Move file to `brain/notes/` preserving filename.
5. Rewrite cross-references in other vault files (`brain/inbox/` → `brain/notes/`).
6. Idempotent: re-running is a no-op once migration is complete.
7. Logged to ADR-743 job ledger.

## Browse page impact

### ViewMode changes

| ViewMode today | After | Replacement |
|----------------|-------|-------------|
| `inbox` | retired | redirect → `/browse?view=notes` |
| `notes` | **canonical** content tab; renders all `brain/notes/*.md` | — |
| `sources` | retired | redirect → `/browse?view=notes&type=url,file` |
| `prompts` | retired | redirect → `/browse?view=notes&type=prompt` |
| `wiki` | unchanged | — |
| `integrations` | unchanged | — |

The `notes` tab renders the existing `BrowseContentGrid` with filter chips at the top. Filter state is reflected in the URL (`?type=...`) so any preset view is a bookmarkable URL.

### `BrowseItem` shape

No interface changes. The existing `typeBadge` string field is populated from `x-augur-note-type`. The existing `metadata` record (already documented as supporting `kind`, `skillTags`, `category`, etc.) absorbs new fields:

| Field | Populated for | Example |
|-------|---------------|---------|
| `duration_seconds` | voice-memo, meeting | `"312"` |
| `transcript_status` | voice-memo, meeting | `"pending"`, `"complete"`, `"failed"` |
| `attendee_count` | meeting | `"5"` |
| `attendee_slugs` | meeting | `"sasha,priya,jay"` |
| `enrichment_status` | url, file | `"pending"`, `"enriched"`, `"skipped"` |
| `trigger_count` | prompt | `"7"` |
| `triggerable` | prompt | `"true"` |
| `source` | non-interactive intakes | `"email"` (future: `"webhook"`, `"archive"` when added) |

### BrowseCard.tsx

Adds type-conditional metadata-strip rendering keyed off `typeBadge`. Each note type gets a one-line strip beneath the title with the most relevant 2–3 metadata fields. No layout changes to the card itself.

Type badges (Lucide icon names, not emoji):

- `url` — `Link2`
- `file` — `FileText`
- `thought` — `Lightbulb`
- `voice-memo` — `Mic`
- `meeting` — `Users`
- `prompt` — `Zap`
- `image` — `Image`

### BrowseDetailPanel.tsx

Adds type-conditional sections:

- `url`: open-original link, embedded snippet, "Enrich…" action
- `file`: file preview (if renderable), extracted-text pane
- `thought`: full body, linked entities (from ADR-738 graph)
- `voice-memo`: audio player, collapsible transcript pane
- `meeting`: audio player, transcript with speaker labels, attendee chip list, "Merge to timeline" action
- `prompt`: prompt body, Trigger button, variable editor, last-N-trigger history (existing ADR-748 UI)
- `image`: preview, OCR/caption pane

### Capture-entry components

`apps/dashboard/features/browse/Ingest*.tsx` → renamed to `Note*.tsx`:

- `IngestFAB.tsx` → `NoteFAB.tsx`
- `IngestModal.tsx` → `NoteModal.tsx` — modal accepts URL paste, file drop, audio drop, folder pick, free-text paste; one modal, mode-tabs inside
- `IngestDropZone.tsx` → `NoteDropZone.tsx` — universal drop target on the notes tab
- `IngestQueueItem.tsx` → `NoteQueueItem.tsx` — streaming-progress card

Per the no-shortcut preference, rename in place rather than aliasing.

## Skill topology and per-skill detail

### 1. `audio-ingest` (NEW skill)

**Location:** `shared-vault/skills/audio-ingest/`

**Purpose:** Own the voice and meeting modalities end-to-end. Take an audio file, transcribe it via `document-extractor`, classify as voice-memo or meeting, enrich for the chosen type, and emit a single note in `brain/notes/`.

**Problem solved:** Augur has no audio capture path today. Voice memos (user's own ad-hoc thinking) and meeting recordings (collaborative knowledge with attendees + decisions + timeline events) are two distinct knowledge shapes both blocked behind the same missing modality.

**User flow:**

```
$ /note ~/Downloads/voice-memo-tuesday.m4a
  -> [document-extractor.transcribe] running whisper.cpp ... 3.2s
  -> [audio-ingest.classify] single speaker, first-person, 1m12s -> voice-memo
  -> [ingest.write-note] brain/notes/2026-05-15-voice-monday-recap.m4a.md
  -> [graph.extract-entities] 0 entities
  done. Note: voice-memo "monday recap" (1m12s)

$ /note ~/Downloads/q2-planning.mp4
  -> [document-extractor.transcribe] running whisper.cpp ... 42s
  -> [audio-ingest.classify] 4 speakers, mixed first/third person, 38m -> meeting
  -> [audio-ingest.speaker-label] dispatched to active AI client ... 5.1s
  -> [graph.extract-entities] 12 entities, 4 attendee matches
  -> [ingest.write-note] brain/notes/2026-05-15-meeting-q2-planning.mp4.md
  done. Note: meeting "Q2 Planning" (38m, 4 attendees, "Merge to timeline" suggested)
```

Override flags `--memo` / `--meeting` bypass the classifier.

**Dependencies:**

- `document-extractor` — transcription op (audio → text). New `extract-audio` MCP tool. Pluggable provider; default whisper.cpp (~1.5 GB model, runs on-device on M-series Macs).
- `graph` (ADR-738) — entity extraction from transcript; attendee resolution.
- `wiki` (ADR-740) — timeline-merge target for meetings.
- `ingest` — note-writing primitives.
- Active AI client — used for speaker labeling, decision extraction, and meeting summary via dispatched calls (Rule 19); never direct from dashboard or skill.

**ADR:** ADR-752.

### 2. Article-enrichment — extends `wiki` skill

**Location:** `shared-vault/skills/wiki/augur/scripts/enrich_article.py` + new MCP tool `enrich-article`.

**Purpose:** Turn a freshly-captured `type: url` or `type: file` note into a structured note with executive summary, verbatim quotes, key insights, why-it-matters, and cross-references — all written back into the same file.

**Problem solved:** Today a captured URL gives you a card with title + content + tags but no synthesis. You re-read the article to remember what mattered. Cards are not 30-second-comprehensible. Enrichment adds the synthesis layer at the top of every captured article, structured and searchable.

**User flow:**

Automatic: every new `type: url` or `type: file` note triggers enrichment in the background. Badge cycles `enrichment_status: pending` → `enriched`. The user can open the card immediately; the enriched sections appear above the raw content when ready.

Manual: detail-panel "Enrich…" action — useful for re-enriching after entities have been added or for old un-enriched cards.

Output file shape:

```markdown
---
title: "Leverage and the Architect"
url: https://hbr.org/...
x-augur-note-type: url
x-augur-enrichment-status: enriched
x-augur-enrichment-version: 1
---

## Executive summary

- bullet 1
- bullet 2
- ...

## Key insights

1. ...
2. ...

## Why it matters

(paragraph tied to user entities and recent notes)

## Verbatim quotes

> "longest impactful passage 1"
> — paragraph 4

> "longest impactful passage 2"
> — paragraph 12

## Cross-references

- [[wiki/concepts/leverage]]
- [[notes/2026-05-10-thought-architect-not-builder]]

## Original content

(full extracted article text — preserved verbatim at the bottom)
```

**Dependencies:**

- `wiki` — compiled-truth pattern (ADR-740); enrichment is essentially a compiled-truth view materialized inside the note.
- `graph` (ADR-738) — cross-reference extraction.
- Active AI client — dispatched call for the actual summarization / quote extraction (Rule 19). If the user is offline, enrichment queues and runs when the client returns.

**ADR:** ADR-753.

## Transcription substrate (deeper detail)

### Default: whisper.cpp (local)

- Runs on-device; no network calls.
- Model: medium.en (~1.5 GB) by default. Configurable via `config/system/transcription.yaml`.
- Performance: roughly 0.3–0.5x realtime on Apple Silicon (a 10-minute meeting transcribes in 2–5 minutes).
- Installed lazily on first audio note (one-time download with user confirmation).

### Pluggable providers

`shared-vault/skills/audio-ingest/SKILL.md` frontmatter declares the active provider:

```yaml
x-augur-transcription:
  provider: whisper-cpp   # whisper-cpp | openai-whisper-api | assemblyai | apple-speech | custom
  model: medium.en        # provider-specific
  language: en            # ISO code; or "auto"
  speaker_labels: false   # only used by providers that support diarization
```

Each provider implementation is a thin adapter under `shared-vault/skills/document-extractor/augur/providers/transcription/*.py`. Adapters share a single signature `transcribe(audio_path, options) -> Transcript`.

### Why this lives in `document-extractor`, not `audio-ingest`

`document-extractor` already abstracts "binary in, clean text out" for PDFs, DOCX, images. Audio is just another binary modality. Putting transcription elsewhere would duplicate the provider-abstraction pattern. `audio-ingest` consumes the transcript and owns audio-specific logic (classifier, speaker labeling, attendee enrichment, timeline merge).

## ADR slate

Three new ADRs, all Proposed, all dated 2026-05-15. Dependency order: ADR-751 is load-bearing (surface + storage); ADR-752 and ADR-753 can ship in either order after it.

| ADR | Title | Depends on |
|-----|-------|-----------|
| ADR-751 | Two-verb daily command surface and unified notes zone | — (load-bearing) |
| ADR-752 | audio-ingest skill for voice memos and meetings | ADR-751, ADR-738, ADR-740 |
| ADR-753 | Article-enrichment extension to wiki | ADR-751, ADR-740, ADR-738 |

## Data flow examples

### Capturing a URL

```
user: /note https://hbr.org/2026/05/leverage-architect
  -> /note router: scheme detected -> url-extract path
  -> ingest.url-extract: fetches via ADR-750 browser-first fetcher
  -> ingest.save-url-source: writes brain/notes/2026-05-15-url-hbr-leverage.md
                              frontmatter: x-augur-note-type: url, enrichment_status: pending
  -> graph.extract-entities (ADR-738): emits typed-edge links
  -> wiki.enrich-article (background, async):
       dispatches to active AI client
       writes summary/insights/quotes back into the note file
       updates frontmatter: enrichment_status: enriched
  -> daemon: notification (dismissable) "URL note enriched"

user sees in /browse?view=notes:
  card "Leverage and the Architect" (type: url, enrichment: pending -> enriched)
```

### Capturing a meeting recording

```
user: /note ~/Downloads/q2-planning.mp4
  -> /note router: ext .mp4 with audio -> audio-ingest path
  -> document-extractor.extract-audio (whisper.cpp): 38m -> transcript
  -> audio-ingest.classify: 4 speakers, mixed person, 38m -> meeting
  -> audio-ingest.speaker-label (dispatched to AI client): per-speaker chunks
  -> graph.extract-entities: 12 entities, 4 match known persons
  -> ingest.write-note: brain/notes/2026-05-15-meeting-q2-planning.mp4.md
       frontmatter: type: meeting, duration_seconds: 2280, attendee_slugs: ...
  -> wiki.merge-timeline (suggested, not auto): user clicks "Merge to timeline"
       emits timeline events into wiki/timeline (ADR-740)
```

### Capturing a thought

```
user: /note "I think RRF works because retrieval failure modes are mostly orthogonal across rankers"
  -> /note router: free text, content-aware sniff -> thought (not prompt-shaped)
  -> ingest.write-note: brain/notes/2026-05-15-thought-rrf-orthogonal-failures.md
       frontmatter: type: thought
  -> graph.extract-entities: links to concept:rrf, concept:retrieval
```

### Capturing a prompt

```
user: /note --as prompt "Review this PR for: ..."
  -> /note router: explicit type prompt
  -> ingest.save-prompt: brain/notes/2026-05-15-prompt-pr-review.md
       frontmatter: type: prompt, triggerable: true
  -> appears in /browse?view=notes&type=prompt as triggerable card

later: user clicks Trigger button in detail panel
  -> /note --trigger pr-review : dispatches prompt to active AI client (ADR-748)
```

## Migration plan

### Vault

One-shot script (idempotent) moves `brain/inbox/*.md` to `brain/notes/` with `x-augur-note-type` added. Cross-references rewritten. Logged to ADR-743 ledger. Existing tests under `tests/dashboard/browse/` continue to pass against the new paths (test fixtures regenerated by the same script in tmp paths).

### Dashboard

Component renames `Ingest* -> Note*` in `apps/dashboard/features/browse/`. ViewMode enum in `apps/dashboard/lib/browse/types.ts` — `inbox`, `sources`, `prompts` retired with redirect handlers from old query strings to new filter URLs. `BrowseCard.tsx` and `BrowseDetailPanel.tsx` get type-conditional rendering for the new note types. Existing tests in `tests/dashboard/browse/` and `tests/dashboard/components/shared/` updated for the renamed types and conditional sections.

### Commands

`/ingest` becomes a thin alias to `/note` in the same command file, emitting a one-time-per-session deprecation notice. Hard removal in the version after this slate ships. `config/system/capability_exposure.yaml` adds a `command:note:` entry and a `command:ingest:` entry that mirrors note but is marked `deprecated: true`.

### Capability exposure

Per the `feedback-command-capability-entry` memory: new `/note` command needs `command:note:` in `config/system/capability_exposure.yaml`. New MCP tools (`extract-audio`, `enrich-article`) each need their own `mcp-tool:` entry classified by preferred surface.

## Testing strategy

Per Rule 34 (verification must prove user value, not mechanical pass), every new capability ships with both a unit-test layer and a real-data verification check:

| Capability | Unit / contract tests | Real-data verification |
|------------|----------------------|------------------------|
| `/note` router | dispatch table per arg shape (URL, file ext, audio ext, text, folder, empty) | exec `/note <real URL>`, `/note <real PDF>`, `/note <real audio file>`, `/note "<thought>"` — verify the right note appears in `/brain/notes` with right frontmatter |
| audio-ingest classifier | classification on canned transcripts (single speaker, multi speaker, short, long, first-person, third-person) | exec `/note <real voice memo>` and `/note <real meeting recording>` — verify the chosen type matches user expectation |
| document-extractor audio op | provider adapter contract (whisper-cpp default; mock adapters for other providers) | exec against 3 real audio files of varying length/quality; assert transcript word-error-rate below threshold against ground-truth |
| article-enrichment | output schema (sections present); fallback when AI client unreachable | enrich 5 real captured articles; assert each enriched file has all required sections and at least one cross-reference |
| Browse `notes` tab | ViewMode redirect tests for retired `inbox`, `sources`, `prompts` URLs; filter-chip URL round-trip | open `/browse?view=notes` in a real browser per Rule 28; verify type filters work and notes load to interactive state |
| Migration script | idempotency on tmp tree; cross-reference rewrites | dry-run against a real `brain/inbox/`; verify cross-reference count matches scan |

Auto-loops (`/auto-test-build`, `/auto-test-dashboard`, `/auto-test-pytest`) cover all of the above. No raw `pnpm`/`pytest` per Rules 19 and 29.

## Open questions

None blocking. One implementation choice defers to ADR-time:

1. **Classifier dispatch.** Local heuristic (no model call) for the voice-memo vs meeting decision, or always dispatch to active AI client? ADR-752 will compare both and recommend. Local heuristic preferred if it hits ≥90% accuracy on a held-out set; client-dispatched otherwise.

## Explicit cuts (not in this slate)

- gbrain `signal-detector` ambient hook — explicit `/note <thought>` only.
- gbrain `archive-crawler` — bulk archive backfill deferred to a later slate; `inbox-scan-folder` covers active inboxes for now.
- gbrain `webhook-transforms` — external push intake deferred to a later slate; revisit when there is concrete integration pull and a security/tunneling story to commit to.
- gbrain `book-mirror` — adjacent to existing `books`; deferred.
- gbrain `brain-pdf` — export pipeline, out of scope.
- gbrain `media-ingest` — substantially overlapped by `document-extractor` post-audio.
- gbrain `idea-ingest` entity layer — already covered by ADR-738 + ADR-748 + `/note` routing.
- Configurable entity templates (person/company/etc. wiki pages) — out of scope; ADR-738 typed graph captures entities at the graph layer for now.
- `/prompt` alias — pure two-verb discipline.

## Memory updates after this spec lands

- `project-gbrain-borrow-slate`: append "supplemented 2026-05-15 with ADR-751..753 ingest port slate; see this spec."
- New memory entry not required; ADR slate and this spec are themselves canonical.
