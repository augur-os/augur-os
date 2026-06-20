---
title: enforcement layers in Augur (Apr 2026)
name: enforcement-layers-in-augur-apr-2026
description: Augur ships rule enforcement across four layers (.githooks, .pre-commit-config,
  .claude/settings.json, auto-agent-config-parity scanner) with documented division
  of responsibility
brain_scope: project
type: project
status: active
source_client: claude-code
source_file: project_enforcement_layers.md
source_hash: 3bf6787de057d952
---

The repo enforces behavioral rules in four mostly-independent layers. Future hook/gate work should slot into the layer matching its scope:

| Layer | Path | Fires for | Use when |
|---|---|---|---|
| Cross-agent commit-msg | `.githooks/commit-msg` (calls `.github/scripts/require_browser_verify.py`) | Anyone committing | Commit-time gates that should fire for every committer (Claude, Codex, Gemini, human, CI rebase) |
| Cross-agent pre-commit framework | `.pre-commit-config.yaml` (commit-msg stage entry: `require-browser-verify`) | Pre-commit framework users | Same intent as above, plumbed for clones using the framework |
| Claude PreToolUse Bash | `.claude/settings.json` → `scripts/hooks/dashboard-shortcut-blocker.sh` | Claude only | Live shell-command interception (kill, rm -rf .next, pnpm dev, etc.) — no cross-agent equivalent surface |
| Parity scanner | `skills/loop-ops/scripts/agent_config_parity.py` (`auto-agent-config-parity` in hardening loop) | Nightly | Detects when a Claude-only gate lacks a cross-agent peer; flags drift |

**Why:** Built during Apr 2026 in response to user feedback that SSR-only smoke claims were masking client-side failures, and that I was bypassing /dev-build manually. CLAUDE.md rules 28 and 29 are the behavioral rules these layers enforce.

**How to apply:** When asked to add a new gate, decide first which layer matches:
- Should fire for any committer? → `.githooks/` + `.pre-commit-config.yaml`
- Should fire for any agent's runtime tool calls? → `.claude/settings.json` PreToolUse for Claude, plus equivalent in `.codex/`/`.gemini/` if those clients have hook surfaces; document and run `auto-agent-config-parity` to verify parity.
- Should fire only for Claude? → only when other clients lack the surface; mark as `unsupported` in the parity scanner output.

Source-of-truth canonical rules: `docs/agent-topics/agent-rules.md` (regenerated to CLAUDE.md / CODEX.md / etc. via `skills/ai/scripts/sync_agents`).
