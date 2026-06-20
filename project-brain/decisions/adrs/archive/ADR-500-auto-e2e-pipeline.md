---
id: ADR-500
title: End-to-End Pipeline Validation Autoloop (GET Direction)
status: Implemented
date: 2026-03-24
deciders: [Gur Sannikov]
tags: [e2e, pipeline, validation, diagnostics, autoloop]
related: [ADR-501]
---

# ADR-500: End-to-End Pipeline Validation Autoloop (GET Direction)

## Context

Data flows through a multi-stage pipeline: vault files -> RAG index -> MCP tools -> API routes -> dashboard rendering. When a dashboard page shows no data, diagnosing which stage broke requires manual investigation across 4+ systems. No automated validation existed for the GET/read direction.

## Decision

Create `auto-e2e-pipeline` skill with an outside-in diagnostic approach:
- Inventory both edges (vault files + dashboard API responses)
- Binary-search inward through RAG index and MCP tool layers
- Classify the exact pipeline stage where data drops for each item
- At d2+, trigger RAG reindex as auto-fix for `rag_stale` issues
- At d4, discover every page->MCP tool mapping (YAML pages, SKILL.md blocks, custom TSX hooks) and verify each tool returns data

Uses `ops_protocol` (OpsCommand contract), httpx for API probes, and frontmatter_utils for vault parsing.

## Consequences

### Positive
- Pinpoints exact failure stage (vault, RAG, MCP, API, render) per item
- Auto-fixes stale RAG index at d2+ without human intervention
- Covers all browse categories and page->MCP tool mappings

### Negative
- API probes require dashboard server running (nightly only)
- httpx dependency added for HTTP probing

## References

- Plan: `docs/superpowers/plans/2026-03-24-auto-e2e-pipeline.md`
- Skill: `skills/auto-e2e-pipeline/`
