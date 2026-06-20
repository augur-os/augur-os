---
title: Workflow Example 03 - Offline Online Transcription Offload
type: demo-runbook
demo_id: demo_03_offload_transcription_airplane
order: 3
pinned: true
x-augur-note-type: file
_source_type: demo-runbook
tags:
  - example
  - workflow-example
  - airplane
  - offline
  - transcription
  - offload
---

# Workflow Example 03 - Offline Online Transcription Offload

## Agent Prompt

Run the bounded command below so the workflow example uses the Augur-owned short clip,
executes offline and regular transcription routes, restores airplane mode, and
prints one judge-facing result block with the transcript file path and a readable
preview of the transcript body.

```text
uv run aug demo-run-transcription-offload --source-path ~/Projects/Au-vault/voice-memos/2026-06-01-offload-demo-short.m4a
```

Return only the final workflow example output block from the command. Do not run ad hoc
Python, do not discover tool implementations, and do not repeat the Expected
Visible Output preview.

Client rule: the full online branch must run from Gemini. When this command is
launched from Codex or Claude, it proves the offline/local route and returns
`partial-pass` with a stop condition telling the presenter to run the online
branch from Gemini.

The first-time capture flow, only if the Augur-owned clip is missing, is:

```text
/keep ~/Downloads/Offload Demo.m4a
```

Use the returned Augur-owned path for every later step. Do not run transcription against Downloads after `/keep` succeeds.
For this workflow example media, pass `consume_source=true` to the `audio-ingest-write` step so the original Downloads file is moved into Augur storage after transcription succeeds.

For the live judge run, use the Augur-owned short clip:

```text
~/Projects/Au-vault/voice-memos/2026-06-01-offload-demo-short.m4a
```

The full preserved source remains at:

```text
~/Projects/Au-vault/voice-memos/2026-06-01-offload-demo.m4a
```

Then run the transcription example twice:

1. With airplane mode on, transcribe the Augur-owned audio path and report the local route.
2. With airplane mode off, transcribe the same Augur-owned audio path and report the regular route.

## Expected Visible Output

```text
Workflow Example 03 is running: we are proving Augur can offload the same transcription task through different execution routes.
Captured source: Augur-owned short clip.
Offline route: route_mode offline, selected engine faster-whisper, cloud_used false.
Online route: route_mode regular, selected engine gemini-transcribe, cloud_used true when Gemini returns within the 10-second workflow example budget.
Regular fallback: if Gemini exceeds the 10-second workflow example budget, output marks fallback_engine faster-whisper, needs_review true, and cloud_used false.
Client boundary: if active client is not Gemini, the online route is skipped and the workflow example returns partial-pass instead of pretending Gemini was exercised.
Human artifact: Workflow Example 03 proof card and transcript file.
Open in Browse: search "Workflow Example 03 Offline Online Transcription Offload".
Transcript preview: <actual words from the recording, not route metadata>
What to show: proof card first, then the transcript card found by searching "Offload Workflow Example Offline".
Judge takeaway: Augur controls the harness and context while the user experiences one seamless transcription workflow.
Reset proof: workflow example reset completed before the run.
Example status: partial-pass when the regular route uses the disclosed fallback; pass when Gemini completes inside the workflow example budget.
```

## Automatic Reset / Idempotency

Before running live, call `demo-run-reset` with reason `before-demo_03_offload_transcription_airplane`.
Use the Augur-owned short clip as the canonical input for repeated runs:
`~/Projects/Au-vault/voice-memos/2026-06-01-offload-demo-short.m4a`.
Do not recapture or consume `~/Downloads/Offload Demo.m4a` during practice once the Augur-owned source exists. Write transcript and evidence artifacts for the current run, and report the proof-card search phrase plus readable transcript preview.

## Bounded Live Command

```text
uv run aug demo-run-transcription-offload --source-path ~/Projects/Au-vault/voice-memos/2026-06-01-offload-demo-short.m4a
```

Return only the final workflow example output block. Do not replace this command with manual
tool discovery or a custom script.

## Live Flow

1. Click Run and let `demo-run-transcription-offload` execute both routes.
2. Confirm the offline output says `offline`, local Whisper, cloud disabled, and the proof-card search phrase.
3. If active client is not Gemini, stop at the partial-pass client-boundary output and switch to Gemini for the online branch.
4. In Gemini, run the same bounded command and confirm the regular output says `regular`, Gemini-agent transcription when it completes inside the workflow example budget, or a clearly marked local fallback with `needs_review` when it does not.
5. Search Browse for `Workflow Example 03 Offline Online Transcription Offload`, then search `Offload Workflow Example Offline` and read the transcript preview.

## Success Criteria

- The source audio is saved into Augur storage before transcription starts.
- The original Downloads file is no longer the canonical workflow example source after capture.
- No transcript command references `~/Downloads/Offload Demo.m4a`.
- Offline mode shows local Whisper route selection.
- Regular mode shows Gemini-agent route selection when available.
- Non-Gemini clients skip the online branch instead of running a slow headless Gemini CLI proof.
- Any fallback to local Whisper in regular mode is explicitly marked as a fallback risk.
- Transcript and evidence artifacts are written.
- The final output names the proof card and shows actual transcript words from the `## Transcript` body.

## Stop Conditions

- Stop if `/keep` does not return an Augur-owned path.
- Stop if the transcript command still uses the Downloads path.
- Stop if route disclosure is missing from the tool response or evidence.
- Stop if regular mode silently falls back to local Whisper without a warning.
- Stop if the workflow example output does not show a proof card and readable transcript preview.

## Judge Talking Points

- Augur controls the harness: the same user action routes differently based on mode.
- Offline mode stays local and explicit.
- Online mode offloads to the agent-native transcription path.
- The user experience is seamless, but the evidence is inspectable.
