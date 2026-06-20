---
status: Deprecated
date: '2026-03-05'
deciders:
- Observability / Daemon maintainers
related: []
hub: null
tags:
- centralized
- ops
- loops
- issue
- inventory
superseded_by: null
---

# ADR-245: Centralized Ops-Loops Issue Inventory (2026-03-05)

**Source Command**: `python plugins/observability/skills/daemon/scripts/adaptive_loop_executor.py pending --create-adr`

## Context

`/ops-loops pending --create-adr` produced a cross-loop scan snapshot of pending findings.

This ADR captures that snapshot as a temporary centralized planning artifact for
cross-loop prioritization and sequencing. It does not replace decentralized ownership
of scan/fix logic in plugin auto-commands.

## Summary

- Total pending issues: 191
- Total pending fixes: 191
- Loops scanned: 6
- Commands scanned: 32

### Per-Loop Totals

| Loop | Pending Issues | Share |
|------|----------------|-------|
| code-quality | 146 | 76.4% |
| command-evolution | 0 | 0.0% |
| hardening | 14 | 7.3% |
| knowledge-enrichment | 29 | 15.2% |
| self-heal | 0 | 0.0% |
| skill-standards | 2 | 1.0% |

### Top Commands By Pending Count

| Loop | Command | Tier | Trigger | Issues | Severity |
|------|---------|------|---------|--------|----------|
| code-quality | auto-coverage-check | 3 | nightly | 142 | warning |
| knowledge-enrichment | auto-rag-reindex | 0 | nightly | 24 | info |
| hardening | auto-flow-optimizer | 5 | nightly | 10 | warning |
| hardening | auto-page-mounts | 0 | nightly | 4 | warning |
| skill-standards | auto-skill-refs | 2 | nightly | 2 | warning |
| code-quality | auto-format | 0 | nightly | 1 | warning |
| knowledge-enrichment | auto-agent-sync | 1 | post-execution | 1 | warning |
| knowledge-enrichment | auto-memory-sync | 1 | nightly | 1 | warning |
| code-quality | auto-logs | 0 | nightly | 1 | info |
| code-quality | auto-markers | 0 | nightly | 1 | info |
| knowledge-enrichment | auto-project-index | 0 | nightly | 1 | info |
| knowledge-enrichment | auto-analytics | 1 | nightly | 1 | info |
| code-quality | auto-git-health | 1 | nightly | 1 | info |
| knowledge-enrichment | auto-orphan-plans | 3 | nightly | 1 | info |
| command-evolution | auto-command-evolution | 0 | post-execution | 0 | info |
| self-heal | auto-self-heal | 0 | continuous | 0 | info |
| skill-standards | auto-skill-md | 0 | nightly | 0 | info |
| hardening | auto-yaml-lint | 0 | nightly | 0 | info |
| code-quality | auto-fix | 1 | nightly | 0 | info |
| knowledge-enrichment | auto-index-notes | 1 | nightly | 0 | info |

## Decision

Use this centralized inventory as a short-lived coordination artifact for
cross-loop triage and remediation sequencing.

Keep implementation decentralized:
- each auto-command remains owned and fixed in its plugin,
- loop behavior remains configured via `config/system/adaptive_loops.yaml`,
- regenerate this ADR when snapshot drift becomes material.

## Prioritization Policy

Apply remediation in this order:
1. `severity=error` commands with highest issue count.
2. Commands causing runtime failures or loader skips.
3. High-volume `warning` commands that degrade nightly signal quality.
4. `info` items after error/warning backlog stabilizes.

First wave for this snapshot:

1. `code-quality/auto-coverage-check` (142, warning)
2. `hardening/auto-flow-optimizer` (10, warning)
3. `hardening/auto-page-mounts` (4, warning)
4. `skill-standards/auto-skill-refs` (2, warning)
5. `code-quality/auto-format` (1, warning)

## Consequences

### Positive
- Single, comparable view across loops and triggers.
- Faster cross-loop prioritization for nightly remediation.

### Negative
- Snapshot staleness: counts drift as fixes land.

### Neutral
- Plugin-first architecture and command ownership remain unchanged.

## Alternatives Considered

### Alternative 1: Loop-local only (no centralized ADR)
Rejected: high friction for cross-loop risk comparison.

### Alternative 2: Permanent centralized backlog file
Rejected: central drift risk and ownership ambiguity.

## Operational Workflow

1. Generate snapshot with `--pending --create-adr`.
2. Execute fixes in owning plugins/commands.
3. Re-run pending scan.
4. Regenerate ADR if counts shift materially.

## Regeneration

Regenerate via:
`python plugins/observability/skills/daemon/scripts/adaptive_loop_executor.py --pending --create-adr`

## References

- `plugins/observability/skills/daemon/commands/ops-loops.md`
- `plugins/observability/skills/daemon/scripts/adaptive/discovery.py`
- `config/system/adaptive_loops.yaml`
- ADR-176 (Adaptive Loop Engine)
- ADR-200 (scan-fix auto-command protocol/discovery)
