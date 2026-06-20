---
status: Implemented
date: '2026-02-08'
deciders:
- Augur team
related:
- ADR-028 (Two-Layer Memory)
- ADR-029 (Adaptive Agent Rules)
hub: null
tags:
- memory
- system
- alignment
- claude
- native
superseded_by: null
---

# ADR-057: Memory System Alignment with Claude Native

**Supersedes**: ADR-028 (partial — replaces curation pipeline, keeps daily logs)

## Context

Claude Code shipped native auto memory — it writes `MEMORY.md` + topic files at `~/.claude/projects/{project}/memory/`, auto-loading the first 200 lines at session start. Augur built a custom memory system before this existed (`data/core/memory/`): daily logs, curation pipeline (`memory_sync.py` — 625 lines), confidence-scored rule promotion (`LEARNED_RULES.md`), and user profile generation (`HUMAN_API.md`).

### Audit Results

| Component | Status | Finding |
|-----------|--------|---------|
| LEARNED_RULES.md | Dead | Zero rules promoted in 4+ days. Threshold (conf ≥0.8, occ ≥5) unreachable at 6.2 entries/day |
| HUMAN_API.md | Orphaned | Generated but never consumed by any active code path |
| Confidence scoring | Broken | Needs ~3 exact text matches via word overlap; never triggers with diverse entries |
| Augur MEMORY.md | Stale | Last curated 2026-02-04 (4 days ago), only 85 lines |
| Claude native MEMORY.md | Active | 76 lines, more current, auto-loaded at every session start |
| Daily logs + post-commit hook | Working | 5 days of logs, 31 entries total |

### Multi-Agent Requirement

Augur supports 8+ agents via the ai-bridge adapter pattern (`sync_agents.py`): Claude Code, Kimi, Codex, Cursor, Windsurf, Copilot, OpenCode, Gemini, Antigravity. Memory must work for ALL agents, not just Claude. The ai-bridge already syncs rules/workflows/skills per-adapter — memory should follow the same pattern.

## Decision

### 1. Adopt Claude's Memory Concepts

Align Augur's memory to Claude's simpler, more effective design:
- **Single MEMORY.md** as runtime index (not a curation target for a scoring pipeline)
- **Topic files** for overflow content (patterns.md, preferences.md, recent-adrs.md)
- **200-line budget** for the main file (190 effective, 10-line margin)
- **Zero-friction writes** (Claude's "remember that..." + Augur's `/learn`)

### 2. Multi-Agent Memory via Adapter Pattern

Follow the ai-bridge `sync_agents.py` pattern — each agent gets memory in its native format:

| Agent | Memory Location | Format |
|-------|----------------|--------|
| Claude Code | `~/.claude/projects/.../memory/` | Native: MEMORY.md + topic files (auto-loaded) |
| Kimi CLI | `~/.kimi/augur-memory.md` | Markdown (injected as context preamble) |
| Cursor | `.cursor/memory/` | Cursor-compatible memory files |
| Codex | `~/.codex/augur-memory.md` | Markdown |
| Copilot | `.github/copilot-memory.md` | Markdown section in copilot instructions |
| Others | Per-adapter location | Adapter-specific format |

### 3. Canonical Source Stays in Repo

`data/core/memory/MEMORY.md` remains the git-tracked canonical memory. The sync pipeline compiles it into per-agent formats. This preserves:
- Version control (memory changes are auditable)
- Multi-agent distribution (one source, many targets)
- Backup (git-tracked, not lost if `~/.claude/` is cleared)

### 4. Drop Dead Infrastructure

| Drop | Reason | Archive Location |
|------|--------|-----------------|
| `LearnedPattern` + confidence scoring | Zero promotions, mathematically broken | Deleted from code |
| `LEARNED_RULES.md` | Empty, never reached threshold | `docs/archive/memory-learned-rules.md` |
| `HUMAN_API.md` | Generated but never consumed | `docs/archive/memory-human-api.md` |
| `apply_rules_to_agent_rules()` | No rules to apply | Deleted from code |
| `--apply`, `--review`, `--profile` flags | No longer needed | Deleted from code |

