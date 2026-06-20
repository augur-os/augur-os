---
status: Implemented
date: '2026-02-11'
deciders:
- User
- Claude Code
related: []
hub: null
tags:
- crew
- bundle
- hardening
- quality
- relevance
superseded_by: null
---

# ADR-075: Crew Bundle Hardening — Quality, Relevance & Consolidation

## Context

An audit of all 8 crew skills (`plugins/dev/skills/`) revealed systemic quality issues and low augur-specific relevance:

**Quality issues:**
- **Bundle composite score: 49/100** (major-rebuild)
- **0/8 SKILL.md files** meet the <100 line guideline (range: 142–447 lines)
- **480+ lines of duplicated tiering boilerplate** across all SKILL.md files (38% waste)
- **13 hardcoded paths** reference the deleted `~/Projects/augur-data/` directory
- **7/8 skills lack dashboard.yaml** — invisible in dashboard UI
- **3 non-existent skills** referenced ("oss-manager", "data-engineer", "design-system")

**Augur-specific relevance gaps:**
- Most crew skills are **generic coding tools** — they'd work on any codebase, not augur-aware
- Only mcp-app-factory understands augur's plugin/bundle/chain structure
- No skill scans `data/` for security issues (PII, credentials in YAML)
- No skill validates plugin compliance (SKILL.md format, dashboard.yaml syntax)
- No skill verifies chain health (dependency resolution, step ordering)
- No skill checks plugin file mounting (source → dashboard sync)
- No skill audits the memory system (MEMORY.md format, daily log health)

**Data directory audit** (`plugins/dev/`):

| Skill | Data Files | Key Contents |
|-------|-----------|--------------|
| analyst | 12 | Prompts, complexity reports, telemetry, eval harness |
| architect | 10 | Vision configs, retrospectives, productization plans |
| developer | 4 | Action templates, test references |
| frontend | 56 | Hardening reports, design audits, page metrics, plans |
| devops | 19 | Infrastructure configs, deployments, setup guides, incidents |
| validator | 11 | QA checklists, structure rules, retrospectives |
| security | 1 | Single audit from Jan 2026 |
| mcp-app-factory | 94 | Plugin workflows, checkpoints, backups, generation configs |

### Audit Scores (per skill)

| Skill | Lines | Scripts | LOC | SKILL.md | Scripts | Paths | Relevance | Composite |
|-------|-------|---------|-----|----------|---------|-------|-----------|-----------|
| developer | 183 | 13 | 3,176 | 4/10 | 8/10 | 2/10 | 9/10 | 50 |
| devops | 189 | 40 | 12,158 | 3/10 | 8/10 | 2/10 | 9/10 | 44 |
| frontend | 240 | 16 | ~5,500 | 3/10 | 8/10 | 2/10 | 8/10 | 49 |
| validator | 261 | 13 | ~4,000 | 3/10 | 8/10 | 2/10 | 8/10 | 49 |
| analyst | 157 | 20 | 6,768 | 4/10 | 9/10 | 2/10 | 7/10 | 50 |
| architect | 142 | 8 | ~2,000 | 4/10 | 7/10 | 2/10 | 7/10 | 46 |
| security | 212 | 6 | ~1,500 | 4/10 | 7/10 | 2/10 | 7/10 | 50 |
| mcp-app-factory | 447 | 61 | 25,737 | 2/10 | 9/10 | 7/10 | 5/10 | 51 |

## Decision

### Part A: Structural Cleanup (Organization)

#### A1. Extract src/lib tiering config

Create `plugins/dev/src/lib/tiering-profiles.yaml` with the standard 3-tier config. Each SKILL.md references it via a one-liner instead of 60+ inline lines.

#### A2. Fix all outdated paths

Replace 13 instances of `~/Projects/augur-data/` with correct paths. Storage references become `plugins/dev/{skill}/`.

#### A3. Trim all SKILL.md to <100 lines

Remove inline tiering/safety/alignment boilerplate, extract methodology docs to `modules/`, remove dead skill references, mark aspirational features with `TODO_IMPROVE`.

#### A4. Merge low-frequency advisory skills

**analyst + architect → `advisor`**: Both read-only advisory agents. Combined scope: "Analyze, design, evaluate."

**security → folds into `validator`**: Both quality/assurance focused. Expanded scope: "Test, audit, secure, verify."

#### A5. Data directory restructuring

Merge data directories alongside skill merges:

