---
title: prefer cross-agent enforcement over Claude-only rules
name: prefer-cross-agent-enforcement-over-claude-only-rules
description: When adding hooks/gates, default to .githooks/ or .pre-commit-config.yaml
  so the rule fires for any agent (Claude, Codex, Gemini, OpenCode, Copilot)
brain_scope: personal
type: feedback
status: active
source_client: claude-code
source_file: feedback_cross_agent_enforcement.md
source_hash: ffb194d9375caf26
---

When a behavior gate is needed, design it to fire for any committer or any client — not Claude only. Cross-agent enforcement is preferred because behavioral rules degrade with context length but mechanical gates don't.

**Why:** Direct user feedback after a long session: "I had agent instructions to use relevant slash command for dashboard ops and not doing it manually why you ignore it?" — and "why is there such degradation in performance lately?" The structural answer is enforcement: pre-commit hooks that fail when SSR-only verification was used for UI changes, or when `pnpm dev`/`kill` show up alongside dashboard files. New rules in CLAUDE.md compete for attention; mechanical gates don't.

**How to apply:** Default the enforcement layer to:
1. `.githooks/` (canonical, `core.hooksPath=.githooks`) — fires for any committer, any client, any human
2. `.pre-commit-config.yaml` — same intent, plumbed through pre-commit framework
3. `.github/scripts/` — shared scripts referenced by both layers

Use `.claude/settings.json` PreToolUse hooks ONLY when no cross-agent equivalent exists for the surface (e.g., live shell command interception). The new `auto-agent-config-parity` scanner (skills/loop-ops/scripts/agent_config_parity.py, hardening loop tier 2) flags any Claude-only gate that lacks a cross-agent peer — treat its findings as actionable.
