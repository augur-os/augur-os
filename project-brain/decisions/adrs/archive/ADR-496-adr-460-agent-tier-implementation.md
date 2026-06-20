---
id: ADR-496
title: ADR-460 Agent Tier Operationalization Implementation
status: Implemented
date: 2026-03-24
deciders: [Gur Sannikov]
tags: [agents, tiers, safety, escalation, performance]
related: [ADR-460]
---

# ADR-496: ADR-460 Agent Tier Operationalization Implementation

## Context

ADR-460 specified agent tier declarations (fast/standard/deep), safety constraints, escalation rules, and performance tracking. The existing state had ~40% done (minimal `x-augur-agent` blocks in 14 SKILL.md files, basic parser). The remaining 60% needed full tier/safety/escalation declarations, JSON schema validation, performance ledger, and tier routing.

## Decision

Implement ADR-460 across 10 tasks:
1. JSON Schema for `x-augur-agent` validation
2. Enrich 14 SKILL.md files with full tier/safety/escalation blocks
3. Extend parser and generator (crew_parser.py, subagent_profile.py)
4. Create performance ledger module (`src/agents/performance_ledger.py`)
5. Wire tier routing into `useActionRunner`
6-10. Telemetry, nightly compaction, agent regeneration, tests, ADR status update

Four agent role templates defined: Executor, Advisor, Validator, Orchestrator.

## Consequences

### Positive
- Every agent has explicit capability boundaries (model, tools, context budget per tier)
- Safety constraints prevent runaway agents (file edit limits, banned paths/operations)
- Performance ledger enables data-driven tier routing decisions

### Negative
- 14 SKILL.md files need ongoing maintenance when agent capabilities change

## References

- Plan: `docs/superpowers/plans/2026-03-20-adr-460-agent-tiers.md`
- Parent ADR: ADR-460 in `Au-vault/dev/adrs/`
