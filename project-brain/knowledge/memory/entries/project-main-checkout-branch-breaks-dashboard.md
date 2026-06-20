---
title: project-main-checkout-branch-breaks-dashboard
name: project-main-checkout-branch-breaks-dashboard
description: Creating a feature branch IN the main checkout silently breaks dashboard
  startup — start-dev.sh's preflight (set -e) aborts; restart only via start-dev.sh
  (npm run dev is hook-blocked)
brain_scope: project
type: project
status: active
source_client: claude-code
source_file: project_main_checkout_branch_breaks_dashboard.md
source_hash: 0162fc6f64dd42ac
---


If the **main checkout** (`~/Projects/Augur`) is on a non-`main`
branch, the dashboard **won't start** and the failure is nearly silent:
`apps/dashboard/scripts/start-dev.sh` runs `set -euo pipefail`, and
`worktree_preflight.py` exits non-zero on its `main_checkout_branch` check
("main checkout is on <branch>; continue branch work in a worktree or merge it
into main"), so the `PREFLIGHT_JSON="$(python3 worktree_preflight.py …)"`
assignment fails → the whole script exits 1 with almost no output.

**Don't `git checkout -b` in the main checkout.** Augur commits to `main`
directly (then merges/pushes); branch isolation via the Agent tool's worktree is
unsafe ([[feedback-agent-isolation-unsafe]]). If you did branch, recover:
`git stash` wip → `git checkout main` → `git merge --ff-only <branch>` →
`git branch -d <branch>` → `git stash pop`.

**Restarting the dev server:** `npm run dev` / `pnpm dev` are blocked by a
PreToolUse hook (rule 29). The hook-allowed gated runner is
`bash apps/dashboard/scripts/start-dev.sh` (run it as a persistent background
task — it ends in a foreground `next dev --turbopack`). `/dev-build` is the
canonical path. To stop first: `cleanup_processes.py --force` (gate-aware).

Chat-CLI note (debugged this session — corrected): the dashboard chat does
**NOT** auto-start a CLI on open in **dev mode** (only `operation` mode auto-starts,
via FloatingChat's `isOpen` effect). `/api/cli` `{action:"start"}` works (returns
HTTP 200 `status:running`). The "Failed to start claude: Unknown error" seen this
session was a **stale persisted chat message** (`localStorage:augur_chat_messages`,
re-rendered on open) from a transient MCP-cleanup disruption — not a real bug.
The "in-chat editable draft" hand-off for Browse AI actions shipped (ADR-748
follow-up): prefill the input + ungate `ChatInput` via a `chatStore.draft` flag.
**Prompt delivery to a cold CLI:** a client send ~300ms after start SILENTLY DROPS
the prompt (CLI-readiness race — `useActionRunner.ts:455` documents this). The
reliable fix is server-side inject: pass the prompt as `oneshotPrompt` in
`POST /api/cli {action:"start"}`; the server writes it to the PTY after startup
then Enter (`app/api/cli/actions.ts`, ~700ms delay so it submits even mid-startup).
Scope the inject to non-`agent-bubble-` CLIs (bubbles inject client-side → double
send otherwise). Related: [[project-browse-devonly-view-hydration-race]].
