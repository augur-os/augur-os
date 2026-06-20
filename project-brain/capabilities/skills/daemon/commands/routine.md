---
description: Run the ADR-755 routine orchestrator CLI.
visibility: dev
x-augur-export-command: false
---

# /routine

`aug routine` is the deterministic and session-bound control surface for the
ADR-755 routine orchestrator. It keeps no hidden model call inside Augur:
scan-only runs pure Python scan/mechanical phases, while orchestrate requires
an active AI-client session for native subagent dispatch.

## Usage

```text
aug routine scan-only --loop <name>
aug routine orchestrate --loop <name>
aug routine pending-escalations --show
aug routine pending-escalations --clear-stale
```

## Verbs

- `scan-only --loop <name>` scans one configured auto-loop and applies only
  deterministic mechanical fixes. It is safe for sessionless automation and
  prints the findings, counts, applied fixes, deferred findings, and job phases
  as JSON.
- `orchestrate --loop <name>` runs the same scan/mechanical path, then dispatches
  local-semantic buckets through the active client's native subagent surface. It
  refuses to run when no supported AI-client session is detected.
- `pending-escalations --show` reads
  `get_runtime_dir()/jobs/_escalations/pending.jsonl` and prints the fresh
  queued semantic findings without mutating the queue.
- `pending-escalations --clear-stale` compacts the queue by dropping TTL-expired
  or malformed entries, then prints the remaining entries and compaction events.

## Notes

- Use `/routines` for the full adaptive-loop management workflow.
- Use `aug routine scan-only --loop testing` as the session-agnostic smoke test
  before relying on session-bound orchestration.
