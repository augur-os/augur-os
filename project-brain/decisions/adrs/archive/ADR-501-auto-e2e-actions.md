---
id: ADR-501
title: End-to-End Actions Validation Autoloop (POST Direction)
status: Implemented
date: 2026-03-24
deciders: [Gur Sannikov]
tags: [e2e, actions, mutations, validation, autoloop]
related: [ADR-500]
---

# ADR-501: End-to-End Actions Validation Autoloop (POST Direction)

## Context

The GET pipeline (ADR-500) validates data reads, but the POST/write direction — dashboard actions wiring to MCP tools, parameter acceptance, and write->read round-trips — had no automated validation. With 202 actions, 30 modals, and 9 row_actions across 31 skills, manual verification was impractical.

## Decision

Create `auto-e2e-actions` skill with 4 difficulty levels:
- **d0**: Wiring audit — every action's `submitTool` resolves to a registered MCP tool
- **d1**: Schema validation — tool parameters match declared action fields
- **d2**: Execution — create `_e2e_test_*` items, verify MCP tool accepts them, clean up
- **d3**: Round-trip — write via action, read back via GET pipeline, verify data appears

Discovers actions from SKILL.md frontmatter across all skills. Uses `ops_protocol` contract.

## Consequences

### Positive
- Catches broken action wiring before users encounter it
- Round-trip validation at d3 proves full write->read cycle works
- Automatic test item cleanup prevents vault pollution

### Negative
- d2+ creates temporary data in the vault (cleaned up but adds risk)
- Requires MCP server running for execution-level tests

## References

- Plan: `docs/superpowers/plans/2026-03-24-auto-e2e-actions.md`
- Skill: `skills/auto-e2e-actions/`
