---
status: Implemented
date: '2026-03-12'
deciders:
- Gur Sannikov
related: []
hub: null
tags:
- adaptive
- bundle
- consolidation
superseded_by: null
---

# ADR-403: Adaptive Bundle Consolidation

## Context

51 auto-commands are scattered across 3 plugin bundles (admin: 38, dev: 11, observability: 2) with no architectural justification.

**Problems:**
1. Admin bundle bloat — 38 auto-commands make `plugins/admin/skills/` enormous
2. False domain coupling — auto-commands are filed under business-domain bundles despite zero dependency on their host plugins
3. Mixed formats — some use legacy augur.yaml command definitions alongside SKILL.md
4. Architectural confusion — the `autoloop` parent skill in admin is a cross-cutting infrastructure concern
5. Discoverability — finding all auto-commands requires searching across 3 bundles

**Dependency analysis** of all auto-command Python scripts confirms zero plugin coupling:
- Every `scan()` operates on the entire project, not its host plugin
- Zero plugin-specific imports — no auto-command reads its parent's augur.yaml or config
- The only shared interface is `src.lib.ops_protocol` (already centralized)
- Auto-commands are infrastructure — analogous to adaptive LLM-driven CI, not domain functionality

Three commands have external script coupling (auto-agent-sync, auto-project-index, auto-rag-reindex) calling scripts in `plugins/ai/` via hard-coded paths with graceful fallback.

## Decision

### 1. Create `plugins/adaptive/` bundle

New top-level bundle containing 48 auto-commands in a flat directory structure. No hub page — headless skill library. Bundle name `adaptive` reflects the differentiator from traditional CI (trust-gated, self-healing, LLM-driven, budget-controlled).

### 2. Relocate 3 coupled commands to target plugins

| Current | New Name | Target |
|---------|----------|--------|
| `auto-agent-sync` | `sync-agents` | `plugins/ai/skills/` |
| `auto-project-index` | `reindex-project` | `plugins/ai/skills/` |
| `auto-rag-reindex` | `reindex-rag` | `plugins/ai/skills/` |

These retain `x-augur-loop` frontmatter (engine still discovers them) but drop the `auto-` prefix, which is reserved for commands in the adaptive bundle. Hub updated to `ai`.

### 3. Standardize all SKILL.md frontmatter

Required fields: `name`, `description`, `x-augur-visibility: auto`, `x-augur-hub`, `x-augur-loop`. Legacy `commands:` blocks in augur.yaml removed.

### 4. Rename `tech-debt-triage` → `auto-tech-debt`

Naming consistency — all commands in the adaptive bundle use the `auto-` prefix.

### 5. Delete `autoloop` parent skill

Absorbed into this ADR. No longer needed as a separate documentation skill.

### 6. Engine stays in observability

The adaptive engine (`plugins/observability/skills/daemon/scripts/adaptive/`) remains untouched. Engine discovery scans `plugins/*/skills/*/SKILL.md` (bundle-agnostic glob). Trust ledger keyed by category name, not path. Runner/script separation (CI analogy).

### 7. Registry updates

Add `"adaptive"` to `PLUGIN_BUNDLES` in `src/config/paths.py` (canonical) and `src/plugins/skill_registry.py` (fallback).

### 8. Trust ledger migration

Rename entries for 3 coupled commands to preserve trust history.

### 9. Future: `auto-ci-sync` command (proposed)

Bridge adaptive engine with `.github/` CI — read workflows to avoid duplication, propose new CI rules when commands reach high trust. Not implemented in this pass.

## Consequences

### Positive

- Admin bundle reduced by 38 skills, dev by 11, observability by 2
- Single location for all adaptive commands: `plugins/adaptive/skills/`
- Consistent SKILL.md format across all auto-commands
- Clear architectural boundary: domain plugins vs infrastructure
- Flat structure with categories in frontmatter — easy to browse and reorganize

### Negative

- New top-level bundle increases bundle count from 15 to 16
- 3 coupled commands live outside the adaptive bundle — requires understanding the split rationale
- Stale dashboard mounts in admin/dev need cleanup after migration

### Neutral

- Engine code and config unchanged — no behavioral changes to the adaptive loop system
- `ops_protocol` remains the only shared interface
- ADR-163 (plugin decentralization) refined to distinguish domain vs infrastructure plugins

## Alternatives Considered

### Alternative 1: Keep commands distributed (status quo)

Each bundle owns its auto-commands. Rejected because dependency analysis proves zero plugin coupling — the distribution is arbitrary, not architectural.

### Alternative 2: Move to `ci` bundle

Name implies traditional CI. Rejected because auto-commands are adaptive (trust-gated, LLM-driven, self-healing) not deterministic CI, and `ci` creates confusion with `.github/` scripts.

### Alternative 3: Move + create hub page (Approach B)

Full hub with dashboard presence. Rejected for unnecessary complexity — adaptive commands are headless infrastructure, not a dashboard destination.

## References

