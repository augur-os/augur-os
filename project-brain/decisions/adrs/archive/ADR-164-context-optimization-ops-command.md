---
status: Implemented
date: '2026-02-26'
deciders:
- Gur Sannikov
related:
- ADR-057 (memory pipeline)
- ADR-074 (context audit sessions)
- ADR-161 (chat context injection optimization)
- ADR-059 (focus-context)
- ADR-030 (context switch algorithm)
hub: null
tags:
- context
- optimization
- ops
- command
- memory
superseded_by: null
---

# ADR-164: Context Optimization Ops Command and Memory Retention Policy

## Context

### How Claude Code memory actually loads

Claude Code's native auto-memory loads **only the first 200 lines of MEMORY.md** at session start. Topic files (`decisions.md`, `patterns.md`, etc.) are **not auto-loaded** — Claude reads them on-demand during a session when it decides to follow a reference link. This means the true startup cost is:

| File | Lines | Tokens (~4/line) | Loaded at |
|------|-------|-------------------|-----------|
| `CLAUDE.md` (project instructions) | 90 | ~360 | Startup (always) |
| `MEMORY.md` (first 200 lines) | 190 | ~760 | Startup (always) |
| `decisions.md` (428 lines) | 428 | ~1,712 | On-demand |
| `patterns.md` (131 lines) | 131 | ~524 | On-demand |
| `preferences.md` (26 lines) | 26 | ~104 | On-demand |
| `structure-audit.md` (195 lines) | 195 | ~780 | On-demand |
| `recent-adrs.md` (27 lines) | 27 | ~108 | On-demand |

Startup is ~280 lines / ~1,120 tokens — manageable. The real problems are quality, staleness, and a dual-writer conflict.

### Pain points

1. **Dual-writer conflict: `memory_sync.py` vs Claude Code native memory.** Two systems write to the same directory (`~/.claude/projects/.../memory/`):
   - **Claude Code** writes when the user says "remember this" — adds entries to MEMORY.md directly
   - **`memory_sync.py --sync`** overwrites the entire directory from the canonical git-tracked `docs/memory/MEMORY.md`
   - **Result**: any memory Claude writes natively gets wiped on the next sync. The user thinks Claude remembered something, but it's gone after `memory_sync.py` runs.

2. **MEMORY.md Decisions = git commit log, not curated knowledge.** The `## Decisions` section contains ~180 entries, ~60-70% of which are `chore(sync): regenerate IDE configs` noise. These are git log messages, not architectural decisions. The section overflows into `decisions.md` (428 lines / 51KB), which Claude may read on-demand — wasting mid-session context on commit noise.

3. **No retention/pruning policy.** `memory_sync.py` appends new entries forever (`days_back=7` only limits daily log reading, not eviction). `decisions.md` grows ~5-10 entries/day with no archive or age-out.

4. **Stale topic files with actively wrong content.** `structure-audit.md` (9KB, 195 lines) describes paths from the pre-ADR-126 layout (`data/plugins/crew/`, `plugins/core/`, `data/plugins/services/`) — all deleted months ago. If any agent reads it for orientation, it gets steered to nonexistent directories. `recent-adrs.md` covers ADR-042–057, all implemented months ago.

5. **Overflow files grow unbounded.** The 190-line split logic keeps MEMORY.md short but creates unbounded topic files. When Claude follows a reference link to `decisions.md`, it loads 428 lines of mostly noise into the active context.

6. **Weak deduplication.** The 100-char prefix check in `dedup_entries()` lets duplicates slip through when entries share a long common prefix.

7. **No ops command for context self-optimization.** Existing commands audit *agent profiles* (`/orch-context-audit`) or *session usage* (`/context-save`), but nothing analyzes the *memory files themselves* — their quality, staleness, or the dual-writer conflict.

## Decision

### 1. Resolve dual-writer conflict with merge-before-overwrite

**Problem**: `memory_sync.py --sync` does a blind overwrite of the Claude native memory dir. Any entries Claude Code wrote natively (via "remember this") are destroyed.

**Solution**: Before overwriting, `compile_claude_native()` reads the existing native MEMORY.md, diffs it against the canonical source, and preserves entries that exist only in the native copy (i.e., entries Claude added directly).

