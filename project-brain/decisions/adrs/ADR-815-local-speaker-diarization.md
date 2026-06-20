---
status: Accepted
date: 2026-06-14
deciders:
  - Gur
related:
  - ADR-752
hub: null
tags:
  - audio
  - transcription
  - diarization
superseded_by: null
spec_file: 2026-06-14-audio-diarization-design.md
plan_file: 2026-06-14-audio-diarization.md
---

# ADR-815: Local speaker diarization

> **ADR-815 is an index file.** The substantive design and implementation steps live in the linked spec + plan. This file carries pointers, status, and a one-line decision summary.

## Decision summary

Add native, opt-in speaker diarization to the audio pipeline by porting
`island-io/mila`'s pyannote.audio pipeline (Apache-2.0) as a best-effort overlay
on the whisper provider, and prefer the ivrit.ai `large-v3` Hebrew model when
installed.

## Spec (canonical)

- [`docs/superpowers/specs/2026-06-14-audio-diarization-design.md`](../../../docs/superpowers/specs/2026-06-14-audio-diarization-design.md)

## Plan (canonical, drives `/adr implement`)

- [`docs/superpowers/plans/2026-06-14-audio-diarization.md`](../../../docs/superpowers/plans/2026-06-14-audio-diarization.md)

## Status notes

Accepted 2026-06-14. Extends — does not reverse — ADR-752, which left
`speaker_labels` as a per-call seam and named provider-supplied diarization as a
future addition. Diarization is gated behind an optional `diarization` extra and
gated model weights, so the default install and the lean whisper path are
unchanged. Real-data verification on Hebrew speech requires the user's Hugging
Face token (the pyannote models are gated) and is reported separately.

## Related

- ADR-752 (audio-ingest skill; diarization seam + non-goal it now fills)

## Impact Manifest

```yaml
impact:
  paths_renamed: []
  apis_changed:
    - "transcribe(..., options={'speaker_labels': True}) now overlays pyannote turns when the diarization extra + models are present"
  patterns_deprecated: []
  files_affected:
    - src/lib/extraction/transcription/diarize.py
    - src/lib/extraction/transcription/diarize_setup.py
    - src/lib/extraction/transcription/whisper_cpp.py
    - pyproject.toml
    - NOTICE
```
