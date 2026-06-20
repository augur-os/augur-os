---
title: Cross-Client Bundle Architecture (Layer 4 — Migration)
date: 2026-04-28
status: proposed
scope: design
related:
  - 2026-04-28-cross-client-bundle-architecture-design.md
---

# Cross-Client Bundle Architecture (Layer 4 — Migration)

## Purpose

The Layer 1 architectural spec (`2026-04-28-cross-client-bundle-architecture-design.md`) defines the target state: an MCP-and-SKILL.md-aligned bundle architecture, framework libraries in `src/lib/`, two project-tier MCP servers (`augur-core` and `augur-framework`), per-bundle vault-tier MCP servers, and no `CURATED_VISIBLE_TOOLS` filter. Layer 1 explicitly defers the cutover plan to this Layer 4 spec.

This document describes how the system transitions from current state to the Layer 1 target state, in a way that:

- Keeps the dashboard and every MCP-using surface working at every step.
- Produces small, reviewable, revertible PRs.
- Verifies architectural claims automatically rather than relying on manual eyeballing.
- Records each track's decision in a lean ADR aligned with the Augur project's ADR governance convention.
- Does not require building distribution machinery (marketplaces, package managers, third-party publishing) — those are future cycles built on top of the same bundle format.

**Important conceptual clarification this migration commits to and the spec records explicitly:** the *vault* is a directory the user owns, not a category of bundle. Bundle format is universal regardless of where the bundle came from (user-authored, copied from a friend, future marketplace install, or migrated from this project). Distribution sources are a future concern; this migration only physically moves three bundles between two directories the user already owns.

## Decisions

- The migration runs as **four parallel/sequenced tracks** plus a **Phase 0 cleanup PR** that fixes the layering smells the audit surfaced before any track starts.
- Tracks 1 (library extraction) and 2 (vault server split) run in parallel — they're independent.
- Track 3 (framework server split: `augur-core` + `augur-framework`) follows after Tracks 1 and 2 land — it depends on the libraries existing and benefits from the per-bundle server pattern being proven.
- Track 4 (visibility filter removal) is the final track, gated on every other server being split correctly.
- Track 1 uses **rename-via-overlap**: `src/lib/X/` is added before `skills/X/` is removed; imports are migrated incrementally; `skills/X/` deleted only after all importers are switched. Standard library-renaming refactor.
- Tracks 2, 3, and 4 use **bundle-atomic moves**: each bundle's tools migrate in one PR; no duplicate tool names exist on the protocol layer at any commit.
- Vault bundle migration is **atomic `git mv` per bundle**: one bundle = one PR pair (Augur-side commit + Au-vault-side commit, coordinated). No "code in two repos" overlap period.
- **Each track gets its own lean ADR** (1–2 pages): records the decision, references the Layer 1 + Layer 4 specs, defines the track's verification check. ADR moves from Proposed → Implemented after evidence (verification script passing + at least one demo session) is recorded.
- **Each track ships a verification script** that proves the architectural claim. Scripts live in `tests/architecture/` and run in CI. Track is incomplete until its verification passes.
- **Phase 0** fixes the 3 layering smells + 2 coupling inversions before any track starts. They are pre-existing bugs, not architectural choices.
- **Within-track ordering is "simplest first to validate the pattern; riskiest last."** Each track's first PR proves the refactor pattern works; subsequent PRs reuse the proven pattern.
- The migration produces **5 lean ADRs** (Phase 0 + Tracks 1–4) and **5 verification scripts**. Bundle-sized PRs within each track may be many but ship under the track's single ADR.
- This spec does NOT specify exact file diffs or task-level steps; those belong in the implementation plan that consumes this spec.
- This spec does NOT specify a marketplace, package distribution mechanism, third-party bundle publishing, or version management for bundles. Those are explicitly future concerns.

## Architecture

### Vault is a location, not a category

A bundle authored by the user, a bundle pulled from a future marketplace, and a bundle copied from a friend's zip file are **the same thing** — same `SKILL.md` + `dashboard.yaml` + `scripts/mcp/` shape, same MCP server contract, same client config registration. The runtime cannot distinguish them.

The only differences are non-architectural: origin, trust, update flow, privacy. **The format is universal**, and "vault" simply means *a directory the user owns*. Today that's `Au-vault/skills/`. Tomorrow it might also be `~/.augur/bundles/` or any directory the user adds to the framework's bundle-discovery paths.

