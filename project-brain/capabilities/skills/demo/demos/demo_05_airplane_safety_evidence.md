---
title: Workflow Example 05 - Airplane Safety Evidence
type: demo-runbook
demo_id: demo_05_airplane_safety_evidence
order: 5
pinned: true
x-augur-note-type: file
_source_type: demo-runbook
tags:
  - example
  - workflow-example
  - airplane
  - local-first
  - safety
  - evidence
---

# Workflow Example 05 - Airplane Safety Evidence

## Agent Prompt

Run the bounded command below so the workflow example resets, snapshots airplane status,
runs the local-only smoke proof, checks the final status, and prints one
judge-facing result block.

```bash
uv run aug demo-run-airplane-safety
```

Return only the final workflow example output block from the command. Do not run ad hoc
Python, do not discover tool implementations, and do not repeat the Expected
Visible Output preview.

The wrapper uses these underlying commands for the live judge run:

```bash
uv run aug toggle-airplane-mode --action status
uv run aug demo-smoke --airplane on --require-cloud false
uv run aug toggle-airplane-mode --action status
```

Do not discover tool names, use `--action query`, or launch a local chat process during the workflow example. Read the JSON output directly and report `success`, `cloud_calls`, `files_indexed`, local policy, selected local engines, evidence pin, and restored airplane preference.

Preferred proof points:

- local backend readiness,
- selected local engines,
- zero cloud calls for offline proof,
- restored airplane preference after the run,
- explicit refusal or unavailable status when memory is insufficient for unsafe local chat launch.

## Expected Visible Output

```text
Workflow Example 05 is running: we are proving offline execution has safety gates and evidence.
Airplane proof: smoke check ran with airplane mode on and cloud disallowed.
Cloud calls: 0.
Local route: OpenVINO, faster-whisper, Ollama, and local backend readiness are visible before launch.
Safety guard: unsafe local launches are reported as unavailable instead of freezing the Mac.
Evidence: the saved workflow example evidence card is visible as a normal Browse card.
Human artifact: Workflow Example 05 proof card.
Open in Browse: search "Workflow Example 05 Local Only Safety Evidence".
What to show: Cloud calls: 0; files indexed: <count>; local engines visible before launch.
Reset proof: workflow example reset completed before the run.
Example status: pass.
```

## Automatic Reset / Idempotency

Before running live, call `demo-run-reset` with reason `before-demo_05_airplane_safety_evidence`.
At the start, snapshot the current airplane preference with `uv run aug toggle-airplane-mode --action status`. Force the offline proof with cloud disallowed by running `uv run aug demo-smoke --airplane on --require-cloud false`, then verify the final preference with `uv run aug toggle-airplane-mode --action status` before returning the final answer. The wrapper command is `uv run aug demo-run-airplane-safety`. If restore fails, return `partial-pass` or `fail` instead of claiming the workflow example passed.

## Bounded Live Command

```bash
uv run aug demo-run-airplane-safety
```

Return only the final workflow example output block. Do not replace this command with tool
discovery or a custom script when preparing the judge-facing answer.

## Live Flow

1. Click Run and let `demo-run-airplane-safety` execute.
2. Show `cloud_calls: 0`, `files_indexed`, and `readiness.capabilities.policy.cloud_escalation_allowed: false`.
3. Show local engine details from readiness: OpenVINO devices, faster-whisper model, Ollama models, and local backend readiness.
4. Search Browse for `Workflow Example 05 Local Only Safety Evidence` and open the proof card.
5. Show the saved evidence card from `evidence_pin` if the judge asks for the raw run record.
6. End on the `Human artifact` block: proof card and the `Cloud calls: 0` proof.

## Success Criteria

- Offline proof reports zero cloud calls.
- Local engine decisions are visible.
- The run restores the previous airplane preference.
- Memory guard behavior is visible when launch is unsafe.
- Evidence appears as a normal pinned Browse card.
- The output names the proof-card search phrase to open.

## Stop Conditions

- Stop if cloud calls are nonzero.
- Stop if airplane preference is left changed after the run.
- Stop if readiness says launch is unsafe and the workflow example tries to launch anyway.
- Stop if the final output does not include a Browse-searchable proof card.

## Judge Talking Points

- Augur is a control layer for the AI PC, not only a prompt library.
- Local-first behavior has safety gates and evidence.
- The system can refuse unsafe local launches instead of freezing the laptop.
