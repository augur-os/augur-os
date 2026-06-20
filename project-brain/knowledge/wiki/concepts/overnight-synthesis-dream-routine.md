---
title: Overnight Synthesis — The Dream Routine
summary: The dream routine is Augur's cross-client overnight compounding pass —
  authored once, projected as a scheduled routine into every supported AI client.
  Deterministic phases run via MCP tools at zero LLM cost; judgment phases run
  inline in the client session. Augur owns no scheduling and makes no LLM calls.
tags:
- dream
- routine
- compounding
- synthesis
- cross-client
aliases:
- dream routine
- overnight synthesis
- dream cycle
related:
- '[[the-wiki-compounding-engine]]'
- '[[agent-separation-mcp-skill-claude]]'
created: '2026-05-31T00:00:00Z'
_page_type: concept
_hub: dev
_sources:
- repo:project-brain/capabilities/skills/dream/SKILL.md
_cites:
- '[[repo:project-brain/capabilities/skills/dream/SKILL.md]]'
_compiler_version: concept-article-v4
_updated: '2026-05-31T00:00:00Z'
---

# Overnight Synthesis — The Dream Routine

## Compiled truth

The dream routine is Augur's nightly compounding pass, implementing ADR-744. Three
non-negotiable principles govern it. First, no Augur-side scheduling: the client's
routine system owns the cron (Codex automations, Claude Code `/schedule`, Gemini
equivalents). Second, no direct LLM calls from Augur — the client runs the routine
in its own session and owns the LLM context; Augur exposes MCP entry points and
records ledger state. Third, no autonomous destructive operations: orphans, dead
citations, and merge candidates are proposals; the user confirms before any
delete or merge. The routine is authored once in the dream skill and projected as
a scheduled routine into every supported AI client, making it cross-client by
construction.

The routine splits into two phase classes. Deterministic phases run via MCP tools
at zero LLM cost: `dream-orphans` (detects wiki pages with no inbound edges),
`dream-dead-citations` (scans timeline `_source:` URIs for dead targets),
`dream-cache-gc` (filesystem GC of the cache dir per retention config), and entity
tier recompute (delegated to the graph skill). Judgment phases run inline in the
client session: compiled-truth refresh (reads recent timeline entries and emits a
proposal — never a write), pattern extraction (proposes new wiki seeds), and wiki
concept merging (reviews high-similarity pairs, proposes merges). Every phase opens
a job via the ADR-743 jobs framework; failure of one deterministic phase does not
block subsequent phases. Output report lands at
`get_documents_dir()/reports/dream/<YYYY-MM-DD>.md`, giving the user a dated
record of every synthesis pass.

## Timeline

- 2026-05-31 — Concept seeded from project-brain/capabilities/skills/dream/SKILL.md (ADR-744 implementation).
