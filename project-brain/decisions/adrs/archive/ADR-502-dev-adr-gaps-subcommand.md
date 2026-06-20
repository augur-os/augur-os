---
id: ADR-502
title: /dev-adr gaps Subcommand for Multi-ADR Gap Analysis
status: Implemented
date: 2026-03-24
deciders: [Gur Sannikov]
tags: [dev-adr, gap-analysis, tooling]
related: []
---

# ADR-502: /dev-adr gaps Subcommand for Multi-ADR Gap Analysis

## Context

After restoring 293 ADRs, there was no way to scan multiple ADRs for implementation gaps in a single command. Manual verification required reading each ADR and grepping the codebase individually. A systematic gap analysis tool was needed.

## Decision

Add a `gaps` subcommand to `/dev-adr` as a pure declarative addition to SKILL.md (no new scripts or MCP tools). The agent reads the spec and executes using built-in tools.

Features:
- Input formats: explicit list, numeric range, status filter
- Gap taxonomy: Unimplemented, Partial, Conflict, Drift
- Severity matrix: Critical, High, Medium, Low
- Dispatch: sequential for 1-2 ADRs, parallel subagents for 3+
- Cross-ADR conflict detection via target map
- Read-only analysis — no file modifications

## Consequences

### Positive
- Single command scans any number of ADRs for implementation gaps
- Cross-ADR conflict detection catches contradictory specs
- Severity ranking focuses effort on critical gaps first

### Negative
- Agent-driven analysis (no deterministic script) means results may vary between runs

## References

- Plan: `docs/superpowers/plans/2026-03-17-dev-adr-gaps-subcommand.md`
- Spec: `docs/superpowers/specs/2026-03-17-dev-adr-gaps-subcommand-design.md`
