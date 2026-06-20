---
title: "Skill Resolvability and MECE Coverage Audit"
date: 2026-05-13
status: draft
scope: design
authors:
  - gsannikov
related:
  - ADR-741
  - ADR-734
  - ADR-742
  - docs/superpowers/plans/2026-05-13-gbrain-borrow-slate.md
  - shared-vault/skills/auto-skill-quality
  - config/system/capability_exposure.yaml
  - docs/references/surface-decision-matrix.md
tags:
  - skills
  - audit
  - quality
  - capabilities
  - mece
---

# Skill Resolvability and MECE Coverage Audit

## 1. Problem

Augur ships 130+ skills, each declaring intent triggers via `description:`, `x-augur-tags:`, and command surfaces in `config/system/capability_exposure.yaml`. There is no automated audit that confirms:

1. Every declared intent is reachable by at least one command surface (CLI / MCP / dashboard / browse). Some intents may be declared in a skill's `description:` but never wired to a surface — silent orphans.
2. Two or more skills do not silently claim overlapping intents without explicit ownership. As the skill catalog grows, intent-overlap drift is a real risk.
3. `capability_exposure.yaml` entries point to skills/tools that still exist. Stale entries accumulate as skills are renamed or removed.
4. Skills are not orphaned — declaring triggers but reachable via no surface at all.

`auto-skill-quality` currently lints **individual skills** for SKILL.md schema, frontmatter, and test conventions. It does NOT perform **global coverage analysis** across the catalog.

The gbrain reference implementation calls this audit `check-resolvable`. It validates resolver reachability, MECE coverage, and routing gaps. The pattern adapts cleanly to Augur because Augur's analogue of gbrain's RESOLVER.md is `capability_exposure.yaml` + per-skill `description:` triggers.

## 2. Goals

- Add a `check-resolvable` audit step inside the existing `auto-skill-quality` auto-loop.
- Audit runs nightly; produces a JSON report under `get_runtime_dir()/quality/resolvable-report.json` (rebuildable runtime state, not durable).
- Detect and report:
  - **Unrouted intents** — declared triggers not reachable by any command surface
  - **Routing collisions** — two or more skills claiming overlapping triggers without explicit ownership
  - **Orphaned skills** — skills declaring triggers but with no surface entries at all
  - **Stale capability entries** — `capability_exposure.yaml` entries pointing to non-existent skills or tools
- Audit findings surfaced in dashboard `dev` browse category under "Skill Coverage."
- New MCP tool `skill-resolvable-report` (CLI default; opt in to MCP via dashboard).
- Audit is **report-only initially**; flips to CI-blocking after one stabilization release (post-merge of this ADR).

## 3. Non-Goals

- No automated routing fix. The audit reports; the human (or AI client) decides scope.
- No LLM-based intent overlap detection. **Deterministic** string and tag analysis only — keeps with Rule #19 ("deterministic work is cheap, judgment is dear") and zero token cost.
- No replacement of `auto-skill-quality`. This is a new audit step **inside** that loop.
- No enforcement of MECE strictness beyond reporting. Some overlap may be intentional (e.g. two skills both handling "search" with different scopes); the system surfaces it, the user decides.
- No new dashboard page — finding surface is one card in the existing `dev` browse category.

## 4. Design

### 4.1 Algorithm

