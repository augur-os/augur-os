# /adr gaps — Live ADR Gap Analysis (post-archive cleanup)

**Date:** 2026-05-10
**Scope:** 30 ADRs scanned (6 Accepted + 24 Proposed)
**Critical:** 1
**High:** 4
**Medium:** 9
**Low / Trivial:** 2

Two of the 24 Proposed (ADR-548, ADR-549) are placeholder test ADRs (one-line "build src/cool.py" / "build src/api/new_endpoint.py" decisions) — flagged separately at the bottom rather than counted as real gaps.

ADR-587 is internally marked `superseded_by: ADR-561` but its frontmatter status is still `Proposed` — flip to Superseded.

---

## Critical / High gaps (need attention)

### ADR-607 — Wiki Signal Priority and Batched Update (Accepted, 2026-05-10)

This was just accepted and is the freshest decision in the live set. Zero implementation has landed yet — the ADR shipped today.

| # | Requirement | Gap | Severity | Evidence |
|---|---|---|---|---|
| 1 | `config/system/wiki_signals.yaml` | Missing | Critical | `ls config/system/wiki_signals.yaml` → No such file |
| 2 | `wiki_signals_config.py` | Missing | Critical | Not in `shared-vault/skills/ingest/scripts/` |
| 3 | `wiki_tier.py` (tier table + weight resolver) | Missing | Critical | Not in scripts dir |
| 4 | `wiki_tier_caps.py` | Missing | Critical | Not in scripts dir |
| 5 | `wiki_memory_adapters.py` (5 adapters: claude memory, episodic, codex, gemini, copilot) | Missing | Critical | Not in scripts dir |
| 6 | `wiki_extraction_guard.py` (skip-if-unchanged) | Missing | Critical | Not in scripts dir |
| 7 | `run_wiki_batched_daily.py` runner | Missing | Critical | Not in scripts dir |
| 8 | `wiki-batched-daily` task in daemon `tasks.yaml` (06:23 UTC) | Missing | Critical | grep returns 0 hits in `shared-vault/skills/daemon/augur/config/tasks.yaml` |
| 9 | `wiki-update` MCP tool gains `tier` parameter | Missing | Critical | not changed in `wiki_tools.py` |
| 10 | Scanner emits `tier`/`weight` per source | Missing | Critical | not in `wiki_scanner.py` |
| 11 | Vault mtime promotion to `save_events` surface | Missing | Critical | not in scanner |
| 12 | `wiki-status` telemetry block (4 fields) | Missing | Critical | not in `wiki_status.py` |

The ADR has a complete implementation prompt (Phase 1 → Phase 3) baked in and a full impact manifest. The single biggest open ADR action item in the repo today.

---

### ADR-471 — Augur Project Framework (Accepted, 2026-03-22)

Largely implemented — `project.yaml`, `get_project_name()` cache, all path helpers consume it. Two stated decisions remain partial.

| # | Requirement | Gap | Severity | Evidence |
|---|---|---|---|---|
| 1 | `augur init <name>` CLI for bootstrapping new projects | Implemented as `shared-vault/skills/onboard/scripts/augur_init.py` (`init_project()`, `main()`) — works | OK | exists |
| 2 | Extract `augur-ops` plugin for framework-generic operational skills | No `augur-ops` skill exists | High | `ls shared-vault/skills/` — only `loop-ops` (loop-specific) is present; no skill bundle named `augur-ops` |
| 3 | Re-tag base skills `x-augur-plugin: augur` (framework-level) vs `augur-*` (project-specific) | Not visible — ADR text says "framework vs project tags" but the codebase uses `x-augur-group` (`augur_core`, `augur_autoloops`, etc.) per ADR-551 | Medium | This decision substantively superseded by ADR-551's `x-augur-group` enum; ADR-471 should be re-stated or pointed at ADR-551 |

The framework decision is real and shipped — the missing item is the `augur-ops` plugin/skill extraction. Consider closing this out by either (a) creating the `augur-ops` bundle, or (b) declaring that ADR-551's group-tag model satisfies the "framework vs project" partition implicitly.

---

### ADR-578 — Auto ADR Lifecycle Autoloop (Proposed, 2026-04-02)

Nothing on disk. Not even the skill skeleton.

