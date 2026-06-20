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
  - ADR-751
hub: brain
tags:
  - ingest
  - audio
  - voice-memo
  - meeting
  - transcription
  - llm-assisted-mcp
  - vendor-neutral
superseded_by: null
spec_file: 2026-05-15-gbrain-ingest-port-design.md
plan_file: 2026-05-16-adr-752-audio-ingest-skill.md
depends_on:
  - ADR-751
---

# ADR-752: audio-ingest skill — voice memos and meetings

## Status

Implemented on 2026-05-16 after ADR-751 landed on `origin/main`.

## Context

Augur has no audio capture path today. The two distinct knowledge shapes inside the audio modality — a user's own voice memo (single speaker, first-person, short, captures a fleeting thought) and a multi-person meeting recording (multiple speakers, time-stamped exchanges, decisions, action items, attendees) — both demand a different downstream structure than a captured URL or file. Both are blocked behind the same missing capability: speech-to-text.

The linked spec settled the architectural shape during brainstorming:

- Transcription is a **modality of `document-extractor`**, not a new concern. `document-extractor` already abstracts "binary in, clean text out" for PDF / DOCX / image / OCR. Audio is just another binary modality. Putting transcription elsewhere would duplicate the provider-abstraction pattern.
- Transcription is **pluggable** via a provider abstraction. The default is whisper.cpp (local, no network call). Future providers (OpenAI Whisper API, AssemblyAI, Apple Speech) can drop in by registering an adapter without changing skill code. The active provider is declared in skill frontmatter / config, never hardcoded.
- The voice-memo-vs-meeting classifier is **heuristic-first, LLM-assisted on uncertainty**. A simple feature set (speaker count, first-person density, duration band, bracket-tagged speaker labels) handles the easy cases with confidence ≥ 0.9. Ambiguous cases escalate via the LLM-Assisted MCP Pattern (`docs/references/llm-assisted-mcp-pattern.md`) so the active AI client decides — never a hardcoded vendor call.
- Meeting transcripts get **attendee resolution** against the ADR-738 typed graph (bracket-tagged speaker names → person-entity slugs) and a "Merge to timeline" affordance for ADR-740 compiled-truth/timeline integration.

A new `audio-ingest` skill at `shared-vault/skills/audio-ingest/` owns the audio-specific routing (classification, attendee resolution, note writing). It depends on the transcription op in `document-extractor`. The `/note` command in `ingest` gets its Audio dispatch wired through `extract-audio` → `audio-classify` → `audio-ingest-write`.

## Decision

Create a new `audio-ingest` skill in `shared-vault/skills/audio-ingest/` (hub: brain). It owns three new MCP atomic ops:

1. `audio-classify` — heuristic-first classifier returning `{type: voice-memo|meeting, confidence, reasoning}`. When heuristic confidence is below threshold (default 0.9), it returns the LLM-Assisted MCP Pattern's `{needs_llm: true, ...}` payload so the active AI client (or a spawned CLI session in Mode 2) decides and submits the result via the companion tool.
2. `submit-audio-classify-result` — companion tool that accepts the LLM-derived `{type, confidence, reasoning}` and returns the merged result.
3. `audio-ingest-write` — persists the voice-memo or meeting note under `<vault>/notes/` with the correct `x-augur-note-type`, frontmatter (`duration_seconds`, `provider`, `provider_version`, `transcript_status: complete`, `audio_path`, `content_hash`), and body (transcript at minimum; for meetings, an "Attendees" section with resolved person-entity links).

Add a new MCP tool `extract-audio` under `document-extractor` that wraps a transcription facade (`src/lib/extraction/transcription/`) returning a provider-neutral `Transcript` dataclass (text + segments + duration + language + provider + provider_version + speaker_count). The default adapter is whisper.cpp via `pywhispercpp` (added as an optional `audio` extra in pyproject.toml so users without audio needs do not pull the model bindings). The medium.en model (~1.5 GB) auto-downloads on first call. Speaker labels are off by default; providers that support diarization can be enabled per-call via the `speaker_labels` option.

