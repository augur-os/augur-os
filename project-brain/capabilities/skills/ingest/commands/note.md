---
description: "Retained source/legacy alias for capture into your brain. /note is no longer exported to primary AI clients; use /keep <url|file|audio|image|folder|thought> instead. Agent picks the dispatcher; atomic ops persist."
visibility: core
x-augur-export-command: false
---

> **Retired primary surface:** `/note` is no longer exported to primary AI
> clients. Use `/keep <url|file|audio|image|folder|thought>` instead.

# /note Command Execution

This command sits at **L2 POLICY** in the [surface decision matrix](../../../../docs/references/surface-decision-matrix.md). It tells the agent what to do based on the argument shape. The agent (L3) picks the right atomic op. Atomic ops (L4 — `save-url-source`, `save-prompt`, `inbox-consume-folder`, `extract-audio` from ADR-752, etc.) only persist.

The argument-after-slash is in `ARGUMENTS`. Parse it before doing anything else.
If `--to <brain-id>` is present, pass that destination through to the atomic
write helper. If it is absent, write routing is deterministic: active project
brain from cwd first, then personal fallback.

## Dispatch

1. If `ARGUMENTS` is `--help` or `-h`: print the dispatch table from frontmatter `description` and stop.
2. If `ARGUMENTS` is empty: open the interactive Note picker when a dashboard surface is available; otherwise prompt the user for one of url/file/folder/thought.
3. Read flags first. Strip and retain optional `--to <brain-id>` before type
   dispatch. If `--thought`, route to **Thought** below. If `--as prompt`, route
   to **Prompt**. If `--memo` or `--meeting`, route to **Audio** with a forced
   sub-type — and if no path argument is given alongside `--memo`, route to
   **Voice-Memo Auto-Grab** (below) first to discover and copy the latest macOS
   Voice Memos recording. If `--from email`, route to **Email-drop**. If
   `--trigger <slug>`, route to **Trigger saved prompt**.
4. Otherwise dispatch by argument shape using `project-brain/capabilities/skills/ingest/scripts/note_type.py:detect_note_type_from_arg`:
   - `url` -> **URL**
   - `audio` -> **Audio**
   - `image` -> **Image**
   - `file` -> **File**
   - `folder` -> **Folder**
   - `thought` -> **Thought**

## URL

The agent classifies and validates the URL and decides whether the content is worth saving (skip paywalled stubs, error pages, or duplicates of something already noted). When it is worth saving, run the **one-shot capture** and report only the result:

```bash
./scripts/aug note-url --url "<url>" --tags '["tag-a","tag-b"]'
```

`note-url` is a CLI/agent workflow that composes the two atomic ops — `url-extract` (fetch full prose) and `save-url-source` (persist) — so the whole capture is a single command. It writes under the resolved brain destination notes root with `x-augur-note-type: url`, is idempotent on content hash, and returns `{path, title, summary, word_count, deduplicated, canonical_url, brain}` when routed.

**Report only that result**: the saved title, the one-line `summary`, the `path`, and whether it `deduplicated`. Do NOT narrate tool loading, file reads, source inspection, or any other internal steps — `note-url` exists precisely so there is nothing to narrate. If `note-url` returns `success: false`, surface the error and stop; never write a stub note.

Callers without an AI session (dashboard, daemon) still compose `url-extract` + `save-url-source` directly — `note-url` is the agent/CLI convenience only, not a dashboard/MCP atomic op. Browser-first fetch follows ADR-750; all fetch and dedupe contracts are unchanged.

## File

Call atomic MCP tool `inbox-consume-folder` in single-file mode against the path, or prefer a per-file MCP tool if one exists. Frontmatter gets `x-augur-note-type: file`. Output is one note in `<vault>/notes/`.

## Audio

Live in ADR-752.

1. Call atomic MCP tool `extract-audio` with the audio file path. Read the result: `text`, `segments`, `duration_seconds`, `speaker_count`, `provider`, `provider_version`.
2. Resolve the audio sub-type. If the user passed `--memo`, force `note_type = "voice-memo"`. If the user passed `--meeting`, force `note_type = "meeting"`. Otherwise:
   - Call atomic MCP tool `audio-classify` with `transcript_text`, `duration_seconds`, and `speaker_count`.
   - If the response includes `needs_llm: true`, that is the LLM-Assisted MCP Pattern callback. Read `instructions` and `transcript_preview`, decide `type` in {`voice-memo`, `meeting`}, then call `submit-audio-classify-result` with `{type_, confidence, reasoning}`. Use that result.
   - Otherwise the response is the heuristic result directly. Use it.
