# Obsidian-Native Ingest URL Wiki MVP Design

## Context

Augur already has the core pieces for an LLM-maintained wiki: a vault-backed
compiled wiki, concept-first wiki compiler, MCP ingest tools, and agent rules
that require wiki compounding after durable knowledge work. The current gap is
the user-facing path. The Substack reference presents a simpler mental model:
save a URL, process inbox items, lint the wiki, and browse the result in
Obsidian-native markdown.

This MVP closes that gap without replacing Augur's architecture. It promotes
the staged Obsidian skill as the native vault/wiki UX layer, adds a focused
`/ingest-url` command and MCP tool, and makes URL source cards route through
Augur's existing hubs and skills instead of a generic tag taxonomy.

## Goals

- Make URL capture obvious from CLI, agent sessions, and dashboard UI.
- Save one markdown source card per URL with summary, status, routing, and
  action metadata.
- Classify captures using live Augur hub and skill metadata plus recent
  worked-on context.
- Keep LLM synthesis in agents, not MCP tools or dashboard code.
- Promote Obsidian as the MVP browsing/editing layer for source cards and
  compiled wiki pages.
- Keep the concept-first wiki compiler as the only writer for compiled
  `wiki/concepts/*` and `wiki/queries/*` pages.

## Non-Goals

- Do not promote the full staged `import` skill in this MVP.
- Do not build a generic web clipper replacement.
- Do not let dashboard code call LLM APIs directly.
- Do not write URL captures directly into `wiki/`.
- Do not add a new parallel taxonomy outside existing Augur hubs and skills.

## User Workflow

### CLI and Agent

```bash
/ingest-url https://example.com/article
/ingest-url https://example.com/article --to sources/web --compile
```

The command calls the `ingest-url` MCP mutation. The tool captures the URL as a
source card, returns the saved file path and routing metadata, and optionally
prepares a wiki update batch. When `--compile` is requested, the agent reads the
batch, extracts concepts, calls `wiki-apply-concept-batch`, then runs
`wiki-reindex`, `wiki-lint`, and `wiki-log`.

### Dashboard

The dashboard exposes an "Ingest URL" affordance in the Brain knowledge/ingest
surface. The UI calls the same `ingest-url` MCP tool with URL, destination, and
compile preference. The UI only shows deterministic status and results:

- saved source card path
- extracted title/domain
- hub and skill candidates
- read/action status
- wiki update state

If the user wants compilation, the UI dispatches an IDE/agent action. It does
not run prompts or LLM calls in browser/server dashboard code.

### Obsidian

Promoted Obsidian support makes the vault a good place to browse both raw URL
source cards and compiled wiki pages. The MVP uses:

- wikilinks for related skill/wiki concepts
- YAML frontmatter for Bases filtering
- callouts for summary, routing, and action review
- `.obsidian` scaffold as an opt-in step

Canvas generation can be designed as a follow-up after the basic source cards
and wiki pages are stable.

## URL Source Card Format

Each URL becomes one markdown file under a source-capture folder such as:

```text
Au-vault/sources/web/2026-04-21-karpathy-llm-wiki-obsidian.md
```

Filename format:

```text
YYYY-MM-DD-title-or-domain-slug.md
```

Duplicate slugs receive a numeric suffix.

Example:

```markdown
---
title: "How I Took Karpathy's LLM Wiki and Built an AI-Powered Second Brain in Obsidian"
source_type: url
url: "https://aimaker.substack.com/p/llm-wiki-obsidian-knowledge-base-andrej-karphaty"
domain: "aimaker.substack.com"
author: "Wyndo"
published: "2026-04-16"
captured: "2026-04-21T12:34:00Z"

hub: brain
skill_candidates:
  - obsidian
  - ingest
  - knowledge
intent:
  - read-later
  - wiki-ux
  - product-research
content_kind: article

read_status: unread
action_status: triage
priority: medium
wiki_compile: queued
confidence: 0.86

classification_basis:
  matched_hub_terms:
    - wiki
    - obsidian
    - markdown
  matched_skill_terms:
    obsidian:
      - vault
      - wikilinks
      - callouts
    ingest:
      - url
      - source capture
  recent_context_boost:
    - wiki
    - ingest
    - obsidian
---

# How I Took Karpathy's LLM Wiki and Built an AI-Powered Second Brain in Obsidian

> [!summary]
> Short human-readable summary for later review.

> [!routing]
> Routed to `brain` because it matched active wiki, Obsidian, and ingest work.
> Candidate skills: `obsidian`, `ingest`, `knowledge`.

## Why It Matters

This source is useful because it describes a concrete Obsidian-native LLM wiki
workflow that Augur can compare against its own concept-first wiki compiler,
ingest commands, and agent execution rules.

## Suggested Actions

- [ ] Promote Obsidian MVP
- [ ] Add `/ingest-url`
- [ ] Update wiki compiler output for Obsidian-native UX

## Extracted Content

The captured article body follows this heading.
```