Replace the `## Audio` stub section in `shared-vault/skills/ingest/commands/note.md` (added by ADR-751's plan) with a live dispatch: extract-audio → audio-classify → (LLM-Assisted callback if needed) → audio-ingest-write. Honour `--memo` and `--meeting` override flags that bypass the classifier.

Extend `apps/dashboard/components/shared/BrowseDetailPanel.tsx` with `voice-memo` and `meeting` sections: HTML5 audio player, transcript pane (collapsible), attendee chip list (for meetings, linked to wiki pages), and an inert "Merge to timeline" button (the wire-up is a follow-up under ADR-740, not in this slate).

Add `mcp-tool:extract-audio`, `mcp-tool:audio-classify`, `mcp-tool:submit-audio-classify-result`, `mcp-tool:audio-ingest-write` to `config/system/capability_exposure.yaml`.

## Non-Goals

- Real-time / streaming transcription. The pipeline is one-shot per audio file.
- Speaker diarization improvement beyond what the provider supplies. If `speaker_labels` returns weak labels, the classifier still uses speaker_count from the segment list, and meeting attendee resolution falls back to bracket-tagged names in the transcript text when present.
- PII redaction. Out of scope; a future ADR can layer it on top.
- Real-time meeting recording / capture from a microphone. The user supplies a finished audio file (Voice Memos export, Zoom export, etc.).
- Auto-uploading audio to a cloud transcription provider. The default is fully local; any cloud provider is an explicit user opt-in via skill frontmatter.
- Browse-side editing of transcripts. The transcript pane is read-only; if the user wants to correct a transcript, they edit the note file directly.

## Consequences

- One new skill in `shared-vault/skills/audio-ingest/`. No existing skill's contract changes except `document-extractor` (gains `extract-audio` tool) and `ingest`'s `/note` command (gains Audio dispatch — already stubbed by ADR-751).
- whisper.cpp model is ~1.5 GB; cold-start of audio ingest on a fresh machine downloads the model on first call (one-time, automatic).
- Audio files themselves are not copied into the vault. The note's `audio_path` frontmatter field points to the source file at its original location; the body holds the transcript. Users who want the audio in the vault can move it there manually before `/note` (or a future ADR can add a `--copy-audio` flag).
- `audio-ingest`'s three MCP tools all follow the four-layer harness model: command policy (in `ingest/commands/note.md`) → agent dispatch → atomic ops. None of the audio code calls an LLM directly; the classifier escalates via the LLM-Assisted MCP Pattern when needed.
- Attendee resolution degrades gracefully: if the ADR-738 graph reader is unavailable (e.g. graph not yet built on a fresh machine), the resolver returns an empty list and the note still writes without attendee_slugs.
- BrowseDetailPanel changes are additive — existing types continue to render unchanged.
- The "Merge to timeline" button is inert in this slate; its handler is a tracked follow-up. The button is rendered now so users see the affordance and so the UI does not require a second-pass redesign when ADR-740's timeline-merge wiring lands.

## Critical context for fresh-session execution

The same conventions named in ADR-751's "Critical context" section apply (test convention, capability registration, vendor neutrality, `sync_agents` scope, dashboard ops, Rule 34 verification, Rule 28 browser verification). They are repeated here because this ADR may be triggered as a standalone session on a fresh machine without ADR-751's document loaded:

1. **Test convention:** skill tests under `shared-vault/skills/<skill>/augur/tests/` load modules via `importlib.util.spec_from_file_location(...)`, never dotted imports.
2. **Capability exposure:** every new MCP tool requires an entry in `config/system/capability_exposure.yaml` under `mcp-tool:<name>:`. Without it the tool does not appear in client surfaces.
3. **Vendor neutrality:** no direct LLM-vendor API calls. The audio classifier uses the LLM-Assisted MCP Pattern documented at `docs/references/llm-assisted-mcp-pattern.md`.
4. **`sync_agents` artifact scope:** after editing skill files, regenerate client surfaces with `augur sync mcp all` (and `augur sync commands all` if you also touched a command file). `sync agents all` is a different artifact class.
5. **Dashboard ops:** use `/dev-build` and `/dev-debug`. Do not `pnpm dev` directly.
6. **Verification standard:** Rule 34 requires real-data verification. The plan's final task captures a real voice memo (Voice Memos app on macOS, drag the .m4a out) and a real meeting recording, runs `/note` against both, and inspects the resulting notes. Do not weaken to tmp-path fixtures.
7. **Browser verification (Rule 28):** dashboard changes require client-side load in a real browser, not just HTTP 200. The plan's verification step opens `/browse?view=notes&type=voice-memo,meeting` in a real browser and confirms the audio player + transcript pane render.
8. **LLM-Assisted MCP Pattern:** read `docs/references/llm-assisted-mcp-pattern.md` if unfamiliar. The pattern has two modes — inside an AI client (the agent IS the LLM) and outside one (the tool spawns a CLI agent session). The audio classifier in this ADR uses the same pattern.

## Execution Kickoff

This ADR is self-contained for fresh-session execution. To implement on any machine:

```
# 1. Prerequisites: ADR-751 must be Implemented (atomic ops write under <vault>/notes/, /note command exists, BrowseCard handles voice-memo/meeting badges). Check:
grep "^status:" docs/adrs/ADR-751-two-verb-command-surface-and-notes-zone.md
# Must show: status: Implemented

# 2. Bootstrap dependencies on the new machine.
corepack enable && pnpm install && uv sync --extra audio
# The --extra audio pulls pywhispercpp for whisper.cpp.

# 3. Trigger the plan with the writing-plans → executing-plans skill chain.
#    In a Claude Code / Codex / Gemini session, invoke either:
#      a) superpowers:subagent-driven-development on docs/superpowers/plans/2026-05-16-adr-752-audio-ingest-skill.md
#      b) superpowers:executing-plans on the same plan file

# 4. The plan owns the rest: 13 tasks, TDD-shaped steps, exact file paths, exact commands.

# 5. Task 13 (real-data verification per Rule 34) requires:
#    - one real voice memo (record one via Voice Memos.app, ~30-60s)
#    - one real meeting recording (Zoom export, podcast .m4a, or similar 2+ speaker audio)
#    The agent runs /note against each, then inspects the resulting notes.

# 6. After Task 13 succeeds, flip frontmatter status to Implemented via /adr.
```

**Prerequisites:** ADR-751 Implemented.

**Plan file:** `docs/superpowers/plans/2026-05-16-adr-752-audio-ingest-skill.md` (13 tasks).

**Spec file:** `docs/superpowers/specs/2026-05-15-gbrain-ingest-port-design.md`.

**External dependencies installed by the plan:** `pywhispercpp` (Python audio extra), whisper.cpp `medium.en` model (~1.5 GB, auto-downloaded on first call).

**Open question resolved during implementation:** the plan benchmarks the heuristic classifier against canned voice-memo and meeting transcripts; if heuristic accuracy on held-out fixtures is ≥ 0.9 the heuristic short-circuits, otherwise the classifier escalates to LLM-Assisted MCP every time. The default `heuristic_threshold: 0.9` in `audio-ingest/config.yaml` controls this.

**Status transition on completion:** flip frontmatter `status: Proposed` → `status: Implemented` via `/adr`, regenerate `docs/generated/adr-index.md`.

## Related

- ADR-738 — typed knowledge graph (attendee resolver reads from this; degrades gracefully if unavailable)
- ADR-740 — compiled-truth + timeline pattern (meeting "Merge to timeline" affordance targets this; full wire-up is a follow-up under ADR-740, not in this slate)
- ADR-743 — file-based job ledger (the plan's verification task records its outcome to the ledger via the migration log)
- ADR-748 — triggerable prompt cards (parallel pattern: triggerable: true in frontmatter is the model for `audio-ingest`'s note-writer style)
- ADR-751 — two-verb daily command surface and unified notes zone (load-bearing prereq)
- ADR-753 — article enrichment (sibling in the same slate; independent of this ADR — can ship in either order after ADR-751)
- LLM-Assisted MCP Pattern reference: `docs/references/llm-assisted-mcp-pattern.md`