**Inputs:**
- Every `SKILL.md` under `shared-vault/skills/` and the configured private vault `skills/` root.
- `config/system/capability_exposure.yaml`.
- `config/system/command_surfaces.yaml` (per Rule #30, the canonical cross-OS command surface declaration).

**Per-skill extraction:**

```python
{
  "skill_id": str,                        # from path or x-augur-config.id
  "hub": str,                             # from x-augur-hub
  "description_phrases": list[str],       # split description; lowercased; stop-words removed; n-grams kept
  "tags": list[str],                      # from x-augur-tags
  "declared_commands": list[str],         # from x-augur-commands
  "declared_mcp_tools": list[str],        # from x-augur-mcp-tools
  "declared_dashboard_pages": list[str],  # from x-augur-dashboard-pages
}
```

**Per-surface extraction:**

```python
{
  "tool_id": str,                         # from capability_exposure.yaml key
  "primary_surface": str,                 # cli / mcp / dashboard / browse / ...
  "export_to": list[str],
  "owner_skill": str,                     # parsed from owner_kind / management hints
}
```

**Detection passes:**

1. **Unrouted intents**: For each skill, check that at least one declared command / mcp tool / dashboard page has a matching entry in `capability_exposure.yaml`. Missing = unrouted.
2. **Routing collisions**: Build an index `phrase → list[skill_id]` from `description_phrases` ∪ `tags`. For each phrase mapping to ≥2 skills, check whether `capability_exposure.yaml` declares explicit ownership (a designated `primary_skill` field or analogous). If not, it's a collision.
3. **Orphaned skills**: Skills with zero declared surfaces or zero surfaces present in `capability_exposure.yaml`.
4. **Stale capability entries**: Entries in `capability_exposure.yaml` whose `owner_skill` does not appear among the scanned skills (or whose tool name does not appear among any skill's `x-augur-mcp-tools`).

### 4.2 Report shape

`get_runtime_dir()/quality/resolvable-report.json`:

```json
{
  "generated_at": "2026-05-13T03:00:00Z",
  "auditor_version": "1.0",
  "summary": {
    "skills_scanned": 137,
    "surfaces_scanned": 412,
    "findings": {
      "unrouted_intents": 4,
      "routing_collisions": 2,
      "orphaned_skills": 1,
      "stale_capability_entries": 8
    }
  },
  "findings": {
    "unrouted_intents": [
      {"skill_id": "career", "intent_phrase": "growth tracking", "remediation": "Add a command or MCP tool that matches; or remove the phrase."}
    ],
    "routing_collisions": [
      {"phrase": "search", "skill_ids": ["knowledge", "scraper"], "remediation": "Declare ownership in capability_exposure.yaml or differentiate descriptions."}
    ],
    "orphaned_skills": [
      {"skill_id": "experimental-x", "remediation": "Wire a surface or move to /staging."}
    ],
    "stale_capability_entries": [
      {"tool_id": "mcp-tool:gone-tool", "remediation": "Remove from capability_exposure.yaml."}
    ]
  }
}
```

### 4.3 Integration with `auto-skill-quality`

The audit is a new step inside the existing `auto-skill-quality` auto-loop. Failure mode:

- **Phase 1 (this ADR's initial ship)**: `report-only`. The loop produces the report; the loop result is green regardless of findings.
- **Phase 2 (one release later)**: `block-on-high-severity`. If any orphaned skills or routing collisions exist, the loop fails. Unrouted intents and stale entries remain warnings.

### 4.4 MCP tool

`skill-resolvable-report`:

- Returns the latest report content.
- Surface: CLI by default per surface-decision-matrix. Opt in to MCP via dashboard for the dashboard card to consume it.

### 4.5 Dashboard surface

`/dev` browse category gains a "Skill Coverage" card:

- Big-number summary (findings counts).
- Click → detail page showing the four finding categories with per-item remediation hints.
- Card data fetched via `useMcpQuery('skill-resolvable-report', 'skill-resolvable-report', 'static')`.

### 4.6 Performance

Initial scan reads ~140 SKILL.md files + 1 capability yaml + 1 command-surfaces yaml. Pure file I/O, no network. Expected runtime: <2 seconds on a developer laptop. No caching needed in v1.

## 5. Boundary

- Pure Python stdlib + PyYAML.
- No LLM calls.
- No mutations — read-only audit. The MCP tool is read-only.
- Report path is under `get_runtime_dir()`; never the repo, never the vault.

## 6. Open Questions

| # | Question | Tentative answer |
|---|---|---|
| 1 | What counts as a "phrase" for collision detection? | Bigrams + tags. Single words match too noisily; trigrams miss too easily. |
| 2 | Should the audit run on every `/auto-skill-quality` invocation, or only nightly? | Both — fast enough to run inline; nightly run produces the canonical report consumed by the dashboard. |
| 3 | How to handle the auditor finding issues in `auto-skill-quality` itself? | Self-report — treat the auditor's own skill as auditable; just note the meta-finding in the report. |
| 4 | Should v1 surface findings via slack/email/notification? | No. Dashboard card + JSON report is enough. Notifications are a follow-up. |

## 7. Acceptance criteria (mirrored in the plan)

- [ ] `shared-vault/skills/auto-skill-quality/scripts/check_resolvable.py` exists and is importable.
- [ ] `skill-resolvable-report` MCP tool is registered.
- [ ] Running the audit produces a valid JSON report at `get_runtime_dir()/quality/resolvable-report.json`.
- [ ] The auditor finds at least one real finding on the current Augur skill catalog (sanity check — the catalog has known unrouted/stale entries).
- [ ] Dashboard `/dev` browse category renders the "Skill Coverage" card.
- [ ] `auto-skill-quality` loop run includes the new step and reports findings without failing in v1.
- [ ] Tests cover: phrase extraction, surface enumeration, each of the 4 detection passes, report serialization.
