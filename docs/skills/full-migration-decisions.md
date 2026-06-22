# Full Skill Migration Decisions

This ledger records the target migration outcome for every skill currently visible in
the Augur brain stack: global/project skills from `project-brain/capabilities/skills`
and personal skills from `~/Projects/Au-vault/_augur/capabilities/skills`.

The migration rule is conservative: a skill becomes standard only when the portable
agent logic can live without Augur runtime metadata, MCP bindings, dashboard pages,
or hardcoded private paths. Augur-specific integration remains in an adapter layer.

## Personal Skills

| Skill | Current contract | Target action | Rationale |
| --- | --- | --- | --- |
| `apple` | `standard-source-ready` | `keep-standard` | Already migrated to Hermes-style standard source with Apple subskills and no Augur runtime dependency in the source bundle. |
| `email` | `standard-source-ready` | `keep-standard` | Already migrated to standard source through the `himalaya` subskill. |
| `note-taking` | `standard-source-ready` | `keep-standard` | Already migrated to standard source through the `obsidian` subskill. |
| `public-presence` | `standard-source-ready` | `keep-standard` | The collateral update workflow now lives as a standard bundle with no Augur metadata or runtime dependency in the source. |
| `books` | `standard-source-ready` | `adapter: books-augur` | Standard portable source is split into `books/reading-library` and `books/reading-list`; Augur Brain hub pages, MCP tools, vault-backed data paths, and runtime actions live in `books-augur`. |
| `file-manager` | `standard-source-ready` | `adapter: file-manager-augur` | Standard portable source is split into `file-manager/local-file-organization`; Browse/routine/MCP integration, path-helper-backed vault/documents access, and runtime history live in `file-manager-augur`. |
| `vault` | `augur-platform-skill` | `keep-platform` | This is the Augur vault integration boundary; portable note behavior belongs in `note-taking`, not this adapter. |

## Global And Project Skills

`global:augur-core` and `project:project-augur` currently resolve to the same
physical skill root. The full migration report deduplicates that root and records
both roles on each project-brain skill.

Real-root audit on 2026-05-30 scanned two physical roots and 34 report rows:
11 standard-source-ready rows and 23 Augur platform adapter rows. The report
deduplicates `global:augur-core` and `project:project-augur` by physical root,
while preserving both roles on each project-brain skill. Standard cores extracted
from Augur platform skills are recorded here with their remaining Augur adapter
boundary.

| Skill | Current contract | Target action | Rationale |
| --- | --- | --- | --- |
| `ai` | `augur-platform-skill` | `keep-platform` | Owns Augur AI client synchronization and generated instruction policy. |
| `audio-ingest` | `augur-platform-skill + standard core` | `standard core: local-audio-processing/audio-transcription; adapter: audio-ingest` | Portable local audio discovery, transcription preparation, transcript quality review, and context classification live in the standard core; Augur extraction/classification MCP submission and ingestion contracts remain adapter-owned. |
| `augur-core` | `augur-platform-skill` | `keep-platform` | Core command/session/local-mode control is Augur runtime. |
| `auto-skill-quality` | `augur-platform-skill` | `keep-platform` | Governs Augur skill contract scans and migration reports. |
| `daemon` | `augur-platform-skill` | `keep-platform` | Daemon scheduling, notifications, and expirations are Augur runtime. |
| `document-extractor` | `augur-platform-skill + standard core` | `standard core: local-document-extraction/document-to-markdown; adapter: document-extractor` | Portable document-to-Markdown guidance for local files lives in the standard core; Augur MCP result submission, queue state, and extraction-status tools remain adapter-owned. |
| `dream` | `augur-platform-skill + standard core` | `standard core: recurring-reflection/dream-routine; adapter: dream` | Portable recurring reflection workflow lives in the standard core; Augur wiki, cache, report, and routine projection tools remain adapter-owned. |
| `evals` | `augur-platform-skill + standard core` | `standard core: retrieval-evals/retrieval-eval-harness; adapter: evals` | Portable JSONL retrieval eval datasets, replay, metrics, and file-first reports live in the standard core; Augur capture/export and project retrieval wiring remain adapter-owned. |
| `graph` | `augur-platform-skill + standard core` | `standard core: markdown-knowledge-graph/typed-link-extraction; adapter: graph` | Portable typed-link extraction from Markdown links, frontmatter, citations, and note structure lives in the standard core; Augur vault graph rebuild/storage contracts remain adapter-owned. |
| `ingest` | `augur-platform-skill` | `keep-platform` | Inbox, wiki, source cards, and ingest lanes are Augur data-plane integration. |
| `knowledge` | `augur-platform-skill` | `keep-platform` | Search, memory, RAG, and profile operations are Augur brain runtime. |
| `onboard` | `augur-platform-skill` | `keep-platform` | Setup and local backend checks are Augur installation workflow. |
| `platform-admin` | `augur-platform-skill` | `keep-platform` | Repo health, CI, releases, and refactor tools are Augur platform operations. |
| `plugin-pack` | `augur-platform-skill` | `keep-platform` | Skill docs/actions health endpoints are Augur plugin infrastructure. |
| `rag` | `augur-platform-skill` | `keep-platform` | RAG index lifecycle is Augur storage/runtime. |
| `routine-codebase` | `augur-platform-skill` | `keep-platform` | Routine implementation is tied to Augur codebase checks. |
| `routine-coverage` | `augur-platform-skill` | `keep-platform` | Routine implementation is tied to Augur coverage checks. |
| `routine-platform` | `augur-platform-skill` | `keep-platform` | Routine implementation is tied to Augur platform checks. |
| `routine-security` | `augur-platform-skill` | `keep-platform` | Routine implementation is tied to Augur security checks. |
| `routine-vault` | `augur-platform-skill` | `keep-platform` | Routine implementation is tied to Augur vault checks. |

