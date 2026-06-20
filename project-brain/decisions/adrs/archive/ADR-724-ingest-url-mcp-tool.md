---
status: Implemented
date: 2026-05-10
deciders:
  - gsannikov
related:
  - ADR-624
hub: brain
tags:
  - ingest
  - mcp
  - wiki
  - url-capture
superseded_by: null
spec_file: 2026-05-10-ingest-url-mcp-tool-design.md
plan_file: 2026-05-10-ingest-url-mcp-tool.md
---

# ADR-724: Ingest URL MCP Tool

> **ADR-724 is an index file.** The substantive design and implementation steps live in the linked spec + plan. This file carries pointers, status, and a one-line decision summary.

## Decision summary

Register a single `ingest-url(url, tags, note)` MCP tool on the existing `ingest` skill that fetches, extracts, canonicalizes, hashes, and persists one URL as a source card under `<vault>/sources/urls/` so the wiki compounder picks it up. The tool is the agent-callable counterpart to the existing folder-inbox path: same persistence shape, same hash-dedup behavior, same downstream wiki signal — just driven by a URL argument instead of a file drop. Failures (network, paywall, robots.txt block, malformed content) surface as structured tool errors rather than swallowed exceptions.

## Spec (canonical)

- [`docs/superpowers/specs/2026-05-10-ingest-url-mcp-tool-design.md`](../superpowers/specs/2026-05-10-ingest-url-mcp-tool-design.md)

## Plan (canonical, drives `/adr implement`)

- [`docs/superpowers/plans/2026-05-10-ingest-url-mcp-tool.md`](../superpowers/plans/2026-05-10-ingest-url-mcp-tool.md)

## Status notes

Index ADR reconstructed on 2026-05-12 from the existing spec + plan to align with the new thin-index ADR workflow (the original `/adr write` run that produced this ADR's spec and plan did not generate the markdown index file). No design content was changed in reconstruction.

This tool layers on top of ADR-731 (Memory Synthesis Consolidation): once 731's wiki query registry is in place, `ingest-url` becomes one of the canonical wiki-feeding entrypoints. The tool's `capability_exposure.yaml` row is an alphabetical insert that coexists with 731's 5 new MCP rows.

Implemented on 2026-05-13 in `shared-vault/skills/ingest/` with deterministic URL helpers, HTML extraction, URL source-card persistence, MCP registration, skill metadata exposure, and focused pytest coverage for the full first-capture and deduplication flow.

## Related

- ADR-624 — Brain Ingest Inbox
