---
description: Synchronize session memory with all agents
visibility: ops
x-augur-export-command: false
---

# /ops-memory

## Memory Sync

Synchronize session memory across all agents. Two-step pipeline: curate daily logs, then sync to all agent memory locations.

## What it does

1. **Cleanup** - Remove temporary files (scratch, drafts, AI temp files) with memory logging
2. **Curate** - Extract decisions/patterns/preferences from daily logs into `get_memory_dir()/MEMORY.md`
3. **Sync** (with `--sync`) - Distribute canonical memory to all enabled client locations

## Usage

```bash
# Curate daily logs into MEMORY.md
python3 .github/scripts/memory_sync.py

# Curate + sync to enabled agents
python3 .github/scripts/memory_sync.py --sync

# CI mode (cleanup + curate, no sync)
python3 .github/scripts/memory_sync.py --ci

# Just cleanup temp files
python3 .github/scripts/memory_sync.py --cleanup-only

# Dry run (no file modifications)
python3 .github/scripts/memory_sync.py --dry-run
```

## Files

| File | Purpose |
|------|---------|
| `get_memory_dir()/daily/*.md` | Raw session event logs |
| `get_memory_dir()/MEMORY.md` | Canonical curated memory |

## Client Memory Targets

| Client | Location | Format |
|-------|----------|--------|
| Claude Code | `~/.claude/projects/.../memory/` | Native (auto-loaded, <=190 lines + topic files) |
| Codex | `~/.codex/augur-memory.md` | Flat Markdown index |
| Gemini | `.gemini/GEMINI.md` + `.gemini/memory/` | Import-style references |
| Cursor | `.cursor/memory/augur-memory.md` | Flat Markdown index |
| Copilot | `.github/copilot-memory.md` | Flat Markdown index |
| Kimi CLI | `~/.kimi/augur-memory.md` | Flat Markdown index |

The resolver treats these as peer client outputs. Claude Code has a different
native load format, but it is not the canonical source of truth.

## How /dev-learn Feeds Memory

`/dev-learn` writes entries to `get_memory_dir()/daily/YYYY-MM-DD.md`. Running `/ops-memory` curates those entries into the canonical `MEMORY.md`, and `--sync` distributes to all agents.

## Related

- ADR-057: Memory System Alignment with Claude Native (historical native-client baseline)
- ADR-429: Multi-Client Memory System
- ADR-028: Two-Layer Memory Architecture (partially superseded by ADR-057)
- `/dev-learn`: Extract learnings from current thread
- `/dev-learn execute`: Capture learnings AND execute actions (TODO markers, fixes, rule updates)
- `/dev-learn refactor`: Analyze recent learnings and suggest priority infrastructure refactors
- `PYTHONPATH=project-brain/capabilities python -m skills.ai.scripts.sync_agents sync agents all`: Alternative sync via ai adapter pattern
