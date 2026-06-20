---
title: external skill strategy
name: external-skill-strategy
description: User's preferred installation tier for third-party AI skills — Claude-only
  by default, vendor/ tier reserved for SHA-bumpable upstream bundles needing multi-client
  distribution
brain_scope: personal
type: feedback
status: active
source_client: claude-code
source_file: feedback_external_skill_strategy.md
source_hash: c0868722bbaf0497
---

External (third-party) AI skills install per a deliberate tier choice, not "everywhere by default":

- **Default:** install third-party skills in **Claude Code only** (via marketplace or direct user-skill copy). Don't fan out to Codex/Gemini/OpenCode/Copilot unless there's a reason.
- **Vendor tier (`vendor/skills/<bundle>/` + `config/external_skills.yaml`):** reserved for upstream bundles that (a) you actively use across multiple AI clients, (b) want SHA-pinned reproducibility for, and (c) need to fan out via `sync_agents`. It is currently empty after the external-skill cleanup.
- **Cross-client exception:** `superpowers` (obra/superpowers) stays in Claude + Gemini extensions but doesn't get expanded to Codex/OpenCode/Copilot unless explicitly asked.

**Why:** May 2026 cleanup decision — user evaluated `geo`, `ui-ux-pro-max`, `superpowers` and concluded multi-client fanout adds maintenance overhead without enough payoff for these specific bundles. Vendor tier proves its value when an asset (a) is genuinely used across clients AND (b) has frequent upstream changes worth pinning.

**How to apply:** When user installs a new third-party skill, default to Claude-only install path (marketplace → `~/.claude/plugins/` or hand-install to `~/.claude/skills/`). Don't copy to `<Augur>/.codex/skills/`, `<Augur>/.gemini/skills/`, `<Augur>/.opencode/skills/`, or generate `.github/instructions/` entries unless the user explicitly says to. When proposing vendoring, confirm the multi-client + SHA-pinning rationale applies before recommending it.