### 5. Simplified Pipeline

**Before** (5 steps, 625 lines):
```
cleanup → curate → analyze → propose rules → generate profile → (optional: apply rules)
```

**After** (2 steps, ~200 lines):
```
curate daily logs → sync to all agents
```

### Architecture

```
Input:
  post-commit hook ──► data/core/memory/daily/*.md
  /learn           ──► data/core/memory/daily/*.md

Pipeline (memory_sync.py):
  Step 1: Curate daily logs → data/core/memory/MEMORY.md
  Step 2: Sync to agents (per-adapter via sync_agents.py pattern)

Per-Agent Sync:
  Claude Code → compile to ~/.claude/.../memory/ (native format, ≤190 lines + topics)
  Kimi/Codex  → write to ~/.{agent}/augur-memory.md (context injection)
  Cursor      → write to .cursor/memory/ (IDE format)
  Others      → per-adapter location
```

## Consequences

### Positive
- Memory auto-loads in Claude Code sessions (zero friction)
- All 8+ agents get memory in their native format
- 300+ lines of dead code removed from memory_sync.py
- Follows proven ai-bridge adapter pattern
- Canonical memory stays git-tracked and auditable

### Negative
- Confidence-scored rule promotion is gone (can reintroduce later if entry velocity increases)
- HUMAN_API.md profile generation gone (was never used anyway)

### Neutral
- Daily logs and post-commit hook unchanged
- `/learn` workflow unchanged (still writes to daily logs)
- `data/core/memory/MEMORY.md` keeps its role as canonical source

## Alternatives Considered

### Alternative 1: Keep Both Systems Running in Parallel
Bridge them without changing either. Rejected: maintains two overlapping systems, doubles maintenance, Augur's pipeline continues producing zero value.

### Alternative 2: Eliminate Augur's Memory Entirely
Move everything to Claude native. Rejected: loses multi-agent support, git-tracked history, and the working daily log pipeline.

### Alternative 3: Fix the Scoring Pipeline
Lower thresholds, improve similar_text(), make it work. Rejected: the fundamental issue is entry velocity (6/day), not thresholds. Even at lower thresholds, the system produces no actionable output.

## References

- ADR-028: Two-Layer Memory Architecture (partially superseded)
- ADR-029: Adaptive Agent Rules
- Claude Code auto memory: `~/.claude/projects/{project}/memory/`
- ai-bridge adapter pattern: `plugins/ai/skills/ai_bridge/scripts/sync_agents.py`
- Current memory pipeline: `.github/scripts/memory_sync.py`

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.

You are implementing **ADR-057: Memory System Alignment with Claude Native**.

Read the full ADR: `docs/decisions/ADR-057-memory-system-alignment.md`

### Offload Protocol (ADR-054)

Before dispatching each step, check if it can be offloaded to a cheap CLI:

1. Read offload config: `cat config/system/llm.yaml` → look for `offload:` section
2. If `offload.enabled: true` AND the step's tier is `low`:
   ```bash
   python3 plugins/orchestration/skills/executor/scripts/offload_dispatcher.py \
     --task "STEP DESCRIPTION" \
     --files "TARGET_FILE_1,TARGET_FILE_2" \
     --context-files "REFERENCE_FILE_FOR_PATTERNS" \
     --work-dir $(pwd)
   ```
3. Review the JSON output — check `success`, `files_changed`, and `diff` fields
4. Record the verdict:
   - Accept: `python3 plugins/orchestration/skills/executor/scripts/offload_dispatcher.py --record-verdict accept`
   - Fix: `python3 plugins/orchestration/skills/executor/scripts/offload_dispatcher.py --record-verdict fix`
   - Escalate: `python3 plugins/orchestration/skills/executor/scripts/offload_dispatcher.py --record-verdict escalate`
