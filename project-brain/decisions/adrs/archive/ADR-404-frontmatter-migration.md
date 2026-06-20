---
status: Implemented
date: '2026-03-12'
deciders:
- Gur Sannikov
related:
- ADR-163
- ADR-270
- ADR-263
hub: null
tags:
- frontmatter
- migration
- yaml
- markdown
- unified
superseded_by: null
---

# ADR-404: Frontmatter Migration — YAML and Markdown to Unified Frontmatter Format

## Context

Augur stores user data in plain text files for transparency and freedom. Users edit vault files directly in IDEs (Antigravity) and note apps (Obsidian). The current format split creates friction:

- **Pure YAML** (~380 plugin files, ~50 vault files) — machine-readable but invisible in Obsidian's graph view. Users can't tag, search, link, or preview these files naturally. Editing nested YAML is error-prone.
- **Pure markdown** (260 ADRs, vault content) — human-readable but unstructured. LLMs parse them less efficiently without structured metadata fields. ADR metadata is embedded as inline bold text, requiring regex parsing.
- **Markdown + YAML frontmatter** (302 SKILL.md files, prompt templates) — already the established middle ground. Obsidian renders frontmatter as a properties panel. LLMs extract structured fields quickly. Users read and edit the body naturally.

SKILL.md files and prompt templates already prove this format works. This ADR extends the pattern to all user-facing files: ADRs, action definitions, and vault user data.

## Decision

Migrate user-facing files from pure YAML and unstructured markdown to markdown with YAML frontmatter, using a category-by-category approach. Each category converts fully before moving to the next. No dual-format maintenance period.

### File Classification Framework

Every file falls into one of three buckets:

| Bucket | Format | Rule |
|--------|--------|------|
| **Markdown+Frontmatter** | `.md` with `---` YAML header | File has structured metadata AND human-readable content, OR benefits from being browsable in Obsidian |
| **Pure YAML** | `.yaml` | Exclusively machine config with no narrative content AND not browsed in Obsidian |
| **Delete** | removed | Duplicates information elsewhere. Must also trace and fix the generator to prevent re-creation |

**Decision rule**: If a user might open this file in Obsidian to read, edit, or link it — it should be markdown.

### Shared Infrastructure (Phase 0)

A common frontmatter utility in `src/lib/frontmatter_utils.py`, built before all other phases:

- `parse_frontmatter(path)` — splits YAML frontmatter from markdown body
- `load_collection(directory)` — scans directory of `.md` files, returns list of dicts (replaces monolithic YAML loads)
- `write_frontmatter(path, metadata, body)` — serializes with `allow_unicode=True`, `sort_keys=False`, `default_flow_style=False`

### Phase 1: ADRs (260 files)

Convert inline bold metadata (`**Status**: Implemented`) to YAML frontmatter with enhanced fields:

| Field | Type | Notes |
|-------|------|-------|
| `status` | string | Canonical: Proposed, Accepted, Implemented, Deprecated, Superseded |
| `date` | date | ISO YYYY-MM-DD |
| `deciders` | array | Split from comma-separated |
| `related` | array | ADR references |
| `hub` | string/null | Manual curation (null default, assigned where ADR clearly belongs to one hub) |
| `tags` | array | Extracted from title keywords |
| `superseded_by` | string/null | Extracted from "Superseded by ADR-XXX" |

Parser updates:
- `src/lib/adr_utils.py` `scan_adrs()` — primary: frontmatter parsing; fallback: inline bold regex
- `.github/scripts/generate_adr_index.py` — consolidate duplicate `scan_adrs()`, import from `adr_utils` instead
- `docs/decisions/TEMPLATE.md` — updated to frontmatter format

### Phase 2: Action Definitions (~286 files)

Convert `plugins/*/skills/*/assets/actions/*.yaml` (~141) and `~/Vault/Augur/{hub}/{skill}/actions/*.yaml` (~145) from YAML to markdown. Vault-wins precedence preserved.

- `description` field → markdown body (first paragraph)
- `prompt` field → `## Prompt` section in body
- All other fields → frontmatter
- File extension: `.yaml` → `.md`

Primary consumer `src/mcp/augur_mcp/infrastructure/actions.py`: `rglob("actions/*.yaml")` → `rglob("actions/*.md")`. Action-specific `load_action(path)` wrapper re-injects `description` and `prompt` into metadata dict for backward compatibility.

### Phase 3+4: Vault Array Files → Directories

Monolithic YAML arrays explode into directories of individual `.md` files. Phase 3 is a classification checklist (not code) folded into Phase 4 planning.