- Design spec: `docs/superpowers/specs/2026-03-12-adaptive-bundle-consolidation-design.md`
- Implementation plan: `docs/superpowers/plans/2026-03-12-adaptive-bundle-consolidation.md`
- ADR-163 — Plugin decentralization (scope refined by this ADR)
- ADR-176 — Adaptive loop engine (unchanged)
- ADR-200 — Ops-loops / auto-commands separation (reinforced)
- ADR-216 — Unified loop configuration (unchanged)
- ADR-252 — Commands-to-skills migration (completed)

## Impact Manifest

```yaml
impact:
  paths_renamed:
    - from: "plugins/admin/skills/auto-*"
      to: "plugins/adaptive/skills/auto-*"
      scope: "plugins/admin/skills/auto-*/**"
    - from: "plugins/dev/skills/auto-*"
      to: "plugins/adaptive/skills/auto-*"
      scope: "plugins/dev/skills/auto-*/**"
    - from: "plugins/observability/skills/auto-*"
      to: "plugins/adaptive/skills/auto-*"
      scope: "plugins/observability/skills/auto-inspect/**,plugins/observability/skills/auto-loop-advisor/**"
    - from: "plugins/admin/skills/tech-debt-triage"
      to: "plugins/adaptive/skills/auto-tech-debt"
      scope: "plugins/admin/skills/tech-debt-triage/**"
    - from: "plugins/admin/skills/auto-agent-sync"
      to: "plugins/ai/skills/sync-agents"
      scope: "plugins/admin/skills/auto-agent-sync/**"
    - from: "plugins/admin/skills/auto-project-index"
      to: "plugins/ai/skills/reindex-project"
      scope: "plugins/admin/skills/auto-project-index/**"
    - from: "plugins/admin/skills/auto-rag-reindex"
      to: "plugins/ai/skills/reindex-rag"
      scope: "plugins/admin/skills/auto-rag-reindex/**"
  patterns_deprecated:
    - grep: "contributes_to: admin.*auto-"
      replacement: "contributes_to: adaptive"
    - grep: "x-augur-hub: admin.*auto-"
      replacement: "x-augur-hub: adaptive"
```

## Implementation Prompt

**Team name**: `adr-403-adaptive-consolidation`

### Phase 1: Bundle Creation and Registry
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | builder | low | Create `plugins/adaptive/skills/` directory | `plugins/adaptive/skills/.gitkeep` |
| 1.2 | builder | low | Add `adaptive` to PLUGIN_BUNDLES | `src/config/paths.py`, `src/plugins/skill_registry.py` |

### Phase 2: Bulk Move
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | builder | medium | Move 34 auto-* from admin to adaptive | `plugins/admin/skills/auto-*` → `plugins/adaptive/skills/` |
| 2.2 | builder | low | Move+rename tech-debt-triage to auto-tech-debt | `plugins/admin/skills/tech-debt-triage` → `plugins/adaptive/skills/auto-tech-debt` |
| 2.3 | builder | medium | Move 11 auto-* from dev to adaptive | `plugins/dev/skills/auto-*` → `plugins/adaptive/skills/` |
| 2.4 | builder | low | Move 2 auto-* from observability to adaptive | `plugins/observability/skills/auto-*` → `plugins/adaptive/skills/` |

### Phase 3: Coupled Commands and Cleanup
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | builder | medium | Relocate 3 coupled commands to ai bundle with renames | `plugins/admin/skills/auto-agent-sync`, `auto-project-index`, `auto-rag-reindex` |
| 3.2 | builder | low | Delete autoloop parent skill | `plugins/admin/skills/autoloop/` |

### Phase 4: Standardize Frontmatter
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 4.1 | builder | medium | Update x-augur-hub to adaptive in all SKILL.md | `plugins/adaptive/skills/*/SKILL.md` |
| 4.2 | builder | medium | Update contributes_to in all augur.yaml | `plugins/adaptive/skills/*/augur/augur.yaml` |
| 4.3 | builder | low | Remove legacy commands blocks from augur.yaml | `plugins/adaptive/skills/*/augur/augur.yaml` |

### Phase 5: Migration and Documentation
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 5.1 | builder | low | Write and run trust ledger migration script | `src/scripts/migrate_trust_ledger.py` |
| 5.2 | builder | low | Clean stale dashboard mounts | `apps/dashboard/app/admin/auto-*`, `apps/dashboard/app/dev/auto-*` |

### Final Phase: Verification
| Step | Agent | Tier | Task |
|------|-------|------|------|
| V.1 | validator | low | Verify engine discovery finds 48 commands in adaptive + 3 in ai |
| V.2 | validator | low | Verify hub alignment (x-augur-hub matches bundle directory) |
| V.3 | validator | low | Verify PLUGIN_BUNDLES includes adaptive in both files |
| V.4 | validator | low | Spot-check scan() invocation on auto-lint |
| V.5 | validator | low | Verify no auto-* skills remain in admin, dev, or observability |

### Completion Criteria
- [ ] All phases executed
- [ ] 48 auto-commands discoverable in `plugins/adaptive/`
- [ ] 3 renamed commands discoverable in `plugins/ai/`
- [ ] All SKILL.md frontmatter standardized
- [ ] No stale dashboard mounts
- [ ] Trust ledger entries migrated
- [ ] ADR status updated to Implemented
