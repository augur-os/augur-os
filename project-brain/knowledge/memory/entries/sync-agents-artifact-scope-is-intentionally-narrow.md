---
title: sync_agents artifact scope is intentionally narrow
name: sync-agents-artifact-scope-is-intentionally-narrow
description: After editing skills/*/commands/*.md (command source), run `sync commands
  all` or `sync all` — `sync agents all` does NOT regenerate command surfaces by design
brain_scope: personal
type: feedback
status: active
source_client: claude-code
source_file: feedback_sync_agents_artifact_scope.md
source_hash: be3aa9f31f471392
---

`sync_agents` artifact narrowing is intentional, not a bug:

- `sync all` → everything (rules + subagents + memory + plugins + MCP + vaults + skills + prompts + commands)
- `sync agents` → agent-instruction surface only (explicitly disables skill/prompt/command exports)
- `sync skills` / `sync prompts` / `sync commands` → that artifact only

**Why:** The `/adr` post-write hook calls `sync agents all` because ADR creation/modification only changes the ADR status table inside CLAUDE.md/AGENTS.md, never command surfaces. Running full `sync all` after every `/adr` invocation would be wasted work. The pre-commit hook `validate-agent-instructions` runs `sync_agents --fix`, which detects drift and runs full sync as a safety net at commit time.

**How to apply:**
- After editing an ADR or skill data → `sync agents all` is correct
- After editing a command source (`skills/*/commands/*.md`) → use `sync commands all` (targeted) or `sync all` (full)
- After editing skill SKILL.md frontmatter → `sync skills all` or `sync all`
- The pre-commit `--fix` hook is the mechanical safety net; user prefers it over per-action behavioral rules
- Do NOT change the `/adr` post-write hook to `sync all` — user explicitly rejected this; the `--fix` gate already covers the gap

**Source files:** `skills/ai/scripts/sync_agents/__init__.py:181-222` (artifact dispatch), `skills/ai/scripts/sync_agents/modes.py:464` (fix_mode runs full sync on drift).
