---
title: browse-three-concept-regroup-shipped
name: browse-three-concept-regroup-shipped
description: Browse nav regrouped into Context/Prompt/Loop Engineering concept groups
  (2026-06-11) — shipped, ADR-812; what rode along and what's still transitional
brain_scope: project
type: project
status: active
source_client: claude-code
source_file: browse-three-concept-regroup-shipped.md
source_hash: ae7a7263c0a7a382
---


Browse navigation shipped as three AI-engineering concept groups (2026-06-11, ADR-812, amends the [[category-action-refactor-spec]] §3): **Context Engineering** (Notes, Documents, Wiki, Pages + Profile/Archive/Drafts in More), **Prompt Engineering** (Prompts, Commands, Skills), **Loop Engineering** (Routines, Agents, Integrations, Workflows + Extensions in More). Framing follows the prompt→context→loop progression (louisbouchard.ai/loop-engineering).

Key facts:
- `journey_group` values are `context`/`prompt`/`loop` + dev `capabilities`/`diagnostics`/`reference`; the ONLY source is `apps/dashboard/lib/browse/types.ts` (nav is fully data-driven). `JOURNEY_GROUP_SUBTITLES` renders as `title` tooltips on group headers.
- Category **ids never changed** — labels only ("Background Routines"→"Routines", "Agent Profiles"→"Agents"). Prompts became a real category (scanner `index_prompts` + reindex dispatch already existed; only the `BROWSE_CATEGORIES` entry, the RETIRED_VIEW_MODES un-fold, and a transforms primary-action case were missing).
- Verification-discovered fix: `ai_artifact_inventory.py` indexed `plugins/agents/README.md` + `.claude/agents/README.md` as agent profiles (two `<agent-name>` placeholder cards). README.md now excluded from the agent-profile glob; registered inventory lives at the BRAIN root (`project-brain/config/inventory/ai-artifacts.json`), not project root — `write_ai_artifact_inventory(inv, project_root/'project-brain')`.
- Transitional riders awaiting their own workstreams: Workflows (ADR-805 fold into Skills), Extensions (deletion), Profile (fold to Notes tag), Drafts (CLI-only).
- Commits: 2bf1c6cfb, 139bd7882, adf9681, 555bfea1e, 366d61602, c819bd973, 4340d1cdb. NOT pushed — a concurrent session had an in-flight Actions workstream (ADR-806/807) with 2 temporarily-red jest suites (catalog.test.ts, generate-item-actions.test.ts) on shared main.

**Gotcha learned:** when two sessions share the main checkout, `git commit` swallows the other session's staged files — always commit by pathspec (`git commit -m ... -- <files>`); also "page stuck on skeletons" can simply be the other session's `aug dev build` window (`gate denied: owned by build_lock`), not a regression.

**Bigger gotcha (2026-06-11, workstream 2):** a plan file authored by another session is a strong signal THAT session intends to execute it. I executed `2026-06-11-skills-as-the-heart.md` in a worktree while its author session executed it on main in parallel — full duplicate (~3.5k deleted lines twice). Main's version won; my branch was proven 100% subsumed (probe greps all zero) and discarded per the rule-26 proof protocol. Before picking up a queued plan, check `git log origin/main` for its commit-subjects already landing, and prefer asking the user which session owns it. Workstream 2 final state on main: skills index 102 entries (leak gone), no Workflows/Extensions tabs, RETIRED workflows→skills mapping (15ab31a4f), Loop Engineering = Routines/Agents/Integrations.
