---
title: dashboard ops use slash commands, never manual
name: dashboard-ops-use-slash-commands-never-manual
description: Use /dev-build /dev-debug /auto-lint /dev-merge for dashboard operations;
  never manually kill the dev server, rm -rf .next, or invoke pnpm dev
brain_scope: personal
type: feedback
status: active
source_client: claude-code
source_file: feedback_dashboard_ops.md
source_hash: 10bf8f6658836152
---

For any dashboard build/restart/debug task, use the canonical slash commands listed in CLAUDE.md's Development Commands section. Never reach for `kill <pid>`, `rm -rf .next`, `pnpm dev`, or `npx next dev` directly.

**Why:** I bypassed `/dev-build` mid-session and got called out — the slash commands carry safety steps (port-owner detection, codex thread state repair, vault sync, post-build verification) that manual gymnastics skip. Manual restart also risks racing the user's own dev session.

**How to apply:** When the dashboard misbehaves (chunk-load errors, stale build, page errors), invoke `/dev-build` (rebuild) or `/dev-debug` (diagnose). The Claude PreToolUse Bash hook (`scripts/hooks/dashboard-shortcut-blocker.sh`) now blocks the manual commands at the source — if you see "Blocked by rule 29", that's the gate working. Don't try to work around it; use the slash command. Cross-agent enforcement also being built via `auto-agent-config-parity` scanner.