| Sub-phase | Source | Target | Body field |
|-----------|--------|--------|------------|
| 4A: Tasks | `productivity/eisenhower/tasks.yaml` | `tasks/{id}.md` | `notes` |
| 4B: Jobs | `career/career/job-analyzer/jobs/jobs-*.yaml` | `jobs/{active,inbox,archive}/{slug}.md` | `description` |
| 4C: Recipes | `lifestyle/recipe-manager/recipes/**/*.yaml` | same path `.md` | `ingredients`, `instructions`, `notes` as sections |
| 4D: Health | `health/health/virtual-doctor.yaml` | `virtual-doctor/{symptoms,medications,history}/*.md` | `notes`, `findings` |
| 4E: Finance | `finance/finance/goals.yaml` | `goals/{id}.md` | none (frontmatter-only) |
| 4F: Reviews | `admin/channels/reviews/{pending_reviews,review_history}.yaml` | `{pending,history}/{id}.md` | `summary` + `details` |

Write-path updates: CRUD shifts from "load array → mutate → save array" to "mutate one file → save one file" using `write_frontmatter()` and `Path.unlink()`.

### Phase 5: Delete Duplicates + Fix Generators

Delete `~/Vault/Augur/dev/developer/decisions/long_term.yaml` (mirrors ADR content). Rewire consumers:
- API route (`plugins/dev/skills/developer/augur/api/decisions/route.ts`) → read ADRs directly via frontmatter
- Dashboard widget (`page.tsx:246`) → source from ADR frontmatter data
- Remove "keep decisions in data/" guidance from SKILL.md and README
- Verify no scripts regenerate the file

### Migration Order

```
Phase 0 (frontmatter_utils.py) ──── prerequisite for all
    ├── Phase 1 (ADRs) ──────────────────────────┐
    ├── Phase 2 (Actions) ── parallel with 1 ─────┤
    └── Phase 3+4 (Audit → Array explosion) ──────┤
        Phase 5 (Delete) ── depends on Phase 1 ───┘
```

### Files Staying as YAML

| Category | Count |
|----------|-------|
| `augur.yaml` (skill metadata) | 121 |
| Seed files | 44 |
| Version files | 23 |
| System config | ~15 |
| Dashboard/tool registries | ~10 |
| Integration config | ~5 |
| Pure key-value user config | ~5 |
| Recipe manager settings | 1 |

## Consequences

### Positive

- All user-facing files become first-class Obsidian documents with properties panel, graph links, and search
- LLMs parse structured metadata from frontmatter without regex heuristics
- ADRs gain enhanced queryability (filter by hub, status, tags in Obsidian)
- Monolithic YAML arrays become individually browsable, editable, linkable notes
- Consistent format across vault: SKILL.md, prompt templates, ADRs, actions, user data all use frontmatter
- Decision log duplication eliminated with single source of truth (ADRs)

### Negative

- All consumers of migrated files need updating (parsers, API routes, CRUD code)
- ~260 ADR files + ~286 action files + ~10 vault arrays = large migration surface
- Array explosion increases file count significantly (hundreds of individual `.md` files)
- Manual curation needed for ADR `hub` field (no algorithmic mapping)

### Neutral

- ~224 files stay as YAML (machine config) — no change needed
- Existing SKILL.md and prompt template files are already in target format
- Migration scripts are one-time tools, not permanent infrastructure

## Alternatives Considered

### Alternative 1: Big-Bang Migration Script

Convert everything in one pass with a single Python tool. Rejected: large blast radius, hard to review, all consumers break simultaneously.

### Alternative 2: Format-First, Migrate Later

Update all readers to accept both formats, then migrate files gradually. Rejected: dual-format maintenance burden, never fully "done", reader complexity persists.

## References

- Design spec: `docs/superpowers/specs/2026-03-12-frontmatter-migration-design.md`
- ADR-163: Plugin decentralization
- ADR-270: External vault data separation
- ADR-263: Standardized markdown action instructions
- Obsidian YAML frontmatter docs: Properties panel, graph view integration

## Impact Manifest

```yaml
impact:
  paths_renamed:
    - from: "plugins/*/skills/*/assets/actions/*.yaml"
      to: "plugins/*/skills/*/assets/actions/*.md"
      scope: "all plugin action definitions"
    - from: "~/Vault/Augur/{hub}/{skill}/actions/*.yaml"
      to: "~/Vault/Augur/{hub}/{skill}/actions/*.md"
      scope: "all vault action overrides"
  apis_changed:
    - function: scan_adrs
      module: src.lib.adr_utils
      breaking: true  # now parses frontmatter instead of inline bold
    - function: _collect_skill_action_files
      module: src.mcp.augur_mcp.infrastructure.actions
      breaking: true  # rglob pattern changes from *.yaml to *.md
    - function: list_action_buttons_impl
      module: src.mcp.augur_mcp.infrastructure.actions
      breaking: true  # yaml.safe_load replaced with load_action
    - function: _save_pending
      module: plugins.admin.skills.channels.augur.lib.registry
      breaking: true  # monolithic YAML write → per-file write
    - function: _write_tasks
      module: plugins.productivity.skills.eisenhower.scripts.mcp
      breaking: true  # monolithic YAML write → per-file write
  patterns_deprecated:
    - grep: "\\*\\*Status\\*\\*:.*"
      replacement: "YAML frontmatter status: field"
    - grep: "yaml\\.safe_load.*actions.*\\.yaml"
      replacement: "load_action() with parse_frontmatter()"
  files_affected:
    - glob: "docs/decisions/ADR-*.md"
    - glob: "plugins/*/skills/*/assets/actions/*.yaml"
    - glob: "src/lib/adr_utils.py"
    - glob: ".github/scripts/generate_adr_index.py"
    - glob: "src/mcp/augur_mcp/infrastructure/actions.py"
    - glob: "plugins/admin/skills/channels/augur/lib/registry.py"
    - glob: "plugins/productivity/skills/eisenhower/scripts/mcp/__init__.py"
    - glob: "plugins/dev/skills/developer/augur/api/decisions/route.ts"
    - glob: "plugins/dev/skills/developer/augur/dashboard/tools/page.tsx"
```

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.
> See detailed design spec at `docs/superpowers/specs/2026-03-12-frontmatter-migration-design.md`