```python
def merge_native_entries(canonical: str, native: str) -> str:
    """Merge Claude-native entries into canonical before overwrite."""
    canonical_entries = extract_entries(canonical)
    native_entries = extract_entries(native)
    # Entries in native but not in canonical = Claude-written
    claude_written = [e for e in native_entries
                      if normalize_entry(e) not in
                      {normalize_entry(c) for c in canonical_entries}]
    if claude_written:
        # Prepend Claude-written entries to Decisions section
        # with a marker so they're visible during curation
        for entry in claude_written:
            canonical = inject_entry(canonical, "Decisions",
                                     f"[claude-native] {entry}")
    return canonical
```

**Flow change in `compile_claude_native()`:**
1. Read existing native MEMORY.md (if exists)
2. Extract entries unique to native (Claude-written)
3. Inject them into canonical content with `[claude-native]` prefix
4. Write merged result
5. Also write Claude-native entries back to `docs/memory/MEMORY.md` so they enter the git-tracked canonical source and survive future syncs

The `[claude-native]` prefix lets the curation pipeline (`/learn --sync`) surface these for human review. After review, the prefix is stripped and they become normal canonical entries.

### 2. New `/ops-context` command

Create an ops slash command that analyzes and optimizes the always-loaded context (CLAUDE.md + MEMORY.md + topic files).

**Source**: `plugins/ai/skills/ai_bridge/augur/data/agent-workflows/ops-context.md`

**What it does:**

1. **Measure** — Read CLAUDE.md, MEMORY.md, and all topic files in the Claude native memory dir. Report: line counts, estimated tokens, percentage of 200K budget consumed before first user message.

2. **Classify decisions** — For each entry in `## Decisions` and `decisions.md`, classify as:
   - `chore` — sync/regenerate commits (noise, safe to archive)
   - `fix` — bug fixes (keep 30 days, then archive)
   - `feat` — features/ADRs (keep 60 days, then archive)
   - `pattern` — architectural insights with no date expiry (keep forever)

3. **Detect stale topic files** — For each `.md` file in the memory dir (excluding MEMORY.md), check:
   - Last modified date (>30 days = stale candidate)
   - Path references (`data/plugins/`, `plugins/core/`, etc.) cross-referenced against the actual filesystem — if >50% of referenced paths don't exist, flag as **harmful stale**

4. **Report** — Output a structured analysis:
   ```
   Context Budget Report
   ─────────────────────
   CLAUDE.md:          90 lines  (~360 tokens)
   MEMORY.md:         190 lines  (~760 tokens)
   decisions.md:      428 lines  (~1,712 tokens)
   patterns.md:       131 lines  (~524 tokens)
   preferences.md:     26 lines  (~104 tokens)
   structure-audit.md: 195 lines (~780 tokens) ⚠ STALE (87% dead paths)
   recent-adrs.md:     27 lines  (~108 tokens) ⚠ STALE (30+ days)
   ─────────────────────
   Total:            1,087 lines (~4,348 tokens)
   Budget used before first message: ~2.2%

   Recommendations:
   - Delete structure-audit.md (harmful stale, 87% dead paths)
   - Delete recent-adrs.md (all entries >30 days old)
   - Archive 120 chore(sync) entries from decisions.md → decisions-archive.md
   - Archive 35 fix() entries older than 30 days
   - Net savings: ~640 lines (~2,560 tokens, 59% reduction)
   ```

5. **Apply** (with confirmation) — Execute the recommended cleanups:
   - Delete stale topic files
   - Move archived entries to `decisions-archive.md` (not loaded by Claude)
   - Recompile MEMORY.md via `memory_sync.py --sync`

### 3. Memory retention policy in `memory_sync.py`

Add retention rules to the curation pipeline so context stays lean automatically:

| Category | Pattern | Retention | Action after expiry |
|----------|---------|-----------|-------------------|
| `chore` | `chore(sync):`, `chore(cleanup):` | 7 days | Archive to `decisions-archive.md` |
| `fix` | `fix(...)` | 30 days | Archive |
| `feat` | `feat(...)`, `docs(adr):` | 60 days | Archive |
| `pattern` | Entries without commit hash (architectural insights) | Forever | Keep |
| `preference` | All preferences | Forever | Keep |