3. Derive a short human title. Use the audio filename stem if no other context is available; for meetings, prefer the first speaker turn or an explicit topic sentence from the transcript if present.
4. Persist via atomic MCP tool `audio-ingest-write` with `audio_path`, `note_type`, `title`, `transcript_text`, `segments_json`, `duration_seconds`, `provider`, and `provider_version`. The tool stores an existing local audio file under the selected vault (`voice-memos/` or `meetings/`), writes the note under `<vault>/notes/`, resolves attendees for meetings, and returns the resolved note path plus the Augur-owned `audio_path`. If the user explicitly asks not to leave the source file behind, pass `consume_source=true` so the store step moves the file after successful transcription.
5. Report the resolved note path and Augur-owned audio path. If the note type is `meeting` and `attendee_slugs` is non-empty, surface them. Suggest the "Merge to timeline" action if the meeting transcript contains decisions or action items.

Errors: if `extract-audio` fails because the audio is corrupt or the provider is unavailable, surface the error to the user. Do not write a stub note.

## Voice-Memo Auto-Grab

Triggered when the user runs `/note --memo` (or `/note memo`) with no path argument. The user wants the most recent macOS Voice Memos recording ingested without manually exporting it.

1. Call atomic MCP tool `voice-memo-latest` with `copy_to` set to the registered Voice Memos inbox folder (the lane named `voice-memos` returned by `inbox-folders`, falling back to `~/Projects/Au-docs/inbox/voice-memos`). The tool reads the macOS Voice Memos sandboxed container and returns `{success, source_path, copied_to, filename, modified_at, size_bytes}` or `{success: false, error, hint}` when the container is TCC-blocked.
2. If `success: false` with the FDA hint, surface the hint to the user verbatim and stop. The user must grant Full Disk Access to their Terminal (or the Python interpreter that runs Augur) in System Settings -> Privacy & Security before this branch can work.
3. If `success: true`, set `audio_path = copied_to` and continue with the **Audio** flow above. The forced sub-type stays `voice-memo` because the original `--memo` flag is still in effect. The agent should also surface `source_path` and `filename` in the final note-report so the user knows which recording was ingested.

## Image

Call `document-extractor` for OCR and caption, then write a note with `x-augur-note-type: image`. Until the image-extraction MCP tool ships, surface the gap to the user. Do not write a stub note.

## Folder

Same as `/ingest folder <path>` before ADR-751: scan by default, consume only when the user explicitly asks for consume semantics.

## Thought

The user typed freeform text. Persist it via `project-brain/capabilities/skills/ingest/scripts/note_capture.py:save_thought_note`, passing `to=<brain-id>` when supplied and the current cwd so the helper can resolve project-brain vs personal fallback. It writes a thought note under the selected destination's notes root with `x-augur-note-type: thought`, then refreshes Browse's `vault` index for new writes. Surface the returned `brain` and `browse_index` status; if the index reports failure, say the note was saved but Browse refresh failed.

If the freeform text looks like a reusable prompt — instruction-shaped, contains `{{placeholder}}`, or opens with system/role framing — ask before persisting:

> "This looks like a reusable prompt rather than a thought. Save it as a Prompt card (triggerable)?"

If the user confirms, route to **Prompt**. Otherwise persist as `thought`.

## Prompt

`--as prompt` is the explicit override. Call atomic MCP tool `save-prompt`, passing `to=<brain-id>` when supplied and cwd otherwise. Frontmatter gets `x-augur-note-type: prompt` and `x-augur-prompt-triggerable: true`. Output is one note in the resolved brain destination notes root.

## Trigger saved prompt

`--trigger <slug>` runs a saved prompt with current context. Read the prompt note from `<vault>/notes/`, fill any `{{placeholder}}` tokens by prompting the user, then dispatch the filled body to the active AI client. See ADR-748 for trigger semantics.

## Email-drop

`--from email` calls the existing `email-drop-consume-source` atomic MCP tool. Output is one or more notes in `<vault>/notes/` per consumed message. Email-drop semantics are otherwise unchanged.

## Layering invariants for this command

- The agent decides which fetcher to use for URL paths.
- Atomic ops write to the resolved brain destination notes root; never construct note paths manually in the command policy.
- Deduplication is content-hash based. Re-noting the same content returns `deduplicated: true`; surface that as "already saved".
- Vendor neutrality: refer to capability categories, not specific AI-client tool names.
- Browser-first fetch for URLs follows ADR-750.
- Current primary-surface minimalism: `/keep` is the canonical capture and artifact-persistence verb, and `/ask` is the reflective output verb. `/note` remains a retained legacy source for the capture policy, not a primary exported command.