| Source | Destination | Files | Action |
|--------|------------|-------|--------|
| `plugins/dev/analyst/` | `plugins/dev/advisor/analytics/` | 12 | Move: prompts, telemetry, eval harness, complexity reports |
| `plugins/dev/architect/` | `plugins/dev/advisor/design/` | 10 | Move: vision configs, retrospectives, productization plans |
| `plugins/dev/security/` | `plugins/dev/validator/security/` | 1 | Move: audit report |

Devops data directory stays at `plugins/dev/devops/` (scripts move, data stays with skill ownership). MCP health data moves with scripts to `plugins/ai/daemon/mcp-health/` if any runtime artifacts exist.

#### A6. Slim down devops (40 → ~20 scripts)

- Move MCP health monitoring → `daemon` skill
- Move IDE integration health → `ai_bridge` skill
- Move context budget tracking → `observe` skill

#### A7. Slim down mcp-app-factory (447 → <100 line SKILL.md)

Extract service design guidelines to `docs/guides/service-design.md`, decision frameworks to `modules/`.

#### A8. Add dashboard.yaml for crew skills

All 5 skills needing config mount under `/control` hub (dev mode) as tabs.

### Part B: Augur-Specific Skill Improvements

These are concrete new capabilities that make each crew skill **augur-aware** rather than generic.

#### B1. advisor (new merged skill) — System Intelligence

| Feature | What It Does | Script/Command |
|---------|-------------|----------------|
| **Skill health dashboard** | Score every skill on completeness (SKILL.md, scripts, tests, dashboard.yaml, data dir) and flag gaps | `scripts/analytics/skill_health_score.py` |
| **Chain dependency audit** | Parse all chain YAML files, verify referenced skills/scripts exist, detect broken step ordering | `scripts/design/audit_chains.py` |
| **Memory system health** | Validate MEMORY.md format, check daily log pipeline, detect curator dedup failures, report staleness | `scripts/analytics/memory_audit.py` |
| **Cost-per-skill reporting** | Aggregate token usage by skill/chain from telemetry, identify expensive patterns | Already exists in analyst scripts, expose as action |

#### B2. developer — Augur-Aware Implementation

| Feature | What It Does | Script/Command |
|---------|-------------|----------------|
| **Data schema migration safety** | When editing YAML files in `data/`, auto-backup before changes, validate schema post-edit, detect orphaned data files | `scripts/data_migration_safety.py` |
| **Plugin-aware refactoring** | When renaming a skill, auto-update: registry.yaml, CLAUDE.md, dashboard.yaml, chain references, agent-workflows, all IDE configs | `scripts/augur_refactor.py` |
| **Remove RALPH loops** | Delete experimental RALPH loop code and references (never used, adds complexity) | Cleanup task |

#### B3. devops — Augur Infrastructure

| Feature | What It Does | Script/Command |
|---------|-------------|----------------|
| **Plugin dependency graph** | Map which skills depend on which services, detect circular deps, visualize in dashboard | `scripts/plugin_dependency_graph.py` |
| **Full-system nightly** | Extend nightly to check: all SKILL.md <100 lines, all dashboard.yaml valid, all chains resolve, all data dirs have README | `scripts/augur_nightly_checks.py` |
| **Data backup/restore** | Snapshot `data/` directory before major operations, one-command restore | `scripts/data_backup.py` |

#### B4. frontend — Dashboard-Specific

| Feature | What It Does | Script/Command |
|---------|-------------|----------------|
| **Plugin mount verification** | Cross-reference `src/dashboard/app/` auto-generated files with plugin sources, detect stale mounts, warn on direct edits | `scripts/verify_plugin_mounts.py` |
| **Action button wiring check** | For every `flow: llm` / `flow: fast` action in dashboard.yaml, verify the target script/chain exists and is callable | `scripts/verify_action_wiring.py` |
| **Hub completeness audit** | For each hub, check: every tab has page.tsx, every action has handler, overview tab exists, no broken cross-hub links | Already partially in `dashboard_hardening_audit.py`, formalize |

#### B5. validator (expanded with security) — Augur Quality Gate

