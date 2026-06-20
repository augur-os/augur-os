---
description: Curate daily logs to MEMORY.md and distribute to all agent targets
visibility: ops
---

# auto-memory-sync

Detect uncurated daily session logs and sync curated memory to all agent
targets (Claude Code, Cursor, Codex, Copilot, Windsurf).
Daemon-managed (knowledge-enrichment loop, tier 1).

## Scan

Checks `get_memory_dir()/daily/` for recent entries (last 7 days) and compares
modification times against MEMORY.md. Issues a warning when daily logs are
newer than the curated output.

## Fix

Runs `memory_sync.py --sync` to curate daily entries into MEMORY.md, decisions.md,
patterns.md, and preferences.md, then distributes to all agent config targets.
Commits the updated memory files.