## Deterministic Classification

The MCP tool should generate routing candidates without using an LLM. It should
build a local classifier from:

- live `skills/*/SKILL.md` frontmatter
- `x-augur-hub`, `x-augur-group`, `x-augur-tab`, and `x-augur-tags`
- skill names, descriptions, commands, and MCP tool names
- staged skill candidates explicitly selected for this MVP, starting with
  Obsidian
- recent session/work focus when available from IDE history, memory, or runtime
  focus state

The classifier should return scored candidates, not pretend certainty. The
agent can then refine the summary and suggested actions while preserving the
deterministic routing evidence.

Recommended first intent set:

- `read-later`
- `task`
- `library-candidate`
- `competitor-research`
- `go-to-market`
- `product-research`
- `wiki-ux`
- `implementation-reference`
- `personal-knowledge`

## Components

### Obsidian Skill Promotion

Promote `staging/r1/skills/obsidian` into live `skills/obsidian` as an MVP
skill. Keep the scope to vault integration:

- `obsidian-read`
- `obsidian-write`
- `obsidian-search`
- `obsidian-status`
- `obsidian-scaffold`
- `obsidian-convert`

The staged tests already pass, but promotion must verify live MCP registration,
skill discovery, generated client surfaces, and the dashboard page source.

### Ingest URL MCP Tool

Add `ingest-url` to the live ingest skill. It should be a focused wrapper over
the existing ingest pipeline, not a second pipeline.

Input:

```json
{
  "url": "https://example.com/article",
  "destination": "sources/web",
  "compile": "queue",
  "read_status": "unread"
}
```

Output:

```json
{
  "success": true,
  "source_path": "sources/web/2026-04-21-example-article.md",
  "title": "Example Article",
  "domain": "example.com",
  "hub": "brain",
  "skill_candidates": ["knowledge", "ingest"],
  "intent": ["read-later", "implementation-reference"],
  "wiki_compile": "queued"
}
```

### Slash Command

Add `skills/ingest/commands/ingest-url.md` and export it through normal skill
sync. The command should:

1. Parse URL and optional flags.
2. Call `ingest-url`.
3. Show saved path, routing, and actions.
4. If compile is requested, call `wiki-update`, process the returned batch as
   an agent, call `wiki-apply-concept-batch`, then verify.

### Dashboard UI

Add an Ingest URL control to the Brain knowledge/ingest surface. Prefer a small
custom component over a YAML-only page if the flow needs mutation state,
toasts, queued compile actions, or field validation.

The dashboard must call MCP through `mcpCall` or `useMcpMutation`. It must not
call Python scripts directly and must not call LLM APIs.

### Agent Instructions

Update `docs/agent-topics/agent-rules.md` and generated agent surfaces so agents
treat the LLM wiki as an execution surface:

- Use `/ingest-url` for URL capture instead of ad hoc notes.
- After URL ingest, preserve source card metadata and queue wiki compilation
  when the source has durable value.
- Use current hubs and skill metadata for deterministic routing.
- Do not hand-write compiled wiki concept pages.
- Use Obsidian-native markdown conventions for user-facing vault/wiki files.

## Data Flow

```text
URL
  -> dashboard or /ingest-url command
  -> ingest-url MCP tool
  -> extraction and source-card write under Au-vault/sources/web/
  -> RAG/source reindex
  -> optional wiki-update batch
  -> IDE/CLI agent concept extraction
  -> wiki-apply-concept-batch
  -> compiled wiki pages
  -> Obsidian/dashboard browse
```

## Error Handling

- Invalid URL: return `success=false` with validation detail.
- Extraction failure: save a minimal source card with failure status only if
  useful for retry; otherwise return error without writing.
- Duplicate capture: detect same canonical URL and offer update, duplicate, or
  skip behavior.
- Weak classification: write `hub: brain`, `skill_candidates: []`, and
  `action_status: triage`.
- Wiki batch unavailable: URL capture still succeeds; report `wiki_compile:
  none` or `queued_failed`.

## Tests and Verification

- Unit tests for deterministic URL classification against synthetic skill
  frontmatter.
- Unit tests for source-card frontmatter/body generation.
- MCP registration test for `ingest-url`.
- Command contract test for `/ingest-url`.
- Existing Obsidian staged tests after promotion.
- `sync_agents check` after command and instruction changes.
- Browser verification for the dashboard Ingest URL control on the correct
  running checkout.
- D4 wiki scan after compiling a representative captured URL.

## Open Decisions

- Whether source cards live under `sources/web/` or `inbox/urls/` by default.
  Recommendation: `sources/web/` for durable captures, with `inbox/urls/` only
  for incomplete or failed triage.
- Whether duplicate URL captures update the existing source card by default.
  Recommendation: skip by default and allow explicit `--refresh`.
- Whether Canvas generation belongs in MVP. Recommendation: defer until source
  cards and Obsidian wiki page conventions are stable.