## Adapter Boundaries Left In Place

These are intentional remaining adapter boundaries, not missed standard-source
work:

- `books`: root `SKILL.md`, `augur/`, and `scripts/mcp/` remain the Augur Brain
  hub and MCP adapter. Standard portable source is `reading-library/` and
  `reading-list/`.
- `file-manager`: root `SKILL.md`, `augur/`, autoloop scripts, and `scripts/mcp/`
  remain the Browse/routine/MCP adapter. Standard portable source is
  `local-file-organization/`.
- `document-extractor`: root `SKILL.md`, extraction status, MCP queue submission,
  and Augur document runtime integration remain the adapter. Standard portable
  source is `local-document-extraction/document-to-markdown/`.
- `audio-ingest`: root `SKILL.md`, Augur audio extraction/classification MCP
  submission, and ingest writeback remain the adapter. Standard portable source
  is `local-audio-processing/audio-transcription/`.
- `evals`: root `SKILL.md`, Augur capture/export/replay tools, and project
  retrieval wiring remain the adapter. Standard portable source is
  `retrieval-evals/retrieval-eval-harness/`.
- `graph`: root `SKILL.md`, Augur vault graph rebuild/storage, and typed-edge
  frontmatter writeback remain the adapter. Standard portable source is
  `markdown-knowledge-graph/typed-link-extraction/`.
- `dream`: root `SKILL.md`, Augur routine projection, wiki/cache/report tools,
  and nightly state integration remain the adapter. Standard portable source is
  `recurring-reflection/dream-routine/`.
- `vault`: root `SKILL.md`, `augur/`, and `scripts/mcp/` remain the vault runtime
  adapter. Generic notes and Obsidian operation stay in `note-taking/obsidian`;
  markdown conversion may be extracted later only if a non-Augur use case is
  proven.

## Full Migration Verification Evidence

Recorded on 2026-05-30 from `~/Projects/Augur`, with the
personal vault repo present at `~/Projects/Au-vault`.

