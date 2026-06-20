---
name: audio-ingest
x-augur-type: domain
x-augur-group: brain
x-augur-release: mvp
x-augur-license: MIT
description: Audio modality for the /note capture command — detects audio files, transcribes voice memos and meeting recordings via extract-audio, classifies them with a heuristic-or-LLM agent step, and writes structured note cards with attendee resolution for meetings.
x-augur-tab: notes
x-augur-requires-platform: true
x-augur-mcp-tools:
  - audio-classify
  - submit-audio-classify-result
  - audio-ingest-write
  - voice-memo-latest
x-augur-dashboard-pages: []
x-augur-config-file: config.yaml
x-augur-dependencies:
  python:
    - pywhispercpp
---

# audio-ingest

Owns the audio path of `/note`.

## Standard core

Portable workflow guidance for this capability lives in:

- `local-audio-processing/audio-transcription`

This skill remains the Augur adapter. It owns MCP tools, dashboard/Browse/routine
projection, path-helper access, runtime state, and real-data verification for
Augur.

1. `/note <audio>` detects the audio extension and calls `extract-audio`.
2. `extract-audio` returns transcript text, duration, segments, and speaker count.
3. `/note` calls `audio-classify`. The classifier either returns a high-confidence heuristic result or a LLM-Assisted MCP callback payload.
4. `/note` calls `audio-ingest-write` with the transcript, classification, and audio metadata.
5. Meeting notes attempt attendee resolution and expose a future timeline-merge affordance.

## Layering

- L2 policy: `/note` in the ingest skill.
- L3 agent: dispatches `extract-audio` -> `audio-classify` -> `audio-ingest-write`.
- L4 atomic ops: the MCP tools in this skill and document-extractor.

## Configuration

See `config.yaml` for classifier thresholds and attendee-resolution settings.

## When to use

Use `audio-ingest` whenever `/note` receives an audio file — a voice memo or a meeting recording — that should be transcribed, classified, and filed into the brain.

## Examples

```bash
# Capture a voice memo (the /note workflow dispatches into this skill)
/note ~/Downloads/standup.m4a
```

See `scripts/` for the extract → classify → write atomic ops and `config.yaml` for classifier thresholds.