**Team name**: `adr-404-frontmatter-migration`

### Phase 0: Shared Infrastructure
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 0.1 | library | medium | Build `parse_frontmatter()`, `load_collection()`, `write_frontmatter()` utilities | `src/lib/frontmatter_utils.py` |
| 0.2 | tester | low | Unit tests for frontmatter round-trip, Unicode, edge cases | `tests/lib/test_frontmatter_utils.py` |

### Phase 1: ADR Migration
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | migrator | medium | Write ADR migration script: extract inline metadata → frontmatter | `scripts/migrate_adrs.py` |
| 1.2 | migrator | medium | Run migration script on all 260 ADRs | `docs/decisions/ADR-*.md` |
| 1.3 | library | medium | Update `adr_utils.py` `scan_adrs()` for frontmatter-first parsing | `src/lib/adr_utils.py` |
| 1.4 | library | low | Consolidate `generate_adr_index.py` to import from `adr_utils` | `.github/scripts/generate_adr_index.py` |
| 1.5 | library | low | Update ADR template to frontmatter format | `docs/decisions/TEMPLATE.md` |
| 1.6 | validator | low | Validate: round-trip all ADRs, regenerate index, diff against original | all ADR files |

### Phase 2: Action Definitions
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | migrator | medium | Write action migration script: YAML → .md with description/prompt in body | `scripts/migrate_actions.py` |
| 2.2 | migrator | medium | Run migration on plugin actions (~141 files) | `plugins/*/skills/*/assets/actions/` |
| 2.3 | migrator | medium | Run migration on vault actions (~145 files) | `~/Vault/Augur/{hub}/{skill}/actions/` |
| 2.4 | library | medium | Write `load_action()` wrapper, update `actions.py` consumers | `src/mcp/augur_mcp/infrastructure/actions.py` |
| 2.5 | validator | low | Validate: action list MCP tool returns same results as before | action consumer paths |

### Phase 3+4: Vault Array Explosion
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | architect | low | Classify all single-record vault YAML files (stays YAML vs Phase 4) | checklist output |
| 4.1 | migrator | medium | Explode tasks YAML → directory of .md files + update `_write_tasks()` | vault tasks + eisenhower MCP |
| 4.2 | migrator | medium | Explode jobs YAML → directory of .md files (3 source files) | vault jobs |
| 4.3 | migrator | medium | Convert recipe YAML → .md files | vault recipes |
| 4.4 | migrator | medium | Explode health YAML → subdirectory structure | vault health |
| 4.5 | migrator | low | Explode finance goals YAML → directory | vault finance |
| 4.6 | migrator | medium | Explode reviews YAML → directory + update ReviewRegistry | vault reviews + registry.py |
| 4.7 | validator | low | Validate: counts match, consumers work, CRUD operations succeed | all vault paths |

### Phase 5: Delete Duplicates + Fix Generators
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 5.1 | library | medium | Rewire decisions API route to read ADRs via frontmatter | `plugins/dev/skills/developer/augur/api/decisions/route.ts` |
| 5.2 | frontend | low | Update dashboard widget to source from ADR data | `plugins/dev/skills/developer/augur/dashboard/tools/page.tsx` |
| 5.3 | cleaner | low | Delete `long_term.yaml`, remove seed data, update SKILL.md/README | vault + plugin docs |
| 5.4 | validator | low | Verify no scripts regenerate deleted files | grep across all plugins |

### Final Phase: Verification
| Step | Agent | Tier | Task |
|------|-------|------|------|
| V.1 | validator | low | Run all tests, verify no regressions |
| V.2 | validator | low | `npm run build` passes |
| V.3 | validator | low | Obsidian spot check: open representative files, verify properties render |
| V.4 | architect | low | Verify ADR intent matches implementation |

### Completion Criteria
- [ ] All phases executed
- [ ] All tests pass
- [ ] No orphaned files or broken references
- [ ] ADR status updated to Implemented
- [ ] ADR index regenerated with new frontmatter-based parser
- [ ] All migrated files render correctly in Obsidian