| Feature | What It Does | Script/Command |
|---------|-------------|----------------|
| **Plugin compliance testing** | Validate plugin structure: SKILL.md format, dashboard.yaml schema, required fields, dependency resolution, data dir layout | `scripts/validate_plugin_compliance.py` |
| **Data directory security scan** | Scan `data/` for: hardcoded paths, PII in YAML, plaintext credentials, API keys in configs, exposed secrets | `scripts/security/scan_data_directory.py` |
| **MCP config validation** | Validate `mcp_tool_groups.yaml` syntax, verify tool references resolve, check server registration consistency | `scripts/security/validate_mcp_config.py` |
| **Pre-merge augur gate** | Combined check before merge: plugin compliance + security scan + chain resolution + mount verification | `scripts/augur_pre_merge.py` |

#### B6. mcp-app-factory — Already Augur-Specific

No new features needed. This skill is already the most augur-aware. Focus on documentation trimming only.

## Consequences

### Positive

- 8 skills → 6 skills (cleaner mental model)
- SKILL.md files drop from avg 229 lines to <100 lines
- 480+ lines of boilerplate eliminated via src/lib config
- **Every crew skill becomes augur-aware** — understands plugins, chains, data/, MCP, dashboard.yaml
- Data directories consolidated alongside skill merges (no orphaned data)
- New pre-merge quality gate catches augur-specific issues (broken chains, stale mounts, data PII)
- All crew skills visible in dashboard

### Negative

- Merge migrations require updating all references (chains, registry, agent-workflows, data dirs)
- advisor is a new name — existing chains referencing "analyst" or "architect" need updates
- Part B features need implementation time (12 new scripts across 5 skills)
- Data dir moves risk breaking scripts that hardcode paths to `plugins/dev/analyst/`

### Neutral

- Existing script code doesn't change — only organizational structure and documentation
- mcp-app-factory keeps its 61 scripts (real code, just needs better docs)
- Data content is preserved — only directory structure changes

## Alternatives Considered

### Alternative 1: Keep all 8 skills, documentation-only fixes

Fix paths and trim SKILL.md but don't merge or restructure. Rejected because the analyst/architect split and security/validator split create artificial boundaries that confuse scope.

### Alternative 2: Aggressive merge to 4 skills

Merge developer+frontend, analyst+architect+security, devops+validator, keep mcp-app-factory. Rejected because developer and frontend have clearly different expertise domains (Python vs TypeScript), and devops+validator mixes CI concerns with testing concerns.

### Alternative 3: Skip augur-specific improvements

Just do structural cleanup without Part B. Rejected because the core problem is that crew skills are generic — cleanup without augur-awareness means they remain interchangeable with any coding assistant's tools.

## References

- Data path consolidation: commits 494b0542, 5e55f005
- SKILL.md guideline: CLAUDE.md ("Write SKILL.md <100 lines")
- Plugin self-containment: ADR-018
- Tiering system: ADR-019
- Crew skill consolidation: ADR-050
- Build ≠ UI works lesson: [2026-02-11 memory entry]

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.

**Team name**: `adr-075-crew-hardening`

### Phase 1: Shared Config & Path Fixes
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | medium | Create `plugins/dev/src/lib/tiering-profiles.yaml` with 3-tier config extracted from any crew SKILL.md. Include low/medium/high tiers with tools, max_files, capability fields | `plugins/dev/src/lib/tiering-profiles.yaml` |
| 1.2 | developer | medium | Fix all 13 outdated path references across crew SKILL.md files. Replace `~/Projects/augur-data/factory/{skill}/` with `plugins/dev/{skill}/`. Replace `augur-config/chains/` with `plugins/dev/{skill}/chains/` | All 8 `plugins/dev/skills/*/SKILL.md` |
| 1.3 | developer | low | Remove all references to non-existent skills: "oss-manager" (devops), "data-engineer" (developer), "design-system" (frontend). Remove "merged from X" annotations | `plugins/dev/skills/{devops,developer,frontend}/SKILL.md` |