This migration relies on this clarification. It does not invent distribution machinery; it physically moves three bundle directories from one user-owned directory (the Augur repo's `skills/`) to another user-owned directory (the user's vault repo's `skills/`). Both are real directories with real `git` versioning today. The move is mechanical.

### Phase 0: Pre-migration cleanup

**Single PR. Fixes pre-existing layering bugs the audit caught.**

Five fixes:

1. `src/config/mcp_tools.py` references `apple` (a vault-private skill). Remove the reference; replace with dynamic discovery from connected MCP servers — but for this Phase 0 PR, just remove the hardcoded reference and use the existing skill registry instead. The dynamic-discovery upgrade lands in Track 3 with `augur-core`.
2. Dashboard scripts (`apps/dashboard/scripts/skill-scripts/skill_generation/comprehensive_dashboard_generator.py` and `dashboard_generator.py`) hardcode `lifestyle`. Generalize to read from the skill registry.
3. `daemon` imports `platform-admin` (`skills/daemon/scripts/ops/stale_paths.py`, `run_system_audits.py`). Move shared utilities into a temporary `src/lib/_shared/` so both daemon and platform-admin can consume them. (`src/lib/_shared/` later gets cleaned up or absorbed into appropriate library packages during Track 1.)
4. `rag` imports `ingest` (`rag/scripts/mcp/rag_tools.py`). Move the helper into `src/lib/_shared/` or invert the call — whichever is the smaller change.
5. `ingest` imports `obsidian` (`ingest/scripts/url_source_card.py`). Same pattern — extract shared logic.

**Verification:** A static-import-graph check passes — no project skill (other than `augur-core`'s explicit registry usage) imports another project skill, and no project module imports a vault-private skill (`apple`, `lifestyle`).

**Phase 0 ADR:** `phase0-layering-cleanup.md` — records the smells, the fixes, and the lint check that prevents regression.

### Track 1 — Library extraction (rename-via-overlap)

Extracts heavily-imported skill code into `src/lib/`. **Five PR ladders** (one ladder per library, ~3–4 PRs per ladder, ~15–20 PRs total). Library order is simplest first to validate the rename-via-overlap pattern, riskiest last.

**Order:**
1. **`document-extractor` → `src/lib/extraction/`** (4 importers via sys.path; smallest blast radius)
2. **`knowledge` library code → `src/lib/knowledge/`** (2 importers; the `tools_summarize.py` and `file_metadata_extractor.py` library portions; MCP-tool surface stays in the bundle for now and folds into `augur-framework` in Track 3)
3. **Daemon library code → `src/lib/runtime/`** (11 importers; the loop-ops modules, scheduling helpers; the daemon process itself stays as a small bundle around `src/lib/runtime/`)
4. **`rag` → `src/lib/index/`** (15 importers; the `unified_indexer.py`, `document_understanding.py`, `index_reader.py`, `ocr_extractor.py`)
5. **`ai` → `src/lib/ai/`** (18 importers; the LLM bridge, model routing — broadest reach, last)

**Per-library PR pattern (rename-via-overlap):**

```
PR a: Add src/lib/X/  (copy of skills/X/scripts/<library_files>)
       Update X's own internal imports to use src/lib/X/
       Existing skills/X/scripts/ still works; nothing imports src/lib/X/ yet
       Tests pass on both paths.

PR b: Migrate the loudest importer (e.g., daemon for ai)
       Switch from `from skills.X.scripts.Y` to `from src.lib.X.Y`
       Tests pass.

PR c: Migrate remaining importers, ~5–10 per PR
       Each PR is auditable.

PR d: Delete skills/X/scripts/ library files; only the bundle's MCP-tool
       wrapper remains (or the entire bundle is gone if X had no MCP surface).
       CI lint check forbids `from skills.X.scripts.` imports going forward.
```

**Verification:** No module under `apps/`, `src/`, `skills/` imports `from skills.<library_name>.scripts.` after the library's PR ladder completes. CI check enforces this.

**Track 1 ADR:** `track1-library-extraction.md` — records the libraries, the rename-via-overlap technique, the per-library lint guard.

### Track 2 — Vault server split (bundle-atomic)

Migrates vault-tier bundles to per-bundle MCP servers. **Five PRs** (one per bundle), simplest first.

**Order:**
1. **`apple` server split** (already lives in `Au-vault/`, only the topology change to validate). Introduces the per-bundle MCP-server entry point, registers `augur-apple` in user-tier client configs, removes apple's tools from the monolith. Validates the per-bundle server pattern.
2. **`lifestyle` server split** (same shape as apple).
3. **`file-manager` `git mv`'d to vault** + per-bundle server (audit confirmed 0 incoming Python importers, so this is the cleanest of the newcomers).
4. **`obsidian` `git mv`'d to vault** + per-bundle server.
5. **`ingest` `git mv`'d to vault** + per-bundle server (most-coupled migrant; last).

**Per-bundle PR pattern (atomic):**

```
PR per bundle (single PR pair across two repos for newcomers):
  - In Augur: git rm -r skills/<bundle>/  (newcomers only)
              + remove the bundle's tools from the monolith MCP server's
                plugin loader
              + remove any project-tier config entries that reference the bundle
  - In Au-vault: add skills/<bundle>/ in the new directory layout
                  (SKILL.md + dashboard.yaml + loops.yaml + commands/ + scripts/mcp/)
                + register augur-<bundle> as its own MCP stdio entry point
  - Update user-tier client configs (~/.claude/settings.json,
    ~/.codex/config.toml, ~/.gemini/settings.json) to register augur-<bundle>
  - Verify: dashboard browse page shows the bundle's data; the bundle's tools
    are reachable via tools/list against augur-<bundle>; the monolith no longer
    advertises those tools.
```

For `apple` and `lifestyle` (already in vault), the PR is single-repo (Au-vault only) — just splitting from the shared monolith into a per-bundle server.

**Verification:** Each migrated bundle has its own running MCP stdio server; `tools/list` against that server returns exactly the bundle's tool set; the monolith's `tools/list` no longer includes those tools; the dashboard's browse and category views still render.

**Track 2 ADR:** `track2-vault-server-split.md` — records the bundle-atomic technique, the per-bundle server convention, the user-tier config layering.

### Track 3 — Framework split + dashboard hub-routing redesign (split into 3a + 3b)

Track 3 was originally framed as a single PR introducing `augur-core` and `augur-framework`. A static-analysis audit run during Phase 0 surfaced that the dashboard hardcodes vault-private skill names (`apple`, `lifestyle`) in 50+ locations across URL routing, skill-import templates, workflow code, and production UI. Removing those hardcodes is not a side-fix during the framework split — it is a separate dashboard-architectural change that must be planned and reviewed on its own. Track 3 therefore splits into two sub-tracks.

#### Track 3a — MCP framework server split + src/ vault-private hardcode removal

Two coupled deliverables in one track:
1. **Framework server split** — introduce `augur-core` and `augur-framework`, redirect all project-tier MCP tools, retire the monolith.
2. **Remove vault-private skill name hardcodes from `src/` framework code.** Discovered during Phase 0 execution: 10 hardcoded `apple`/`lifestyle` references across `src/config/mcp_tools.py`, `src/mcp/augur_mcp/infrastructure/`, `src/mcp/augur_mcp/domain/`, `src/mcp/augur_mcp/tools/hubs/`. These bake vault-tier assumptions into framework code (e.g., `bundle: str = "lifestyle"` as a default parameter; entire modules like `scrape_and_save_idea.py` keyed to lifestyle). Track 3a removes them as part of the framework refactor since the dynamic-discovery mechanism that replaces them comes online with `augur-core`.

The framework server split cannot be incremental on the protocol layer — at the moment the project-tier monolith is split, all its tools must be re-homed at once or the dashboard breaks. The `src/` hardcode removal is incremental within the same PR (or can be staged across follow-up PRs after the split lands).

**Known src/ hardcodes** (confirmed during Phase 0 audit; full set the track must address):

- `src/config/mcp_tools.py:387` — `vertical_skills = {"career", "lifestyle", ...}` set literal in `_detect_project_context()`. Replace with dynamic skill registry lookup.
- `src/mcp/augur_mcp/infrastructure/mcp_management.py:289` — classification heuristic referencing `"lifestyle"`. Generalize.
- `src/mcp/augur_mcp/infrastructure/config.py:736` — `"lifestyle"` literal in a list. Replace with discovery.
- `src/mcp/augur_mcp/domain/plugins.py:218` — `bundle: str = "lifestyle"` default parameter. Remove default; require explicit bundle.
- `src/mcp/augur_mcp/tools/hubs/capabilities.py:24` — hardcoded `"apple"` capability description. Move to skill-declared metadata.
- `src/mcp/augur_mcp/tools/hubs/scrape_and_save_idea.py:17,22,53` — entire module hardcoded to `lifestyle`. Restructure as bundle-parameterized.
- `src/mcp/augur_mcp/infrastructure/browse/dev.py:98` — `"lifestyle"` literal in a list.

**PR contents:**

- New `src/mcp/augur_core/` and `src/mcp/augur_framework/` packages with their own `__main__.py` stdio entry points.
- All previously-monolith tools sorted into one of the two:
  - **`augur-core`**: `list-skills`, `get-skill`, `find-skill`, `list-skill-actions`, `cross-skill`, `unified-search`, `search-skill-knowledge`, `browse-index`, `get-scheduled-execution-detail`, `list-api-routes`. ~10–15 tools.
  - **`augur-framework`**: tools backed by `src/lib/*` (built in Track 1) + `auto-skill-quality`'s and `platform-admin`'s tools (operational meta-tooling, multiplexed in). ~50 tools total.
- `augur-core` reads the user's client config at startup and indexes other connected servers' `tools/list` for cross-bundle operations — replaces the previous `mcp__augur__*`-name-based registry assumption.
- Project-tier client configs (`.claude/settings.json` and parallel files for Codex/Gemini in repo) updated to register `augur-core` and `augur-framework` instead of `augur`.
- The old `augur` monolith entry point is deleted.
- The 10 known `src/` vault-private hardcodes (listed above) replaced with dynamic discovery / parameterization. The `_detect_project_context()` function refactored to consult the skill registry rather than enumerating skill names.
- New architecture-rule test added: `tests/architecture/test_no_vault_skill_refs.py` (scope: `src/`). With Track 3a's hardcode removal complete, this test passes with no exceptions. Phase 0 deliberately did not add this test; Track 3a owns it because Track 3a delivers the conditions under which it can pass.

**Verification:**

- `augur-core` and `augur-framework` are running as separate stdio processes (verified via `ps`).
- The dashboard's browse page renders normally (verified in browser via Chrome MCP or screenshot).
- `unified-search` returns results that span both servers' contributions.
- `find-skill apple` discovers `apple` even when it's a vault-tier server, demonstrating cross-server discovery.
- `tools/list` against the old `augur` name returns nothing (the entry is removed).
- `tests/architecture/test_no_vault_skill_refs.py` passes with no allowlist exceptions for `src/`.

**Track 3a ADR:** `track3a-framework-split.md` — records the augur-core/augur-framework boundary, cross-server discovery via `augur-core`, retirement of the monolith, removal of the 10 known src/ vault-private hardcodes, and the addition of the parallel architecture-rule test.

#### Track 3b — Dashboard hub-routing redesign

Removes the dashboard's structural assumption that `lifestyle` and `apple` are first-class hub URL prefixes. This is its own design conversation — Track 3b deserves its own brainstorming cycle and its own implementation spec, not a sub-PR within 3a.

**Scope** (preliminary; finalized in the Track 3b spec):

- Replace the hardcoded `{vertical: lifestyle, horizontal: hands, factory: agents}` hub URL mapping in `dashboard_generator.py`, `comprehensive_dashboard_generator.py`, and the broader generator pipeline with a metadata-driven layout. Skills declare their hub via a generic field; the dashboard generates routes from the metadata.
- Rewrite skill-import templates (`blueprint_generator.py`, `placement_analyzer.py`, `route_templates.py`, `productization_plan_generator.py`, `_hardening_implementation.py`, `import_stages/blueprint.py`, `skill_importer.py`, `skill_import.py`, `import_codegen.py`, `generate_skill_ui.py`) to emit hub-neutral code that references whatever hub the imported skill declares, not a hardcoded `lifestyle`.
- Remove `lifestyle`/`apple` literal references from production code: `apps/dashboard/app/actions.ts`, `lib/api/record-helpers.ts`, `lib/help.ts`, `lib/paths.ts`, `lib/server/voice-memos.ts`, `lib/browse/types.ts`, `features/components/CalendarWidget.tsx`, `features/extensions-bundles/plugins/plugin-dialogs.tsx`.
- Regenerate `lib/tabs/generated-registry.ts` from the updated skill metadata (auto-cleared once the upstream generators stop emitting hardcoded names).
- Workflow / MCP tools in `apps/dashboard/scripts/skill-scripts/` (`tools_plugin.py`, `tools_workflow.py`, `workflow/engine.py`, `workflow/state_manager.py`, `scoring/user_research.py`) — case-by-case analysis; some may be domain logic that legitimately references hub names, others are templates.

**Estimated scope:** 50+ files. Multi-day to multi-week implementation depending on how much of the import-template machinery gets rewritten vs. patched. Cannot be done as part of 3a — splitting them protects 3a from scope creep and gives 3b the design attention it requires.

**Why split now (not at execution time):**

- 3a is an MCP server topology change reviewable in isolation. 3b is a dashboard architectural change reviewable in isolation. Mixing them produces an unreviewable PR.
- 3b needs its own brainstorming cycle to choose the metadata mechanism (skill-declared hub field, central hub registry, dashboard-config-driven, or some combination). That conversation hasn't happened.
- The verification gate for 3a (`browse page renders normally`) does not require 3b to be done. Browse page works fine while the dashboard still has hardcoded `lifestyle` URLs — those URLs just continue routing to the existing pages.

**Track 3b ADR:** Deferred until brainstorming. The ADR is written as part of the 3b spec cycle, not in advance.

#### Sequencing of 3a vs 3b

3a and 3b are largely independent. They can run in either order or in parallel:

- 3a moves MCP servers without touching dashboard code (except the small dynamic-discovery fix to `mcp_tools.py`).
- 3b changes dashboard code without touching MCP server topology.

Recommended order is **3a first, then 3b**: 3a completes the MCP architecture migration faster, leaving the bigger dashboard refactor as a clean follow-up cycle. Track 4 (visibility filter removal) can land after 3a alone — it does not depend on 3b.

**Original "Track 3 ADR" reference is now `track3a-framework-split.md`. Track 3b gets its own ADR after the brainstorm.**

### Track 4 — Visibility filter removal (single small PR)

**One small PR** that deletes `CURATED_VISIBLE_TOOLS`, `COWORK_VISIBLE_TOOLS`, and the `filter_tools_for_client` curation branches in `src/mcp/augur_mcp/client_surface.py`. After Tracks 1–3, no server is registering more than ~50 tools and every tool is intentionally hosted by the right server. The filter is no longer needed.

**PR contents:**

- Delete the two frozenset literals.
- Simplify `filter_tools_for_client` to either return all tools or be deleted entirely if no logic remains.
- Update any tests that asserted the filter's behavior.
- Remove the `x-augur-visibility` field references from any code that still reads it (the field itself was already irrelevant by Layer 1; this PR removes the dead reads).

**Verification:**

- A fresh Claude Code session lists previously-hidden tools (verify by listing `apple-list-emails`, `obsidian-read`, `extract-document` are present).
- A fresh Codex session does the same.
- A fresh Gemini session does the same.
- `tools/list` against `augur-core` and `augur-framework` returns the same tools regardless of which client connects.
- The 91%-hidden problem cannot recur because the mechanism that caused it no longer exists.

**Track 4 ADR:** `track4-visibility-filter-removal.md` — records the deletion, the verification across three clients, the closing of the architectural debt.

### Per-track ADR template

Each ADR is short. Format:

```
# ADR-<n>: <track-or-phase title>

## Status
Proposed | Implemented

## Context
One paragraph: why this track exists, references Layer 1 + Layer 4 specs.

## Decision
The technique used for this track (rename-via-overlap, bundle-atomic, etc.)
plus any track-specific choices.

## Verification
The check that proves the track succeeded — what runs in CI, what the
acceptance criterion is.

## Consequences
What changes after this track. What the next track depends on.
```

ADRs live in `get_adr_dir()` per Augur convention. They are NOT specs (specs live in `docs/superpowers/specs/`); ADRs are the permanent decision record.

### Verification scripts

Each track ships a verification script in `tests/architecture/`. They run in CI on every PR within the track. Failing verification fails the PR.

| Track | Script | Checks |
|---|---|---|
| Phase 0 | `tests/architecture/test_no_cross_skill_imports.py` | No project module imports another project skill or a vault-private skill |
| Track 1 | `tests/architecture/test_libraries_in_lib.py` | No `from skills.<library>.scripts.` imports remain after the library has been migrated |
| Track 2 | `tests/architecture/test_per_bundle_servers.py` | Each migrated bundle has its own MCP server entry; the monolith doesn't re-advertise those tools |
| Track 3 | `tests/architecture/test_framework_split.py` | `augur-core` and `augur-framework` exist as separate stdio entry points; the old `augur` entry is gone; cross-server discovery works |
| Track 4 | `tests/architecture/test_no_curated_filter.py` | `CURATED_VISIBLE_TOOLS` does not exist; previously-hidden tools are reachable from a fresh client session |

### Migration timeline (rough)

This is descriptive, not prescriptive. The implementation plan will sequence specific tasks.

```
Day 0:        Phase 0 PR (layering cleanup) lands.
Days 1–10:    Track 1 ladder (5 libraries × 4 PRs avg = ~20 small PRs).
Days 1–10:    Track 2 ladder (5 vault bundles × 1 PR each = 5 PRs).
              Tracks 1 and 2 run in parallel.
Day 11:       Track 3 single big PR (framework split).
Day 12:       Track 4 single small PR (visibility filter removal).
Day 13:       Final verification across all three clients.
```

For a single-developer project, "days" are loose calendar units; what matters is the ordering and the per-track gates.

### What this design does NOT specify

- Specific file diffs or task-level pseudo-code — those belong in the implementation plan.
- Cross-bundle dependency resolution at runtime (e.g., what happens if `augur-apple` declares it requires `augur-ingest`). Bundle dependencies aren't part of this migration; they're a future concern when/if the bundle ecosystem gets a dependency manifest.
- Version management for bundles, semver, version pinning, etc. — future concern when bundles become independently distributed.
- Marketplace, package manager, third-party bundle publishing — future concern. This migration only handles bundle directories the user already owns.
- Build-time export pipeline tuning (SKILL.md → `.codex/skills/` etc.). The current export pipeline already exists and is touched by these moves but not redesigned.
- Per-client config schema changes beyond adding/removing server entries. The client config formats themselves are not modified.

## Risks and Trade-offs

### Risks

- **Track 1's `ai` library is the most-imported module in the codebase** (18 importers). Even with rename-via-overlap, the final import-cleanup PR touches a lot of files. Mitigation: that PR is structured as small importer-group sub-PRs, and the verification script catches any forgotten import path.
- **Track 3 is one big PR by necessity** — the protocol-layer split has to happen atomically. Risk is concentrated. Mitigation: structured PR with explicit verification of every claim before merge; rollback is `git revert` and re-run the previous setup.
- **Vault config drift between users** (if Augur ever has more than one user). User-tier configs are per-user; if the bundle directory layout in vault evolves, each user has to update their own config. Acceptable today (single user); a future cycle for multi-user would need bundle-discovery automation.
- **Stale references to the old `augur` MCP name.** Any external tooling that hardcodes the name `augur` (e.g., docs, third-party scripts referencing `mcp__augur__*`) will break in Track 3. Mitigation: a grep-and-replace pass during Track 3 PR; document the rename in the ADR.

### Trade-offs accepted

- **Bundle-atomic moves create momentary risk per bundle.** A bug in the new server means that bundle's tools are dead until rollback. We accept this in exchange for clean state at every commit; the alternative (dual-stack with name duplication) confuses clients more reliably than it protects us.
- **No dual-stack on the protocol layer.** Tools live in exactly one server at any time. We don't run old and new MCP servers in parallel except during Track 1's library overlap (which is at the Python import layer, not the protocol layer).
- **Five ADRs instead of one big migration ADR.** Per-track ADRs add a small documentation cost in exchange for: each track's decision record being independently auditable, future contributors being able to read a single ADR to understand a single decision, and the verification claim being co-located with the decision that depends on it.
- **No marketplace, no version pinning.** This migration doesn't build distribution mechanisms. Bundles will move via `git mv` and live where the user puts them. Future cycles add distribution if/when there's demand.

## Verification — How we know the migration worked

The migration is complete when, simultaneously:

1. **Phase 0 verification passes.** No cross-skill imports, no project references to vault-private skills.
2. **Track 1 verification passes.** No `from skills.<library>.scripts.` imports remain in the codebase. The five `src/lib/*` packages exist and pass tests.
3. **Track 2 verification passes.** Each of the five vault-tier bundles runs as its own MCP stdio server. Dashboard browse + category views show their data unchanged.
4. **Track 3 verification passes.** `augur-core` and `augur-framework` are running. The old `augur` monolith is gone. Cross-bundle discovery works.
5. **Track 4 verification passes.** No `CURATED_VISIBLE_TOOLS`. Three fresh client sessions (Claude Code, Codex, Gemini) all list the same tools.

End-user-observable acceptance criterion: open a fresh Claude Code session, ask it to list emails using `apple-list-emails`. The tool is callable and works. Repeat in Codex and Gemini sessions. The 91%-hidden problem is gone, no proprietary `x-augur-visibility` field is consulted anywhere in the protocol path, and the architecture is uniformly cross-client.
