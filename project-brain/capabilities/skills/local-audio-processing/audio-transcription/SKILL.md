---
name: audio-transcription
description: Use when discovering local audio files, preparing local transcription, reviewing transcript quality, or classifying audio context without relying on a hosted model provider.
---

# Audio Transcription

## Operating Contract

- Work from user-provided local audio files, folders, transcripts, or review reports.
- Use local CLIs and deterministic scripts for audio probing, format checks, and transcript preparation when available.
- Do not call hosted model providers from scripts.
- Leave speaker judgment, context classification, and transcript review decisions to the active AI client.
- Keep platform-specific MCP, dashboard, runtime, and generated-client behavior in an adapter.

## Workflow

1. Inspect the local audio input, media metadata, transcript state, and dependency availability.
2. Produce deterministic local evidence, prepared transcript files, or structured review output.
3. Ask for approval before destructive edits, outbound uploads, or irreversible media conversions.
4. Report missing dependencies directly instead of fabricating transcript output.