| Check | Command | Status | Concrete evidence observed |
| --- | --- | --- | --- |
| Books real-data check | `~/Projects/Augur/.venv/bin/python3 - <<'PY' ... Path("~/Projects/Au-vault/notes/books") ... PY` | PASS | `books_yaml_exists=True`; `book_notes=17`; first notes included `a-random-walk-down-wall-street.md`, `appliance.md`, `breaking-the-tie.md`, `die-with-zero.md`, and `fire-and-blood.md`. |
| File-manager real-data check | `~/Projects/Augur/.venv/bin/python3 - <<'PY' ... Path.home() / "Downloads" ... PY` | PASS | `downloads_files=11`; first local candidates included `.DS_Store`, `205e69f8_11322.pdf`, `Perplexity.dmg`, `scorecard.md`, and `.localized`. |
| Requested migrated-skill test set | `~/Projects/Augur/.venv/bin/python3 -m pytest project-brain/capabilities/skills/document-extractor/augur/tests/test_extractor.py project-brain/capabilities/skills/audio-ingest/augur/tests/test_classifier.py project-brain/capabilities/skills/evals/augur/tests/test_replay.py project-brain/capabilities/skills/graph/augur/tests/test_graph_rebuild.py project-brain/capabilities/skills/dream/augur/tests/test_dream_report.py -q` | PASS | All requested test paths existed; pytest reported `40 passed in 0.98s`. |
| Document-extractor real file check | `.venv/bin/aug extract-document --path ~/Downloads/scorecard.md --include-metadata true` | PASS | Extracted real Downloads file `scorecard.md`; result returned `success=true`, `title=scorecard`, `format=md`, `tier_used=0`, `ocr_applied=false`, `size_bytes=12299`, and Markdown headed `Stress-test scorecard — Augur Compounding Edge Device`. |
| Graph real cache check | `.venv/bin/aug graph stats` | PASS | Real graph cache reported `edge_count=2204`, `entity_count=1049`, edge types `mentions=164`, `relates_to=1232`, `authored_by=15`, `cites=793`, tier distribution `3=874`, `2=171`, `1=4`, and no dangling targets. |
| Graph real edge query | `.venv/bin/aug graph query --type cites` | PASS | Returned real cite edges, including `2026-04-29-samsung-ai-kickoff-proposal` citing `notes/career/hard-skills/ai-and-hpc-networking-learning-roadmap.md` and other vault/document paths. |
| Evals real storage check | `.venv/bin/aug eval capture-status` | PASS | Real eval capture state reported `consent=true`, `enabled=false`, `last_capture_ts=2026-05-24T10:16:48Z`, `queries_captured_total=114`, and `queries_today=0`. |
| Evals latest run stats | `.venv/bin/aug eval stats` | PASS_WITH_CONCERNS | Latest run `2026-05-24-142528-2bde94e` reported `total_queries=60`, `scored=35`, `unlabeled=25`, `index_drift=true`, `vault_manifest_hash=1aed3493b22b`, and non-empty score metrics. The drift flag means this is evidence of real stored eval output, not a fresh green retrieval-quality gate. |
| Dream real report check | `.venv/bin/aug dream last-report` | PASS | Latest real dream report was dated `2026-05-18` at `~/Projects/Au-docs/reports/dream/2026-05-18.md`. |
| Dream real job status | `.venv/bin/aug dream status` | PASS | Latest real dream job `20260518-203103-197-000-dream-cycle` was `complete`; returned history included ten complete dream-cycle jobs. |
| Audio dependency repair | `uv sync --extra audio --frozen` | PASS | Synced the existing locked `audio` extra without changing repo files; installed `pywhispercpp==1.4.1`, `platformdirs==4.9.6`, and `tqdm==4.67.3`. |
| Audio real extraction attempt | `.venv/bin/aug extract-audio --audio-path ~/Downloads/L28.m4a --language en` | PASS_WITH_CONCERNS | Real audio file `~/Downloads/L28.m4a` extracted after the audio extra sync; result returned `success=true`, `provider=whisper-cpp`, `provider_version=1.4.1`, `language=en`, `duration_seconds=2513.0`, and `speaker_count=0`. Transcript quality still needs review because the source contains substantial non-English speech while the command forced `--language en`. |

Remaining real-data gaps:

- `document-extractor/augur/tests/test_extractor.py` uses generated `tmp_path`
  files and mocked OCR paths. The real-data value check is covered separately by
  extracting `~/Downloads/scorecard.md`.
- `audio-ingest/augur/tests/test_classifier.py` uses committed transcript
  fixtures. Real local audio extraction now runs after syncing the locked audio
  extra, but the `L28.m4a` transcript needs human review because the file contains
  substantial non-English speech while the command forced English.
- `evals/augur/tests/test_replay.py` explicitly mocks live retrieval so it does
  not depend on a real vault/index. Real eval storage exists, but the latest
  stats report `index_drift=true`; a fresh replay against the current index is
  still a separate retrieval-quality gate.
- `graph/augur/tests/test_graph_rebuild.py` rebuilds a temporary vault fixture.
  Real graph value is evidenced by `graph stats` and `graph query --type cites`;
  this task did not run a mutating full-vault rebuild.
- `dream/augur/tests/test_dream_report.py` writes reports under `tmp_path`.
  Real dream value is evidenced by the existing latest report and complete job
  ledger status; this task did not run a new dream cycle.

## Acceptance For This Migration

- Discovery lists standard bundle subskills as first-class skills.
- The committed manifest preserves private standard subskill paths.
- `public-presence`, `books`, `file-manager`, `document-extractor`,
  `audio-ingest`, `evals`, `graph`, and `dream` become standard-source-ready or
  have only documented adapter overhead left.
- Platform skills remain explicit decisions, not accidental leftovers.
- Final verification runs against the real Augur project brain and real personal
  vault roots, not fixture-only data.