5. If `offload.enabled: false` OR tier is `medium`/`high` → do the step yourself

### Phase 1: Archive Dead Infrastructure
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | low | Move LEARNED_RULES.md to docs/archive/memory-learned-rules.md | `data/core/memory/LEARNED_RULES.md` → `docs/archive/memory-learned-rules.md` |
| 1.2 | developer | low | Move HUMAN_API.md to docs/archive/memory-human-api.md | `data/core/memory/HUMAN_API.md` → `docs/archive/memory-human-api.md` |
| 1.3 | developer | low | Add archive header to data/core/memory/MEMORY.md noting it's the canonical git-tracked source | `data/core/memory/MEMORY.md` |

### Phase 2: Simplify memory_sync.py
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | medium | Remove LearnedPattern, confidence scoring, analyze/generate/apply functions, HUMAN_API generation, similar_text helper, --apply/--review/--profile flags. Keep cleanup_temp_files, curate_daily_logs, update_memory_file, DAILY_DIR/MEMORY_FILE constants. Target: ~100 lines remaining. | `.github/scripts/memory_sync.py` |
| 2.2 | developer | medium | Add get_claude_native_memory_dir() — resolve ~/.claude/projects/-{path}/memory/, return None if missing | `.github/scripts/memory_sync.py` |
| 2.3 | developer | medium | Add compile_claude_native(memory_content) — read canonical MEMORY.md, compile ≤190-line version + topic files (patterns.md, preferences.md, recent-adrs.md), write atomically to Claude native dir | `.github/scripts/memory_sync.py` |
| 2.4 | developer | medium | Add sync_memory_to_agents() — call compile_claude_native for Claude, write augur-memory.md for CLI agents. Add --sync flag. Update main() pipeline to: curate → sync | `.github/scripts/memory_sync.py` |

### Phase 3: Add memory sync to sync_agents.py
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | developer | medium | Add sync_memory() method to BaseAdapter in sync_agents.py. Implement ClaudeCodeAdapter.sync_memory() calling compile_claude_native from memory_sync. Implement basic sync_memory() for CursorAdapter, KimiAdapter, CodexAdapter (write augur-memory.md to agent-specific location). | `plugins/ai/skills/ai_bridge/scripts/sync_agents.py` |

### Phase 4: Update Workflows and Docs
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 4.1 | developer | low | Update memory-sync.md — remove LEARNED_RULES/HUMAN_API/rule promotion references, document 2-step pipeline (curate + sync), add --sync flag | `data/ai-bridge/agent-workflows/memory-sync.md` |
| 4.2 | developer | low | Update learn.md — add note that /learn feeds all agents via /memory-sync | `data/ai-bridge/agent-workflows/learn.md` |
| 4.3 | developer | low | Remove "Learned Rules (Auto-Generated)" section from agent-rules.md, add note about /memory-sync | `docs/agent-rules.md` |

### Final Phase: Verification
**Strategy**: PIPELINE

| Step | Agent | Tier | Task |
|------|-------|------|------|
| V.1 | validator | low | Run `python3 .github/scripts/memory_sync.py` — pipeline runs clean |
| V.2 | validator | low | Run `python3 .github/scripts/memory_sync.py --sync` — syncs to Claude native dir |
| V.3 | validator | low | Verify ~/.claude/projects/-Users-<user>-Projects-Augur/memory/MEMORY.md exists and is ≤190 lines |
| V.4 | validator | low | Run `pytest tests/src/` — no regressions |
| V.5 | validator | low | Verify archived files exist in docs/archive/ |

### Completion Criteria
- [ ] LEARNED_RULES.md and HUMAN_API.md archived to docs/archive/
- [ ] memory_sync.py simplified (625→~200 lines)
- [ ] Claude native memory compiled from canonical source
- [ ] sync_agents.py has sync_memory() per adapter
- [ ] Workflow docs updated (memory-sync.md, learn.md)
- [ ] agent-rules.md Learned Rules section removed
- [ ] All tests pass
