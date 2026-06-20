---
status: Implemented
date: 2026-03-25
deciders:
  - Gur Sannikov
related: []
hub: adaptive
tags:
  - data-result
  - seed-data
  - transparency
  - dashboard
superseded_by: null
---

# ADR-516: DataResult Helper — Seed Data Transparency Across the Pipeline

## Context

MCP tools silently return seed/demo data when vault data is missing. The dashboard and user cannot distinguish real data from demo data. When vault returns empty, there's no diagnosis of why — wrong path, missing directory, or genuinely no data yet. Additionally, the pulse health check probes 8 API endpoints that don't exist, polluting health status with false 404s.

## Decision

### 1. DataResult Helper

New `src/lib/data_result.py` with a `DataResult` envelope:

```python
@dataclass
class DataResult:
    data: Any
    source: str           # "vault" | "seed" | "default"
    vault_status: str     # "ok" | "missing_dir" | "no_file" | "empty_file"
    vault_path: str | None = None
    seed_path: str | None = None
```

Main entry: `read_skill_data(caller_file, filename, default, loader="yaml")` — resolves vault path, diagnoses state, falls back to seed with full transparency.

### 2. Skill Migration (13 files across 11 skills)

Replace inline seed fallback patterns with `read_skill_data()` across: apple, career (2 files), google-workspace (2 files), evolve, reading-list, lifestyle, health, growth, smb-client-template (2 files), daemon, knowledge.

### 3. Scanner Enforcement

Extend `auto-e2e-pipeline` d0 seed_fallback check with adoption tracking: count migrated vs legacy files, report ratio, evolve to d2 runtime validation when legacy hits 0.

### 4. Pulse Endpoint Cleanup

Remove 8 dead endpoints from pulse route probe lists that don't exist.

### 5. Dashboard SeedBadge Component

New `SeedBadge` component in framework layer (`@/` alias) that shows "Sample data" when `source === "seed"`. Integrated via `useBlockData` metadata sideband — extracts `source`/`vault_status` before `unwrapToolData()` strips them.

## Consequences

### Positive

- Users can distinguish real data from demo data at a glance
- Vault path diagnosis visible in tool responses for debugging
- Pulse health check no longer reports false 404s

### Negative

- 13 file migration is mechanical but touches many skills
- Mixed source reporting (health skill) adds complexity

### Neutral

- No changes to vault path resolution or `get_own_data_dir()`
- Additive to existing blocks — `meta` is undefined for non-migrated tools

## Alternatives Considered

### Alternative 1: Per-Skill Source Tracking

Each skill implements its own source tracking. Rejected because it leads to inconsistent field names and missing coverage.

### Alternative 2: Global Middleware

Intercept all MCP tool responses and inject source metadata. Rejected because source detection requires knowledge of vault vs seed paths that only the skill has.

## References

- Design spec: `docs/superpowers/specs/2026-03-25-data-result-seed-transparency-design.md`
- Implementation plan: `docs/superpowers/plans/2026-03-25-data-result-seed-transparency.md`
