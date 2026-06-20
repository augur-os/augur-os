---
status: Implemented
date: '2026-03-04'
deciders:
- Gur Sannikov
related: []
hub: null
tags:
- dev
- merge
- three
- mode
- redesign
superseded_by: null
---

# ADR-215: Dev-Merge Three-Mode Redesign (fast/full/all)

## Context

`/dev-merge` is slow because it always runs the full 10-step pipeline including sync_agents (30-60s+), collateral routing, and learnings capture. When merging multiple worktrees, these heavy steps run redundantly for each worktree. Most merges only need the git operations (commit, push, merge, branch cleanup) and don't benefit from running sync/learn every time.

## Decision

Restructure `/dev-merge` into three modes:

### Mode Dispatcher

| Invocation | Mode | Steps Executed |
|---|---|---|
| `/dev-merge` | fast | 0 → 1 → 2 → 3 → 3.5 → 4 → 5 → 6 → 10 |
| `/dev-merge full` | full | 0 → 1 → 2 → 3 → 3.5 → 4 → 5 → 6 → 7 → 8 → 9 → 10 |
| `/dev-merge all` | all | Discover worktrees → Loop(fast per worktree) → 7 → 8 → 9 → 10 |

- **fast** (default): Pure git operations only. Skips collateral routing (7), sync_agents (8), and learnings (9).
- **full**: Today's behavior, unchanged. All 10 steps.
- **all**: Batch mode for multiple worktrees. Fast-merges each sequentially, then runs heavy steps once.

### `/dev-merge all` Batch Flow

1. Acquire merge lock (once for entire batch)
2. Run `git worktree list` → parse worktree paths (exclude main)
3. Show summary: "Found N worktrees: [branch1, branch2, ...]"
4. Ask user to confirm or select subset
5. For each worktree (sequential):
   - cd into worktree path
   - Run fast-mode steps (1-6) inline
   - Worktree cleanup: kill processes, unregister, remove worktree, delete branch
   - Report result; on failure ask user to skip or abort-all
6. Back on main repo: Step 7 (collateral) → Step 8 (sync_agents) → Step 9 (/learn) — once
7. Release merge lock

### Key Design Decisions

- Single lock for entire batch (no per-worktree lock/release churn)
- Sequential execution (avoids concurrent merge-to-main conflicts)
- Lock step updates: `merge_lock.py update --step "all: merging N/M (branchname)"`
- Worktree discovery via `git worktree list` (native git, no registry dependency)
- Old `/dev-merge all` (stage-all-files) renamed to `--stage-all` flag

### Error Handling

| Scenario | Behavior |
|---|---|
| `/dev-merge all` with 0 worktrees | Fallback to fast mode on current branch |
| Worktree merge conflict during `all` | Pause, show conflict, ask: resolve/skip/abort |
| Lock timeout during `all` batch | Show holder, wait or abort (same as today) |
| `/dev-merge` on main with clean tree | Skip steps 2-5, verify (Step 6), release lock |
| Partial `all` completion (3/5 then abort) | Steps 7-9 still run for already-merged branches |

## Consequences

### Positive

- Default `/dev-merge` drops from ~60-90s to ~5-10s
- Batch worktree merging with 3 worktrees: ~90s total vs ~270s
- Heavy steps (sync_agents, collateral, learnings) run exactly once regardless of worktree count
- No changes to existing reference docs (worktree.md, collateral.md, multi-repo.md)

### Negative

- `all` argument meaning changes (was "stage all files", now "batch worktrees") — mitigated by `--stage-all` flag
- Fast mode skips learnings capture — users must remember to run `/dev-merge full` or `/learn` separately when they want learnings

### Neutral

- SKILL.md structure changes but step numbering and content within each step stays the same
- Merge lock behavior unchanged (ADR-195 still applies)

## Alternatives Considered

### Alternative 1: Separate SKILL.md per mode

Three files: `dev-merge/SKILL.md` (fast), `dev-merge-full/SKILL.md`, `dev-merge-all/SKILL.md`. Rejected because it duplicates shared steps (0-6, 10), requires three command registrations, and creates drift risk.

### Alternative 2: Shared step library + mode files

Extract steps into reusable reference docs, each mode includes relevant steps. Rejected as over-engineered for 3 modes — adds indirection without proportional benefit.

## References

- ADR-195: Dev-Merge Concurrency Lock
- Design doc: `docs/plans/2026-03-04-dev-merge-modes-design.md`
- Implementation plan: `docs/plans/2026-03-04-dev-merge-modes-impl.md`
- SKILL.md: `plugins/dev/skills/devops/commands/dev-merge/SKILL.md`

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.

**Team name**: `adr-215-dev-merge-modes`

### Phase 1: SKILL.md Rewrite
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | editor | medium | Rewrite SKILL.md: add Mode Selection section, mode-aware routing table in Step 1, gate Steps 7-9 behind full/all modes, add All Mode Batch Orchestration section | `plugins/dev/skills/devops/commands/dev-merge/SKILL.md` |
| 1.2 | editor | low | Disambiguate `all` arg: rename stage-all to `--stage-all` flag in Step 2 and Usage | `plugins/dev/skills/devops/commands/dev-merge/SKILL.md` |

### Final Phase: Verification
| Step | Agent | Tier | Task |
|------|-------|------|------|
| V.1 | validator | low | Read final SKILL.md, verify mode table, step gating, all-mode section, no orphaned references |
| V.2 | validator | low | Read worktree.md, collateral.md, multi-repo.md — confirm unchanged |

### Completion Criteria
- [ ] Mode Selection table present with fast/full/all routing
- [ ] Steps 7-9 gated with "SKIP if fast mode"
- [ ] All Mode section with A1-A4 sub-steps
- [ ] `all` arg disambiguated to `--stage-all`
- [ ] Reference docs unchanged
- [ ] ADR status updated to Accepted