| # | Requirement | Gap | Severity | Evidence |
|---|---|---|---|---|
| 1 | `skills/auto-adr-lifecycle/` skill bundle | Missing | High | no dir under `shared-vault/skills/` or any private vault |
| 2 | `adr_lifecycle_ops.py` with `scan()` + `fix()` | Missing | High | grep finds zero hits |
| 3 | Delete legacy `auto-orphan-plans` and its ops module | Partly: ADR text + SKILL.md note in `shared-vault/skills/ai/SKILL.md` line 201 ("Self-repair needed for auto-adr-lifecycle (formerly auto-orphan-plans)"); a stub category exists in `run_inspection.py:48` referencing `orphan-plans-report` | Medium | `shared-vault/skills/daemon/scripts/adaptive/run_inspection.py:48` still refers to "orphan-plans-report" but no producer module ships it |
| 4 | `docs/generated/orphan-plans-report.md` and `docs/generated/adr-gaps-report.md` | Missing | Medium | not on disk (ironic — this very analysis is the manual fallback) |

The category renaming has happened in metadata only ("formerly auto-orphan-plans"); the actual ops module that would produce the renamed loop's output is absent.

---

### ADR-595 — Brain Email Intake (Proposed, 2026-04-27)

The brain inbox infrastructure exists (`inbox_models.py`, `inbox_consume.py`, `inbox_scan.py`, `inbox_store.py`, `inbox_routing.py` — see ADR-564) but no email source type was added.

| # | Requirement | Gap | Severity | Evidence |
|---|---|---|---|---|
| 1 | Source record `type: email`, `adapter: apple_mail \| gmail` in inbox runtime | Missing | High | grep `email\|adapter\|apple_mail` against ingest scripts → 0 hits |
| 2 | Apple Mail adapter (Phase 1) | Missing | High | no `email_*.py` or `apple_mail*.py` adapter file exists |
| 3 | Link classifier (`article_resource`, `downloadable_file`, `internal_app`, `unsupported_or_noisy`) | Missing | High | no classifier helper |
| 4 | Aftercare archive to "Augur Consumed" destination | Missing | High | no aftercare hook |
| 5 | Apple/Google integration skills promoted from draft to private skills folder | Cannot verify (vault-side) | Low | external-vault dependency stated explicitly in ADR |

Phase 1 not started.

---

### ADR-566 — Split auto-security-audit vs auto-skill-quality (Proposed, 2026-04-28)

The security loop still owns the housekeeping checks the ADR moves out.

| # | Requirement | Gap | Severity | Evidence |
|---|---|---|---|---|
| 1 | License check in `s4_integrity.py` | Still in security scanner | High | `shared-vault/skills/loop-security/scripts/s4_integrity.py:94-103` still does `Check x-augur-license` and emits `category_name: "missing-license"` |
| 2 | Equivalent license check added to skill-quality scanner | Missing | High | `shared-vault/skills/loop-quality/scripts/` has `checks.py`, `lint.py`, `format.py`, `scorer.py`, `ui_quality.py`, `visual.py`, `yaml_lint_ops.py`, `fixers.py` — no `skill_quality.py`; no missing-license/commands-declared check |
| 3 | S5 commands-declared moved to skill-quality | Not started | High | analogous gap |
| 4 | Frontmatter completeness moved to `auto-skill-md` | Not started | Medium | no evidence of move |
| 5 | `auto-security-audit` trust state reset | Cannot verify here, but blocked on items 1-3 | Medium | n/a |

---

## Medium gaps (Proposed, work pending)

### ADR-484 — Page Consolidation (Proposed, 2026-03-23)

Partial: the `observe` hub has been dissolved (target met; no `apps/dashboard/app/observe`). `ActionBar` and `DataList` exist (`apps/dashboard/components/blocks/`). The remaining 10 of 12 named shared components are missing as named:

| Missing | StatGrid, DataTable, StatusBadge, SearchFilter, PageHero, CollapsibleSection, NavLinkGrid, LightControlCard, SceneQuickButtons, PageStates |
|---|---|

Path is wrong too — ADR specifies `skills/dashboard/components/shared/`; the codebase uses `apps/dashboard/components/{blocks,shared}/`. The dashboard architecture moved to `@/` + `@/features/` aliases (ADR-490), so this ADR's pathing is stale.