### Phase 2: Skill Merges + Data Directory Restructuring
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | high | **Merge analyst + architect → advisor (skills)**. Create `plugins/dev/skills/advisor/` with combined SKILL.md (<100 lines). Move scripts: analyst scripts → `advisor/scripts/analytics/`, architect scripts → `advisor/scripts/design/`. Create `advisor/dashboard.yaml` with hub_id: advisor. Delete source skill dirs after move | `plugins/dev/skills/advisor/` (new), `plugins/dev/skills/advisor/` (delete), `plugins/dev/skills/advisor/` (delete) |
| 2.2 | developer | high | **Merge analyst + architect → advisor (data)**. Create `plugins/dev/advisor/`. Move: `plugins/dev/analyst/` contents → `plugins/dev/advisor/analytics/` (12 files: prompts, telemetry, eval harness, complexity reports). Move: `plugins/dev/architect/` contents → `plugins/dev/advisor/design/` (10 files: vision configs, retrospectives, productization plans). Delete source data dirs | `plugins/dev/advisor/` (new), `plugins/dev/analyst/` (delete), `plugins/dev/architect/` (delete) |
| 2.3 | developer | high | **Merge security → validator (skills + data)** *(completed)*. Moved security scripts → `plugins/dev/skills/validator/scripts/security/`. Updated validator SKILL.md to include security audit commands. Deleted source dirs | `plugins/dev/skills/validator/` |
| 2.4 | developer | medium | **Update all references** to merged skills across codebase: registry.yaml, agent-workflows, chains, CLAUDE.md skill tables, hardening report references. Map: `analyst` → `advisor`, `architect` → `advisor`, `security` → `validator`. Update any scripts that reference data paths under old skill names | `data/ide-integration/registry.yaml`, `CLAUDE.md`, `plugins/ai/ai_bridge/agent-rules.md`, all chain files |

### Phase 3: Devops Slimming (Scripts + Data)
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | developer | medium | Move MCP health monitoring scripts from devops to daemon: `mcp_health_check.py`, `mcp_health_monitor.py`, `ide_integration_health.py`. If any MCP health data exists under `plugins/dev/devops/`, move relevant files to `plugins/ai/daemon/mcp-health/` | `plugins/dev/skills/devops/scripts/` → `plugins/observability/skills/daemon/scripts/` |
| 3.2 | developer | medium | Move context budget tracking scripts from devops to observe. Move any context-budget data artifacts similarly | `plugins/dev/skills/devops/scripts/` → `plugins/observability/skills/observe/scripts/` |
| 3.3 | developer | low | Update devops, daemon, and observe SKILL.md to reflect script moves. Update data README files if they exist | Affected SKILL.md files |

### Phase 4: SKILL.md Trimming & Dashboard Config
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 4.1 | frontend | medium | Trim all 6 remaining crew SKILL.md files to <100 lines each: remove inline tiering (replace with `tiering: $ref plugins/dev/src/lib/tiering-profiles.yaml`), remove inline safety/alignment boilerplate, extract methodology docs to `modules/`, mark aspirational features with `TODO_IMPROVE` | All `plugins/dev/skills/*/SKILL.md` |
| 4.2 | frontend | medium | Create dashboard.yaml for developer, devops, frontend, advisor. Each gets hub_id matching skill name, 2-3 actions (flow: llm for complex, flow: fast for automated), mode: dev. Mount under `/control` hub as tabs | `plugins/dev/skills/{developer,devops,frontend,advisor}/dashboard.yaml` |
| 4.3 | developer | medium | Trim mcp-app-factory SKILL.md from 447 to <100 lines. Extract service design guidelines to `docs/guides/service-design.md`. Extract decision frameworks to `plugins/ai/skills/mcp-app-factory/modules/` | `plugins/ai/skills/mcp-app-factory/SKILL.md`, `docs/guides/service-design.md` |

