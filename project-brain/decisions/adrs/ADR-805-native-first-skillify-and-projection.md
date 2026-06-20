---
status: Accepted
date: 2026-06-08
deciders:
  - gsannikov
related:
  - ADR-745
  - ADR-605
  - ADR-802
  - ADR-804
hub: null
tags:
  - skills
  - skillify
  - sync_agents
  - native-skills
  - claude
superseded_by: null
spec_file: null
plan_file: 2026-06-08-skillify-native-first-skills.md
---

# ADR-805: Native-First Skillify + Clean Native Skill Projection

> **ADR-805 is an index file.** The implementation steps live in the linked plan. This file carries pointers, status, and the decision summary.

## Decision summary

`/skillify` authors skills **native-first** — a Claude Agent Skill `SKILL.md` (`name` + a "Use when…" `description` + body) is the primary contract, and `x-augur-*` frontmatter is **additive**, added only when a skill needs MCP tools / dashboard pages / scheduled routines (Step 5). Skills opt into client exposure via `export_to` (Step 8). The **existing** per-skill write path (`sync_agents.skill_sync._sync_skill_exports`) now renders a **clean native `SKILL.md`** — `x-augur-*` stripped, keeping `name`/`description`/`allowed-tools` — for **every native-`SKILL.md` client** (Claude, Codex, Gemini-antigravity, OpenCode), instead of writing the Augur source verbatim. This **extends ADR-745** (the skillify workflow).

## Plan (canonical)

- [`docs/superpowers/plans/2026-06-08-skillify-native-first-skills.md`](../superpowers/plans/2026-06-08-skillify-native-first-skills.md)

## Status notes

**Accepted (2026-06-08) — implemented + tested.** Built on branch `feat/skillify-native-first`:

- **Phase 1:** `/skillify` Step 5 rewritten native-first (commit `1764985`); also scrubbed a stale `x-augur-hub` field reference (ADR-802 debt).
- **Phase 2:** native renderer carries `allowed-tools` (`8aa6b91`); `_render_native_skill_md` strips `x-augur-*` and the shared `has_subdirs` write at `skill_sync.py:~1173` now emits clean native for all native-`SKILL.md` clients, inside the existing manifest/orphan contract (`c1a8bb6`); Step 8 documents the `export_to: [claude, …]` opt-in (`2983ef8`). **239 sync_agents tests pass.** Verified (rule 34): `obsidian` projects clean native — `0` `x-augur-*` lines, body intact — to `.claude/skills/`, `.codex/skills/`, `.opencode/skills/`, `.antigravity/plugins/`.
- Non-subdir clients (Cursor `.cursor/rules`, Copilot `.github/instructions`) already write body-only and are unchanged.

**Rejected alternatives:**
- *Verbatim passthrough* (only add `claude` to `export_to`): keeps `x-augur-*` noise in the projected SKILL.md.
- *New `project_native_skills()` projector*: would fight the single `.augur-generated-prompts.json` manifest/orphan-reconciliation contract; reusing the existing write path avoids that.
- *`~/.claude/skills/` (global)*: needs flipping `home_sync`/`skill_scope` — broader blast radius. Repo-local `.claude/skills/` is already read by Claude Code.

**Investigation correction (rule 34):** the `geo*` skills in `~/.claude/skills/` are pre-existing **external** installs, not Augur output; the real gates were `export_to` policy + project/global scope, not a missing renderer.

**Carry-forward:** residual hub vocabulary in skillify Step 3 / lines ~126,133 (pre-ADR-802 debt) — reconcile when next touching those steps. Optional follow-up: extend clean render to the Codex `_codex_native` secondary path if a distinct global Codex surface is ever wanted.

## Related

- **Extends ADR-745** (skillify bug-to-skill workflow). Complements ADR-605 (external skill bundles), ADR-802 (no hub taxonomy), ADR-804 (skillify optimize mode).

## Impact Manifest

> Additive change to projection rendering — no path renames or API removals.

```yaml
impact:
  paths_renamed: []
  apis_changed:
    - "standard_skill_projection._render_skill_frontmatter / _render_client_skill: added optional allowed_tools param (back-compatible)"
  patterns_deprecated: []
```