Recommendation: either re-spec to match the current architecture, or close as superseded by the ADR-490 partition.

### ADR-485 — MCP Health Audit (Proposed, 2026-03-23)

Implemented but in a different home than the ADR specifies. Files exist:
- `shared-vault/skills/loop-ops/scripts/mcp_health_audit.py`
- `shared-vault/skills/loop-ops/commands/auto-mcp-health-audit.md`
- `shared-vault/skills/loop-ops/evals/auto-mcp-health-audit-evals.json`

ADR specified `skills/auto-mcp-health-audit/`. This is a path mismatch but the substance is on disk. Status flip to Implemented is plausible if the relocation under `loop-ops` is the canonical home.

The ADR's last item ("retire `auto-mcp-hygiene` stub") — `shared-vault/skills/daemon/commands/auto-mcp-hygiene.md` still exists.

### ADR-486 — Venture Hub Consolidation (Proposed, 2026-03-23)

Dead. The dashboard hub list has been radically narrowed — only `brain` and `(views)/browse` are mounted at app top level. There is no `venture/`, no `business/`, no `career/` directory. `business-expert` and the 7 new YAML data dirs (`analytics`, `market`, `positioning`, `content`, `outreach`, `contracts`, `financials`) do not exist.

ADR-573 (Studio Consolidation) shows the same pattern — large hub-rebuild ADRs against a hub that has since been removed entirely.

Recommendation: close as Cancelled. The hub model the ADR plans for is no longer the architecture.

### ADR-487 — Service Design Guidelines (Proposed, 2026-03-23)

`apps/dashboard/lib/services/` does not exist. ADR is doc-only guidance ("services live in this dir, follow this pattern"); without any services folder there is nothing for the rule to apply to. Rule 11 in CLAUDE.md ("Dashboard uses MCP, not direct local execution") covers most of the substance.

Recommendation: low-priority, or close as superseded by CLAUDE.md rule 11.

### ADR-499 — Architecture Review Phases 1-3 (Proposed, 2026-03-24)

Mostly done.
- Phase 1a (vault elimination) — `docs/agent-topics/agent-rules.md` exists.
- Phase 2 (plugin tool loading) — `get-plugin-load-status` MCP tool exists at `src/mcp/augur_framework/tools/domain/plugins.py:648`.
- Phase 3 (RAG unification) — `src/lib/index/unified_indexer.py` exists; `rag_indexer.py` is gone (consolidated).
- Phase 1b (remote execution wiring + settings UI) — partial; no `useActionRunner` remote-mode evidence found.

Status flip to Implemented is reasonable, with Phase 1b (remote execution) as a remaining sub-item if it was actually shipped. Verify locally.

### ADR-503 — Distribution Plugins (Obsidian / VS Code) (Proposed, 2026-03-24)

Partial. `scripts/install.sh` accepts `--from <source>` — implemented (lines 7, 13, 577, 600). Missing:
- `dist/platform-plugins/` directory tree
- Obsidian plugin codebase
- VS Code extension codebase
- `dist/platform-plugins/lib/health.ts` shared library

The two market-side artifacts are absent. Likely held back from the Apr 20 launch window.

### ADR-535 — Dashboard UX Hardening for Launch (Proposed, 2026-04-06)

Substantially implemented. Welcome banner storage key wired (`apps/dashboard/app/(views)/browse/page.tsx:33` references `WELCOME_STORAGE_KEY = "augur-welcome-dismissed"`), session reconnect/detach implemented (`apps/dashboard/app/api/cli/actions.ts` references `detachSession`, `detachTimer`, `entry.detached`, with explicit ADR-535 0E comment at line 422). Status flip to Implemented is reasonable; spot-check the chat-panel sub-tasks (0G–0M) before flipping.

### ADR-536 — Website Positioning Refresh (Proposed, 2026-04-06)

External — files live at `~/Projects/Au-docs/venture-augur/website-working/`. The dir has the expected files (`index.html`, `enterprise.html`, `course.html`, `more.html`). Cannot verify copy changes without diffing against the ADR's specified text. This ADR's surface is outside this repo.

### ADR-537 — Open Source Launch Execution (Proposed, 2026-04-06)

Partial. `packages/create-augur/` exists with `package.json`, `index.js`, `README.md` (Phase 1 done). Demo video, GitHub Discussions, README polish, social-preview update, CHANGELOG drafting are external/launch-coordination items not verifiable here.

