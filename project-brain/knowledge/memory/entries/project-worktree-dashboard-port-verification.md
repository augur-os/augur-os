---
title: project-worktree-dashboard-port-verification
name: project-worktree-dashboard-port-verification
description: A worktree session's dashboard runs on its OWN port (from .augur-worktree.yaml,
  e.g. 3003) — :3000 is the MAIN checkout and does NOT contain the worktree branch's
  edits, so verifying UI changes on :3000 from a worktree silently checks the wrong
  code
brain_scope: project
type: project
status: active
source_client: claude-code
source_file: project_worktree_dashboard_port_verification.md
source_hash: 50e442c52a29f3e7
---


When verifying dashboard UI edits made inside a git worktree, the worktree's dashboard runs on its **own port**, read from `<worktree>/.augur-worktree.yaml` (`dashboard_port`, e.g. **3003**; also `mcp_port`, e.g. 8083). Port **3000 is the MAIN checkout** (`~/Projects/Augur`) — a *separate* working copy that does NOT contain the worktree branch's uncommitted edits. Verifying on :3000 from a worktree silently checks the wrong code; edits will appear to "not apply."

**Why:** Burned significant effort this session verifying fixes on :3000 (main) and concluding HMR was broken, when the edits were correct but in the worktree (which wasn't even running). Generalizes [[feedback-chrome-mcp-multi-browser]] and CLAUDE.md rule 33 (identify your worktree) to the verification step.

**How to apply:**
- Before browser-verifying, read `.augur-worktree.yaml` for this worktree's `dashboard_port`; verify there, not :3000.
- `shared-vault/skills/daemon/scripts/cleanup_processes.py` (and `/dev-build` cleanup) targets **port 3000 = main** regardless of the current worktree, so it will kill the user's main dashboard. The `dashboard_monitor` daemon (production mode) auto-respawns main on :3000 within seconds — see [[project-dashboard-monitor-stuck-gate-fix]].
- To start the worktree instance: `bash apps/dashboard/scripts/start-dev.sh` as a background Bash task. It reads `.augur-worktree.yaml` → binds the worktree port, runs `next dev` **foreground** (stays alive as long as the task runs), and **auto-clears a corrupted Turbopack cache on restart** when a prior PANIC marker exists (the "Next.js package not found" / "Failed to write app endpoint" Turbopack panic). Each worktree has an **isolated** pnpm `node_modules`, so starting it is safe and never touches main.