### Phase 5: Augur-Specific Skill Improvements
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 5.1 | developer | high | **advisor**: Create `scripts/analytics/skill_health_score.py` — score every skill on completeness (SKILL.md exists & <100 lines, scripts exist, dashboard.yaml exists, data dir exists, tests exist). Create `scripts/design/audit_chains.py` — parse chain YAML files, verify referenced skills and scripts exist, detect broken step ordering. Create `scripts/analytics/memory_audit.py` — validate MEMORY.md format, check daily log pipeline, detect curator dedup failures | `plugins/dev/skills/advisor/scripts/analytics/`, `plugins/dev/skills/advisor/scripts/design/` |
| 5.2 | developer | high | **developer**: Create `scripts/data_migration_safety.py` — before editing YAML in `data/`, auto-backup to `data/runtime/backups/`, validate schema post-edit, detect orphaned data files. Create `scripts/augur_refactor.py` — when renaming a skill, auto-update registry.yaml, CLAUDE.md, dashboard.yaml, chain references, agent-workflows, all IDE configs. Remove RALPH loop experimental code and references | `plugins/dev/skills/developer/scripts/` |
| 5.3 | developer | high | **devops**: Create `scripts/plugin_dependency_graph.py` — map skill→service dependencies from SKILL.md and imports, detect circular deps. Create `scripts/augur_nightly_checks.py` — extend nightly to check: all SKILL.md <100 lines, all dashboard.yaml valid, all chains resolve, all data dirs have README. Create `scripts/data_backup.py` — snapshot `data/` before major operations | `plugins/dev/skills/devops/scripts/` |
| 5.4 | frontend | high | **frontend**: Create `scripts/verify_plugin_mounts.py` — cross-reference `src/dashboard/app/` auto-generated files with plugin sources, detect stale mounts, warn on direct edits to mounted files. Create `scripts/verify_action_wiring.py` — for every action in dashboard.yaml, verify target script/chain exists and is callable | `plugins/dev/skills/frontend/scripts/` |
| 5.5 | developer | high | **validator**: Create `scripts/validate_plugin_compliance.py` — validate plugin structure (SKILL.md format, dashboard.yaml schema, required fields, data dir layout). Create `scripts/security/scan_data_directory.py` — scan `data/` for hardcoded paths, PII in YAML, plaintext credentials, API keys. Create `scripts/security/validate_mcp_config.py` — validate mcp_tool_groups.yaml syntax, verify tool refs resolve. Create `scripts/augur_pre_merge.py` — combined pre-merge gate (compliance + security + chain resolution + mount verification) | `plugins/dev/skills/validator/scripts/` |

### Phase 6: Reference Updates & Sync
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 6.1 | developer | medium | Regenerate CLAUDE.md skill table to reflect merges (8→6 crew skills) and new augur-specific capabilities. Run `sync_agents.py` to distribute to all IDEs | `CLAUDE.md`, all IDE adapter files |
| 6.2 | developer | low | Update `data/ide-integration/registry.yaml` — remove analyst, architect, security entries; add advisor entry with combined actions; update validator entry with security actions | `data/ide-integration/registry.yaml` |
| 6.3 | developer | low | Add README.md to new data directories: `plugins/dev/advisor/README.md`, `plugins/dev/advisor/analytics/README.md`, `plugins/dev/advisor/design/README.md`, `plugins/dev/validator/security/README.md` | New README files |

### Final Phase: Verification
| Step | Agent | Tier | Task |
|------|-------|------|------|
| V.1 | validator | low | Run `python3 .github/scripts/scan_code_markers.py` — verify no remaining references to deleted skills (analyst, architect, security as standalone) |
| V.2 | validator | low | Run `python3 .github/scripts/audit_paths.py` — verify no hardcoded augur-data paths remain |
| V.3 | validator | low | Verify all 6 crew SKILL.md files are <100 lines: `wc -l plugins/dev/skills/*/SKILL.md` |
| V.4 | validator | low | Verify data directories: `plugins/dev/analyst/` and `plugins/dev/architect/` and `plugins/dev/security/` no longer exist; `plugins/dev/advisor/` exists with analytics/ and design/ subdirs |
| V.5 | validator | low | Run `npm run build` in `src/dashboard/` — verify dashboard builds with new dashboard.yaml files |
| V.6 | validator | low | Run `pytest tests/` — verify no test regressions from script/data moves |
| V.7 | validator | low | If Chrome MCP available: browse `/control` hub, verify all crew skill tabs render, check console for errors |
| V.8 | validator | low | Run new augur-specific scripts to verify they work: `skill_health_score.py`, `audit_chains.py`, `validate_plugin_compliance.py`, `verify_plugin_mounts.py` |

### Completion Criteria
- [ ] 8 crew skills consolidated to 6 (analyst+architect→advisor, security→validator)
- [ ] All SKILL.md files <100 lines
- [ ] Shared tiering config created and referenced
- [ ] 0 hardcoded augur-data paths
- [ ] 0 references to deleted skills
- [ ] All 6 crew skills have dashboard.yaml
- [ ] Data directories restructured (advisor/{analytics,design}, validator/security)
- [ ] No orphaned data directories (analyst, architect, security dirs deleted)
- [ ] Data dir READMEs created for new directories
- [ ] devops reduced from 40 to ~20 scripts
- [ ] mcp-app-factory SKILL.md <100 lines
- [ ] 12 new augur-specific scripts created and functional
- [ ] All tests pass
- [ ] Dashboard builds successfully
- [ ] Browser verification (if Chrome MCP available)
- [ ] ADR status updated to Accepted