### ADR-540 — Browse Workbench Redesign (Proposed, 2026-04-07)

Partial. `BrowseDetailPanel` and `ScheduledExecutionDetailPanel` exist (`apps/dashboard/components/shared/`); `apps/dashboard/app/(views)/browse/page.tsx` imports both at lines 8-9 and renders them at lines 490, 495. The "three-zone Split Workbench" with persistent left rail + center + right is partially expressed but not the dominant browse shape today. Acceptable partial status.

### ADR-541 — Browse Taxonomy / Visibility / Logs (Proposed, 2026-04-09)

Implemented. Dev-only category filter exists in `apps/dashboard/app/(views)/browse/useBrowseState.ts:451` (`BROWSE_CATEGORIES.filter((c) => !c.devOnly || isDev)`); the cli-commands → commands rename is reflected in `src/mcp/augur_framework/tools/infrastructure/browse/__init__.py:141` which still uses `name="list-cli-commands"` for the MCP tool but returns `"commands"` keyed payload (`cli.py:141`). Status flip to Implemented is reasonable; the `list-cli-commands` MCP tool name lag is a minor follow-up.

### ADR-573 — Studio Hub Consolidation (Proposed, 2026-03-20)

Studio hub doesn't exist on disk. `find -path "*pages/studio*" -name "page.tsx"` → 0 hits. The hub was removed entirely, not consolidated to 5 pages.

Recommendation: close as Cancelled or Superseded — the consolidation did not happen as designed; the hub was retired instead.

### ADR-587 — Wiki Backlog Worker and Page Quality (Proposed, 2026-04-14)

The ADR text itself states `superseded_by: ADR-561` and explicitly says "Historical, not implemented as designed." Frontmatter still lists `status: Proposed` and `superseded_by: ADR-561`. Frontmatter should be `status: Superseded`.

---

## Low / placeholder ADRs

### ADR-548 — Cool Feature

```
Context: We need a cool feature.
Decision: Build src/cool.py.
```

Body is one sentence. `src/cool.py` does not exist. This looks like a doctest/template artifact that escaped into the ADR set. Recommendation: delete or move to `docs/adrs/archive/` as a placeholder.

### ADR-549 — New API Design

```
Context: We need a new API endpoint.
Decision: Build src/api/new_endpoint.py.
```

Same situation. `src/api/new_endpoint.py` does not exist. Likely created as ADR generator smoke output. Same recommendation as 548.

---

## Status flip recommendations

ADRs that look fully implemented despite being labeled Proposed/Accepted — recommend flipping to **Implemented**:

- **ADR-478** Browse Index Freshness — `last_indexed` aggregation lives at `src/mcp/augur_framework/tools/infrastructure/browse/index.py:451-605`; `getStalenessLevel` widely consumed; freshness banner wired.
- **ADR-492** Type-Aware Skill Scoring — `RUBRICS`, `_resolve_rubric`, `_read_behavioral`, `_compute_tier` all in `src/lib/skill_scorer.py`; `stamp_import_metadata` in `src/lib/frontmatter_utils.py:357`; full ADR contract on disk.
- **ADR-524** Skill Ownership — `ownership` field threaded through `src/plugins/skill_discovery.py` (96, 287, 292, 472, 498); `src/mcp/augur_core/tools/core/skill_lifecycle.py` exists.
- **ADR-541** Browse Taxonomy — dev-only filter live in `useBrowseState.ts`; backend categories carry `commands`/`logs`. Minor cosmetic gap (`list-cli-commands` MCP tool name) is not blocking.
- **ADR-550** Windows Hardening — `SupportedPlatform` literal + `OPS_CAPABILITIES.platforms` contract in `src/lib/ops_protocol.py:31-154`; `ci-cross-platform.yml` workflow on disk.
- **ADR-551** Skill Group/Release — `x-augur-group` and `x-augur-release` are in skill SKILL.md frontmatter (`augur-core`, `loop-wiring`, `document-extractor` confirmed); `src/lib/release_workspace.py` exists.
- **ADR-563** Vault-Owned User Skills/Pages/Drafts — `get_vault_drafts_dir()` and `get_shared_vault_drafts_dir()` exist (`src/config/paths.py:477, 535`); `staging/` removed from repo root.
- **ADR-564** Open-Source Brain Inbox — `inbox-folders`, `inbox-scan-folder`, `inbox-consume-folder`, `brain-insights` MCP tools all wired in `shared-vault/skills/ingest/SKILL.md` and tests; `apps/dashboard/features/pages/brain/{inbox,insights}` directories exist.
- **ADR-572** Loop Coverage — Remediation 1 (self-heal main-checkout gate) implemented at `shared-vault/skills/daemon/scripts/ops/self_heal.py:43, 178`; Remediations 2-4 explicitly deferred in the ADR text (not gaps).
- **ADR-535** Dashboard UX Launch — see Medium section.
- **ADR-499** Arch Review Phases 1-3 — see Medium section, modulo Phase 1b.

