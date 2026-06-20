---
title: feedback-agent-isolation-unsafe
name: feedback-agent-isolation-unsafe
description: 'Agent tool''s `isolation: "worktree"` is UNSAFE in Augur — it returns
  the main repo path instead of creating an isolated worktree, causing parallel subagents
  to collide on `git checkout`'
brain_scope: personal
type: feedback
status: active
source_client: claude-code
source_file: feedback_agent_isolation_unsafe.md
source_hash: 4b1d606eebfeb628
_mentions:
- '[[project-gbrain-borrow-slate]]'
_entity_tier: 3
---




Do NOT use the Agent tool's `isolation: "worktree"` parameter for parallel subagent work in Augur. When Augur's main repo is already registered in its worktree registry (`~/Library/Application Support/Augur/state/worktree_registry.yaml`), the Agent tool sees the existing registration and reuses the main repo path **for every parallel subagent** instead of creating fresh isolated worktrees. The result: N concurrent subagents share the same physical checkout, and each one's `git checkout feature/...` yanks the working tree out from under the others, wiping untracked files and stashing in-flight work.

**Why:** Observed during Phase 1 of [[project-gbrain-borrow-slate]] (ADR-741, ADR-745, ADR-746) on 2026-05-13. Three subagents dispatched in parallel via `Agent(isolation: "worktree", run_in_background: true)`. All three returned `worktreePath: ~/Projects/Augur` (the main repo). Branch switches in mid-flight cost ~30 min of recovery work. ADR-746 lost its commit entirely and had to be reapplied from `git stash` in a real isolated worktree afterwards.

**How to apply:**

For any task that needs N parallel subagents working on independent code paths:

1. **Manually create N real `git worktree` paths** before dispatch:
   ```bash
   git worktree add ~/Projects/augur-wt-<task-id> -b feature/<task-id>-<slug> main
   python3 scripts/worktree_registry.py register \
     --path ~/Projects/augur-wt-<task-id> \
     --name <task-id>
   ```
2. **Pass the worktree path in each subagent's prompt** (not via `isolation:`). Instruct the agent: "cd to `~/Projects/augur-wt-<task-id>`. Stay there. Never `git checkout` to switch branches."
3. **Skip the `isolation: "worktree"` flag entirely**. Use `subagent_type: claude` and `run_in_background: true` if needed; let the worktree isolation come from physical path separation.
4. **Verify before dispatch**: `git worktree list` should show one worktree per subagent + the main repo, with distinct branches.
5. **After subagents finish**: `git worktree remove` + `scripts/worktree_registry.py unregister` to release ports (3001–3010) and clean up.

The cost of manual setup (one extra Bash call per worktree) is much smaller than the cost of recovering from the collision. For solo subagent work, `isolation: "worktree"` may still be safe because there's nothing to collide with — but verify the agent's `worktreePath` in its completion report is NOT the main repo path; if it is, redo with manual worktree.

**`EnterWorktree` fails the same way (confirmed 2026-05-24).** The native `EnterWorktree` tool, when run from the Augur main checkout, returned `{"path": "~/Projects/Augur", "branch": "main", ...}` (the main repo, not a new worktree) and then errored `ENOENT ... chdir` because it tried to chdir into the JSON blob. Same Augur worktree-integration root cause. **For solo in-session code work, skip `EnterWorktree` and create a manual git worktree directly:** `git worktree add .worktrees/<slug> -b wt-<date>-<slug> HEAD` (`.worktrees/` is already gitignored). The worktree has no `.venv`, but the main checkout's `.venv/bin/python` works cross-worktree because `pyproject.toml` sets `pythonpath=[".", "project-brain/capabilities"]`, resolved relative to the pytest cwd. Merge with `git merge --no-ff wt-...` from the main checkout (do NOT push unless asked).