**Implementation in `curate_daily_logs()`:**
- After appending new entries, scan existing entries for age-out
- Move expired entries to a non-referenced archive file
- Keep the archive for historical lookup but don't link from MEMORY.md

### 4. Noise filter for `chore(sync)` entries

Add a skip list to `update_memory_file()`:

```python
NOISE_PATTERNS = [
    r"^chore\(sync\): regenerate",
    r"^chore\(sync\): update generated",
]
```

Entries matching these patterns are never written to MEMORY.md — they go directly to the archive. They carry zero durable knowledge (they're mechanical outputs of `sync_agents.py`).

### 5. Overflow file budgets

Add a `TOPIC_FILE_LINE_BUDGET = 200` constant. When a topic file exceeds this limit, the oldest entries are archived. This prevents `decisions.md` from growing unbounded.

### 6. Stale topic file cleanup

Delete immediately:
- `structure-audit.md` — pre-ADR-126 paths, 87% dead references, actively misleading
- `recent-adrs.md` — ADR-042–057, all months-old implementations

### 7. Stronger deduplication

Replace the 100-char prefix check with full-text comparison after normalizing whitespace and stripping commit hashes:

```python
def normalize_entry(text: str) -> str:
    """Normalize for dedup — strip hash, collapse whitespace."""
    text = re.sub(r'\([a-f0-9]{8,},?\s*\d+\s*files?\)', '', text)
    return ' '.join(text.split()).strip()
```

## Consequences

**Positive:**
- "Remember this" actually persists — Claude-native entries survive sync cycles via merge-before-overwrite
- On-demand topic files are cleaner — `decisions.md` shrinks from 428 to ~100 lines after noise/retention purge
- Stale/misleading memory files eliminated — agents won't be steered to dead paths
- Automatic retention prevents unbounded growth going forward
- `/ops-context` provides visibility into what's consuming the context budget
- Noise filter stops `chore(sync)` from ever entering memory
- `[claude-native]` marker creates a review pipeline for user-spoken memories to enter the canonical source

**Negative:**
- Archived entries are no longer instantly available to agents (must grep `decisions-archive.md` manually)
- Retention policy requires one-time migration of existing entries
- Merge-before-overwrite adds complexity to `compile_claude_native()` — must handle format differences between Claude-written and Augur-written entries

**Neutral:**
- CLAUDE.md itself is already lean (~90 lines) and needs no changes
- Startup context (MEMORY.md first 200 lines) is already within budget — the improvements target on-demand file quality and the dual-writer conflict
- The memory sync pipeline architecture (ADR-057) stays the same; we're adding merge + pruning to the existing flow

## Implementation Order

```
Phase 1: Immediate cleanup (manual, no code changes)
├── Step 1: Delete structure-audit.md from Claude native memory dir
└── Step 2: Delete recent-adrs.md from Claude native memory dir

Phase 2: Dual-writer resolution (memory_sync.py)
├── Step 3: Add merge_native_entries() to compile_claude_native()
└── Step 4: Add write-back of [claude-native] entries to docs/memory/MEMORY.md

Phase 3: Memory retention policy (memory_sync.py changes)
├── Step 5: Add NOISE_PATTERNS skip list to update_memory_file()
├── Step 6: Add retention policy with age-out logic to curate_daily_logs()
├── Step 7: Add TOPIC_FILE_LINE_BUDGET and enforce on topic file writes
└── Step 8: Improve dedup with normalize_entry()

Phase 4: /ops-context command
├── Step 9: Create ops-context.md workflow in agent-workflows/
└── Step 10: Register in augur.yaml and run sync_agents.py

Phase 5: One-time migration
├── Step 11: Run retention policy on existing decisions.md (archive expired entries)
└── Step 12: Recompile and sync via memory_sync.py --sync

Phase 6: Verification
├── Step 13: Verify MEMORY.md + topic files total < 500 lines after migration
├── Step 14: Run memory_sync.py --sync and verify no regressions
├── Step 15: Test dual-writer: add a native entry, run sync, verify it persists
└── Step 16: Run stale path scanner
```

## Alternatives Considered

### Alternative 1: RAG-indexed memory instead of flat files

Replace the flat MEMORY.md with a vector-indexed memory store that agents query semantically.

**Rejected because:** Claude Code's native auto-memory mechanism requires flat `.md` files in `~/.claude/projects/.../memory/`. Switching to RAG would require a custom retrieval step before every session, adding latency and complexity. The flat-file approach works fine once pruned — the problem isn't the format, it's the unbounded growth.

### Alternative 2: Single monolithic MEMORY.md with aggressive truncation

Keep everything in one file, hard-cap at 190 lines, and ruthlessly prune.

**Rejected because:** 190 lines isn't enough for meaningful architectural memory. The current topic-file overflow strategy is sound — it just needs budgets on the overflow files and a retention policy to prevent unbounded growth.

## References

- ADR-057: Memory pipeline architecture
- ADR-074: Context audit sessions
- ADR-161: Chat context injection optimization
- `memory_sync.py`: `.github/scripts/memory_sync.py`
- Claude native memory dir: `~/.claude/projects/-Users-<user>-Projects-Augur/memory/`
- Existing commands: `/orch-context-audit`, `/context-save`, `/focus`, `/ops-optimize`

## Impact Manifest

```yaml
impact:
  apis_changed:
    - function: compile_claude_native
      module: .github.scripts.memory_sync
      breaking: false
      note: "adds merge_native_entries() before overwrite"
    - function: update_memory_file
      module: .github.scripts.memory_sync
      breaking: false
      note: "adds noise filter and stronger dedup"
    - function: curate_daily_logs
      module: .github.scripts.memory_sync
      breaking: false
      note: "adds retention policy with age-out"
  patterns_deprecated:
    - grep: "structure-audit\\.md"
      replacement: "deleted — pre-ADR-126 stale content"
    - grep: "recent-adrs\\.md"
      replacement: "deleted — stale ADR references"
  files_affected:
    - glob: ".github/scripts/memory_sync.py"
    - glob: "~/.claude/projects/-Users-<user>-Projects-Augur/memory/structure-audit.md"
    - glob: "~/.claude/projects/-Users-<user>-Projects-Augur/memory/recent-adrs.md"
```

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.

You are implementing **ADR-164: Context Optimization Ops Command and Memory Retention Policy**.

Read the full ADR: `docs/decisions/ADR-164-context-optimization-ops-command.md`

### Team Orchestration

Create a team and spawn teammates to execute the plan below:

1. **Create team**: `TeamCreate(team_name="adr-164-context-opt", description="Implementing ADR-164: Context Optimization Ops Command and Memory Retention Policy")`
2. **Create tasks**: For each step in the Execution Plan, create a task via `TaskCreate`. Set `blocked_by` for PIPELINE dependencies.
3. **Spawn teammates**: For each unique agent role in the Execution Plan, spawn a teammate:
   ```
   Task(subagent_type="general-purpose", team_name="adr-164-context-opt", name="{role}",
        model="{tier-model}", prompt="You are '{role}' on the adr-164 team.
        Read your profile: .claude/agents/{role}.md
        Check TaskList for your assigned tasks. After each task: TaskUpdate to complete,
        SendMessage to team lead. If blocked, move to next available task.")
   ```
4. **Profile loading**: Each teammate MUST read `.claude/agents/{name}.md` for iron laws and constraints
5. **Communication**: Teammates use `SendMessage` to report completion, request reviews, and debate
6. **Dependencies**: PARALLEL phases -> spawn all at once. PIPELINE phases -> use task blocking
7. **Review cycle**: After implementation, validator reviews changes and debates with developer via `SendMessage`
8. **Shutdown**: When all phases pass, send `shutdown_request` to all teammates, then `TeamDelete()`

**Model mapping**: `low` -> haiku, `medium` -> sonnet, `high` -> opus

### Execution Plan

**Team name**: `adr-164-context-opt`

#### Phase 1: Immediate Cleanup
**Strategy**: PARALLEL
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | low | Delete `structure-audit.md` from Claude native memory dir `~/.claude/projects/-Users-<user>-Projects-Augur/memory/` | `structure-audit.md` |
| 1.2 | developer | low | Delete `recent-adrs.md` from Claude native memory dir | `recent-adrs.md` |

#### Phase 2: Dual-Writer Resolution
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | medium | Add `merge_native_entries()` function to `compile_claude_native()` — before overwriting, read existing native MEMORY.md, extract entries not in canonical, preserve them with `[claude-native]` prefix | `.github/scripts/memory_sync.py` |
| 2.2 | developer | medium | Add write-back logic — after merge, write `[claude-native]` entries back to `docs/memory/MEMORY.md` Decisions section so they enter the git-tracked canonical source and survive future syncs | `.github/scripts/memory_sync.py` |

#### Phase 3: Memory Retention Policy
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | developer | medium | Add `NOISE_PATTERNS` skip list to `update_memory_file()` — entries matching `chore(sync): regenerate` or `chore(sync): update generated` are never written to MEMORY.md, go directly to archive | `.github/scripts/memory_sync.py` |
| 3.2 | developer | medium | Add retention policy with `classify_entry()` and `archive_expired_entries()` functions to `curate_daily_logs()` — classify by commit prefix (chore/fix/feat/pattern), age-out per policy table in ADR, move expired to `decisions-archive.md` | `.github/scripts/memory_sync.py` |
| 3.3 | developer | medium | Add `TOPIC_FILE_LINE_BUDGET = 200` to `compile_claude_native()` — when writing topic files, if lines exceed budget, archive oldest entries to `{slug}-archive.md` (not referenced from MEMORY.md) | `.github/scripts/memory_sync.py` |
| 3.4 | developer | medium | Replace `dedup_entries()` 100-char prefix check with `normalize_entry()` — strip commit hashes `([a-f0-9]{8,}, N files)`, collapse whitespace, then compare full text | `.github/scripts/memory_sync.py` |

#### Phase 4: Ops Context Command
**Strategy**: PARALLEL
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 4.1 | developer | medium | Create `/ops-context` workflow — measure all files in Claude native memory dir, classify decisions, detect stale topic files by cross-referencing path mentions against filesystem, output budget report with recommendations, apply with confirmation | `plugins/ai/skills/ai_bridge/augur/data/agent-workflows/ops-context.md` |
| 4.2 | devops | low | Register `ops-context` in the ai_bridge skill's augur.yaml workflows section and run `python3 plugins/ai/skills/ai_bridge/scripts/sync_agents.py` to generate IDE copy | `plugins/ai/skills/ai_bridge/augur.yaml`, `.claude/skills/ops-context/SKILL.md` |

#### Phase 5: One-Time Migration
**Strategy**: PIPELINE (depends on Phase 3)
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 5.1 | developer | low | Run the new retention policy on existing `decisions.md` — archive all `chore(sync)` entries and entries older than retention thresholds to `decisions-archive.md` | `docs/memory/MEMORY.md`, `~/.claude/projects/.../memory/decisions.md` |
| 5.2 | devops | low | Run `python3 .github/scripts/memory_sync.py --sync` to recompile and sync all agents | All memory target files |

#### Phase 6: Verification
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task |
|------|-------|------|------|
| 6.1 | validator | low | Verify MEMORY.md + all topic files in Claude native memory dir total < 500 lines combined |
| 6.2 | validator | low | Run `python3 .github/scripts/memory_sync.py --sync` and verify no errors, no regressions |
| 6.3 | validator | low | **Dual-writer test**: Write a test entry to native MEMORY.md, run `memory_sync.py --sync`, verify entry persists with `[claude-native]` prefix and is written back to `docs/memory/MEMORY.md` |
| 6.4 | validator | low | Verify `structure-audit.md` and `recent-adrs.md` no longer exist in memory dir |
| 6.5 | architect | low | Verify ADR-164 intent: dual-writer conflict resolved, stale files eliminated, retention prevents regrowth |

### Completion Criteria
- [ ] All phases executed
- [ ] Dual-writer conflict resolved — Claude-native "remember this" entries survive sync
- [ ] `structure-audit.md` and `recent-adrs.md` deleted
- [ ] `memory_sync.py` has merge-before-overwrite, noise filter, retention policy, topic file budgets, improved dedup
- [ ] `/ops-context` command created and synced
- [ ] Existing decisions migrated (expired entries archived)
- [ ] Total on-demand topic files < 500 lines after migration
- [ ] ADR status updated to "Accepted" or "Implemented"

### How to Run
```
# Option 1: Use /implement-adr (handles team orchestration automatically)
/implement-adr docs/decisions/ADR-164-context-optimization-ops-command.md

# Option 2: Paste this prompt into Claude Code
# The agent will create the team, spawn teammates, and coordinate
```