Status flips that should be **Cancelled** or **Superseded** (work won't happen, hub structure has moved on):

- **ADR-486** Venture Hub Consolidation — venture/business/career hubs no longer exist in dashboard.
- **ADR-573** Studio Consolidation — studio hub removed entirely; consolidation did not occur.
- **ADR-587** Wiki Backlog Worker — body says superseded by ADR-561; frontmatter should match.
- **ADR-548** / **ADR-549** — placeholder/test ADRs; delete or move to archive.
- **ADR-484** Page Consolidation — partly delivered; remaining items conflict with ADR-490 framework partition; consider re-spec.
- **ADR-487** Service Design Guidelines — superseded by CLAUDE.md rule 11; close as Adopted/Superseded.

---

## ADRs with no real gaps found

- ADR-478, ADR-492, ADR-524, ADR-550, ADR-551, ADR-563, ADR-564, ADR-572 (with R1 only as scoped), ADR-541, ADR-499 (modulo Phase 1b)

These should be flipped to Implemented; see the status-flip section above.

---

## Summary table

| ADR | Status today | Recommended action |
|---|---|---|
| ADR-471 | Accepted | Close out `augur-ops` plugin extraction or re-state vs ADR-551; flip when done |
| ADR-478 | Accepted | Flip to Implemented |
| ADR-484 | Proposed | Re-spec or close (path conflict with ADR-490) |
| ADR-485 | Proposed | Flip to Implemented (relocated under loop-ops); retire auto-mcp-hygiene stub |
| ADR-486 | Proposed | Cancel — hub doesn't exist |
| ADR-487 | Proposed | Close as superseded by CLAUDE.md rule 11 |
| ADR-492 | Accepted | Flip to Implemented |
| ADR-499 | Proposed | Flip to Implemented; verify Phase 1b separately |
| ADR-503 | Proposed | Implement Obsidian/VS Code plugin codebases or defer explicitly |
| ADR-524 | Accepted | Flip to Implemented |
| ADR-535 | Proposed | Flip to Implemented after spot-check of 0G-0M chat fixes |
| ADR-536 | Proposed | External; verify on next website rebuild |
| ADR-537 | Proposed | Phase 1 done; rest is launch coordination, defer |
| ADR-540 | Proposed | Partial; defer or split |
| ADR-541 | Proposed | Flip to Implemented |
| ADR-548 | Proposed | Delete / archive — placeholder |
| ADR-549 | Proposed | Delete / archive — placeholder |
| ADR-550 | Proposed | Flip to Implemented |
| ADR-551 | Proposed | Flip to Implemented |
| ADR-563 | Proposed | Flip to Implemented |
| ADR-564 | Accepted | Flip to Implemented |
| ADR-566 | Proposed | High priority — implement housekeeping move from S4/S5 to skill-quality |
| ADR-572 | Proposed | Flip to Implemented (R1 only, R2-4 explicitly deferred) |
| ADR-573 | Proposed | Cancel — studio hub removed |
| ADR-578 | Proposed | High priority — implement auto-adr-lifecycle skill |
| ADR-581 | Proposed | Flip to Implemented |
| ADR-582 | Proposed | Substantially done; flip to Implemented after spot-check of sync loop |
| ADR-587 | Proposed | Flip to Superseded by ADR-561 (per body) |
| ADR-595 | Proposed | High priority — Phase 1 not started |
| ADR-607 | Accepted | Critical — full implementation is open work, has Implementation Prompt baked in |
