---
title: skills-as-the-heart-shipped
name: skills-as-the-heart-shipped
description: Workstream 2 (skills as the heart) SHIPPED 2026-06-11 — skills index
  dedupe (102 honest entries), Workflows category retired, Extensions deleted; the
  four-layer dedupe map and the inventory-merge gotcha
brain_scope: project
type: project
status: active
source_client: claude-code
source_file: skills-as-the-heart-shipped.md
source_hash: 5b74a6a2364e97f0
---


**Workstream 2 of [[category-action-refactor-spec]] is SHIPPED** (origin/main `ad9a3367e`, 2026-06-11, subagent-driven execution of `docs/superpowers/plans/2026-06-11-skills-as-the-heart.md`). Browse Skills now shows exactly **102 honest entries** (canonical project-brain 25 + private-vault 17 + plugin-cache + genuine client-installed vendor skills); Workflows and Extensions categories are gone; `?view=workflows` deep links fold to Skills via `RETIRED_VIEW_MODES` (extensions-bundles deliberately unmapped → default fallback, rule 14).

**The Browse skills card count is a MERGE of two independent sources** — this is the gotcha that almost shipped a half-fix: (1) the RAG index (`src/lib/index/`), and (2) the **AI-artifact inventory** (`src/lib/ai_artifact_inventory.py::inventory_browse_entries_for_category`, merged in `browse_index_impl`). Fixing dedupe in the index alone left 6 fake cards (ask/discover/keep/project/routines/skillify — sync_agents exports of Augur *commands* under `.codex/skills/`) riding in via inventory entries the classifier itself marked `classification: "generated"`. Four dedupe layers now compose: skill_discovery tier/authority arbitration → index `_is_duplicate_generated_skill` (canonical-id match OR `_is_sync_agents_export` marker check, client-origin-gated) → inventory skips `generated` skill records → dashboard `dedupeSkillBrowseItems` name-merge. Rule-34 lesson reconfirmed: the rag files being clean (102) proved nothing about the page (108) — always verify the surface the user sees.

**Parallel-session hazards hit during integration** (shared main checkout, three sessions): a concurrent session's staged restructure blocked `git merge` on main → recovery was rebase-the-worktree-branch-onto-main + `merge --ff-only` (ff updates only branch-diff paths, disjoint from the other session's dirty files); a `dashboard-shortcut-staged-scan` hook false-positives on merge commits that bring in main's existing content (merge direction makes it look "introduced") — rebase avoids it entirely; and another session independently started executing the same plan in `augur-skills-heart` (its Part-B commit duplicates shipped work — check `git worktree list` for plan-name collisions before executing a plan). Worktree jest/pytest need: `corepack pnpm install --frozen-lockfile` from `apps/dashboard` (no root package.json), the build:scripts + generate-item-actions + rebuild-plugins generation chain, and the main checkout's `.venv/bin/python3` as interpreter with worktree paths.
