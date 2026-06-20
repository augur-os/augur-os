---
id: ADR-495
title: ADR-443 through ADR-449 Implementation Plan
status: Implemented
date: 2026-03-24
deciders: [Gur Sannikov]
tags: [autoloop, safety, vault, skills, hub-restructuring]
related: [ADR-443, ADR-444, ADR-445, ADR-446, ADR-447, ADR-448, ADR-449]
---

# ADR-495: ADR-443 through ADR-449 Implementation Plan

## Context

ADRs 443-449 covered autoloop safety, engine LLM escalation, hub assembly, skill quality fixes, standalone deep-dive pages, skills.sh naming, and vault-git integration. Each had individual gaps remaining after initial acceptance. A coordinated implementation plan was needed to close all gaps using parallel agent execution across 4 phases.

## Decision

Execute a 4-phase parallel implementation plan:
- Phase 1: Independent fixes (vault-status health_score, skills.sh naming, seed generation, engine LLM dispatch)
- Phase 2: Dependent work (fix() LLM fallback, standalone deep-dive page)
- Phase 3: Hub restructuring (assembly engine, per-hub skill migration across 5 agents)
- Phase 4: Verification (gap re-scan, gate hardening)

Each phase dispatches independent agents in parallel. Dependencies are respected between phases.

## Consequences

### Positive
- All 7 ADR gaps closed in a single coordinated session
- Parallel execution reduced wall-clock time vs serial implementation
- Verification phase caught regressions before marking complete

### Negative
- Complex orchestration required careful dependency tracking between phases

## References

- Plan: `docs/superpowers/plans/2026-03-19-adr-443-449-implementation.md`
- Parent ADRs: ADR-443 through ADR-449 in `Au-vault/dev/adrs/`
